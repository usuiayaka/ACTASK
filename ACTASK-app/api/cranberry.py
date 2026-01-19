from fastapi import FastAPI, APIRouter, UploadFile, File, Form
from fastapi.responses import JSONResponse
import numpy as np
import cv2
import asyncio
from concurrent.futures import ThreadPoolExecutor
from google.cloud import vision
from googleapiclient.discovery import build
from google.oauth2 import service_account
from typing import Any, Dict, List, Optional
import re
from datetime import datetime, timedelta
import os

router = APIRouter()

# =========================================================
# Cloud Run 対応：
# サービスアカウント認証を使用するため、
# GOOGLE_APPLICATION_CREDENTIALS は不要
# =========================================================
vision_client = vision.ImageAnnotatorClient()

# Google Calendar API のスコープとクライアント初期化
CALENDAR_SCOPES = ['https://www.googleapis.com/auth/calendar']

def get_calendar_service():
    """
    Google Calendar API サービスを取得する。
    credentials/ ディレクトリのサービスアカウントキーを使用。
    """
    cred_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
    if not cred_path:
        # デフォルトのパスを試す
        cred_path = 'credentials/actask-app-40b0576cfbd3.json'
    
    credentials = service_account.Credentials.from_service_account_file(
        cred_path, scopes=CALENDAR_SCOPES)
    
    service = build('calendar', 'v3', credentials=credentials)
    return service


### 新機能：カレンダーマス目の正規化座標 (x_min, y_min, x_max, y_max) を返す関数追加 ===
def get_calendar_mask_coords():
    """
    ピクセル座標を返す (この値は、カメラの解像度が変動しない前提で使用可能)
    """
    coords = [
        # {'day': '', 'box': [0.13, 0.065, 0.86, 0.94]},
        {'day': 'MON', 'box': [0.13, 0.065, 0.21, 0.22], 'schedule': ''},
        {'day': '1', 'box': [0.21, 0.065, 0.3, 0.25], 'schedule': ''},
        {'day': '2', 'box': [0.3, 0.065, 0.39, 0.25], 'schedule': ''},
        {'day': '3', 'box': [0.39, 0.065, 0.47, 0.25], 'schedule': ''},
        {'day': '4', 'box': [0.51, 0.065, 0.597, 0.25], 'schedule': ''},
        {'day': '5', 'box': [0.597, 0.073, 0.68, 0.25], 'schedule': ''},
        {'day': '6', 'box': [0.68, 0.076, 0.767, 0.25], 'schedule': ''},
        {'day': '7', 'box': [0.767, 0.078, 0.86, 0.25], 'schedule': ''},

        {'day': '8', 'box': [0.21, 0.25, 0.302, 0.36], 'schedule': ''},
        {'day': '9', 'box': [0.3, 0.25, 0.39, 0.36], 'schedule': ''},
        {'day': '10', 'box': [0.39, 0.25, 0.47, 0.36], 'schedule': ''},
        {'day': '11', 'box': [0.51, 0.25, 0.6, 0.36], 'schedule': ''},
        {'day': '12', 'box': [0.6, 0.25, 0.685, 0.36], 'schedule': ''},
        {'day': '13', 'box': [0.685, 0.25, 0.77, 0.36], 'schedule': ''},
        {'day': '14', 'box': [0.77, 0.25, 0.86, 0.36], 'schedule': ''},
        
        {'day': '15', 'box': [0.21, 0.36, 0.305, 0.505], 'schedule': ''},
        {'day': '16', 'box': [0.305, 0.36, 0.39, 0.505], 'schedule': ''},
        {'day': '17', 'box': [0.39, 0.36, 0.47, 0.505], 'schedule': ''},
        {'day': '18', 'box': [0.515, 0.36, 0.6, 0.505], 'schedule': ''},
        {'day': '19', 'box': [0.6, 0.36, 0.685, 0.505], 'schedule': ''},
        {'day': '20', 'box': [0.685, 0.36, 0.77, 0.505], 'schedule': ''},


        {'day': '21', 'box': [0.77, 0.36, 0.86, 0.505], 'schedule': ''},

        {'day': '22', 'box': [0.21, 0.505, 0.305, 0.65], 'schedule': ''},
        {'day': '23', 'box': [0.305, 0.505, 0.39, 0.65], 'schedule': ''},
        {'day': '24', 'box': [0.39, 0.505, 0.47, 0.65], 'schedule': ''},
        {'day': '25', 'box': [0.515, 0.505, 0.6, 0.65], 'schedule': ''},
        {'day': '26', 'box': [0.6, 0.505, 0.685, 0.65], 'schedule': ''},
        {'day': '27', 'box': [0.685, 0.505, 0.77, 0.65], 'schedule': ''},
        {'day': '28', 'box': [0.77, 0.505, 0.86, 0.65], 'schedule': ''},

        {'day': '29', 'box': [0.21, 0.65, 0.305, 0.805], 'schedule': ''},
        {'day': '30', 'box': [0.305, 0.65, 0.39, 0.805], 'schedule': ''},
        {'day': '31', 'box': [0.39, 0.65, 0.47, 0.805], 'schedule': ''},
        {'day': '0', 'box': [0.515, 0.65, 0.6, 0.8], 'schedule': ''},
        {'day': '0', 'box': [0.6, 0.65, 0.685, 0.8], 'schedule': ''},
        {'day': '0', 'box': [0.685, 0.65, 0.77, 0.8], 'schedule': ''},
        {'day': '0', 'box': [0.77, 0.65, 0.86, 0.8], 'schedule': ''},

        {'day': '0', 'box': [0.21, 0.8, 0.305, 0.95], 'schedule': ''},
        {'day': '0', 'box': [0.305, 0.8, 0.39, 0.95], 'schedule': ''},
        {'day': '0', 'box': [0.39, 0.8, 0.47, 0.95], 'schedule': ''},
        {'day': '0', 'box': [0.515, 0.8, 0.6, 0.95], 'schedule': ''},
        {'day': '0', 'box': [0.6, 0.8, 0.685, 0.95], 'schedule': ''},
        {'day': '0', 'box': [0.685, 0.8, 0.77, 0.95], 'schedule': ''},


        {'day': '0', 'box': [0.77, 0.8, 0.86, 0.95], 'schedule': ''},
    ]
    return coords


def vision_document_ocr(content: bytes, language_hints: Optional[List[str]] = None) -> str:
    """
    同期処理:
    Google Cloud Vision の document_text_detection で画像からテキスト（手書き対応）を抽出する。
    認証は Cloud Run のサービスアカウントを使用
    """

    image = vision.Image(content=content)
    image_context = None


    if language_hints:
        image_context = vision.ImageContext(language_hints=language_hints)

    response = vision_client.document_text_detection(
        image=image,
        image_context=image_context
    )

    if getattr(response, 'error', None) and getattr(response.error, 'message', None):
        raise RuntimeError(response.error.message)

    if response.full_text_annotation and response.full_text_annotation.text:
        return response.full_text_annotation.text

    texts = response.text_annotations
    if texts:
        return texts[0].description

    return ""


def vision_document_ocr_with_boxes(content: bytes, language_hints: Optional[List[str]] = None):
    """
    document_text_detection の結果から全文テキストと文字ごとのバウンディングボックスを取得する。
    """
    image = vision.Image(content=content)
    image_context = None
    if language_hints:
        image_context = vision.ImageContext(language_hints=language_hints)

    response = vision_client.document_text_detection(
        image=image,
        image_context=image_context
    )

    if getattr(response, 'error', None) and getattr(response.error, 'message', None):
        raise RuntimeError(response.error.message)

    text = ""
    if response.full_text_annotation and response.full_text_annotation.text:
        text = response.full_text_annotation.text
    elif response.text_annotations:
        text = response.text_annotations[0].description

    return text, response.text_annotations


def _center_of_vertices(vertices, img_shape) -> Optional[tuple]:
    """
    頂点配列から正規化された中心座標 (cx, cy) を計算する。
    """
    if not vertices:
        return None
    h, w = img_shape[:2]
    xs = [v.x for v in vertices if v.x is not None]
    ys = [v.y for v in vertices if v.y is not None]
    if not xs or not ys:
        return None
    cx = sum(xs) / len(xs) / w
    cy = sum(ys) / len(ys) / h
    return cx, cy


def _extract_day_token(text: str) -> Optional[str]:
    """
    "1"〜"31" または「1日」〜「31日」を日付トークンとして抽出する。
    """
    m = re.match(r"^(0?[1-9]|[12][0-9]|3[01])(?:日)?$", text)
    if not m:
        return None
    return m.group(1).lstrip("0") or "0"


def _extract_month_token(text: str) -> Optional[int]:
    """
    "1"〜"12" または「1月」〜「12月」を月トークンとして抽出する。
    """
    m = re.match(r"^(0?[1-9]|1[0-2])(?:月)?$", text)
    if not m:
        return None
    return int(m.group(1))


def register_to_google_calendar(cells: List[Dict[str, Any]], year: int = None, calendar_id: str = 'primary') -> Dict[str, Any]:
    """
    OCRで取得したセル情報をGoogleカレンダーに登録する。
    
    Args:
        cells: map_text_to_calendar_cells の結果
        year: 登録する年（省略時は現在の年）
        calendar_id: Googleカレンダーのカレンダー ID（省略時は primary）
    
    Returns:
        登録結果の情報
    """
    if year is None:
        year = datetime.now().year
    
    service = get_calendar_service()
    registered_events = []
    skipped_cells = []
    errors = []
    
    for cell in cells:
        # 月と日が有効で、予定がある場合のみ登録
        month = cell.get('month')
        day = cell.get('day')
        schedule = cell.get('schedule', '').strip()
        
        # 最初のセル（MON）や、day='0'のセル、予定が空のセルはスキップ
        if not month or not day or day == 'MON' or day == '0' or not schedule:
            if schedule:  # 予定があるのにスキップされた場合は記録
                skipped_cells.append({
                    'day': day,
                    'month': month,
                    'schedule': schedule,
                    'reason': 'invalid_date'
                })
            continue
        
        try:
            # 日付を整数に変換
            day_int = int(day)
            if not (1 <= day_int <= 31):
                skipped_cells.append({
                    'day': day,
                    'month': month,
                    'schedule': schedule,
                    'reason': 'invalid_day_range'
                })
                continue
            
            # 日付オブジェクトを作成
            event_date = datetime(year, month, day_int)
            
            # イベントを作成（終日イベントとして登録）
            event = {
                'summary': schedule,
                'start': {
                    'date': event_date.strftime('%Y-%m-%d'),
                    'timeZone': 'Asia/Tokyo',
                },
                'end': {
                    'date': event_date.strftime('%Y-%m-%d'),
                    'timeZone': 'Asia/Tokyo',
                },
                'description': f'ACTASK OCRから自動登録: {year}年{month}月{day}日',
            }
            
            # カレンダーにイベントを登録
            created_event = service.events().insert(
                calendarId=calendar_id,
                body=event
            ).execute()
            
            registered_events.append({
                'date': f'{year}-{month:02d}-{day_int:02d}',
                'schedule': schedule,
                'event_id': created_event.get('id'),
                'link': created_event.get('htmlLink')
            })
            
        except ValueError as e:
            errors.append({
                'day': day,
                'month': month,
                'schedule': schedule,
                'error': f'invalid_date: {str(e)}'
            })
        except Exception as e:
            errors.append({
                'day': day,
                'month': month,
                'schedule': schedule,
                'error': str(e)
            })
    
    return {
        'registered_count': len(registered_events),
        'skipped_count': len(skipped_cells),
        'error_count': len(errors),
        'registered_events': registered_events,
        'skipped_cells': skipped_cells,
        'errors': errors
    }


def map_text_to_calendar_cells(text_annotations, img_shape) -> List[Dict[str, Any]]:
    """
    各セル内に含まれるすべてのテキストを集める。
    最初のセル（index 0）から月の数字を抽出して全セルに適用。
    その後、各セルから日付トークン（1-31）を探して day を設定、
    残りのテキストを schedule にする。
    """
    cells = [dict(day=cell['day'], box=cell['box'], schedule="", month=None, texts=[]) for cell in get_calendar_mask_coords()]

    # text_annotations[0] は全文。個別文字は index 1 以降
    for ann in text_annotations[1:]:
        center = _center_of_vertices(ann.bounding_poly.vertices, img_shape)
        if center is None:
            continue
        cx, cy = center
        piece = ann.description.strip()
        if not piece:
            continue
        
        # 中心がセル内に入るセルに割り当て
        matched = False
        for idx, cell in enumerate(cells):
            x_min, y_min, x_max, y_max = cell['box']
            if x_min <= cx <= x_max and y_min <= cy <= y_max:
                cell['texts'].append(piece)
                print(f"[MAPPING] Text '{piece}' ({cx:.3f}, {cy:.3f}) → Day {cell['day']} (box: {cell['box']})", flush=True)
                matched = True
                break
        
        if not matched:
            print(f"[MAPPING] Text '{piece}' ({cx:.3f}, {cy:.3f}) → NO MATCH (outside all cells)", flush=True)

    # 最初のセル（MON位置）から月を抽出
    detected_month = None
    if cells and cells[0]['texts']:
        for text in cells[0]['texts']:
            month_token = _extract_month_token(text)
            if month_token:
                detected_month = month_token
                break

    # 各セルで日付を探して day を更新、月を設定、残りを schedule に
    for idx, cell in enumerate(cells):
        day_found = False
        schedule_parts = []
        
        # 最初のセルは月なので日付処理をスキップ
        if idx == 0:
            cell['month'] = detected_month
            cell['schedule'] = ""
            del cell['texts']
            continue
        
        for text in cell['texts']:
            day_token = _extract_day_token(text)
            if day_token and not day_found:
                cell['day'] = day_token
                day_found = True
            elif not day_token:
                schedule_parts.append(text)
        
        cell['schedule'] = " ".join(schedule_parts)
        cell['month'] = detected_month
        del cell['texts']

    return cells



@router.get("/info")
async def info():
    return {"service": "cranberry", "version": "0.1"}


# === 新機能: カレンダーマス目座標取得エンドポイント ===
@router.get("/mask_coords")
async def get_mask_coordinates():
    """
    カレンダーの日付マス目の正規化座標（0.0〜1.0）を返す
    """
    return {"coordinates": get_calendar_mask_coords()}


@router.post("/ocr")
async def ocr_image(file: UploadFile = File(...), lang: str = Form('ja')):
    """
    Cloud Vision を使って手書き文字を取得するエンドポイント。
    - file: 画像ファイル（multipart/form-data）
    - lang: 言語ヒント（例: 'ja'）
    """
    try:
        contents = await file.read()

        # 軽い画像検証
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return JSONResponse(status_code=400, content={"error": "invalid image"})

        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor() as pool:
            text = await loop.run_in_executor(
                pool,
                vision_document_ocr,
                contents,
                [lang]
            )

        return {"filename": file.filename, "text": text}

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": "ocr_failed", "detail": str(e)}
        )





@router.post("/ocr_with_cells")
async def ocr_image_with_cells(file: UploadFile = File(...), lang: str = Form('ja')):
    """
    OCR結果の文字をカレンダーの各マスに割り当てて schedule に格納して返す。
    """
    try:
        contents = await file.read()

        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return JSONResponse(status_code=400, content={"error": "invalid image"})

        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor() as pool:
            text, annotations = await loop.run_in_executor(
                pool,
                vision_document_ocr_with_boxes,
                contents,
                [lang]
            )

        cells = map_text_to_calendar_cells(annotations, img.shape)

        return {"filename": file.filename, "text": text, "cells": cells}

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": "ocr_failed", "detail": str(e)}
        )


@router.post("/register_to_calendar")
async def register_ocr_to_calendar(
    file: UploadFile = File(...),
    lang: str = Form('ja'),
    year: int = Form(None),
    calendar_id: str = Form('primary')
):
    """
    OCRで取得した予定をGoogleカレンダーに登録する。
    
    Args:
        file: カレンダー画像
        lang: 言語ヒント（デフォルト: 'ja'）
        year: 登録する年（省略時は現在の年）
        calendar_id: GoogleカレンダーのID（省略時は 'primary'）
    """
    try:
        contents = await file.read()

        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return JSONResponse(status_code=400, content={"error": "invalid image"})

        # OCR処理
        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor() as pool:
            text, annotations = await loop.run_in_executor(
                pool,
                vision_document_ocr_with_boxes,
                contents,
                [lang]
            )

        cells = map_text_to_calendar_cells(annotations, img.shape)

        # Googleカレンダーに登録
        result = await loop.run_in_executor(
            pool,
            register_to_google_calendar,
            cells,
            year,
            calendar_id
        )

        return {
            "filename": file.filename,
            "ocr_text": text,
            "cells": cells,
            "calendar_registration": result
        }

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": "registration_failed", "detail": str(e)}
        )


# Standalone app for testing this module directly
app = FastAPI(title="Cranberry API")
app.include_router(router)
