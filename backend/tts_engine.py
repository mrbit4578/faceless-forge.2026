"""TTS engines: Edge TTS (Microsoft) + Google Translate TTS (gTTS)."""
import asyncio
import logging

import edge_tts
from gtts import gTTS
from gtts.lang import tts_langs

from media_store import new_media_path, media_url

logger = logging.getLogger(__name__)

_edge_voices_cache = None
_gtts_langs_cache = None


async def get_edge_voices():
    global _edge_voices_cache
    if _edge_voices_cache is None:
        raw = await edge_tts.list_voices()
        voices = []
        for v in raw:
            voices.append({
                "short_name": v.get("ShortName"),
                "locale": v.get("Locale"),
                "gender": v.get("Gender"),
                "friendly_name": v.get("FriendlyName") or v.get("ShortName"),
            })
        voices.sort(key=lambda x: (x["locale"] or "", x["short_name"] or ""))
        _edge_voices_cache = voices
    return _edge_voices_cache


def get_gtts_langs():
    global _gtts_langs_cache
    if _gtts_langs_cache is None:
        try:
            langs = tts_langs()
        except Exception:  # noqa: BLE001
            langs = {"vi": "Vietnamese", "en": "English", "ja": "Japanese",
                     "ko": "Korean", "zh-CN": "Chinese", "fr": "French",
                     "es": "Spanish", "de": "German", "th": "Thai", "id": "Indonesian"}
        _gtts_langs_cache = [{"code": k, "name": v} for k, v in sorted(langs.items(), key=lambda x: x[1])]
    return _gtts_langs_cache


def _pct(v: int) -> str:
    return f"{'+' if v >= 0 else ''}{int(v)}%"


def _hz(v: int) -> str:
    return f"{'+' if v >= 0 else ''}{int(v)}Hz"


async def edge_generate(text: str, voice: str, rate: int = 0, pitch: int = 0,
                        volume: int = 0, out_path=None):
    """Generate speech mp3 with Edge TTS. rate/volume in %, pitch in Hz."""
    if out_path is None:
        out_path = new_media_path("tts", "mp3", "edge_")
    communicate = edge_tts.Communicate(
        text, voice, rate=_pct(rate), volume=_pct(volume), pitch=_hz(pitch)
    )
    await communicate.save(str(out_path))
    return out_path


async def gtts_generate(text: str, lang: str = "vi", slow: bool = False, out_path=None):
    if out_path is None:
        out_path = new_media_path("tts", "mp3", "gtts_")

    def _gen():
        tts = gTTS(text=text, lang=lang, slow=slow)
        tts.save(str(out_path))

    await asyncio.to_thread(_gen)
    return out_path


async def generate_tts(engine: str, text: str, voice: str, rate: int = 0,
                       pitch: int = 0, volume: int = 0, out_path=None):
    """Unified TTS entry. Returns (path, url)."""
    text = (text or "").strip()
    if not text:
        raise ValueError("N\u1ed9i dung v\u0103n b\u1ea3n tr\u1ed1ng")
    if engine == "edge":
        path = await edge_generate(text, voice or "vi-VN-HoaiMyNeural", rate, pitch, volume, out_path)
    elif engine == "gtts":
        path = await gtts_generate(text, voice or "vi", slow=False, out_path=out_path)
    else:
        raise ValueError(f"Engine kh\u00f4ng h\u1ee3p l\u1ec7: {engine}")
    return path, media_url(path)
