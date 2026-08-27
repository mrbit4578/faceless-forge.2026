"""RAG engine: document ingestion, TF-IDF retrieval (pure python), LLM Q&A + video script."""
import logging
import math
import re
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from ai_engine import DEFAULT_TEXT_MODEL, _ask, _new_chat

logger = logging.getLogger(__name__)

DOCS_COLLECTION = "rag_docs"
CHUNKS_COLLECTION = "rag_chunks"

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100

_WORD_RE = re.compile(r"[\w\u00C0-\u1EF9]+", re.UNICODE)


def _tokenize(text: str):
    return [w.lower() for w in _WORD_RE.findall(text or "")]


def parse_document(path: Path, filename: str) -> str:
    ext = (filename or path.name).lower().rsplit(".", 1)[-1]
    if ext in ("txt", "md", "markdown", "srt", "csv", "json"):
        return path.read_text(encoding="utf-8", errors="ignore")
    if ext == "pdf":
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    if ext in ("docx",):
        import docx
        d = docx.Document(str(path))
        return "\n".join(p.text for p in d.paragraphs)
    raise ValueError(f"\u0110\u1ecbnh d\u1ea1ng .{ext} ch\u01b0a h\u1ed7 tr\u1ee3 (d\u00f9ng txt/md/pdf/docx)")


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP):
    text = re.sub(r"\n{3,}", "\n\n", (text or "").strip())
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            window = text[start:end]
            cut = max(window.rfind("\n\n"), window.rfind(". "), window.rfind("\n"))
            if cut > size * 0.5:
                end = start + cut + 1
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


async def ingest_document(db, path: Path, original_name: str) -> dict:
    text = parse_document(path, original_name)
    chunks = chunk_text(text)
    if not chunks:
        raise ValueError("T\u00e0i li\u1ec7u tr\u1ed1ng ho\u1eb7c kh\u00f4ng \u0111\u1ecdc \u0111\u01b0\u1ee3c n\u1ed9i dung")
    doc = {
        "id": str(uuid.uuid4()),
        "name": original_name,
        "size": path.stat().st_size,
        "chunk_count": len(chunks),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db[DOCS_COLLECTION].insert_one({**doc})
    chunk_docs = [{
        "id": f"{doc['id']}-{i}",
        "doc_id": doc["id"],
        "doc_name": original_name,
        "index": i,
        "text": c,
        "tokens": _tokenize(c),
    } for i, c in enumerate(chunks)]
    await db[CHUNKS_COLLECTION].insert_many([{**c} for c in chunk_docs])
    return doc


async def list_documents(db):
    return await db[DOCS_COLLECTION].find({}, {"_id": 0}).sort("created_at", -1).to_list(200)


async def delete_document(db, doc_id: str):
    await db[DOCS_COLLECTION].delete_one({"id": doc_id})
    await db[CHUNKS_COLLECTION].delete_many({"doc_id": doc_id})


async def retrieve(db, question: str, doc_ids=None, top_k: int = 5):
    """TF-IDF cosine retrieval over stored chunks."""
    query = {"doc_id": {"$in": doc_ids}} if doc_ids else {}
    projection = {"_id": 0, "id": 1, "doc_id": 1, "doc_name": 1, "index": 1,
                  "text": 1, "tokens": 1}
    chunks = await db[CHUNKS_COLLECTION].find(query, projection).limit(3000).to_list(3000)
    if not chunks:
        return []
    q_tokens = _tokenize(question)
    if not q_tokens:
        return []
    n = len(chunks)
    df = Counter()
    for c in chunks:
        df.update(set(c.get("tokens") or _tokenize(c["text"])))
    idf = {t: math.log((n + 1) / (df[t] + 1)) + 1 for t in df}

    q_tf = Counter(q_tokens)
    q_vec = {t: (1 + math.log(f)) * idf.get(t, math.log(n + 1) + 1) for t, f in q_tf.items()}
    q_norm = math.sqrt(sum(v * v for v in q_vec.values())) or 1.0

    scored = []
    for c in chunks:
        tokens = c.get("tokens") or _tokenize(c["text"])
        tf = Counter(tokens)
        score = 0.0
        c_norm_sq = 0.0
        for t, f in tf.items():
            w = (1 + math.log(f)) * idf.get(t, 1.0)
            c_norm_sq += w * w
            if t in q_vec:
                score += w * q_vec[t]
        c_norm = math.sqrt(c_norm_sq) or 1.0
        cos = score / (q_norm * c_norm)
        if cos > 0:
            scored.append((cos, c))
    scored.sort(key=lambda x: -x[0])
    return [{"id": c["id"], "doc_id": c["doc_id"], "doc_name": c.get("doc_name", ""),
             "index": c["index"], "text": c["text"], "score": round(s, 4)}
            for s, c in scored[:top_k]]


async def ask(db, question: str, doc_ids=None, top_k: int = 5,
              model_key: str = DEFAULT_TEXT_MODEL):
    hits = await retrieve(db, question, doc_ids, top_k)
    if not hits:
        return {"answer": "Kh\u00f4ng t\u00ecm th\u1ea5y n\u1ed9i dung li\u00ean quan trong t\u00e0i li\u1ec7u. H\u00e3y upload t\u00e0i li\u1ec7u ho\u1eb7c \u0111\u1eb7t c\u00e2u h\u1ecfi kh\u00e1c.",
                "citations": []}
    context = "\n\n".join(f"[C{i + 1}] (t\u00e0i li\u1ec7u: {h['doc_name']})\n{h['text']}"
                           for i, h in enumerate(hits))
    system = (
        "B\u1ea1n l\u00e0 tr\u1ee3 l\u00fd h\u1ecfi \u0111\u00e1p t\u00e0i li\u1ec7u (RAG). "
        "CH\u1ec8 tr\u1ea3 l\u1eddi d\u1ef1a tr\u00ean c\u00e1c tr\u00edch \u0111o\u1ea1n \u0111\u01b0\u1ee3c cung c\u1ea5p. "
        "Tr\u1ea3 l\u1eddi b\u1eb1ng ti\u1ebfng Vi\u1ec7t, r\u00f5 r\u00e0ng, c\u00f3 c\u1ea5u tr\u00fac. "
        "Khi d\u00f9ng th\u00f4ng tin t\u1eeb tr\u00edch \u0111o\u1ea1n n\u00e0o, ghi [C1], [C2]... ngay sau c\u00e2u. "
        "N\u1ebfu tr\u00edch \u0111o\u1ea1n kh\u00f4ng \u0111\u1ee7 th\u00f4ng tin, n\u00f3i r\u00f5 l\u00e0 t\u00e0i li\u1ec7u kh\u00f4ng \u0111\u1ec1 c\u1eadp."
    )
    chat = _new_chat(system, model_key)
    answer = await _ask(chat, f"TR\u00cdCH \u0110O\u1ea0N:\n{context}\n\nC\u00c2U H\u1eceI: {question}")
    citations = [{"label": f"C{i + 1}", "doc_name": h["doc_name"], "doc_id": h["doc_id"],
                  "snippet": h["text"][:220], "score": h["score"]}
                 for i, h in enumerate(hits)]
    return {"answer": answer.strip(), "citations": citations}


async def generate_video_script(db, doc_ids=None, topic: str = "", style: str = "storytelling",
                                duration_sec: int = 60, model_key: str = DEFAULT_TEXT_MODEL):
    query_text = topic or "n\u1ed9i dung ch\u00ednh c\u1ee7a t\u00e0i li\u1ec7u"
    hits = await retrieve(db, query_text, doc_ids, top_k=8)
    if not hits:
        raise ValueError("Ch\u01b0a c\u00f3 t\u00e0i li\u1ec7u \u0111\u1ec3 t\u1ea1o k\u1ecbch b\u1ea3n \u2014 h\u00e3y upload tr\u01b0\u1edbc")
    context = "\n\n".join(h["text"] for h in hits)
    words = max(60, int(duration_sec * 2.4))
    system = (
        "B\u1ea1n l\u00e0 bi\u00ean k\u1ecbch video chuy\u00ean nghi\u1ec7p. D\u1ef1a tr\u00ean t\u00e0i li\u1ec7u \u0111\u01b0\u1ee3c cung c\u1ea5p, "
        "vi\u1ebft l\u1eddi b\u00ecnh (voice-over) ti\u1ebfng Vi\u1ec7t t\u1ef1 nhi\u00ean nh\u01b0 ng\u01b0\u1eddi th\u1eadt n\u00f3i, "
        "c\u00f3 m\u1edf \u0111\u1ea7u cu\u1ed1n h\u00fat, th\u00e2n b\u00e0i m\u1ea1ch l\u1ea1c, k\u1ebft th\u00fac k\u00eau g\u1ecdi h\u00e0nh \u0111\u1ed9ng. "
        "KH\u00d4NG d\u00f9ng markdown, KH\u00d4NG ti\u00eau \u0111\u1ec1, KH\u00d4NG ghi ch\u00fa c\u1ea3nh quay \u2014 "
        "ch\u1ec9 vi\u1ebft \u0111o\u1ea1n v\u0103n l\u1eddi b\u00ecnh li\u1ec1n m\u1ea1ch \u0111\u1ec3 \u0111\u1ecdc th\u00e0nh audio."
    )
    user = (f"T\u00c0I LI\u1ec6U:\n{context}\n\n"
            f"Y\u00caU C\u1ea6U: Vi\u1ebft l\u1eddi b\u00ecnh video kho\u1ea3ng {words} t\u1eeb "
            f"(~{duration_sec} gi\u00e2y \u0111\u1ecdc). Phong c\u00e1ch: {style}. "
            + (f"Ch\u1ee7 \u0111\u1ec1 tr\u1ecdng t\u00e2m: {topic}." if topic else ""))
    chat = _new_chat(system, model_key)
    script = (await _ask(chat, user)).strip()
    return {"script": script, "word_count": len(script.split()),
            "est_duration_sec": duration_sec, "sources": [h["doc_name"] for h in hits[:3]]}
