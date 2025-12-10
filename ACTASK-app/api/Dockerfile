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

# API側のファイルをコピー
COPY . .

# フロント側のファイルを static ディレクトリにコピー
COPY ../front /app/static

# ポート設定（Cloud Run の要件）
ENV PORT=8080
EXPOSE 8080

# Uvicorn を使って main.app を起動
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
