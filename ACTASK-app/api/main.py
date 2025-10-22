from fastapi import FastAPI, UploadFile, File
import httpx
from cranberry import router as cranberry_router
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="ACTASK Main API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cranberry_router, prefix="/cranberry")

@app.post("/call-cranberry")
async def call_cranberry(file: UploadFile = File(...)):
    """10秒ごとに送られてくる画像を Cranberry API に転送して結果を返す"""
    async with httpx.AsyncClient() as client:
        try:
            files = {"file": (file.filename, await file.read(), file.content_type)}
            resp = await client.post("http://127.0.0.1:8000/cranberry/ocr", files=files)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            return {"error": "failed to call cranberry", "detail": str(e)}
    return {"cranberry_response": data}
