# Faceless Forge

Faceless Forge is a single-workflow web studio for turning one creative brief into a polished vertical faceless video.

1. **Viral Blueprint** — creates a platform-aware hook, titles, a complete Vietnamese voice-over, shot list, image prompts, SEO pack and a publication checklist.
2. **One-click production** — creates an AI key visual, Edge TTS voice-over, subtitles and an `1080 × 1920` MP4 as one background job.
3. **Responsible monetisation** — the product does not promise revenue, views or algorithmic distribution and highlights rights/policy checks before publishing.

The FastAPI service serves the zero-build HTML/CSS/JS interface and `/api` from one domain. Existing media workstation API routes remain available for TTS, dubbing, SRT translation, image generation, rendering, splitting and document RAG.

## Run locally

Prerequisites: Python 3.11+, FFmpeg, MongoDB and an Emergent LLM key for live AI planning/image generation.

```bash
cp .env.example backend/.env
# Fill in EMERGENT_LLM_KEY and MONGO_URL
pip install -r backend/requirements.production.txt
cd backend
uvicorn forge_app:app --host 0.0.0.0 --port 8001
```

Open `http://localhost:8001`.

## Deploy online

This repo has a production `Dockerfile` and `render.yaml`.

1. Create a MongoDB database (MongoDB Atlas is suitable) and create a Render Web Service from this repository.
2. Let Render use the Dockerfile, then set `MONGO_URL` and `EMERGENT_LLM_KEY` as secrets. `DB_NAME=faceless_forge` and `CORS_ORIGINS=*` are provided in `render.yaml`.
3. Deploy. The service runs `forge_app:app` and exposes the UI and API together.

Never commit a real `.env` file or generated media.

## Main API

- `POST /api/forge/blueprint` — plan a short-form video from a creative brief.
- `POST /api/forge/produce` — make visual + voice + vertical MP4 as a background job.
- `GET /api/jobs/{id}` — poll production status.
- `GET /api/health` — verify FFmpeg, MongoDB and AI-key availability.

## Notes

- The no-key fallback creates a local planning template. Live AI visual/video generation requires `EMERGENT_LLM_KEY`.
- Check factual claims, commercial-use rights for assets, and TikTok/YouTube/Instagram policies before publishing.
