from fastapi import FastAPI

from .routes import router as api_router

app = FastAPI(title="Cross-Run Context API", version="0.1.0")

app.include_router(api_router)


@app.get("/healthz", tags=["health"])
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
