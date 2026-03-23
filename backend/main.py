from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import media, export, generate

app = FastAPI(title="insta-helper", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(media.router, prefix="/api/media", tags=["media"])
app.include_router(export.router, prefix="/api/export", tags=["export"])
app.include_router(generate.router, prefix="/api/generate", tags=["generate"])

@app.get("/health")
async def health():
    return {"status": "ok"}
