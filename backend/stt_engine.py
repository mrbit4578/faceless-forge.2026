"""Speech-to-text: Whisper Cloud (whisper-1 via Emergent key) + Whisper Local (faster-whisper)."""
import asyncio
import inspect
import logging
import os
from datetime import timedelta
from pathlib import Path

import srt as srt_lib

from media_store import new_media_path, run_ffmpeg

logger = logging.getLogger(__name__)

_local_models = {}
CLOUD_MAX_BYTES = 24 * 1024 * 1024


async def extract_audio_for_stt(input_path: Path) -> Path:
    """Convert any media to 16k mono mp3 (small, whisper-friendly)."""
    out = new_media_path("uploads", "mp3", "stt_audio_")
    await run_ffmpeg(["-i", str(input_path), "-vn", "-ac", "1", "-ar", "16000",
                      "-b:a", "48k", str(out)])
    return out


def segments_to_srt(segments) -> str:
    subs = []
    for i, seg in enumerate(segments, start=1):
        subs.append(srt_lib.Subtitle(
            index=i,
            start=timedelta(seconds=max(0.0, float(seg["start"]))),
            end=timedelta(seconds=max(0.0, float(seg["end"]))),
            content=(seg["text"] or "").strip(),
        ))
    return srt_lib.compose(subs)


def parse_srt(content: str):
    subs = list(srt_lib.parse(content))
    return [{"start": s.start.total_seconds(), "end": s.end.total_seconds(),
             "text": s.content.strip()} for s in subs]


async def transcribe_cloud(audio_path: Path, language: str = None):
    """Whisper-1 via Emergent key. Returns list of segments."""
    from emergentintegrations.llm.openai.speech_to_text import OpenAISpeechToText

    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        raise RuntimeError("Thi\u1ebfu EMERGENT_LLM_KEY")
    size = audio_path.stat().st_size
    if size > CLOUD_MAX_BYTES:
        raise RuntimeError("File qu\u00e1 25MB cho Whisper Cloud \u2014 h\u00e3y d\u00f9ng Whisper Local")

    stt = OpenAISpeechToText(api_key=api_key)
    kwargs = {"response_format": "verbose_json"}
    if language:
        kwargs["language"] = language

    res = None
    with open(audio_path, "rb") as audio_file:
        res = stt.transcribe(audio_file, **kwargs)
        if inspect.isawaitable(res):
            res = await res

    segments = None
    raw_segments = getattr(res, "segments", None)
    if raw_segments is None and isinstance(res, dict):
        raw_segments = res.get("segments")
    if raw_segments:
        segments = []
        for s in raw_segments:
            if isinstance(s, dict):
                segments.append({"start": s.get("start", 0), "end": s.get("end", 0),
                                 "text": s.get("text", "")})
            else:
                segments.append({"start": getattr(s, "start", 0), "end": getattr(s, "end", 0),
                                 "text": getattr(s, "text", "")})
    if not segments:
        text = getattr(res, "text", None) or (res.get("text") if isinstance(res, dict) else "") or ""
        if not text.strip():
            raise RuntimeError("Whisper Cloud kh\u00f4ng tr\u1ea3 v\u1ec1 k\u1ebft qu\u1ea3")
        segments = [{"start": 0.0, "end": 5.0, "text": text.strip()}]
    return segments


def _get_local_model(model_size: str):
    from faster_whisper import WhisperModel

    if model_size not in _local_models:
        _local_models[model_size] = WhisperModel(model_size, device="cpu", compute_type="int8")
    return _local_models[model_size]


async def transcribe_local(audio_path: Path, model_size: str = "base", language: str = None):
    """faster-whisper local CPU. Returns list of segments."""
    model_size = model_size if model_size in ("tiny", "base", "small") else "base"

    def _run():
        model = _get_local_model(model_size)
        kwargs = {"beam_size": 1, "vad_filter": True}
        if language:
            kwargs["language"] = language
        seg_iter, _info = model.transcribe(str(audio_path), **kwargs)
        return [{"start": s.start, "end": s.end, "text": s.text} for s in seg_iter]

    segments = await asyncio.to_thread(_run)
    if not segments:
        raise RuntimeError("Kh\u00f4ng nh\u1eadn di\u1ec7n \u0111\u01b0\u1ee3c gi\u1ecdng n\u00f3i trong file")
    return segments


async def transcribe(audio_path: Path, mode: str = "cloud", model_size: str = "base",
                     language: str = None):
    if mode == "local":
        return await transcribe_local(audio_path, model_size, language)
    return await transcribe_cloud(audio_path, language)
