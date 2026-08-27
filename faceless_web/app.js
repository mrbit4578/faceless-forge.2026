/*
 * Static-host adapter.
 * Vercel and GitHub Pages serve the visual interface but have no /api backend.
 * This adapter returns a useful local blueprint instead of passing HTML to the
 * legacy client as JSON. When the FastAPI service runs on the same domain, all
 * requests pass straight through to the real API.
 */
(() => {
  const nativeFetch = window.fetch.bind(window);
  const configuredBase = String(window.FACELESS_FORGE_API_URL || "").replace(/\/$/, "");
  const json = (body, status = 200) => new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });

  const localBlueprint = (brief) => {
    const topic = String(brief.topic || "ý tưởng của bạn").trim();
    const duration = Math.max(15, Math.min(180, Number(brief.duration_sec || 45)));
    const opening = `Bạn có từng tự hỏi vì sao ${topic} lại khiến nhiều người bỏ lỡ điều quan trọng nhất?`;
    const purposes = ["Câu móc mở đầu", "Đặt vấn đề", "Bật mí insight", "Ví dụ trực quan", "Điểm then chốt", "Kết & CTA"];
    const narrations = [
      opening,
      "Đây là điều phần lớn mọi người thường bỏ qua.",
      "Hãy nhìn vào chi tiết này để thấy khác biệt.",
      "Đặt nó vào một ví dụ đơn giản, dễ nhớ.",
      "Điểm quan trọng là biến kiến thức thành hành động.",
      "Lưu lại và theo dõi để xem phần tiếp theo.",
    ];
    const overlays = ["DỪNG LẠI 3 GIÂY", "ÍT AI ĐỂ Ý", "ĐIỂM MẤU CHỐT", "VÍ DỤ THỰC TẾ", "ÁP DỤNG NGAY", "LƯU VIDEO NÀY"];
    const count = Math.max(4, Math.min(6, Math.round(duration / 8)));
    const shots = Array.from({ length: count }, (_, index) => ({
      start_sec: Math.round(index * duration / count),
      end_sec: Math.round((index + 1) * duration / count),
      purpose: purposes[Math.min(index, purposes.length - 1)],
      visual: `Cảnh faceless giàu chuyển động minh hoạ ${topic}, bố cục dọc 9:16.`,
      narration: narrations[Math.min(index, narrations.length - 1)],
      on_screen_text: overlays[Math.min(index, overlays.length - 1)],
      image_prompt: `Vertical 9:16 cinematic editorial illustration about ${topic}, faceless storytelling, premium lighting, clean center space for Vietnamese captions, no text, no watermark`,
    }));
    return {
      fallback: true,
      viral_score: 72,
      concept: `Video ${String(brief.tone || "kể chuyện").toLowerCase()} giải mã ${topic} bằng nhịp nhanh, hình ảnh rõ ý và CTA tự nhiên.`,
      why_it_can_work: ["Mở bằng câu hỏi tạo khoảng trống tò mò.", "Mỗi đoạn thay đổi hình ảnh để giữ nhịp xem.", "Kết thúc tạo lý do để lưu và quay lại xem phần tiếp theo."],
      titles: [`Sự thật về ${topic} mà nhiều người bỏ lỡ`, `Đừng lướt: hiểu ${topic} trong ${duration} giây`, `Tại sao ${topic} quan trọng hơn bạn nghĩ?`],
      thumbnail_text: "ĐỪNG BỎ QUA",
      hook: opening,
      script: `${opening} Chỉ trong vài giây tới, bạn sẽ thấy một góc nhìn khác. ${topic} không chỉ là một chi tiết thú vị; nó có thể thay đổi cách chúng ta nhìn vấn đề. Đầu tiên, hãy bắt đầu từ điều ít người để ý nhất. Tiếp theo, kết nối nó với một tình huống rất quen thuộc trong đời sống. Và đây là điểm mấu chốt: khi hiểu nguyên lý phía sau, bạn có thể áp dụng ngay thay vì chỉ xem rồi quên. Nếu bạn muốn phần tiếp theo sâu hơn, hãy lưu video này và theo dõi để không bỏ lỡ.`,
      shots,
      seo: {
        description: `Một góc nhìn ngắn, dễ hiểu về ${topic}. Xem đến cuối và lưu lại nếu bạn thấy hữu ích.`,
        hashtags: ["#faceless", "#shorts", "#contentcreator", "#viralvideo"],
        pinned_comment: "Bạn muốn mình làm video tiếp theo về khía cạnh nào?",
      },
      monetization: {
        angle: "Xây dựng series cùng một niche và chỉ dùng tư liệu có quyền sử dụng.",
        cta: "Lưu video và theo dõi để xem phần tiếp theo.",
        disclosure: "Không cam kết view hoặc doanh thu. Kiểm tra bản quyền và chính sách nền tảng trước khi đăng.",
      },
      production_checklist: [
        "Kiểm chứng mọi số liệu/câu khẳng định.",
        "Dùng hình, nhạc và footage có quyền thương mại.",
        "Giữ chữ trên màn hình ngắn, tương phản tốt.",
        "Xuất 9:16, xem lại phụ đề trước khi đăng.",
      ],
    };
  };

  window.fetch = async (resource, options) => {
    const path = typeof resource === "string" ? resource : resource.url;
    if (!path.startsWith("/api/")) return nativeFetch(resource, options);
    const url = configuredBase ? `${configuredBase}${path}` : path;

    if (path === "/api/forge/blueprint") {
      try {
        const response = await nativeFetch(url, options);
        const contentType = response.headers.get("content-type") || "";
        if (response.ok && contentType.includes("application/json")) return response;
      } catch {
        // Static hosts and offline pages intentionally use the local plan below.
      }
      let brief = {};
      try { brief = JSON.parse(options?.body || "{}"); } catch { /* use defaults */ }
      return json(localBlueprint(brief));
    }

    if (configuredBase) return nativeFetch(url, options);
    return json({
      detail: "Bạn đang dùng bản giao diện tĩnh. Để tạo ảnh, giọng đọc và MP4 thật, hãy mở bản Docker trên Render/Railway và cấu hình MONGO_URL cùng EMERGENT_LLM_KEY.",
    }, 503);
  };

  const script = document.createElement("script");
  script.src = "app.legacy.js";
  script.async = false;
  document.body.appendChild(script);
})();
