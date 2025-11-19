from fastapi import FastAPI, APIRouter, UploadFile, File, Form
from fastapi.responses import JSONResponse
import numpy as np
import cv2
import asyncio
from concurrent.futures import ThreadPoolExecutor
from google.cloud import vision
from typing import Optional, List

router = APIRouter()

###新機能：カレンダーマス目の正規化座標 (x_min, y_min, x_max, y_max) を返す関数追加 ===
# 便宜上、31個のダミー座標を定義します。
def get_calendar_mask_coords():
    """
    正規化されたカレンダーのマス目の座標データ (0.0 - 1.0) を生成する。
    ここでは便宜上、サンプルとして31個の座標を定義する。
    """
    coords = [
    # --- 1行目 (Day 1 - 7) ---
    # 画像の左端からカレンダーが始まると仮定し、最初の列をDay 1 (番号なし) と見なし、Day 2からスタート
    # y座標の調整: 1行目の上端を0.03、下端を0.19に設定し、1マスあたりy方向に約0.16の高さ、x方向に約0.113の幅とする。
    {'day': 0, 'box': [0.143, 0.03, 0.256, 0.19]}, # 2列目
    {'day': 0, 'box': [0.256, 0.03, 0.369, 0.19]}, # 3列目
    {'day': 0, 'box': [0.369, 0.03, 0.482, 0.19]}, # 4列目
    {'day': 1, 'box': [0.482, 0.03, 0.595, 0.19]}, # 5列目
    {'day': 2, 'box': [0.595, 0.03, 0.708, 0.19]}, # 6列目
    {'day': 3, 'box': [0.708, 0.03, 0.821, 0.19]}, # 7列目
    {'day': 4, 'box': [0.821, 0.03, 0.934, 0.19]}, # 8列目 (本来はカレンダーの日付ではない、または8列目は存在しない)

    # --- 2行目 (Day 9 - 16) ---
    # y座標: 0.19から0.35
    {'day': 5, 'box': [0.143, 0.19, 0.256, 0.35]},
    {'day': 6, 'box': [0.256, 0.19, 0.369, 0.35]},
    {'day': 7, 'box': [0.369, 0.19, 0.482, 0.35]},
    {'day': 8, 'box': [0.482, 0.19, 0.595, 0.35]},
    {'day': 9, 'box': [0.595, 0.19, 0.708, 0.35]},
    {'day': 10, 'box': [0.708, 0.19, 0.821, 0.35]},
    {'day': 11, 'box': [0.821, 0.19, 0.934, 0.35]},

    # --- 3行目 (Day 17 - 24) ---
    # y座標: 0.35から0.51
    {'day': 12, 'box': [0.143, 0.35, 0.256, 0.51]},
    {'day': 13, 'box': [0.256, 0.35, 0.369, 0.51]},
    {'day': 14, 'box': [0.369, 0.35, 0.482, 0.51]},
    {'day': 15, 'box': [0.482, 0.35, 0.595, 0.51]},
    {'day': 16, 'box': [0.595, 0.35, 0.708, 0.51]},
    {'day': 17, 'box': [0.708, 0.35, 0.821, 0.51]},
    {'day': 18, 'box': [0.821, 0.35, 0.934, 0.51]},

    # --- 4行目 (Day 25 - 32) ---
    # y座標: 0.51から0.67
    {'day': 19, 'box': [0.143, 0.51, 0.256, 0.67]},
    {'day': 20, 'box': [0.256, 0.51, 0.369, 0.67]},
    {'day': 21, 'box': [0.369, 0.51, 0.482, 0.67]},
    {'day': 22, 'box': [0.482, 0.51, 0.595, 0.67]},
    {'day': 23, 'box': [0.595, 0.51, 0.708, 0.67]},
    {'day': 24, 'box': [0.708, 0.51, 0.821, 0.67]},
    {'day': 25, 'box': [0.821, 0.51, 0.934, 0.67]},

    # --- 5行目 (Day 33 - 40) ---
    # y座標: 0.67から0.83
    {'day': 26, 'box': [0.143, 0.67, 0.256, 0.83]},
    {'day': 27, 'box': [0.256, 0.67, 0.369, 0.83]},
    {'day': 28, 'box': [0.369, 0.67, 0.482, 0.83]},
    {'day': 29, 'box': [0.482, 0.67, 0.595, 0.83]},
    {'day': 30, 'box': [0.595, 0.67, 0.708, 0.83]},
    {'day': 31, 'box': [0.708, 0.67, 0.821, 0.83]},
    {'day': 0, 'box': [0.821, 0.67, 0.934, 0.83]},

    # --- 6行目 (Day 41 - 48) ---
    # y座標: 0.83から0.99
    {'day': 0, 'box': [0.143, 0.83, 0.256, 0.99]},
    {'day': 0, 'box': [0.256, 0.83, 0.369, 0.99]},
    {'day': 0, 'box': [0.369, 0.83, 0.482, 0.99]},
    {'day': 0, 'box': [0.482, 0.83, 0.595, 0.99]},
    {'day': 0, 'box': [0.595, 0.83, 0.708, 0.99]},
]
    return coords


def vision_document_ocr(content: bytes, language_hints: Optional[List[str]] = None) -> str:
    """同期処理: Google Cloud Vision の document_text_detection で画像からテキスト（手書き対応）を抽出する。"""
    client = vision.ImageAnnotatorClient()
    image = vision.Image(content=content)
    image_context = None
    if language_hints:
        image_context = vision.ImageContext(language_hints=language_hints)

    response = client.document_text_detection(image=image, image_context=image_context)
    if getattr(response, 'error', None) and getattr(response.error, 'message', None):
        raise RuntimeError(response.error.message)

    # full_text_annotation があれば全文を返す
    if hasattr(response, 'full_text_annotation') and response.full_text_annotation and getattr(response.full_text_annotation, 'text', None):
        return response.full_text_annotation.text

    # フォールバック
    texts = response.text_annotations
    if texts:
        return texts[0].description
    return ""

@router.get("/info")
async def info():
    return {"service": "cranberry", "version": "0.1"}

# === 新機能: カレンダーマス目座標取得エンドポイント追加 ===
@router.get("/mask_coords")
async def get_mask_coordinates():
    """
    カレンダーの日付マス目の正規化座標（0.0〜1.0）を返すエンドポイント
    """
    return {"coordinates": get_calendar_mask_coords()}


@router.post("/ocr")
async def ocr_image(file: UploadFile = File(...), lang: str = Form('ja')):
    """Cloud Vision を使って手書き文字を取得するエンドポイント。
    - file: 画像ファイル（multipart/form-data）
    - lang: 言語ヒント（例: 'ja'）
    認証はサービスアカウント JSON を環境変数 `GOOGLE_APPLICATION_CREDENTIALS` で指定してください。
    """
    try:
        contents = await file.read()

        # オプション: 軽い読み込み確認
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return JSONResponse(status_code=400, content={"error": "invalid image"})

        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor() as pool:
            text = await loop.run_in_executor(pool, vision_document_ocr, contents, [lang])

        return {"filename": file.filename, "text": text}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": "ocr_failed", "detail": str(e)})


# Standalone app for testing this module directly
app = FastAPI(title="Cranberry API")
app.include_router(router)

