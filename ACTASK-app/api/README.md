ビルドと実行例（PowerShell）

# イメージをビルド

docker build -t actask-api .

# コンテナを起動（ポート 8000 を公開）

docker run -p 8000:8000 --rm --name actask-api actask-api

# ブラウザで確認

# http://localhost:8000/status

# http://localhost:8000/cranberry/info

# http://localhost:8000/call-cranberry

# ビルド／起動:

# cd "C:\Users\ayaka\Desktop\授業用ファイル\卒業制作\ACTASK\ACTASK-app\api"

# docker compose up -d --build

# コンテナ状態／ログ確認:

# docker compose ps

# docker compose logs -f --tail 200

# API（ルート）と静的ファイル確認

# curl http://127.0.0.1:8000/

# curl http://127.0.0.1:8000/static/index.css

# コンテナ内でファイルを確認（必要な場合）

# docker compose exec app ls -la /app/static

# docker compose exec app cat /app/static/index.css

# ブラウザで開く（ローカル）

# start http://localhost:8000/
