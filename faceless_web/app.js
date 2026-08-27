const form = document.querySelector("#brief-form");
const blueprintNode = document.querySelector("#blueprint");
const emptyNode = document.querySelector("#empty-state");
const blueprintButton = document.querySelector("#blueprint-button");
const toastNode = document.querySelector("#toast");

let currentBlueprint = null;
let toastTimer = null;

const $ = (selector) => document.querySelector(selector);
const value = (selector) => $(selector).value.trim();
const safe = (input = "") => String(input)
  .replaceAll("&", "&amp;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;")
  .replaceAll("'", "&#039;");

function notify(message, isError = false) {
  clearTimeout(toastTimer);
  toastNode.textContent = message;
  toastNode.classList.toggle("error", isError);
  toastNode.classList.add("show");
  toastTimer = setTimeout(() => toastNode.classList.remove("show"), 3400);
}

async function copyText(text, label = "Đã sao chép") {
  if (!text) return notify("Chưa có nội dung để sao chép", true);
  try {
    await navigator.clipboard.writeText(text);
    notify(label);
  } catch {
    notify("Trình duyệt không cho phép sao chép", true);
  }
}

function collectBrief() {
  return {
    topic: value("#topic"),
    niche: value("#niche"),
    audience: value("#audience"),
    platform: value("#platform"),
    duration_sec: Number(value("#duration")),
    tone: value("#tone"),
    language: "Tiếng Việt",
    monetization_goal: value("#goal"),
    model: value("#model"),
  };
}

function tags(items = []) {
  return items.map((item) => `<span class="tag">${safe(item)}</span>`).join("");
}

function titles(items = []) {
  return items.map((item, index) => `<button type="button" class="copy-card" data-copy-title="${index}" data-index="TITLE 0${index + 1}">${safe(item)}</button>`).join("");
}

function shotCards(items = []) {
  return items.map((shot, index) => `
    <article class="shot">
      <div class="shot-top"><span><span class="time">${safe(String(shot.start_sec).padStart(2, "0"))}–${safe(String(shot.end_sec).padStart(2, "0"))}s</span> <span class="purpose">${safe(shot.purpose)}</span></span><button class="prompt-copy" type="button" data-copy-prompt="${index}">COPY PROMPT</button></div>
      <div class="shot-grid"><p><span class="label">VISUAL</span>${safe(shot.visual)}</p><p><span class="label">VOICE-OVER</span>${safe(shot.narration)}</p></div>
      <span class="overlay">${safe(shot.on_screen_text)}</span>
    </article>`).join("");
}

function renderBlueprint(plan) {
  const reasons = (plan.why_it_can_work || []).map((item) => `<li>${safe(item)}</li>`).join("");
  const checks = (plan.production_checklist || []).map((item) => `<li>${safe(item)}</li>`).join("");
  const seo = plan.seo || {};
  const money = plan.monetization || {};
  blueprintNode.innerHTML = `
    <div class="blueprint-head">
      <div><div class="kicker">VIRAL BLUEPRINT · ${plan.fallback ? "LOCAL PLAN MODE" : "AI STRATEGY"}</div><h2>${safe(plan.concept)}</h2></div>
      <div class="score"><b>${safe(plan.viral_score)}</b><small>fit score</small></div>
    </div>
    <div class="info-grid"><div class="info-card"><span class="label">HOOK · 0–3 GIÂY</span><p>${safe(plan.hook)}</p></div><div class="info-card"><span class="label">THUMBNAIL TEXT</span><p class="thumb">${safe(plan.thumbnail_text)}</p></div></div>
    <section class="section-card"><div class="section-title">3 hướng tiêu đề <small>Bấm để copy</small></div><div class="title-grid">${titles(plan.titles)}</div></section>
    <section class="section-card"><div class="section-title">Lời bình hoàn chỉnh <small>${(plan.script || "").trim().split(/\s+/).filter(Boolean).length} từ</small></div><p class="script">${safe(plan.script)}</p><div class="tool-row"><button class="button ghost" type="button" data-copy-script>⧉ Copy voice-over</button><button class="button ghost" type="button" data-copy-publish>⧉ Copy publish pack</button><button class="button ghost forge" type="button" data-produce>✦ Dựng video MP4 tự động</button></div><div class="job" id="production-job"><div class="job-line"><span id="job-message">Đang chuẩn bị...</span><b id="job-percent">0%</b></div><div class="bar"><i id="job-bar"></i></div><div id="render-result" class="render-result"></div></div></section>
    <section class="section-card"><div class="section-title">Shot list &amp; visual prompt <small>1 cảnh / 5–9 giây</small></div><div class="shot-list">${shotCards(plan.shots)}</div></section>
    <div class="bottom-grid"><section class="section-card"><div class="section-title">Gói xuất bản <small>SEO dễ đọc</small></div><p class="publish-copy">${safe(seo.description)}</p><div class="tags">${tags(seo.hashtags)}</div><p class="publish-copy"><span class="label">GHIM BÌNH LUẬN</span>${safe(seo.pinned_comment)}</p></section><section class="section-card"><div class="section-title">Đăng có trách nhiệm <small>CHECK TRƯỚC KHI POST</small></div><ul class="checklist">${checks}</ul><p class="notice">${safe(money.disclosure)}</p></section></div>
    <section class="section-card production"><div class="section-title">Vì sao hướng này có thể giữ nhịp xem <small>GỢI Ý, KHÔNG PHẢI CAM KẾT</small></div><ul class="checklist">${reasons}</ul><p class="notice">${safe(money.angle)}<br /><br /><b>CTA:</b> ${safe(money.cta)}</p></section>`;
  emptyNode.classList.add("hidden");
  blueprintNode.classList.remove("hidden");
  blueprintNode.scrollIntoView({ behavior: "smooth", block: "start" });
}

function publishPack() {
  const seo = currentBlueprint?.seo || {};
  return [currentBlueprint?.titles?.[0], seo.description, ...(seo.hashtags || []), "", `Bình luận ghim: ${seo.pinned_comment || ""}`].filter(Boolean).join("\n");
}

async function pollJob(jobId) {
  const job = $("#production-job");
  const message = $("#job-message");
  const percent = $("#job-percent");
  const bar = $("#job-bar");
  const result = $("#render-result");
  job.classList.add("show");
  for (;;) {
    const response = await fetch(`/api/jobs/${encodeURIComponent(jobId)}`);
    if (!response.ok) throw new Error("Không đọc được trạng thái render");
    const data = await response.json();
    const progress = Math.max(0, Math.min(100, Number(data.progress || 0)));
    message.textContent = data.message || "Đang dựng video...";
    percent.textContent = `${progress}%`;
    bar.style.width = `${progress}%`;
    if (data.status === "done") {
      const media = data.result || {};
      result.innerHTML = `${media.video_url ? `<video controls src="${safe(media.video_url)}" aria-label="Video Faceless Forge"></video><a class="download" href="${safe(media.video_url)}" download>TẢI VIDEO MP4 ↓</a>` : ""}${media.audio_url ? `<a class="download" href="${safe(media.audio_url)}" download> · TẢI VOICE-OVER MP3 ↓</a>` : ""}`;
      notify("Video faceless đã render xong!");
      return;
    }
    if (data.status === "error") throw new Error(data.error || data.message || "Render thất bại");
    await new Promise((resolve) => setTimeout(resolve, 1800));
  }
}

async function produceVideo(button) {
  if (!currentBlueprint) return;
  button.disabled = true;
  button.textContent = "◌ Đang tạo visual, voice & MP4...";
  try {
    const response = await fetch("/api/forge/produce", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ blueprint: currentBlueprint, voice: "vi-VN-HoaiMyNeural", image_model: "nano-banana", resolution: "1080x1920" }),
    });
    const job = await response.json();
    if (!response.ok) throw new Error(job.detail || "Không thể bắt đầu dựng video");
    await pollJob(job.id);
  } catch (error) {
    notify(error.message || "Dựng video thất bại", true);
  } finally {
    button.disabled = false;
    button.textContent = "✦ Dựng video MP4 tự động";
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const brief = collectBrief();
  if (brief.topic.length < 3) return notify("Hãy nhập chủ đề cụ thể hơn", true);
  blueprintButton.disabled = true;
  blueprintButton.innerHTML = "<span>◌</span> Đang xây blueprint...";
  try {
    const response = await fetch("/api/forge/blueprint", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(brief) });
    const plan = await response.json();
    if (!response.ok) throw new Error(plan.detail || "Không thể tạo blueprint");
    currentBlueprint = plan;
    renderBlueprint(plan);
    notify(plan.fallback ? "Đã tạo khung kế hoạch local" : "Viral Blueprint đã sẵn sàng");
  } catch (error) {
    notify(error.message || "Không thể kết nối Forge", true);
  } finally {
    blueprintButton.disabled = false;
    blueprintButton.innerHTML = "<span>✦</span> Tạo Viral Blueprint";
  }
});

blueprintNode.addEventListener("click", (event) => {
  const target = event.target.closest("button");
  if (!target || !currentBlueprint) return;
  if (target.dataset.copyTitle !== undefined) return copyText(currentBlueprint.titles?.[Number(target.dataset.copyTitle)], "Đã copy title");
  if (target.dataset.copyPrompt !== undefined) return copyText(currentBlueprint.shots?.[Number(target.dataset.copyPrompt)]?.image_prompt, "Đã copy visual prompt");
  if (target.hasAttribute("data-copy-script")) return copyText(currentBlueprint.script, "Đã copy voice-over");
  if (target.hasAttribute("data-copy-publish")) return copyText(publishPack(), "Đã copy gói xuất bản");
  if (target.hasAttribute("data-produce")) return produceVideo(target);
});
