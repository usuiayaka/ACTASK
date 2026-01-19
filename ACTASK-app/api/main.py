from fastapi import FastAPI, UploadFile, File
import httpx
from cranberry import router as cranberry_router
from cranberry import (
    vision_document_ocr,
    vision_document_ocr_with_boxes,
    map_text_to_calendar_cells,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
import asyncio
from datetime import datetime, timedelta
import re
from pathlib import Path
import cv2
import numpy as np
import sys

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
        # 画像をデコードしてサイズを取得（マス当て込みに使用）
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return {"error": "invalid image"}

        # OCR全文＋文字ボックスを取得
        ocr_text, annotations = await asyncio.to_thread(
            vision_document_ocr_with_boxes,
            image_bytes
        )

        # デバッグ：画像サイズと正規化座標情報を出力
        print(f"\n[IMAGE INFO] Image shape: {img.shape} (H x W x C)", flush=True)
        h, w = img.shape[:2]
        
        # OCR結果の生座標をコンソールに表示
        print("\n=== RAW OCR COORDINATES (with normalized) ===", flush=True)
        for i, annotation in enumerate(annotations):
            vertices = [(v.x, v.y) for v in annotation.bounding_poly.vertices]
            # 中心座標を計算
            if annotation.bounding_poly.vertices:
                xs = [v.x for v in annotation.bounding_poly.vertices if v.x is not None]
                ys = [v.y for v in annotation.bounding_poly.vertices if v.y is not None]
                if xs and ys:
                    cx_pixel = sum(xs) / len(xs)
                    cy_pixel = sum(ys) / len(ys)
                    cx_norm = cx_pixel / w
                    cy_norm = cy_pixel / h
                    print(f"[{i}] Text: '{annotation.description}' | Pixel: {vertices} | Center (px): ({cx_pixel:.1f}, {cy_pixel:.1f}) | Center (norm): ({cx_norm:.3f}, {cy_norm:.3f})", flush=True)
        
        sys.stdout.flush()

        # 文字を各マスの schedule に割い当て
        cells = map_text_to_calendar_cells(annotations, img.shape)
        
        # マッピング後の座標情報を表示
        print("\n=== MAPPED TO CALENDAR CELLS ===", flush=True)
        for cell in cells:
            day = cell.get('day', '?')
            box = cell.get('box', [])
            schedule = cell.get('schedule', '')
            if schedule:  # スケジュールがある場合のみ表示
                print(f"Day: {day} | Box (norm): {box} | Schedule: '{schedule}'", flush=True)
        sys.stdout.flush()
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
        "event_id": event_id,
        "cells": cells
    }

# === カレンダー一括登録エンドポイント ===
@app.post("/api/register-schedules")
async def register_schedules_to_calendar(cells: list):
    """
    cells 配列を受け取り、各予定をGoogleカレンダーに登録する
    cells = [
        {day: '1', schedule: '買い物をする', month: 1},
        {day: '5', schedule: ': 00-21 : 00 索', month: 1},
        ...
    ]
    """
    if not calendar_service:
        return {
            "status": "error",
            "message": "Calendar service not initialized"
        }
    
    if not GOOGLE_CALENDAR_ID:
        return {
            "status": "error",
            "message": "Calendar ID not configured"
        }
    
    registered_events = []
    failed_events = []
    
    for cell in cells:
        day = cell.get('day', '')
        schedule = cell.get('schedule', '').strip()
        month = cell.get('month', 1)
        
        # スケジュールが空または曜日の場合はスキップ
        if not schedule or day in ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']:
            continue
        
        # 日付が数字でない場合はスキップ
        try:
            day_int = int(day)
        except (ValueError, TypeError):
            continue
        
        # デフォルトの年は2026年
        year = 2026
        
        # 日付を構築
        try:
            # 開始日時・終了日時を設定（終日イベントとして登録）
            start_date = datetime(year, month, day_int)
            end_date = start_date + timedelta(days=1)
            
            # Googleカレンダーに登録
            event = {
                'summary': schedule,
                'start': {'date': start_date.strftime('%Y-%m-%d'), 'timeZone': 'Asia/Tokyo'},
                'end': {'date': end_date.strftime('%Y-%m-%d'), 'timeZone': 'Asia/Tokyo'},
            }
            
            created_event = await asyncio.to_thread(
                lambda: calendar_service.events().insert(
                    calendarId=GOOGLE_CALENDAR_ID,
                    body=event
                ).execute()
            )
            
            registered_events.append({
                'date': f"{year}-{month}-{day_int}",
                'schedule': schedule,
                'event_id': created_event['id']
            })
            
            print(f"✅ カレンダー登録: {year}/{month}/{day_int} - {schedule}")
            
        except Exception as e:
            failed_events.append({
                'date': f"{year}-{month}-{day_int}",
                'schedule': schedule,
                'error': str(e)
            })
            print(f"❌ カレンダー登録失敗: {year}/{month}/{day_int} - {schedule}: {e}")
    
    return {
        "status": "completed",
        "registered": len(registered_events),
        "failed": len(failed_events),
        "registered_events": registered_events,
        "failed_events": failed_events
    }
