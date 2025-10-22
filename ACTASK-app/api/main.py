from fastapi import FastAPI, UploadFile, File
import httpx
from cranberry import router as cranberry_router
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv 

# === LINE Messaging API設定 ===
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_USER_ID = os.getenv("LINE_USER_ID")

# === FastAPI設定 ===
app = FastAPI(title="ACTASK Main API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cranberry_router, prefix="/cranberry")


# === LINE送信関数 ===
async def send_line_message_to_user(message: str):
    """LINE公式アカウント（Messaging API）でユーザーにメッセージ送信"""
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
    }
    data = {
        "to": LINE_USER_ID,
        "messages": [{"type": "text", "text": message}],
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=headers, json=data)
        if resp.status_code != 200:
            print("❌ LINE送信失敗:", resp.text)
        else:
            print("✅ LINE送信成功")


# === メイン処理 ===
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

    # OCR結果を取得
    ocr_text = data.get("text", "テキストが検出されませんでした")

    # LINEに送信
    await send_line_message_to_user(f"OCR結果: {ocr_text}")

    return {"cranberry_response": data, "line_status": "sent"}
