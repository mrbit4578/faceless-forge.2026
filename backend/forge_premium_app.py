"""Production entry point for Faceless Forge's multi-scene video workflow.

This module keeps every existing workstation API from ``forge_app`` but places
the premium production route before its older single-image route.  Docker runs
this entry point; static deployments continue to serve the same UI safely.
"""
from fastapi import HTTPException
from fastapi.routing import APIRoute

import ai_engine
import jobs as jobs_mod
import premium_pipeline
import server as legacy
from forge_app import ForgeProductionRequest, app


async def forge_produce_multiscene(req: ForgeProductionRequest):
    """Queue a real per-shot visual + voice + subtitle render job."""
    blueprint = req.blueprint or {}
    shots = blueprint.get("shots") if isinstance(blueprint.get("shots"), list) else []
    if not shots:
        raise HTTPException(400, "Blueprint chưa có shot list để dựng video nhiều cảnh")
    if req.image_model not in ai_engine.IMAGE_MODELS:
        raise HTTPException(400, "Model ảnh không hợp lệ")

    try:
        planned_scenes = premium_pipeline.prepare_scenes(
            shots, str(blueprint.get("concept") or blueprint.get("topic") or "")
        )
        premium_pipeline._parse_resolution(req.resolution)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not planned_scenes:
        raise HTTPException(400, "Shot list chưa có lời bình hợp lệ để dựng video")

    job = await jobs_mod.create_job(legacy.db, "faceless_forge_multiscene", {
        "voice": req.voice,
        "image_model": req.image_model,
        "resolution": req.resolution,
        "topic": str(blueprint.get("concept") or blueprint.get("topic") or "")[:200],
        "scene_count": len(planned_scenes),
    })

    async def worker(progress_cb):
        return await premium_pipeline.render_multiscene_video(
            progress_cb,
            shots=shots,
            concept=str(blueprint.get("concept") or blueprint.get("topic") or ""),
            voice=req.voice,
            image_model=req.image_model,
            resolution=req.resolution,
        )

    jobs_mod.launch_job(legacy.db, job, worker)
    return job


def _install_premium_route() -> None:
    """Make the old browser button use the premium path without changing its API."""
    route = APIRoute(
        "/api/forge/produce", forge_produce_multiscene, methods=["POST"],
        name="forge_produce_multiscene",
    )
    for index, existing in enumerate(app.router.routes):
        if getattr(existing, "path", None) == "/api/forge/produce":
            app.router.routes.insert(index, route)
            return
    # Defensive fallback: still place it before the catch-all static mount.
    app.router.routes.append(route)


_install_premium_route()
