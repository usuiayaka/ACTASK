from fastapi import FastAPI, APIRouter, UploadFile, File, Form
from fastapi.responses import JSONResponse
import numpy as np
import cv2
import asyncio
from concurrent.futures import ThreadPoolExecutor
from google.cloud import vision
from typing import Optional, List

router = APIRouter()


@router.get("/info")
async def info():
    return {"service": "cranberry", "version": "0.1"}


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

