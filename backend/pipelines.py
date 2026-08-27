"""Heavy media pipelines: Video Dub, Render Studio, B\u0103m Studio."""
import logging
import math
import uuid
from pathlib import Path

import srt as srt_lib

from ai_engine import translate_texts, DEFAULT_TEXT_MODEL
from media_store import (MEDIA_DIR, get_duration, has_video_stream, media_url,
                         new_media_path, run_ffmpeg)
from stt_engine import extract_audio_for_stt, segments_to_srt, transcribe
from tts_engine import edge_generate

logger = logging.getLogger(__name__)

MAX_DUB_SEGMENTS = 300
MIX_BATCH = 20


async def _fit_segment_audio(seg_path: Path, slot_seconds: float) -> Path:
    """Speed up TTS audio if longer than its subtitle slot (max 2x)."""
    try:
        dur = await get_duration(seg_path)
    except Exception:  # noqa: BLE001
        return seg_path
    if dur <= 0 or slot_seconds <= 0.2 or dur <= slot_seconds * 1.05:
        return seg_path
    ratio = min(dur / slot_seconds, 2.0)
    out = seg_path.with_name(seg_path.stem + "_fit.mp3")
    await run_ffmpeg(["-i", str(seg_path), "-filter:a", f"atempo={ratio:.3f}", str(out)])
    return out


async def _mix_timeline(segment_files, total_duration: float, out_path: Path):
    """Mix (path, start_seconds) tuples into a single audio track."""
    work_dir = out_path.parent
    intermediates = []
    for b in range(0, len(segment_files), MIX_BATCH):
        batch = segment_files[b:b + MIX_BATCH]
        args = []
        filters = []
        for i, (p, start) in enumerate(batch):
            args += ["-i", str(p)]
            delay_ms = max(0, int(start * 1000))
            filters.append(f"[{i}:a]adelay={delay_ms}|{delay_ms}[a{i}]")
        joined = "".join(f"[a{i}]" for i in range(len(batch)))
        filters.append(f"{joined}amix=inputs={len(batch)}:duration=longest:normalize=0[out]")
        inter = work_dir / f"mix_{uuid.uuid4().hex[:8]}.wav"
        await run_ffmpeg(args + ["-filter_complex", ";".join(filters),
                                 "-map", "[out]", str(inter)])
        intermediates.append(inter)

    args = ["-f", "lavfi", "-t", f"{max(total_duration, 0.5):.2f}",
            "-i", "anullsrc=r=44100:cl=stereo"]
    filters = []
    for i, p in enumerate(intermediates):
        args += ["-i", str(p)]
    n = len(intermediates) + 1
    joined = "".join(f"[{i}:a]" for i in range(n))
    filters.append(f"{joined}amix=inputs={n}:duration=first:normalize=0[out]")
    await run_ffmpeg(args + ["-filter_complex", ";".join(filters), "-map", "[out]",
                             "-b:a", "192k", str(out_path)])
    for p in intermediates:
        p.unlink(missing_ok=True)
    return out_path


async def video_dub_worker(progress_cb, input_path: Path, target_lang: str, voice: str,
                           stt_mode: str = "cloud", whisper_model: str = "base",
                           source_lang: str = None, model_key: str = DEFAULT_TEXT_MODEL):
    await progress_cb(5, "\u0110ang t\u00e1ch audio t\u1eeb file...")
    audio_path = await extract_audio_for_stt(input_path)
    total_duration = await get_duration(audio_path)

    await progress_cb(12, f"\u0110ang nh\u1eadn di\u1ec7n gi\u1ecdng n\u00f3i (Whisper {stt_mode})...")
    segments = await transcribe(audio_path, mode=stt_mode, model_size=whisper_model,
                                language=source_lang or None)
    if len(segments) > MAX_DUB_SEGMENTS:
        raise RuntimeError(f"Video qu\u00e1 d\u00e0i ({len(segments)} c\u00e2u) \u2014 gi\u1edbi h\u1ea1n {MAX_DUB_SEGMENTS} c\u00e2u")
    srt_original = segments_to_srt(segments)

    await progress_cb(35, "\u0110ang d\u1ecbch ph\u1ee5 \u0111\u1ec1...")
    texts = [s["text"] for s in segments]
    translated = await translate_texts(texts, target_lang, model_key,
                                       progress_cb=progress_cb, base_progress=35, span=20)
    for s, t in zip(segments, translated):
        s["text_translated"] = t
    srt_translated = segments_to_srt([{"start": s["start"], "end": s["end"],
                                       "text": s["text_translated"]} for s in segments])

    await progress_cb(58, "\u0110ang t\u1ea1o gi\u1ecdng thuy\u1ebft minh (Edge TTS)...")
    work_dir = MEDIA_DIR / "dub" / uuid.uuid4().hex[:10]
    work_dir.mkdir(parents=True, exist_ok=True)
    seg_files = []
    for i, s in enumerate(segments):
        text = (s.get("text_translated") or "").strip()
        if not text:
            continue
        seg_path = work_dir / f"seg_{i:04d}.mp3"
        try:
            await edge_generate(text, voice, out_path=seg_path)
        except Exception as e:  # noqa: BLE001
            logger.warning("TTS segment %s failed: %s", i, e)
            continue
        slot = float(s["end"]) - float(s["start"])
        fitted = await _fit_segment_audio(seg_path, slot)
        seg_files.append((fitted, float(s["start"])))
        if i % 10 == 0:
            pct = 58 + int(22 * (i + 1) / len(segments))
            await progress_cb(pct, f"\u0110ang t\u1ea1o gi\u1ecdng... ({i + 1}/{len(segments)} c\u00e2u)")
    if not seg_files:
        raise RuntimeError("Kh\u00f4ng t\u1ea1o \u0111\u01b0\u1ee3c \u0111o\u1ea1n TTS n\u00e0o")

    await progress_cb(82, "\u0110ang gh\u00e9p audio thuy\u1ebft minh...")
    dubbed_audio = new_media_path("dub", "mp3", "dubbed_")
    await _mix_timeline(seg_files, total_duration, dubbed_audio)

    result = {
        "audio_url": media_url(dubbed_audio),
        "srt_original": srt_original,
        "srt_translated": srt_translated,
        "segment_count": len(segments),
    }

    if await has_video_stream(input_path):
        await progress_cb(92, "\u0110ang gh\u00e9p audio v\u00e0o video...")
        out_video = new_media_path("dub", "mp4", "dubbed_")
        await run_ffmpeg(["-i", str(input_path), "-i", str(dubbed_audio),
                          "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
                          "-c:a", "aac", "-shortest", str(out_video)])
        result["video_url"] = media_url(out_video)

    return result


async def render_worker(progress_cb, audio_path: Path = None, image_path: Path = None,
                        video_path: Path = None, srt_content: str = None,
                        resolution: str = "1280x720"):
    """Render Studio: (audio+image -> mp4) or (video + optional srt burn)."""
    srt_file = None
    if srt_content and srt_content.strip():
        try:
            list(srt_lib.parse(srt_content))
        except Exception:  # noqa: BLE001
            raise RuntimeError("File SRT kh\u00f4ng h\u1ee3p l\u1ec7 \u2014 ki\u1ec3m tra \u0111\u1ecbnh d\u1ea1ng/UTF-8")
        srt_file = new_media_path("renders", "srt", "burn_")
        srt_file.write_text(srt_content, encoding="utf-8")

    w, h = (resolution.split("x") + ["720"])[:2]
    out = new_media_path("renders", "mp4", "render_")

    if video_path is not None:
        await progress_cb(30, "\u0110ang render video...")
        vf = f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2"
        if srt_file:
            vf += f",subtitles={srt_file}"
        args = ["-i", str(video_path)]
        if audio_path is not None:
            args += ["-i", str(audio_path), "-map", "0:v:0", "-map", "1:a:0"]
        args += ["-vf", vf, "-c:v", "libx264", "-preset", "veryfast",
                 "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(out)]
        await run_ffmpeg(args, timeout=1800)
    else:
        if audio_path is None or image_path is None:
            raise RuntimeError("C\u1ea7n audio + \u1ea3nh n\u1ec1n (ho\u1eb7c video) \u0111\u1ec3 render")
        await progress_cb(30, "\u0110ang render video t\u1eeb \u1ea3nh + audio...")
        vf = f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2"
        if srt_file:
            vf += f",subtitles={srt_file}"
        await run_ffmpeg(["-loop", "1", "-i", str(image_path), "-i", str(audio_path),
                          "-vf", vf, "-c:v", "libx264", "-preset", "veryfast",
                          "-tune", "stillimage", "-pix_fmt", "yuv420p",
                          "-c:a", "aac", "-b:a", "192k", "-shortest", str(out)],
                         timeout=1800)

    await progress_cb(95, "\u0110ang ho\u00e0n t\u1ea5t file...")
    dur = await get_duration(out)
    return {"video_url": media_url(out), "duration": round(dur, 2)}


async def bam_worker(progress_cb, input_path: Path, mode: str = "duration",
                     value: float = 60):
    """Split media into segments by duration (seconds) or by count."""
    total = await get_duration(input_path)
    if total <= 0:
        raise RuntimeError("Kh\u00f4ng \u0111\u1ecdc \u0111\u01b0\u1ee3c th\u1eddi l\u01b0\u1ee3ng file")
    if mode == "count":
        count = max(1, int(value))
        seg_time = math.ceil(total / count * 100) / 100
    else:
        seg_time = max(1.0, float(value))

    is_video = await has_video_stream(input_path)
    ext = "mp4" if is_video else "mp3"
    out_dir = MEDIA_DIR / "segments" / uuid.uuid4().hex[:10]
    out_dir.mkdir(parents=True, exist_ok=True)
    pattern = out_dir / f"part_%03d.{ext}"

    await progress_cb(30, "\u0110ang c\u1eaft file...")
    await run_ffmpeg(["-i", str(input_path), "-f", "segment",
                      "-segment_time", f"{seg_time:.2f}", "-reset_timestamps", "1",
                      "-c", "copy", str(pattern)], timeout=1800)

    files = sorted(out_dir.glob(f"part_*.{ext}"))
    if not files:
        raise RuntimeError("Kh\u00f4ng t\u1ea1o \u0111\u01b0\u1ee3c \u0111o\u1ea1n n\u00e0o")
    await progress_cb(90, "\u0110ang l\u1eadp danh s\u00e1ch k\u1ebft qu\u1ea3...")
    items = []
    for f in files:
        try:
            d = await get_duration(f)
        except Exception:  # noqa: BLE001
            d = 0
        items.append({"filename": f.name, "url": media_url(f), "duration": round(d, 2),
                      "size": f.stat().st_size})
    return {"segments": items, "total_duration": round(total, 2), "segment_time": seg_time}
