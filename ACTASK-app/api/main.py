from fastapi import FastAPI, UploadFile, File
import httpx
from cranberry import router as cranberry_router
from cranberry import vision_document_ocr   # ★ 追加（関数直接呼び出し）
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
from google.auth import default   # ★ 追加（Cloud Run 自動認証）

# === 環境変数読み込み ===
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_USER_ID = os.getenv("LINE_USER_ID")
GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID")

# カレンダーIDが未設定ならデフォルト値を入れて通知
if not GOOGLE_CALENDAR_ID:
    GOOGLE_CALENDAR_ID = "ususirosaika2@gmail.com"
    print("ℹ️ GOOGLE_CALENDAR_ID auto-set to default ususirosaika2@gmail.com")

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
    credentials, _ = default(scopes=SCOPES)
    calendar_service = build('calendar', 'v3', credentials=credentials)
    print("✅ Google Calendar service initialized (Cloud Run auth)")
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
    created_event = calendar_service.events().insert(
        calendarId=GOOGLE_CALENDAR_ID,
        body=event
    ).execute()
    return created_event

# === 日時抽出関数 (追加) ===
def parse_datetime_from_ocr(text: str):
    """OCRテキストからパターンを抽出"""
    """パターン1: スラッシュ区切り + 終了時刻あり (例: 2026/2/12 17:00~18:00)"""
    pattern1 = re.compile(
        r'(\d{4})[/／](\d{1,2})[/／](\d{1,2})\s+(\d{1,2}):(\d{2})\s*[~〜～-]\s*(\d{1,2}):(\d{2})'
    )
    match = pattern1.search(text)
    if match:
        year, month, day, start_hour, start_minute, end_hour, end_minute = map(int, match.groups())
        start_dt = datetime(year, month, day, start_hour, start_minute)
        end_dt = datetime(year, month, day, end_hour, end_minute)
        summary = pattern1.sub('', text).strip()
        return summary, start_dt.isoformat(), end_dt.isoformat()

    """パターン2: スラッシュ区切り + 開始時刻のみ (例: 2026/2/12 17:00)"""
    pattern2 = re.compile(
        r'(\d{4})[/／](\d{1,2})[/／](\d{1,2})\s+(\d{1,2}):(\d{2})'
    )
    match = pattern2.search(text)
    if match:
        year, month, day, start_hour, start_minute = map(int, match.groups())
        start_dt = datetime(year, month, day, start_hour, start_minute)
        end_dt = start_dt + timedelta(hours=1)
        summary = pattern2.sub('', text).strip()
        return summary, start_dt.isoformat(), end_dt.isoformat()

    """パターン3: 漢字区切り (例: 2026年2月12日 17:00~18:00)"""
    pattern3 = re.compile(
        r'(\d{4})年(\d{1,2})月(\d{1,2})日\s*(\d{1,2}):(\d{2})\s*[~〜-]\s*(\d{1,2}):(\d{2})'
    )
    match = pattern3.search(text)
    if match:
        year, month, day, start_hour, start_minute, end_hour, end_minute = map(int, match.groups())
        start_dt = datetime(year, month, day, start_hour, start_minute)
        end_dt = datetime(year, month, day, end_hour, end_minute)
        summary = pattern3.sub('', text).strip()
        return summary, start_dt.isoformat(), end_dt.isoformat()

    # マッチしない場合は現在時刻を使用
    start = datetime.now()
    end = start + timedelta(hours=1)
    return text.strip(), start.isoformat(), end.isoformat()

# === メイン処理 ===
@app.post("/api/call-cranberry")
async def call_cranberry(file: UploadFile = File(...)):
    """
    画像を Cranberry OCR API に転送し、OCR結果をLINEとGoogleカレンダーに登録
    """
    try:
        image_bytes = await file.read()
        ocr_text = await asyncio.to_thread(
            vision_document_ocr,
            image_bytes
        )
    except Exception as e:
        return {
            "error": "failed to execute cranberry OCR",
            "detail": str(e)
        }

    summary, start_time_str, end_time_str = parse_datetime_from_ocr(ocr_text)

    cal_status = "pending"
    cal_error = None
    event_id = None

    if not calendar_service:
        cal_status = "skipped (Calendar service not initialized)"
        cal_error = "calendar_service_not_initialized"
    elif not GOOGLE_CALENDAR_ID:
        cal_status = "skipped (Calendar ID not configured)"
        cal_error = "calendar_id_missing"
    else:
        try:
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
            cal_status = "failed"
            cal_error = str(e)
            print(f"❌ カレンダー登録失敗: {e}")

    # # --- LINE送信（作成されたイベントIDも通知） ---
    # if event_id:
    #     await send_line_message_to_user(
    #         f"OCR結果: {ocr_text}\nカレンダー登録: {cal_status}\nEventID: {event_id}"
    #     )
    # else:
    #     await send_line_message_to_user(
    #         f"OCR結果: {ocr_text}\nカレンダー登録: {cal_status}"
    #     )

    return {
        "cranberry_ocr_text": ocr_text,
        "parsed_summary": summary,
        "start_time": start_time_str,
        "end_time": end_time_str,
        "calendar_status": cal_status,
        "calendar_error": cal_error,
        "event_id": event_id
    }
