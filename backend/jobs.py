"""Mongo-backed async job system."""
import asyncio
import logging
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

JOBS_COLLECTION = "jobs"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def create_job(db, job_type: str, params: dict) -> dict:
    job = {
        "id": str(uuid.uuid4()),
        "type": job_type,
        "status": "pending",
        "progress": 0,
        "message": "\u0110ang ch\u1edd x\u1eed l\u00fd...",
        "params": params,
        "result": None,
        "error": None,
        "created_at": _now(),
        "updated_at": _now(),
    }
    await db[JOBS_COLLECTION].insert_one({**job})
    return job


async def update_job(db, job_id: str, **fields):
    fields["updated_at"] = _now()
    await db[JOBS_COLLECTION].update_one({"id": job_id}, {"$set": fields})


async def get_job(db, job_id: str):
    return await db[JOBS_COLLECTION].find_one({"id": job_id}, {"_id": 0})


async def list_jobs(db, job_type: str = None, limit: int = 50):
    query = {"type": job_type} if job_type else {}
    cursor = db[JOBS_COLLECTION].find(query, {"_id": 0}).sort("created_at", -1).limit(limit)
    return await cursor.to_list(limit)


async def delete_job(db, job_id: str):
    await db[JOBS_COLLECTION].delete_one({"id": job_id})


def launch_job(db, job: dict, worker_coro_factory):
    """Run job worker in background task with status handling.

    worker_coro_factory: callable(progress_cb) -> coroutine returning result dict
    progress_cb: async fn(progress:int, message:str)
    """
    job_id = job["id"]

    async def progress_cb(progress: int, message: str):
        await update_job(db, job_id, progress=int(progress), message=message)

    async def runner():
        try:
            await update_job(db, job_id, status="running", message="\u0110ang x\u1eed l\u00fd...")
            result = await worker_coro_factory(progress_cb)
            await update_job(db, job_id, status="done", progress=100,
                             message="Ho\u00e0n t\u1ea5t", result=result)
        except Exception as e:  # noqa: BLE001
            logger.exception("Job %s (%s) failed", job_id, job.get("type"))
            await update_job(db, job_id, status="error", error=str(e)[:600],
                             message=f"L\u1ed7i: {str(e)[:300]}")

    asyncio.create_task(runner())
