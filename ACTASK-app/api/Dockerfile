FROM python:3.11-slim

WORKDIR /app

# 必要なシステムパッケージを追加（tesseract とビルドに必要な依存）
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libsm6 libxext6 libxrender1 \
    build-essential && \
    rm -rf /var/lib/apt/lists/*

<<<<<<< HEAD
# API側のファイルをコピー
<<<<<<< HEAD
=======
# credentials フォルダを明示的にコピー
COPY api/credentials/ /app/credentials/
>>>>>>> parent of f847e7c (Dockerファイルを修正)
=======
# API側の requirements をコピーしてインストール
>>>>>>> f847e7c9f7eb1ed3dab3f0f6a9f0589bf230e51f
COPY api/requirements.txt /app/
RUN pip install --no-cache-dir -r /app/requirements.txt

# API側のコードをコピー
COPY api/ /app/

# credentials フォルダを明示的にコピー（.dockerignore で除外される場合の対策）
COPY api/credentials/ /app/credentials/

# フロント側のファイルを static ディレクトリにコピー
COPY front/ /app/static/

# ポート設定（Cloud Run の要件）
ENV PORT=8080
EXPOSE 8080

# Uvicorn を使って main.app を起動
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
