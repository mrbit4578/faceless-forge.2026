# Đưa Faceless Forge chạy online

## Nguyên nhân lỗi hiện tại

- GitHub Pages đã xuất bản gốc repository, vì thế nó hiển thị `README.md` thay vì `faceless_web/index.html`.
- Vercel không biết thư mục output là `faceless_web`, vì thế URL deployment trả `404: NOT_FOUND`.
- AI, Edge TTS, FFmpeg render MP4 và background jobs MongoDB không chạy được bằng static hosting. Chúng cần service backend Docker chạy liên tục.

Commit này thêm workflow GitHub Pages và `vercel.json`, nên sau khi deploy lại cả hai URL sẽ hiển thị đúng giao diện. Để các nút tạo blueprint, audio và MP4 hoạt động đầy đủ, hoàn tất backend Render/Railway bên dưới.

## 1. GitHub Pages — phục vụ giao diện

1. Vào repository **Settings → Pages**.
2. Ở **Build and deployment → Source**, chọn **GitHub Actions**.
3. Vào tab **Actions** và chờ workflow `Deploy static interface to GitHub Pages` hoàn tất.
4. Mở `https://mrbit4578.github.io/faceless-forge.2026/`.

## 2. Vercel — phục vụ giao diện

1. Vercel Dashboard → project `faceless-forge-2026` → **Settings → General**.
2. Đặt **Root Directory** là `.` và **Framework Preset** là `Other`.
3. Xóa mọi Output Directory override trong dashboard; repo đã có `vercel.json` đặt output là `faceless_web`.
4. Redeploy từ nhánh `main`.

Vercel sẽ hết 404 và hiển thị giao diện. Nó không phù hợp để chạy render video dài hạn.

## 3. Render hoặc Railway — bản đầy đủ có AI/TTS/render MP4

1. Tạo MongoDB Atlas cluster và copy connection string.
2. Render Dashboard → **New → Blueprint** → kết nối repo `mrbit4578/faceless-forge.2026` → chọn `render.yaml`.
3. Thêm Environment Variables:
   - `MONGO_URL`: Atlas connection string
   - `EMERGENT_LLM_KEY`: khoá AI của bạn
   - `DB_NAME`: `faceless_forge`
   - `CORS_ORIGINS`: URL frontend của bạn (hoặc `*` trong giai đoạn thử nghiệm)
4. Deploy Docker service. Bản đầy đủ phục vụ UI/API cùng một domain, vì vậy hãy dùng URL Render/Railway làm URL chính của công cụ.

Không đưa `MONGO_URL`, `EMERGENT_LLM_KEY` hoặc PAT GitHub vào source code/repository.
