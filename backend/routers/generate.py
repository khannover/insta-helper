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
    params = {
        "width": req.width,
        "height": req.height,
        "model": req.model,
        "nologo": str(req.nologo).lower(),
    }
    if req.seed is not None:
        params["seed"] = req.seed

    url = POLLINATIONS_URL.format(prompt=req.prompt)

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get(url, params=params, follow_redirects=True)
        if resp.status_code != 200:
            raise HTTPException(502, "Pollinations API error")
        content_type = resp.headers.get("content-type", "image/jpeg")

    ext = ".jpg" if "jpeg" in content_type else ".png"
    filename = f"{uuid.uuid4().hex}{ext}"
    dest = UPLOAD_DIR / filename

    async with httpx.AsyncClient(timeout=60) as client:
        async with client.stream("GET", url, params=params, follow_redirects=True) as r:
            async with aiofiles.open(dest, "wb") as f:
                async for chunk in r.aiter_bytes():
                    await f.write(chunk)

    return {
        "id": filename,
        "type": "image",
        "url": f"/api/media/file/{filename}",
        "prompt": req.prompt
    }
