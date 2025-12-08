# ACTASK - Cloud Build/Cloud Run デプロイガイド

このプロジェクトは、バックエンド（FastAPI）とフロント（静的 HTML/CSS/JS）を単一のコンテナで実行し、Google Cloud の Cloud Build と Cloud Run にデプロイするように構成されています。

## プロジェクト構成

```
ACTASK/
├── ACTASK-app/
│   ├── api/                    # バックエンド（FastAPI）
│   │   ├── main.py             # メイン API サーバー
│   │   ├── cranberry.py        # Cranberry OCR API
│   │   ├── requirements.txt    # Python依存関係
│   │   ├── credentials/        # GCP サービスアカウント JSON
│   │   └── Dockerfile          # 個別ビルド用（開発）
│   ├── front/                  # フロント（静的ファイル）
│   │   ├── index.html          # メインページ
│   │   ├── index.css           # スタイル
│   │   └── main.js             # スクリプト
│   ├── cloud-run-config.yaml   # Cloud Run デプロイ設定
│   └── Dockerfile              # 統一ビルド用（本番）
├── cloudbuild.yaml             # Cloud Build 設定
└── .gcloudignore              # Cloud Build で無視するファイル
```

## 準備

### 前提条件

- Google Cloud Platform (GCP) アカウント
- `gcloud` CLI がインストール・設定済み
- GitHub リポジトリが準備済み

### 1. GCP プロジェクト設定

```bash
# プロジェクト ID を設定
export PROJECT_ID="your-gcp-project-id"
gcloud config set project $PROJECT_ID

# 必要な API を有効化
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable containerregistry.googleapis.com

# Cloud Build のサービスアカウントに必要な権限を付与
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member=serviceAccount:$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')@cloudbuild.gserviceaccount.com \
  --role=roles/run.admin

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member=serviceAccount:$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')@cloudbuild.gserviceaccount.com \
  --role=roles/iam.serviceAccountUser
```

### 2. GitHub 連携設定

GitHub リポジトリを Cloud Build に接続：

```bash
gcloud builds connect --repository-name=ACTASK --repository-owner=usuiayaka --region=us-central1
```

### 3. Cloud Build トリガー作成

```bash
gcloud builds triggers create github \
  --repository-name=ACTASK \
  --repository-owner=usuiayaka \
  --branch-pattern="^main$" \
  --build-config=cloudbuild.yaml \
  --region=us-central1 \
  --name="actask-unified-deploy"
```

### 4. GCP Secret Manager でシークレット登録（重要）

GCP 認証情報（サービスアカウント JSON）を Secret Manager に登録：

```bash
# Secret Manager の API を有効化
gcloud services enable secretmanager.googleapis.com

# Secret を作成（GCP サービスアカウント JSON ファイルの内容を使用）
gcloud secrets create gcp-credentials-json \
  --data-file=./ACTASK-app/api/credentials/actask-app-a125d7e12c21.json

# Cloud Run のサービスアカウントに Secret へのアクセス権限を付与
gcloud secrets add-iam-policy-binding gcp-credentials-json \
  --member=serviceAccount:$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')-compute@developer.gserviceaccount.com \
  --role=roles/secretmanager.secretAccessor
```

**注意**: credentials ファイルは `.gcloudignore` で除外されているため、ビルド時に含まれません。  
代わりに Secret Manager から Cloud Run にマウントされます。

## デプロイ手順

### オプション A: Cloud Build で自動デプロイ（推奨）

1. リポジトリに変更をコミット
2. GitHub にプッシュ
3. Cloud Build が自動的にトリガーされ、ビルド → デプロイが実行されます

### オプション B: 手動デプロイ

```bash
# ビルドを手動で開始
gcloud builds submit \
  --config=cloudbuild.yaml \
  --substitutions=_REGION="us-central1",_SERVICE_NAME="actask-unified" \
  .

# または、簡単にビルド・デプロイ
gcloud run deploy actask-unified \
  --source=. \
  --region=us-central1 \
  --platform=managed
```

## サービスアクセス

デプロイ後、Cloud Run が割り当てた URL にアクセス：

```
https://actask-unified-XXXXXX.run.app
```

## API エンドポイント

- **ホーム**: `/` - フロントエンド（HTML）
- **ステータス**: `/status` - サーバー状態確認
- **Cranberry OCR**: `/cranberry/ocr` - 画像 OCR 処理
- **その他**: `/call-cranberry` など

## 環境変数・認証情報

### 設定方法

1. **ローカル開発**:

   - `api/.env` ファイルで環境変数を定義
   - `docker-compose.yml` で読み込み

2. **Cloud Run**:
   - Cloud Run サービスの環境変数セクションで設定
   - Secrets Manager で機密情報を管理（推奨）

例：

```bash
gcloud run services update actask-unified \
  --region=us-central1 \
  --set-env-vars=GOOGLE_APPLICATION_CREDENTIALS=/app/credentials/actask-app-a125d7e12c21.json
```

## トラブルシューティング

### Cloud Build がビルド失敗

- ログを確認: `gcloud builds log <BUILD_ID>`
- Dockerfile のパスを確認
- credentials ファイルが含まれているか確認

### Cloud Run でサービスが起動しない

- Cloud Run のログを確認: `gcloud run services describe actask-unified --region=us-central1`
- メモリ・CPU リソース不足がないか確認

### API へのアクセスが拒否される

- Cloud Run サービスが公開されているか確認
- CORS 設定を確認（FastAPI に CORS ミドルウェアが設定済み）

## ローカルテスト

```bash
# イメージをローカルでビルド
docker build -t actask-unified:latest -f ./ACTASK-app/Dockerfile ./ACTASK-app

# コンテナ起動
docker run -p 8000:8000 \
  -e GOOGLE_APPLICATION_CREDENTIALS=/app/credentials/actask-app-a125d7e12c21.json \
  actask-unified:latest

# ブラウザでアクセス
open http://localhost:8000
```

## 参考リンク

- [Google Cloud Build ドキュメント](https://cloud.google.com/build/docs)
- [Google Cloud Run ドキュメント](https://cloud.google.com/run/docs)
- [FastAPI ドキュメント](https://fastapi.tiangolo.com/)
