from fastapi import FastAPI, UploadFile, File
import httpx
from cranberry import router as cranberry_router
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
import asyncio
from datetime import datetime, timedelta
import re
from pathlib import Path

# Google Calendar
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials

# === 環境変数読み込み ===
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_USER_ID = os.getenv("LINE_USER_ID")
GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")  # Dockerマウント済みJSON

# === FastAPI設定 ===
app = FastAPI(title="ACTASK Main API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cranberry OCR用ルーターを追加（/api プレフィックス付き）
app.include_router(cranberry_router, prefix="/api/cranberry")

# === 静的ファイルの配信設定 ===
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# === ルートエンドポイント（フロント index.html を返す） ===
@app.get("/")
async def root():
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "ACTASK API Server is running"}

# === Googleカレンダーサービス作成 ===
SCOPES = ['https://www.googleapis.com/auth/calendar']
calendar_service = None

try:
    if GOOGLE_CREDENTIALS_FILE and os.path.exists(GOOGLE_CREDENTIALS_FILE):
        credentials = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_FILE, scopes=SCOPES)
        calendar_service = build('calendar', 'v3', credentials=credentials)
    else:
        print("⚠️ Google Calendar credentials file not found or not configured")
except Exception as e:
    print(f"⚠️ Failed to initialize Google Calendar service: {e}")
    calendar_service = None

# === LINE送信関数 ===
# async def send_line_message_to_user(message: str):
#     """LINE公式アカウント（Messaging API）でユーザーにメッセージ送信"""
#     url = "https://api.line.me/v2/bot/message/push"
#     headers = {
#         "Content-Type": "application/json",
#         "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
#     }
#     data = {
#         "to": LINE_USER_ID,
#         "messages": [{"type": "text", "text": message}],
#     }

#     async with httpx.AsyncClient() as client:
#         resp = await client.post(url, headers=headers, json=data)
#         if resp.status_code != 200:
#             print("❌ LINE送信失敗:", resp.text)
#         else:
#             print("✅ LINE送信成功")

# === Googleカレンダー登録関数 ===
def add_event_to_calendar(summary: str, start_time: str, end_time: str):
    """
    同期関数。FastAPI の async 内で呼ぶ場合は asyncio.to_thread を使用。
    """
    event = {
        'summary': summary,
        'start': {'dateTime': start_time, 'timeZone': 'Asia/Tokyo'},
        'end': {'dateTime': end_time, 'timeZone': 'Asia/Tokyo'},
    }
    created_event = calendar_service.events().insert(calendarId='ususirosaika2@gmail.com', body=event).execute()
    return created_event

# === 日時抽出関数 (追加) ===
def parse_datetime_from_ocr(text: str):
    """OCRテキストから「年/月/日 時刻〜時刻」のパターンを抽出"""
    # 例: 2025年11月3日 12:00~13:00
    pattern = re.compile(
        r'(\d{4})年(\d{1,2})月(\d{1,2})日\s*(\d{1,2}):(\d{2})[~〜-](\d{1,2}):(\d{2})'
    )
    match = pattern.search(text)

    if match:
        year, month, day, start_hour, start_minute, end_hour, end_minute = map(int, match.groups())

        # 開始日時を生成 (ISO 8601形式の文字列)
        start_dt = datetime(year, month, day, start_hour, start_minute)
        start_time_str = start_dt.isoformat()

        # 終了日時を生成
        end_dt = datetime(year, month, day, end_hour, end_minute)
        end_time_str = end_dt.isoformat()

        # 日付と時刻の文字列を削除し、残りを予定のサマリーとする
        summary = pattern.sub('', text).strip()
        
        return summary, start_time_str, end_time_str
    
    # パターンが見つからない場合、デフォルト値（現在時刻から1時間）を返す
    start = datetime.now()
    end = start + timedelta(hours=1)
    return text.strip(), start.isoformat(), end.isoformat()

# === メイン処理 ===
@app.post("/api/call-cranberry")
async def call_cranberry(file: UploadFile = File(...)):
    """
    画像を Cranberry OCR API に転送し、OCR結果をLINEとGoogleカレンダーに登録
    """
    # --- OCR呼び出し ---
    # ocr_text = "テキストが検出されませんでした"
    # async with httpx.AsyncClient() as client:
    #     try:
    #         # 実際のファイル転送にはawait file.read()が必要です
    #         files = {"file": (file.filename, await file.read(), file.content_type)}
    #         # 外部OCRサービスのURL（ご自身の環境に合わせてください）
    #         resp = await client.post("http://127.0.0.1:8000/cranberry/ocr", files=files)
    #         resp.raise_for_status()
    #         data = resp.json()
    #         ocr_text = data.get("text", "テキストが検出されませんでした")
    #     except Exception as e:
    #         # OCRサービスへの接続/実行失敗
    #         return {"error": "failed to call cranberry OCR service", "detail": str(e)}

    # --- 日時と予定の抽出 ---
    # 外部で定義された parse_datetime_from_ocr を呼び出す
    summary, start_time_str, end_time_str = parse_datetime_from_ocr(ocr_text)

    # --- Googleカレンダー登録（非同期に変換し、エラーを捕捉） ---
    cal_status = "pending"
    event_id = None
    
    # 外部で定義された calendar_service が正しく初期化されているか確認
    if calendar_service:
        try:
            # 同期処理であるadd_event_to_calendarをasyncio.to_threadで別スレッドで実行
            event = await asyncio.to_thread(
                add_event_to_calendar, 
                summary, 
                start_time_str, 
                end_time_str
            )
            print(f"✅ カレンダー登録完了 Summary: '{summary}', EventID: {event['id']}")
            cal_status = "done"
            event_id = event['id']
        except Exception as e:
            # APIエラー（権限不足など）や実行時エラー
            cal_status = "failed"
            print(f"❌ カレンダー登録失敗: {e}")
            # エラーが発生したことをクライアントに詳細に返す
            return {
                "error": "Calendar registration failed (API/Permission Error)", 
                "detail": str(e),
                "ocr_summary": summary,
                "start_time": start_time_str,
            }
    else:
        # サーバー起動時にカレンダー認証が失敗していた場合
        cal_status = "skipped (Calendar service not initialized)"

    # # --- LINE送信（作成されたイベントIDも通知） ---
    # await send_line_message_to_user(
    #     f"OCR結果: {ocr_text}\nカレンダー登録: done\nEventID: {event['id']}"
    # )

    # return {
    #     "cranberry_ocr_text": ocr_text,
    #     "parsed_summary": summary,
    #     "start_time": start_time_str,
    #     "end_time": end_time_str,
    #     "calendar_status": cal_status,
    #     "event_id": event_id
    # }
