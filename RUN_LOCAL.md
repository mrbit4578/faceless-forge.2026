# Chạy Faceless Forge trên máy Windows

Bạn phải chạy tại thư mục chứa `Dockerfile`, tức là thư mục `release` trong workspace hiện tại — không phải thư mục cha có các file zip cũ.

```powershell
cd E:\AI\Grok-V1\faceless-forge\release
.\start-local.ps1
```

Lần chạy đầu script sẽ tạo `backend\.env` từ `.env.example` và dừng lại. Mở `backend\.env`, điền giá trị thật cho:

```dotenv
EMERGENT_LLM_KEY=...
MONGO_URL=...
DB_NAME=faceless_forge
```

Sau đó chạy lại:

```powershell
.\start-local.ps1
```

Mở [http://127.0.0.1:8001](http://127.0.0.1:8001). Entry point của bản nhiều cảnh là `forge_premium_app:app`; script đã chọn sẵn entry point này.

Nếu muốn thao tác thủ công, dùng đúng các lệnh sau:

```powershell
cd E:\AI\Grok-V1\faceless-forge\release
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\backend\requirements.production.txt
Copy-Item .\.env.example .\backend\.env
# điền EMERGENT_LLM_KEY và MONGO_URL trong backend\.env
cd .\backend
..\.venv\Scripts\python.exe -m uvicorn forge_premium_app:app --host 0.0.0.0 --port 8001
```

MongoDB phải đang truy cập được trước khi bắt đầu render vì hệ thống dùng nó để theo dõi job dựng video. Cài FFmpeg và thêm vào `PATH` nếu máy chưa có; Dockerfile production đã tự cài FFmpeg.
