ビルドと実行例（PowerShell）

# イメージをビルド

docker build -t actask-api .

# コンテナを起動（ポート 8000 を公開）

docker run -p 8000:8000 --rm --name actask-api actask-api

# ブラウザで確認

# http://localhost:8000/status

# http://localhost:8000/cranberry/info

# http://localhost:8000/call-cranberry
