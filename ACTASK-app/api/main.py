from fastapi import FastAPI
import httpx
from cranberry import router as cranberry_router
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="ACTASK Main API")

# CORS を許可（開発用: 全オリジンを許可）。本番では適切なオリジンに制限してください。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cranberry の router を取り込んで main の OpenAPI に統合
app.include_router(cranberry_router, prefix="/cranberry")

@app.get("/status")
async def status():
    return {"status": "ok", "service": "main"}

@app.get("/call-cranberry")
async def call_cranberry():
    """同一コンテナ内にマウントされた Cranberry API の /info を HTTP で呼ぶサンプル。
    uvicorn が同プロセスで起動しているため localhost 経由で呼べます。
    """
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get("http://127.0.0.1:8000/cranberry/info", timeout=5.0)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            return {"error": "failed to call cranberry", "detail": str(e)}
    return {"cranberry_response": data}
