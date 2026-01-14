from fastapi import FastAPI, APIRouter, UploadFile, File, Form
from fastapi.responses import JSONResponse
import numpy as np
import cv2
import asyncio
from concurrent.futures import ThreadPoolExecutor
from google.cloud import vision
from typing import Optional, List

router = APIRouter()

# =========================================================
# Cloud Run 対応：
# サービスアカウント認証を使用するため、
# GOOGLE_APPLICATION_CREDENTIALS は不要
# =========================================================
vision_client = vision.ImageAnnotatorClient()


### 新機能：カレンダーマス目の正規化座標 (x_min, y_min, x_max, y_max) を返す関数追加 ===
def get_calendar_mask_coords():
    """
    ピクセル座標を返す (この値は、カメラの解像度が変動しない前提で使用可能)
    """
    coords = [
        # {'day': '', 'box': [0.13, 0.065, 0.86, 0.94]},
        {'day': 'MON', 'box': [0.13, 0.065, 0.21, 0.22] },
         {'day': '1', 'box': [0.21, 0.065, 0.3, 0.21] },
        {'day': '2','box': [0.3, 0.065, 0.39, 0.21] },
        {'day': '3', 'box': [0.39, 0.065, 0.47, 0.21]},
        {'day': '4', 'box': [0.51, 0.065, 0.597, 0.21] },
        {'day': '5', 'box': [0.597, 0.073, 0.68, 0.22] },
        {'day': '6', 'box': [0.68, 0.076, 0.767, 0.22] },
        {'day': '7', 'box': [0.767, 0.078, 0.86, 0.22] },

        {'day': '8', 'box': [0.21, 0.21, 0.302, 0.36] },
        {'day': '9', 'box': [0.3, 0.21, 0.39, 0.36] },
        {'day': '10', 'box': [0.39, 0.21, 0.47, 0.36] },
        {'day': '11', 'box': [0.51, 0.21, 0.6, 0.36] },
        {'day': '12', 'box': [0.6, 0.22, 0.685, 0.36] },
        {'day': '13', 'box': [0.685, 0.22, 0.77, 0.36] },
        {'day': '14', 'box': [0.77, 0.22, 0.86, 0.36] },
        
        {'day': '15', 'box': [0.21, 0.36, 0.305, 0.505] },
        {'day': '16', 'box': [0.305, 0.36, 0.39, 0.505] },
        {'day': '17', 'box': [0.39, 0.36, 0.47, 0.505] },
        {'day': '18', 'box': [0.515, 0.36, 0.6, 0.505] },
        {'day': '19', 'box': [0.6, 0.36, 0.685, 0.505] },
        {'day': '20', 'box': [0.685, 0.36, 0.77, 0.505] },
        {'day': '21', 'box': [0.77, 0.36, 0.86, 0.505] },

        {'day': '22', 'box': [0.21, 0.505, 0.305, 0.65] },
        {'day': '23', 'box': [0.305, 0.505, 0.39, 0.65] },
        {'day': '24', 'box': [0.39, 0.505, 0.47, 0.65] },
        {'day': '25', 'box': [0.515, 0.505, 0.6, 0.65] },
        {'day': '26', 'box': [0.6, 0.505, 0.685, 0.65] },
        {'day': '27', 'box': [0.685, 0.505, 0.77, 0.65] },
        {'day': '28', 'box': [0.77, 0.505, 0.86, 0.65] },

        {'day': '29', 'box': [0.21, 0.65, 0.305, 0.805] },
        {'day': '30', 'box': [0.305, 0.65, 0.39, 0.805] },
        {'day': '31', 'box': [0.39, 0.65, 0.47, 0.805] },
        {'day': '0', 'box': [0.515, 0.65, 0.6, 0.8] },
        {'day': '0', 'box': [0.6, 0.65, 0.685, 0.8] },
        {'day': '0', 'box': [0.685, 0.65, 0.77, 0.8] },
        {'day': '0', 'box': [0.77, 0.65, 0.86, 0.8] },

        {'day': '0', 'box': [0.21, 0.8, 0.305, 0.95] },
        {'day': '0', 'box': [0.305, 0.8, 0.39, 0.95] },
        {'day': '0', 'box': [0.39, 0.8, 0.47, 0.95] },
        {'day': '0', 'box': [0.515, 0.8, 0.6, 0.95] },
        {'day': '0', 'box': [0.6, 0.8, 0.685, 0.95] },
        {'day': '0', 'box': [0.685, 0.8, 0.77, 0.95] },
        {'day': '0', 'box': [0.77, 0.8, 0.86, 0.95] },
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


# Standalone app for testing this module directly
app = FastAPI(title="Cranberry API")
app.include_router(router)
