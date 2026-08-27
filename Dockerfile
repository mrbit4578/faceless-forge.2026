FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8001

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.production.txt /app/backend/requirements.production.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.production.txt

COPY backend /app/backend
COPY faceless_web /app/faceless_web

WORKDIR /app/backend
CMD sh -c "uvicorn forge_app:app --host 0.0.0.0 --port ${PORT}"
