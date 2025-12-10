FROM python:3.11-slim

WORKDIR /app

# 必要なシステムパッケージを追加（tesseract とビルドに必要な依存）
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libsm6 libxext6 libxrender1 \
    build-essential && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Cloud Run は PORT 環境変数を設定する。デフォルト 8080
ENV PORT=8080
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT}
