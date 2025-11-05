from fastapi import FastAPI, UploadFile, File
import httpx
from cranberry import router as cranberry_router
from fastapi.middleware.cors import CORSMiddleware
import os
import asyncio
from datetime import datetime, timedelta

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

# Cranberry OCR用ルーターを追加
app.include_router(cranberry_router, prefix="/cranberry")

# === Googleカレンダーサービス作成 ===
SCOPES = ['https://www.googleapis.com/auth/calendar']
credentials = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_FILE, scopes=SCOPES)
calendar_service = build('calendar', 'v3', credentials=credentials)

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

# === メイン処理 ===
@app.post("/call-cranberry")
async def call_cranberry(file: UploadFile = File(...)):
    """
    画像を Cranberry OCR API に転送し、OCR結果をLINEとGoogleカレンダーに登録
    """
    # --- OCR呼び出し ---
    async with httpx.AsyncClient() as client:
        try:
            files = {"file": (file.filename, await file.read(), file.content_type)}
            resp = await client.post("http://127.0.0.1:8000/cranberry/ocr", files=files)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            return {"error": "failed to call cranberry", "detail": str(e)}

    # --- OCR結果取得 ---
    ocr_text = data.get("text", "テキストが検出されませんでした")

    # --- Googleカレンダー登録（非同期に変換） ---
    start = datetime.now()
    end = start + timedelta(hours=1)  # デフォルトで1時間イベント
    event = await asyncio.to_thread(add_event_to_calendar, ocr_text, start.isoformat(), end.isoformat())
    print(f"✅ カレンダー登録完了 EventID: {event['id']}")

    # --- LINE送信（作成されたイベントIDも通知） ---
    await send_line_message_to_user(
        f"OCR結果: {ocr_text}\nカレンダー登録: done\nEventID: {event['id']}"
    )

    return {
        "cranberry_response": data,
        "line_status": "sent",
        "calendar_status": "done",
        "event_id": event['id']
    }
