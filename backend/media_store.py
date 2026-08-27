"""File storage + ffmpeg helpers for SUPER AUDIO TOOLS."""
import asyncio
import json
import logging
import os
import re
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).parent
MEDIA_DIR = ROOT_DIR / "media"
CATEGORIES = ["uploads", "tts", "images", "dub", "renders", "segments"]

for cat in CATEGORIES:
    (MEDIA_DIR / cat).mkdir(parents=True, exist_ok=True)

SAFE_NAME_RE = re.compile(r"[^a-zA-Z0-9._-]+")


def safe_filename(name: str) -> str:
    name = os.path.basename(name or "file")
    return SAFE_NAME_RE.sub("_", name)[:120]


def new_media_path(category: str, ext: str, prefix: str = "") -> Path:
    fname = f"{prefix}{uuid.uuid4().hex[:12]}.{ext.lstrip('.')}"
    return MEDIA_DIR / category / fname


def media_url(path: Path) -> str:
    """Return relative API url for a media file."""
    rel = path.relative_to(MEDIA_DIR)
    return f"/api/media/{rel.as_posix()}"


async def run_cmd(args, timeout: int = 600) -> str:
    """Run a subprocess command, raise on failure, return stderr text."""
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        raise RuntimeError(f"Lenh {args[0]} qua thoi gian cho ({timeout}s)")
    if proc.returncode != 0:
        tail = (err or out or b"").decode(errors="ignore")[-800:]
        raise RuntimeError(f"{args[0]} loi: {tail}")
    return (err or b"").decode(errors="ignore")


async def run_ffmpeg(args, timeout: int = 600) -> str:
    return await run_cmd(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"] + list(args), timeout=timeout)


async def ffprobe_info(path) -> dict:
    proc = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", "-show_streams", str(path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, _ = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError("Khong doc duoc thong tin file media")
    return json.loads(out.decode(errors="ignore") or "{}")


async def get_duration(path) -> float:
    info = await ffprobe_info(path)
    dur = info.get("format", {}).get("duration")
    if dur is None:
        for s in info.get("streams", []):
            if s.get("duration"):
                dur = s["duration"]
                break
    return float(dur or 0)


async def has_video_stream(path) -> bool:
    info = await ffprobe_info(path)
    return any(s.get("codec_type") == "video" for s in info.get("streams", []))
