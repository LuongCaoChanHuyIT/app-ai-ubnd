# Bộ Trợ lý AI UBND Xã, Phường — Backend (`ubnd-ai-backend`)

Dịch vụ Backend API phục vụ 7 phân hệ nghiệp vụ UBND cấp xã, phường xây dựng trên **Python 3.12+**, **FastAPI**, **Uvicorn** và **SQLite3**.

## Yêu cầu kiến trúc bắt buộc khi Deploy

1. **Chạy đúng 1 worker (`--workers 1`):** Hệ thống lưu phiên xử lý tài liệu tạm thời trong RAM (`EphemeralSessionStore`) kết hợp SQLite, nên bắt buộc giữ `--workers 1`.
2. **Gắn ổ đĩa bền vững (Persistent Volume):** Gắn volume lưu trữ bền vững vào `/var/lib/ubnd-ai` (chứa `ubnd_ai.db` và `tenants/*.db`) để bảo toàn dữ liệu khi redeploy container.

## Cài đặt & Chạy trực tiếp bằng Python

```bash
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

cp .env.example .env
# Chạy được cả `uvicorn main:app` lẫn `uvicorn backend.main:app`:
UBND_ENV=production \
UBND_DB_PATH=/var/lib/ubnd-ai/ubnd_ai.db \
UBND_ALLOWED_ORIGINS=https://tenmien-frontend.vn \
.venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 1 --proxy-headers
```

## Deploy bằng Docker

```bash
docker build -t ubnd-ai-backend .

docker run -d \
  --name ubnd-ai-backend \
  -p 8000:8000 \
  -v ubnd_ai_data:/var/lib/ubnd-ai \
  -e UBND_ENV=production \
  -e UBND_DB_PATH=/var/lib/ubnd-ai/ubnd_ai.db \
  -e UBND_ALLOWED_ORIGINS=https://tenmien-frontend.vn \
  ubnd-ai-backend
```

## Sao lưu SQLite trực tuyến (Online Backup)

```bash
UBND_DATA_DIR=/var/lib/ubnd-ai UBND_BACKUP_DIR=/var/backups/ubnd-ai bash deploy/scripts/backup-sqlite.sh
```

## Kiểm thử

```bash
.venv/bin/python -m unittest discover -s backend/tests -v
```

