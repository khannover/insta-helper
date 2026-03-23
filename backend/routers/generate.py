import uuid
import httpx
import aiofiles
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()
UPLOAD_DIR = Path("/app/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

POLLINATIONS_URL = "https://image.pollinations.ai/prompt/{prompt}"


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

    url = POLLINATIONS_URL.format(prompt=req.prompt)
    filename = f"{uuid.uuid4().hex}.jpg"
    dest = UPLOAD_DIR / filename

    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream("GET", url, params=params, follow_redirects=True) as r:
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
        "prompt": req.prompt
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
