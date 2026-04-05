import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from routers import media, export, generate
from app_paths import FRONTEND_DIR
from monitoring import monitoring_loop

app = FastAPI(title="insta-helper", version="1.0.0")

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(monitoring_loop())

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "*"
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(media.router, prefix="/api/media", tags=["media"])
app.include_router(export.router, prefix="/api/export", tags=["export"])
app.include_router(generate.router, prefix="/api/generate", tags=["generate"])

@app.get("/health")
async def health():
    return {"status": "ok"}


if FRONTEND_DIR:
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
