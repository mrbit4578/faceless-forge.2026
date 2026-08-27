"""Creative planning engine for Faceless Forge.

It produces an actionable, platform-aware package before media is generated.
Distribution and monetisation are controlled by platforms and cannot be promised.
"""
import json
import re
from typing import Any

from ai_engine import DEFAULT_TEXT_MODEL, _ask, _new_chat


def _clean_list(value: Any, fallback: list[str], limit: int) -> list[str]:
    if not isinstance(value, list):
        return fallback
    cleaned = [str(item).strip() for item in value if str(item).strip()]
    return cleaned[:limit] or fallback


def _fallback_blueprint(request: dict) -> dict:
    """Useful no-key response so the planning workspace also works locally."""
    topic = request["topic"].strip()
    duration = int(request.get("duration_sec", 45))
    platform = request.get("platform", "TikTok & YouTube Shorts")
    tone = request.get("tone", "Kể chuyện giàu nhịp")
    opening = f"Bạn có từng tự hỏi vì sao {topic} lại khiến nhiều người bỏ lỡ điều quan trọng nhất?"
    script = (
        f"{opening} Chỉ trong vài giây tới, bạn sẽ thấy một góc nhìn khác. "
        f"{topic} không chỉ là một chi tiết thú vị; nó có thể thay đổi cách chúng ta nhìn vấn đề. "
        "Đầu tiên, hãy bắt đầu từ điều ít người để ý nhất. Tiếp theo, kết nối nó với một tình huống rất quen thuộc trong đời sống. "
        "Và đây là điểm mấu chốt: khi hiểu nguyên lý phía sau, bạn có thể áp dụng ngay thay vì chỉ xem rồi quên. "
        "Nếu bạn muốn phần tiếp theo sâu hơn, hãy lưu video này và theo dõi để không bỏ lỡ."
    )
    shot_count = max(4, min(7, round(duration / 8)))
    shots = []
    for index in range(shot_count):
        start = round(index * duration / shot_count)
        end = round((index + 1) * duration / shot_count)
        phases = ["Câu móc mở đầu", "Đặt vấn đề", "Bật mí insight", "Ví dụ trực quan", "Điểm then chốt", "Kết & CTA", "Kết & CTA"]
        phase = phases[min(index, len(phases) - 1)]
        narrations = [opening, "Đây là điều phần lớn mọi người thường bỏ qua.", "Hãy nhìn vào chi tiết này để thấy khác biệt.", "Đặt nó vào một ví dụ đơn giản, dễ nhớ.", "Điểm quan trọng là biến kiến thức thành hành động.", "Lưu lại và theo dõi để xem phần tiếp theo."]
        overlays = ["DỪNG LẠI 3 GIÂY", "ÍT AI ĐỂ Ý", "ĐIỂM MẤU CHỐT", "VÍ DỤ THỰC TẾ", "ÁP DỤNG NGAY", "LƯU VIDEO NÀY"]
        shots.append({
            "start_sec": start,
            "end_sec": end,
            "purpose": phase,
            "visual": f"Cảnh faceless giàu chuyển động minh hoạ {topic}, bố cục dọc 9:16.",
            "narration": narrations[min(index, len(narrations) - 1)],
            "on_screen_text": overlays[min(index, len(overlays) - 1)],
            "image_prompt": (
                f"Vertical 9:16 cinematic editorial illustration about {topic}, {phase.lower()}, "
                "faceless storytelling, strong subject separation, premium lighting, clean center space for Vietnamese captions, no text, no watermark"
            ),
        })
    return {
        "viral_score": 72,
        "concept": f"Một video {tone.lower()} giải mã {topic} bằng nhịp nhanh, hình ảnh rõ ý và CTA tự nhiên.",
        "why_it_can_work": [
            "Mở bằng một câu hỏi tạo khoảng trống tò mò.",
            "Mỗi đoạn đều có một thay đổi hình ảnh để giữ nhịp xem.",
            "Kết thúc tạo lý do để lưu và quay lại xem phần tiếp theo.",
        ],
        "titles": [
            f"Sự thật về {topic} mà nhiều người bỏ lỡ",
            f"Đừng lướt: hiểu {topic} trong {duration} giây",
            f"Tại sao {topic} quan trọng hơn bạn nghĩ?",
        ],
        "thumbnail_text": "ĐỪNG BỎ QUA",
        "hook": opening,
        "script": script,
        "shots": shots,
        "seo": {
            "description": f"Một góc nhìn ngắn, dễ hiểu về {topic}. Xem đến cuối và lưu lại nếu bạn thấy hữu ích.",
            "hashtags": ["#faceless", "#shorts", "#learnontiktok", "#contentcreator", "#viralvideo"],
            "pinned_comment": "Bạn muốn mình làm video tiếp theo về khía cạnh nào?",
        },
        "monetization": {
            "angle": "Xây dựng series cùng một niche để tăng độ tin cậy và cơ hội xem lại; chỉ dùng nguồn tư liệu có quyền sử dụng.",
            "cta": "Lưu video và theo dõi để xem phần tiếp theo.",
            "disclosure": "Không cam kết view hoặc doanh thu. Kiểm tra chính sách kiếm tiền, bản quyền và nội dung tổng hợp của nền tảng trước khi đăng.",
        },
        "production_checklist": [
            "Kiểm chứng mọi số liệu/câu khẳng định trước khi thu âm.",
            "Dùng hình, nhạc và footage bạn có quyền sử dụng thương mại.",
            "Giữ chữ trên màn hình dưới 7 từ mỗi cảnh và đủ tương phản.",
            f"Xuất 9:16, xem lại phụ đề và đăng thử trên {platform}.",
        ],
        "fallback": True,
    }


def _normalise_blueprint(data: dict, request: dict) -> dict:
    fallback = _fallback_blueprint(request)
    if not isinstance(data, dict):
        return fallback
    blueprint = {**fallback, **data}
    try:
        blueprint["viral_score"] = max(1, min(100, int(data.get("viral_score", fallback["viral_score"]))))
    except (TypeError, ValueError):
        blueprint["viral_score"] = fallback["viral_score"]
    blueprint["concept"] = str(data.get("concept") or fallback["concept"]).strip()
    blueprint["hook"] = str(data.get("hook") or fallback["hook"]).strip()
    blueprint["script"] = str(data.get("script") or fallback["script"]).strip()
    blueprint["thumbnail_text"] = str(data.get("thumbnail_text") or fallback["thumbnail_text"]).strip()[:48]
    blueprint["titles"] = _clean_list(data.get("titles"), fallback["titles"], 5)
    blueprint["why_it_can_work"] = _clean_list(data.get("why_it_can_work"), fallback["why_it_can_work"], 5)
    blueprint["production_checklist"] = _clean_list(data.get("production_checklist"), fallback["production_checklist"], 7)
    seo = data.get("seo") if isinstance(data.get("seo"), dict) else {}
    blueprint["seo"] = {
        "description": str(seo.get("description") or fallback["seo"]["description"]).strip(),
        "hashtags": _clean_list(seo.get("hashtags"), fallback["seo"]["hashtags"], 10),
        "pinned_comment": str(seo.get("pinned_comment") or fallback["seo"]["pinned_comment"]).strip(),
    }
    monetization = data.get("monetization") if isinstance(data.get("monetization"), dict) else {}
    blueprint["monetization"] = {
        "angle": str(monetization.get("angle") or fallback["monetization"]["angle"]).strip(),
        "cta": str(monetization.get("cta") or fallback["monetization"]["cta"]).strip(),
        "disclosure": str(monetization.get("disclosure") or fallback["monetization"]["disclosure"]).strip(),
    }
    shots = data.get("shots")
    if isinstance(shots, list) and shots:
        cleaned_shots = []
        for index, shot in enumerate(shots[:12]):
            if not isinstance(shot, dict):
                continue
            fallback_shot = fallback["shots"][min(index, len(fallback["shots"]) - 1)]
            cleaned_shots.append({
                "start_sec": shot.get("start_sec", fallback_shot["start_sec"]),
                "end_sec": shot.get("end_sec", fallback_shot["end_sec"]),
                "purpose": str(shot.get("purpose") or fallback_shot["purpose"]).strip(),
                "visual": str(shot.get("visual") or fallback_shot["visual"]).strip(),
                "narration": str(shot.get("narration") or fallback_shot["narration"]).strip(),
                "on_screen_text": str(shot.get("on_screen_text") or fallback_shot["on_screen_text"]).strip(),
                "image_prompt": str(shot.get("image_prompt") or fallback_shot["image_prompt"]).strip(),
            })
        blueprint["shots"] = cleaned_shots or fallback["shots"]
    else:
        blueprint["shots"] = fallback["shots"]
    blueprint["fallback"] = False
    return blueprint


def _extract_json(text: str) -> dict:
    cleaned = (text or "").strip()
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", cleaned)
        if not match:
            raise
        return json.loads(match.group(0))


async def generate_viral_blueprint(request: dict) -> dict:
    """Generate a structured video-production brief, with a deterministic fallback."""
    fallback = _fallback_blueprint(request)
    system = """You are Faceless Forge's senior short-form video strategist. Create original, useful,
truthful video plans that help a creator make a polished faceless video. Never promise views,
revenue, monetisation acceptance, or algorithmic reach. Do not invent facts, testimonials,
medical/legal/financial advice, or copyrighted characters. Recommend licensed/original assets.

Return ONLY valid JSON. No markdown and no text before or after it. The JSON schema is:
{
  "viral_score": 1-100,
  "concept": "one concise sentence",
  "why_it_can_work": ["3 concise reasons"],
  "titles": ["3 platform-safe title options"],
  "thumbnail_text": "2-5 impactful words",
  "hook": "first spoken sentence",
  "script": "a complete natural voice-over in the requested language; no headings or production notes",
  "shots": [{"start_sec":0,"end_sec":7,"purpose":"...","visual":"...","narration":"...","on_screen_text":"...","image_prompt":"detailed English, vertical 9:16, no text, no watermark"}],
  "seo": {"description":"...","hashtags":["#..."],"pinned_comment":"..."},
  "monetization": {"angle":"ethical series or product-fit idea without promises","cta":"...","disclosure":"short rights/policy reminder"},
  "production_checklist": ["4-6 practical checks"]
}
Use fresh, specific wording. Make one shot about every 5-9 seconds, retain a fast visual rhythm,
and ensure the spoken script follows the shots."""
    user = (
        f"Topic: {request['topic']}\nNiche: {request.get('niche', 'General')}\n"
        f"Audience: {request.get('audience', 'General')}\nPlatform: {request.get('platform', 'Short-form')}\n"
        f"Target duration: {request.get('duration_sec', 45)} seconds\nTone: {request.get('tone', 'Storytelling')}\n"
        f"Language: {request.get('language', 'Vietnamese')}\nMonetisation goal: {request.get('monetization_goal', 'Build a sustainable audience')}"
    )
    try:
        chat = _new_chat(system, request.get("model") or DEFAULT_TEXT_MODEL)
        response = await _ask(chat, user)
        return _normalise_blueprint(_extract_json(response), request)
    except Exception:
        return fallback
