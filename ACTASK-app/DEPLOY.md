# Cloud Run デプロイガイド

このドキュメントでは、ACTASK アプリを Google Cloud Run にデプロイする手順を説明します。

## 必要な準備

1. **Google Cloud プロジェクトの作成**

   - [Google Cloud Console](https://console.cloud.google.com) にアクセス
   - 新規プロジェクトを作成

2. **必要な API を有効化**

   ```bash
   gcloud services enable \
     cloudbuild.googleapis.com \
     run.googleapis.com \
     containerregistry.googleapis.com \
     calendar-json.googleapis.com
   ```

3. **Google Cloud SDK のインストール**

   - [gcloud CLI をインストール](https://cloud.google.com/sdk/docs/install)

4. **認証情報の設定**
   - `api/credentials/actask-app-40b0576cfbd3.json` が存在することを確認

## デプロイ手順

### 方法 1：gcloud run deploy（推奨・最も簡単）

```bash
# プロジェクト ID を設定
export PROJECT_ID="your-project-id"
export SERVICE_NAME="actask-app"
export REGION="asia-northeast1"

# ACTASK-app ディレクトリから実行
cd ACTASK-app

# ビルドしてデプロイ
gcloud run deploy $SERVICE_NAME \
  --source . \
  --region $REGION \
  --platform managed \
  --allow-unauthenticated \
  --port 8080 \
  --timeout 3600 \
  --memory 2Gi \
  --cpu 2 \
  --set-env-vars="GOOGLE_APPLICATION_CREDENTIALS=/app/credentials/actask-app-40b0576cfbd3.json" \
  --project $PROJECT_ID
```

### 方法 2：Cloud Build を使用（CI/CD パイプライン用）

```bash
# ACTASK-app ディレクトリから実行
cd ACTASK-app

# Cloud Build でビルドしてデプロイ
gcloud builds submit . \
  --config cloudbuild.yaml \
  --project $PROJECT_ID
```

このコマンドは以下を実行します：

1. Dockerfile をビルド
2. Container Registry にプッシュ
3. Cloud Run にデプロイ

## Dockerfile について

- **ポート**: `8080` にバインド（Cloud Run の要件）
- **フロント**: デプロイ時に `front/` から `api/static/` にコピーされます
- **スタティックファイル**: `/static` パスで配信されます

## API エンドポイント

デプロイ後のエンドポイント:

- **ルート（フロント）**: `https://<SERVICE_NAME>-<RANDOM>.a.run.app/`
- **API ベース**: `https://<SERVICE_NAME>-<RANDOM>.a.run.app/api/`
- **Cranberry OCR**: `POST https://<SERVICE_NAME>-<RANDOM>.a.run.app/api/call-cranberry`
- **座標取得**: `GET https://<SERVICE_NAME>-<RANDOM>.a.run.app/api/cranberry/mask_coords`

## 環境変数の設定

Cloud Run のサービスの「環境変数」タブで以下を設定してください：

- `LINE_CHANNEL_ACCESS_TOKEN`: LINE Messaging API のアクセストークン
- `LINE_USER_ID`: LINE ユーザー ID
- `GOOGLE_APPLICATION_CREDENTIALS`: `/app/credentials/actask-app-40b0576cfbd3.json`

## トラブルシューティング

### ビルドエラー

```bash
# Cloud Build のログを確認
gcloud builds log --stream
```

### デプロイエラー

```bash
# Cloud Run のログを確認
gcloud run logs read $SERVICE_NAME --region $REGION --limit 50
```

### ローカルでテスト

```bash
# Docker でローカルテスト
docker build -t actask-app:latest -f api/Dockerfile .
docker run -p 8080:8080 \
  -e GOOGLE_APPLICATION_CREDENTIALS=/app/credentials/actask-app-40b0576cfbd3.json \
  actask-app:latest
```

ブラウザで http://localhost:8080 にアクセスしてテストできます。

## ファイル構成

```
ACTASK-app/
├── api/
│   ├── main.py              # メイン FastAPI アプリケーション
│   ├── cranberry.py         # OCR ロジック
│   ├── requirements.txt      # Python 依存関係
│   ├── Dockerfile           # Docker イメージ定義
│   ├── credentials/         # Google Cloud 認証情報
│   └── static/              # ビルド時にフロント側ファイルがコピー
├── front/
│   ├── index.html           # メインページ
│   ├── index.css            # スタイル
│   └── main.js              # フロントエンドロジック
├── cloudbuild.yaml          # Cloud Build 設定（推奨）
└── .gcloudignore            # Cloud デプロイ時の除外ファイル
```

## 重要な注意事項

1. **認証情報**: `credentials/` ディレクトリの JSON ファイルは安全に管理してください
2. **CORS**: 現在、すべてのオリジンから CORS リクエストを許可しています。本番環境では制限してください
3. **ポート**: Cloud Run は `8080` ポートをリッスンします
4. **メモリ/CPU**: デプロイ時に `--memory 2Gi --cpu 2` を指定しています。必要に応じて調整してください

## 参考資料

- [Cloud Run ドキュメント](https://cloud.google.com/run/docs)
- [Cloud Build ドキュメント](https://cloud.google.com/build/docs)
- [FastAPI デプロイガイド](https://fastapi.tiangolo.com/deployment/)
