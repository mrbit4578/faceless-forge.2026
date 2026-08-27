"""LLM helpers: SRT translation, prompt enhancement, image generation (Emergent key)."""
import asyncio
import base64
import logging
import os
import re
import uuid

from media_store import new_media_path, media_url

logger = logging.getLogger(__name__)

TEXT_MODELS = {
    "gemini-flash": ("gemini", "gemini-3.7-flash"),
    "gpt-5.4": ("openai", "gpt-5.4"),
    "gpt-4.1-mini": ("openai", "gpt-4.1-mini"),
    "claude-sonnet": ("anthropic", "claude-sonnet-4-6"),
}
DEFAULT_TEXT_MODEL = "gemini-flash"

IMAGE_MODELS = ["gpt-image-1", "nano-banana"]

_LINE_RE = re.compile(r"^\s*(\d+)\s*\|\|\s*(.*)$")


def _get_key() -> str:
    key = os.environ.get("EMERGENT_LLM_KEY")
    if not key:
        raise RuntimeError("Thi\u1ebfu EMERGENT_LLM_KEY trong backend/.env")
    return key


def _new_chat(system_message: str, model_key: str):
    from emergentintegrations.llm.chat import LlmChat

    provider, model = TEXT_MODELS.get(model_key, TEXT_MODELS[DEFAULT_TEXT_MODEL])
    chat = LlmChat(api_key=_get_key(), session_id=f"sat-{uuid.uuid4().hex[:10]}",
                   system_message=system_message)
    chat.with_model(provider, model)
    return chat


async def _ask(chat, text: str) -> str:
    from emergentintegrations.llm.chat import UserMessage

    resp = await chat.send_message(UserMessage(text=text))
    if isinstance(resp, str):
        return resp
    return getattr(resp, "text", None) or str(resp)


async def translate_texts(texts, target_lang: str, model_key: str = DEFAULT_TEXT_MODEL,
                          progress_cb=None, base_progress: int = 0, span: int = 100):
    """Translate a list of strings, preserving order. Batches of 25 lines."""
    system = (
        "You are a professional subtitle translator. Translate each numbered line into "
        f"{target_lang}. Preserve meaning, tone and approximate length. "
        "Reply with ONLY lines in the exact format: <number>||<translation>. "
        "One line per input line. No commentary, no markdown."
    )
    results = list(texts)
    batch_size = 25
    batches = [list(range(i, min(i + batch_size, len(texts)))) for i in range(0, len(texts), batch_size)]
    for bi, idxs in enumerate(batches):
        chat = _new_chat(system, model_key)
        payload = "\n".join(f"{j + 1}||{texts[idx]}" for j, idx in enumerate(idxs))
        answer = await _ask(chat, payload)
        parsed = {}
        for line in answer.splitlines():
            m = _LINE_RE.match(line)
            if m:
                parsed[int(m.group(1))] = m.group(2).strip()
        for j, idx in enumerate(idxs):
            if (j + 1) in parsed and parsed[j + 1]:
                results[idx] = parsed[j + 1]
        if progress_cb:
            pct = base_progress + int(span * (bi + 1) / len(batches))
            await progress_cb(pct, f"\u0110ang d\u1ecbch... ({bi + 1}/{len(batches)} nh\u00f3m)")
    return results


async def enhance_prompt(prompt: str, model_key: str = DEFAULT_TEXT_MODEL) -> str:
    system = (
        "You are an expert AI image prompt engineer. Rewrite the user's idea into one "
        "detailed, vivid English image-generation prompt (subject, style, lighting, "
        "composition, quality tags). Reply with ONLY the prompt text."
    )
    chat = _new_chat(system, model_key)
    return (await _ask(chat, prompt)).strip()


async def generate_image_openai(prompt: str, n: int = 1, quality: str = "medium"):
    """gpt-image-1 via Emergent key. Returns list of saved file paths."""
    from emergentintegrations.llm.openai.image_generation import OpenAIImageGeneration

    api_key = _get_key()

    def _run():
        gen = OpenAIImageGeneration(api_key=api_key)
        return asyncio.run(gen.generate_images(prompt=prompt, model="gpt-image-1",
                                               number_of_images=n, quality=quality))
    images = await asyncio.to_thread(_run)
    paths = []
    for img_bytes in images or []:
        p = new_media_path("images", "png", "gptimg_")
        p.write_bytes(img_bytes)
        paths.append(p)
    if not paths:
        raise RuntimeError("gpt-image-1 kh\u00f4ng tr\u1ea3 v\u1ec1 \u1ea3nh")
    return paths


async def generate_image_gemini(prompt: str):
    """Nano Banana (gemini-3.1-flash-image-preview). Returns list of saved file paths."""
    from emergentintegrations.llm.chat import LlmChat, UserMessage

    chat = LlmChat(api_key=_get_key(), session_id=f"img-{uuid.uuid4().hex[:10]}",
                   system_message="You are a helpful AI assistant")
    chat.with_model("gemini", "gemini-3.1-flash-image-preview").with_params(
        modalities=["image", "text"])
    _text, images = await chat.send_message_multimodal_response(UserMessage(text=prompt))
    paths = []
    for img in images or []:
        data = img.get("data") if isinstance(img, dict) else None
        if not data:
            continue
        p = new_media_path("images", "png", "banana_")
        p.write_bytes(base64.b64decode(data))
        paths.append(p)
    if not paths:
        raise RuntimeError("Nano Banana kh\u00f4ng tr\u1ea3 v\u1ec1 \u1ea3nh")
    return paths


async def generate_images(prompt: str, model: str = "gpt-image-1", n: int = 1):
    if model == "nano-banana":
        paths = []
        for _ in range(max(1, min(n, 4))):
            paths.extend(await generate_image_gemini(prompt))
        return [{"url": media_url(p), "filename": p.name} for p in paths]
    paths = await generate_image_openai(prompt, n=max(1, min(n, 4)))
    return [{"url": media_url(p), "filename": p.name} for p in paths]
