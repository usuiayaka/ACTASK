from fastapi import FastAPI, APIRouter, UploadFile, File
from fastapi.responses import JSONResponse
import numpy as np
import cv2
import pytesseract

router = APIRouter()

@router.get("/info")
async def info():
    return {"service": "cranberry", "version": "0.1"}

@router.post("/ocr")
async def ocr_image(file: UploadFile = File(...)):
    """受け取った画像ファイルから文字を抽出して返すシンプルな API。
    Content-Type: multipart/form-data でファイルを送信してください。
    """
    try:
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return JSONResponse(status_code=400, content={"error": "invalid image"})

        # 前処理（グレースケール化）
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # 必要に応じて二値化やノイズ除去を追加できます。

        # pytesseract で OCR 実行
        text = pytesseract.image_to_string(gray)

        return {"filename": file.filename, "text": text}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": "ocr_failed", "detail": str(e)})

# Standalone app for testing this module directly
app = FastAPI(title="Cranberry API")
app.include_router(router)

