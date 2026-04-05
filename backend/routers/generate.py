import os
import uuid
import httpx
import aiofiles
from urllib.parse import quote
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app_paths import UPLOAD_DIR

router = APIRouter()

POLLINATIONS_URL_FREE = "https://image.pollinations.ai/prompt/{prompt}"
POLLINATIONS_URL_AUTH = "https://gen.pollinations.ai/image/{prompt}"
POLLINATIONS_API_KEY = os.getenv("POLLINATIONS_API_KEY")


class GenerateRequest(BaseModel):
    prompt: str
    width: int = 1024
    height: int = 1024
    seed: int | None = None
    model: str = "flux"
    nologo: bool = True


@router.post("/image")
async def generate_image(req: GenerateRequest):
    if not req.prompt.strip():
        raise HTTPException(400, "Prompt cannot be empty")

    params = {
        "width": req.width,
        "height": req.height,
        "model": req.model,
        "nologo": str(req.nologo).lower(),
    }
    if req.seed is not None:
        params["seed"] = req.seed

    headers = {}
    if POLLINATIONS_API_KEY:
        headers["Authorization"] = f"Bearer {POLLINATIONS_API_KEY}"
        url_base = POLLINATIONS_URL_AUTH
        # Adding key to params as a fallback/alternative for some endpoints
        params["key"] = POLLINATIONS_API_KEY
    else:
        url_base = POLLINATIONS_URL_FREE

    url = url_base.format(prompt=quote(req.prompt))
    filename = f"{uuid.uuid4().hex}.jpg"
    dest = UPLOAD_DIR / filename

    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream("GET", url, params=params, headers=headers, follow_redirects=True) as r:
            if r.status_code == 403:
                raise HTTPException(403, "Pollinations API: 403 Forbidden. Check your API key balance and permissions at enter.pollinations.ai")
            if r.status_code != 200:
                raise HTTPException(502, f"Pollinations API returned {r.status_code}")
            content_type = r.headers.get("content-type", "image/jpeg")
            ext = ".png" if "png" in content_type else ".jpg"
            filename = f"{uuid.uuid4().hex}{ext}"
            dest = UPLOAD_DIR / filename
            async with aiofiles.open(dest, "wb") as f:
                async for chunk in r.aiter_bytes():
                    await f.write(chunk)

    return {
        "id": filename,
        "type": "image",
        "url": f"/api/media/file/{filename}",
        "download": f"/api/export/download/{filename}",
        "prompt": req.prompt,
        "seed": req.seed,
    }


@router.get("/models")
async def list_models():
    return {
        "models": [
            "flux",
            "turbo",
            "flux-realism",
            "flux-anime",
            "flux-3d",
            "flux-pro",
            "gptimage",
        ]
    }
