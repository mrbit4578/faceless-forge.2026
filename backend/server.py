"""SUPER AUDIO TOOLS (VIP) - FastAPI backend."""
from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import shutil
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid
from datetime import datetime, timezone

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI(title="SUPER AUDIO TOOLS (VIP)")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

import ai_engine
import jobs as jobs_mod
import pipelines
import rag_engine
import stt_engine
import tts_engine
from media_store import (CATEGORIES, MEDIA_DIR, media_url, new_media_path,
                         safe_filename)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------- Models ----------------------------

class TTSRequest(BaseModel):
    text: str
    engine: str = "edge"  # edge | gtts
    voice: str = "vi-VN-HoaiMyNeural"
    rate: int = 0
    pitch: int = 0
    volume: int = 0


class TranslateSRTRequest(BaseModel):
    srt_content: str
    target_lang: str = "Vietnamese"
    model: str = ai_engine.DEFAULT_TEXT_MODEL


class EnhancePromptRequest(BaseModel):
    prompt: str
    model: str = ai_engine.DEFAULT_TEXT_MODEL


class ImageGenRequest(BaseModel):
    prompt: str
    model: str = "gpt-image-1"  # gpt-image-1 | nano-banana
    n: int = 1


class STTRequest(BaseModel):
    file_id: str
    mode: str = "cloud"  # cloud | local
    model_size: str = "base"  # tiny | base | small
    language: Optional[str] = None


class VideoDubRequest(BaseModel):
    file_id: str
    target_lang: str = "Vietnamese"
    voice: str = "vi-VN-HoaiMyNeural"
    stt_mode: str = "cloud"
    whisper_model: str = "base"
    source_lang: Optional[str] = None
    model: str = ai_engine.DEFAULT_TEXT_MODEL


class RenderRequest(BaseModel):
    audio_file_id: Optional[str] = None
    image_file_id: Optional[str] = None
    video_file_id: Optional[str] = None
    srt_content: Optional[str] = None
    resolution: str = "1280x720"


class BamRequest(BaseModel):
    file_id: str
    mode: str = "duration"  # duration | count
    value: float = 60


class RagAskRequest(BaseModel):
    question: str
    doc_ids: Optional[List[str]] = None
    top_k: int = 5
    model: str = ai_engine.DEFAULT_TEXT_MODEL


class RagScriptRequest(BaseModel):
    doc_ids: Optional[List[str]] = None
    topic: str = ""
    style: str = "storytelling"
    duration_sec: int = 60
    model: str = ai_engine.DEFAULT_TEXT_MODEL


class ScriptToTTSRequest(BaseModel):
    script: str
    voice: str = "vi-VN-HoaiMyNeural"
    rate: int = 0
    pitch: int = 0
    volume: int = 0


# ---------------------------- Core / Health ----------------------------

@api_router.get("/")
async def root():
    return {"message": "SUPER AUDIO TOOLS (VIP) API"}


@api_router.get("/health")
async def health():
    ffmpeg_ok = shutil.which("ffmpeg") is not None
    mongo_ok = True
    try:
        await db.command("ping")
    except Exception:  # noqa: BLE001
        mongo_ok = False
    return {
        "status": "ok",
        "ffmpeg": ffmpeg_ok,
        "mongo": mongo_ok,
        "emergent_key": bool(os.environ.get("EMERGENT_LLM_KEY")),
        "engines": {"edge_tts": True, "gtts": True, "whisper_cloud": True,
                    "whisper_local": True},
    }


# ---------------------------- Media serve / upload ----------------------------

@api_router.get("/media/{category}/{filename:path}")
async def serve_media(category: str, filename: str):
    if category not in CATEGORIES:
        raise HTTPException(404, "Danh mục không tồn tại")
    path = (MEDIA_DIR / category / filename).resolve()
    if not str(path).startswith(str((MEDIA_DIR / category).resolve())) or not path.is_file():
        raise HTTPException(404, "File không tồn tại")
    return FileResponse(path, filename=path.name)


@api_router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    orig = safe_filename(file.filename or "file")
    ext = orig.rsplit(".", 1)[-1] if "." in orig else "bin"
    dest = new_media_path("uploads", ext, "up_")
    size = 0
    with open(dest, "wb") as f:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            f.write(chunk)
    rec = {
        "id": str(uuid.uuid4()),
        "filename": dest.name,
        "original_name": orig,
        "size": size,
        "content_type": file.content_type,
        "url": media_url(dest),
        "created_at": _now(),
    }
    await db.uploads.insert_one({**rec})
    return rec


async def _get_upload_path(file_id: str) -> Path:
    rec = await db.uploads.find_one({"id": file_id}, {"_id": 0})
    if not rec:
        raise HTTPException(404, "Không tìm thấy file đã upload")
    path = MEDIA_DIR / "uploads" / rec["filename"]
    if not path.is_file():
        raise HTTPException(404, "File đã bị xoá khỏi ổ đĩa")
    return path


# ---------------------------- TTS ----------------------------

@api_router.get("/tts/voices")
async def tts_voices():
    edge_voices = await tts_engine.get_edge_voices()
    gtts_langs = tts_engine.get_gtts_langs()
    return {"edge": edge_voices, "gtts": gtts_langs}


@api_router.post("/tts/generate")
async def tts_generate(req: TTSRequest):
    if not req.text.strip():
        raise HTTPException(400, "Nội dung văn bản trống")
    if len(req.text) > 20000:
        raise HTTPException(400, "Văn bản quá dài (tối đa 20.000 ký tự)")
    try:
        path, url = await tts_engine.generate_tts(
            req.engine, req.text, req.voice, req.rate, req.pitch, req.volume)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:  # noqa: BLE001
        logger.exception("TTS failed")
        raise HTTPException(500, f"Tạo giọng thất bại: {str(e)[:300]}")
    rec = {
        "id": str(uuid.uuid4()),
        "engine": req.engine,
        "voice": req.voice,
        "text": req.text[:300],
        "filename": path.name,
        "url": url,
        "created_at": _now(),
    }
    await db.tts_history.insert_one({**rec})
    return rec


@api_router.get("/tts/history")
async def tts_history():
    return await db.tts_history.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)


@api_router.delete("/tts/history/{item_id}")
async def tts_history_delete(item_id: str):
    rec = await db.tts_history.find_one({"id": item_id}, {"_id": 0})
    if rec:
        (MEDIA_DIR / "tts" / rec["filename"]).unlink(missing_ok=True)
        await db.tts_history.delete_one({"id": item_id})
    return {"deleted": bool(rec)}


# ---------------------------- STT ----------------------------

@api_router.post("/stt/transcribe")
async def stt_transcribe(req: STTRequest):
    input_path = await _get_upload_path(req.file_id)
    job = await jobs_mod.create_job(db, "stt", req.model_dump())

    async def worker(progress_cb):
        await progress_cb(10, "Đang tách audio...")
        audio = await stt_engine.extract_audio_for_stt(input_path)
        await progress_cb(30, f"Đang nhận diện (Whisper {req.mode})...")
        segments = await stt_engine.transcribe(
            audio, mode=req.mode, model_size=req.model_size, language=req.language)
        await progress_cb(90, "Đang tạo file SRT...")
        srt_text = stt_engine.segments_to_srt(segments)
        srt_path = new_media_path("uploads", "srt", "stt_")
        srt_path.write_text(srt_text, encoding="utf-8")
        return {"srt": srt_text, "srt_url": media_url(srt_path),
                "segment_count": len(segments)}

    jobs_mod.launch_job(db, job, worker)
    return job


# ---------------------------- AI: translate / prompt / image ----------------------------

@api_router.get("/ai/models")
async def ai_models():
    return {
        "text_models": [{"key": k, "provider": v[0], "model": v[1]}
                        for k, v in ai_engine.TEXT_MODELS.items()],
        "image_models": ai_engine.IMAGE_MODELS,
        "default_text_model": ai_engine.DEFAULT_TEXT_MODEL,
    }


@api_router.post("/ai/translate-srt")
async def translate_srt(req: TranslateSRTRequest):
    try:
        cues = stt_engine.parse_srt(req.srt_content)
    except Exception:  # noqa: BLE001
        raise HTTPException(400, "File SRT không hợp lệ — kiểm tra định dạng/UTF-8")
    if not cues:
        raise HTTPException(400, "File SRT không có nội dung")
    if len(cues) > 1500:
        raise HTTPException(400, "SRT quá dài (tối đa 1500 câu)")
    job = await jobs_mod.create_job(db, "translate_srt", {
        "target_lang": req.target_lang, "model": req.model, "cues": len(cues)})

    async def worker(progress_cb):
        texts = [c["text"] for c in cues]
        translated = await ai_engine.translate_texts(
            texts, req.target_lang, req.model,
            progress_cb=progress_cb, base_progress=5, span=85)
        srt_out = stt_engine.segments_to_srt([
            {"start": c["start"], "end": c["end"], "text": t}
            for c, t in zip(cues, translated)])
        srt_path = new_media_path("uploads", "srt", "translated_")
        srt_path.write_text(srt_out, encoding="utf-8")
        return {"srt": srt_out, "srt_url": media_url(srt_path), "cues": len(cues)}

    jobs_mod.launch_job(db, job, worker)
    return job


@api_router.post("/ai/enhance-prompt")
async def enhance_prompt(req: EnhancePromptRequest):
    if not req.prompt.strip():
        raise HTTPException(400, "Prompt trống")
    try:
        result = await ai_engine.enhance_prompt(req.prompt, req.model)
    except Exception as e:  # noqa: BLE001
        logger.exception("enhance prompt failed")
        raise HTTPException(500, f"Lỗi AI: {str(e)[:300]}")
    return {"prompt": result}


@api_router.post("/ai/generate-image")
async def generate_image(req: ImageGenRequest):
    if not req.prompt.strip():
        raise HTTPException(400, "Prompt trống")
    if req.model not in ai_engine.IMAGE_MODELS:
        raise HTTPException(400, "Model ảnh không hợp lệ")
    job = await jobs_mod.create_job(db, "image_gen", req.model_dump())

    async def worker(progress_cb):
        await progress_cb(20, f"Đang tạo ảnh với {req.model}...")
        images = await ai_engine.generate_images(req.prompt, req.model, req.n)
        for img in images:
            await db.image_history.insert_one({
                "id": str(uuid.uuid4()), "prompt": req.prompt[:300],
                "model": req.model, "url": img["url"],
                "filename": img["filename"], "created_at": _now()})
        return {"images": images}

    jobs_mod.launch_job(db, job, worker)
    return job


@api_router.get("/images/history")
async def images_history():
    return await db.image_history.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)


@api_router.delete("/images/history/{item_id}")
async def images_history_delete(item_id: str):
    rec = await db.image_history.find_one({"id": item_id}, {"_id": 0})
    if rec:
        (MEDIA_DIR / "images" / rec["filename"]).unlink(missing_ok=True)
        await db.image_history.delete_one({"id": item_id})
    return {"deleted": bool(rec)}


# ---------------------------- Pipelines ----------------------------

@api_router.post("/videodub/start")
async def videodub_start(req: VideoDubRequest):
    input_path = await _get_upload_path(req.file_id)
    job = await jobs_mod.create_job(db, "videodub", req.model_dump())

    async def worker(progress_cb):
        return await pipelines.video_dub_worker(
            progress_cb, input_path, req.target_lang, req.voice,
            stt_mode=req.stt_mode, whisper_model=req.whisper_model,
            source_lang=req.source_lang, model_key=req.model)

    jobs_mod.launch_job(db, job, worker)
    return job


@api_router.post("/render/start")
async def render_start(req: RenderRequest):
    audio_path = await _get_upload_path(req.audio_file_id) if req.audio_file_id else None
    image_path = await _get_upload_path(req.image_file_id) if req.image_file_id else None
    video_path = await _get_upload_path(req.video_file_id) if req.video_file_id else None
    if video_path is None and (audio_path is None or image_path is None):
        raise HTTPException(400, "Cần (audio + ảnh nền) hoặc video đầu vào")
    job = await jobs_mod.create_job(db, "render", req.model_dump())

    async def worker(progress_cb):
        return await pipelines.render_worker(
            progress_cb, audio_path=audio_path, image_path=image_path,
            video_path=video_path, srt_content=req.srt_content,
            resolution=req.resolution)

    jobs_mod.launch_job(db, job, worker)
    return job


@api_router.post("/bam/start")
async def bam_start(req: BamRequest):
    input_path = await _get_upload_path(req.file_id)
    if req.mode not in ("duration", "count"):
        raise HTTPException(400, "Chế độ cắt không hợp lệ")
    if req.value <= 0:
        raise HTTPException(400, "Giá trị cắt phải lớn hơn 0")
    job = await jobs_mod.create_job(db, "bam", req.model_dump())

    async def worker(progress_cb):
        return await pipelines.bam_worker(progress_cb, input_path, req.mode, req.value)

    jobs_mod.launch_job(db, job, worker)
    return job


# ---------------------------- Jobs ----------------------------

@api_router.get("/jobs")
async def jobs_list(type: Optional[str] = None, limit: int = 50):
    return await jobs_mod.list_jobs(db, type, min(limit, 200))


@api_router.get("/jobs/{job_id}")
async def jobs_get(job_id: str):
    job = await jobs_mod.get_job(db, job_id)
    if not job:
        raise HTTPException(404, "Job không tồn tại")
    return job


@api_router.delete("/jobs/{job_id}")
async def jobs_delete(job_id: str):
    await jobs_mod.delete_job(db, job_id)
    return {"deleted": True}


# ---------------------------- RAG ----------------------------

@api_router.post("/rag/docs/upload")
async def rag_upload(file: UploadFile = File(...)):
    orig = safe_filename(file.filename or "document.txt")
    ext = orig.rsplit(".", 1)[-1].lower() if "." in orig else "txt"
    if ext not in ("txt", "md", "markdown", "pdf", "docx", "srt", "csv", "json"):
        raise HTTPException(400, f"Định dạng .{ext} chưa hỗ trợ (txt/md/pdf/docx)")
    dest = new_media_path("uploads", ext, "rag_")
    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(400, "Tài liệu quá 20MB")
    dest.write_bytes(content)
    try:
        doc = await rag_engine.ingest_document(db, dest, orig)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:  # noqa: BLE001
        logger.exception("RAG ingest failed")
        raise HTTPException(500, f"Lỗi xử lý tài liệu: {str(e)[:300]}")
    return doc


@api_router.get("/rag/docs")
async def rag_docs():
    return await rag_engine.list_documents(db)


@api_router.delete("/rag/docs/{doc_id}")
async def rag_doc_delete(doc_id: str):
    await rag_engine.delete_document(db, doc_id)
    return {"deleted": True}


@api_router.post("/rag/ask")
async def rag_ask(req: RagAskRequest):
    if not req.question.strip():
        raise HTTPException(400, "Câu hỏi trống")
    try:
        result = await rag_engine.ask(db, req.question, req.doc_ids,
                                      min(max(req.top_k, 1), 10), req.model)
    except Exception as e:  # noqa: BLE001
        logger.exception("RAG ask failed")
        raise HTTPException(500, f"Lỗi AI: {str(e)[:300]}")
    rec = {"id": str(uuid.uuid4()), "question": req.question[:300],
           "answer": result["answer"][:2000], "created_at": _now()}
    await db.rag_history.insert_one({**rec})
    return result


@api_router.get("/rag/history")
async def rag_history():
    return await db.rag_history.find({}, {"_id": 0}).sort("created_at", -1).to_list(50)


@api_router.post("/rag/video-script")
async def rag_video_script(req: RagScriptRequest):
    try:
        result = await rag_engine.generate_video_script(
            db, req.doc_ids, req.topic, req.style,
            min(max(req.duration_sec, 15), 600), req.model)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:  # noqa: BLE001
        logger.exception("RAG script failed")
        raise HTTPException(500, f"Lỗi AI: {str(e)[:300]}")
    return result


@api_router.post("/rag/script-to-tts")
async def rag_script_to_tts(req: ScriptToTTSRequest):
    if not req.script.strip():
        raise HTTPException(400, "Kịch bản trống")
    try:
        path, url = await tts_engine.generate_tts(
            "edge", req.script, req.voice, req.rate, req.pitch, req.volume)
    except Exception as e:  # noqa: BLE001
        logger.exception("script-to-tts failed")
        raise HTTPException(500, f"Tạo giọng thất bại: {str(e)[:300]}")
    rec = {
        "id": str(uuid.uuid4()), "engine": "edge", "voice": req.voice,
        "text": req.script[:300], "filename": path.name, "url": url,
        "created_at": _now(),
    }
    await db.tts_history.insert_one({**rec})
    return rec


# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
