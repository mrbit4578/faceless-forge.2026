"""Faceless Forge entry point.

Run with ``uvicorn forge_app:app --host 0.0.0.0 --port 8001`` from backend/.
It keeps the existing media workstation API and adds the unified Faceless Forge
workflow plus its zero-build web interface.
"""
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import ai_engine
import forge_engine
import jobs as jobs_mod
import pipelines
import server as legacy
import stt_engine
import tts_engine

app = legacy.app


class ForgeBlueprintRequest(BaseModel):
    topic: str = Field(min_length=3, max_length=300)
    niche: str = Field(default="Giáo dục / kiến thức", max_length=100)
    audience: str = Field(default="18–34 tuổi", max_length=120)
    platform: str = Field(default="TikTok & YouTube Shorts", max_length=100)
    duration_sec: int = Field(default=45, ge=15, le=180)
    tone: str = Field(default="Kể chuyện giàu nhịp", max_length=100)
    language: str = Field(default="Tiếng Việt", max_length=60)
    monetization_goal: str = Field(default="Tăng khán giả cho kênh", max_length=180)
    model: str = ai_engine.DEFAULT_TEXT_MODEL


class ForgeProductionRequest(BaseModel):
    blueprint: dict[str, Any]
    voice: str = "vi-VN-HoaiMyNeural"
    image_model: str = "nano-banana"
    resolution: str = "1080x1920"


def _shots_to_srt(shots: list[dict[str, Any]]) -> str:
    segments = []
    for index, shot in enumerate(shots):
        try:
            start = max(0.0, float(shot.get("start_sec", index * 6)))
            end = max(start + 0.5, float(shot.get("end_sec", start + 6)))
        except (TypeError, ValueError):
            start, end = index * 6.0, (index + 1) * 6.0
        text = str(shot.get("narration") or shot.get("on_screen_text") or "").strip()
        if text:
            segments.append({"start": start, "end": end, "text": text})
    return stt_engine.segments_to_srt(segments) if segments else ""


@app.post("/api/forge/blueprint")
async def forge_blueprint(req: ForgeBlueprintRequest):
    """Turn a short creative brief into a publishing-ready video blueprint."""
    result = await forge_engine.generate_viral_blueprint(req.model_dump())
    return result


@app.post("/api/forge/produce")
async def forge_produce(req: ForgeProductionRequest):
    """Generate a key visual, a voice-over and a vertical MP4 as one background job."""
    blueprint = req.blueprint or {}
    script = str(blueprint.get("script") or "").strip()
    shots = blueprint.get("shots") if isinstance(blueprint.get("shots"), list) else []
    first_shot = shots[0] if shots and isinstance(shots[0], dict) else {}
    image_prompt = str(first_shot.get("image_prompt") or "").strip()
    if not script:
        raise HTTPException(400, "Blueprint chưa có lời bình để tạo video")
    if not image_prompt:
        raise HTTPException(400, "Blueprint chưa có visual prompt để tạo video")
    if req.image_model not in ai_engine.IMAGE_MODELS:
        raise HTTPException(400, "Model ảnh không hợp lệ")

    job = await jobs_mod.create_job(legacy.db, "faceless_forge", {
        "voice": req.voice, "image_model": req.image_model, "resolution": req.resolution,
        "topic": str(blueprint.get("concept") or "")[:200],
    })

    async def worker(progress_cb):
        await progress_cb(8, "Đang tạo visual chủ đạo cho video...")
        images = await ai_engine.generate_images(image_prompt, req.image_model, 1)
        image = images[0]
        image_path = legacy.MEDIA_DIR / "images" / image["filename"]
        await progress_cb(38, "Đang tạo voice-over bằng Edge TTS...")
        audio_path, audio_url = await tts_engine.generate_tts("edge", script, req.voice)
        await progress_cb(62, "Đang dựng video dọc và gắn phụ đề...")
        srt_content = _shots_to_srt(shots)
        result = await pipelines.render_worker(
            progress_cb, audio_path=audio_path, image_path=image_path,
            srt_content=srt_content or None, resolution=req.resolution,
        )
        return {
            "video_url": result["video_url"],
            "duration": result["duration"],
            "image_url": image["url"],
            "audio_url": audio_url,
            "srt": srt_content,
        }

    jobs_mod.launch_job(legacy.db, job, worker)
    return job


WEB_DIR = Path(__file__).resolve().parent.parent / "faceless_web"
if WEB_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="faceless-web")
