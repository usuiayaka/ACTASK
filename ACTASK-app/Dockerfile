# 統一 Dockerfile: バックエンド（FastAPI）+ フロント（静的ファイル）をサーバーする
# Cloud Build / Cloud Run でデプロイ可能

FROM python:3.11-slim

WORKDIR /app

# === システムパッケージ ===
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libsm6 libxext6 libxrender1 \
    build-essential && \
    rm -rf /var/lib/apt/lists/*

# === Python依存関係 ===
COPY ./api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# === バックエンドコード ===
COPY ./api/main.py .
COPY ./api/cranberry.py .

# === credentials フォルダ（Cloud Run/ローカルで環境変数で指定） ===
# NOTE: credentials は .gcloudignore で除外されているため、
#       ビルド時にはコピーしない。
#       - Cloud Run: Secret Manager から /app/credentials に注入
#       - ローカル: docker-compose.yml でボリュームマウント

# === フロントエンド（静的ファイル）===
# フロント側の static ファイルをコンテナ内の front/ ディレクトリにコピー
# main.py で StaticFiles を使用して /app/front から提供するように設定
COPY ./front ./front

# === ヘルスチェック ===
# ヘルスチェックではコンテナ内の環境変数 PORT を参照して /status を叩く
# Docker の HEALTHCHECK はシェルが使えるため、python 内で環境変数を参照する方式にします
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=5 \
    CMD python -c "import os, urllib.request; port=os.environ.get('PORT','8080'); urllib.request.urlopen(f'http://localhost:{port}/status')" || exit 1

# === ポート公開 ===
EXPOSE 8000

# === デフォルト環境変数 ===
# Cloud Run では Secret Manager から /app/credentials/xxxxx.json がマウントされる
# ローカル開発では docker-compose.yml でボリュームマウント
ENV GOOGLE_APPLICATION_CREDENTIALS=/app/credentials/actask-app-a125d7e12c21.json

# === サーバー起動 ===
# Cloud Run は実行時に環境変数 PORT をセットします。exec 形式だとシェル展開されない
# ため sh -c を使って展開するか、エントリポイントスクリプトを使います。ここでは sh -c を使用します。
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]

