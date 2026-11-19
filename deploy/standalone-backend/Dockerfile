FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UBND_ENV=production \
    UBND_DB_PATH=/var/lib/ubnd-ai/ubnd_ai.db \
    PORT=8000

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt

COPY main.py /app/main.py
COPY backend /app/backend
COPY deploy /app/deploy

RUN mkdir -p /var/lib/ubnd-ai/tenants

EXPOSE 8000

# Mandatory --workers 1 so EphemeralSessionStore RAM & SQLite write locks stay consistent
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --proxy-headers"]

