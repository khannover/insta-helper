import uuid
import aiofiles
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from app_paths import UPLOAD_DIR

router = APIRouter()

ALLOWED_IMAGE = {"image/jpeg", "image/png", "image/webp", "image/gif"}
ALLOWED_VIDEO = {"video/mp4", "video/quicktime", "video/webm"}
ALLOWED_AUDIO = {"audio/mpeg", "audio/mp4", "audio/wav", "audio/ogg", "audio/flac"}


@router.post("/upload")
async def upload_media(file: UploadFile = File(...)):
    if file.content_type not in ALLOWED_IMAGE | ALLOWED_VIDEO | ALLOWED_AUDIO:
        raise HTTPException(400, f"Unsupported file type: {file.content_type}")

    ext = Path(file.filename).suffix
    filename = f"{uuid.uuid4().hex}{ext}"
    dest = UPLOAD_DIR / filename

    async with aiofiles.open(dest, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            await f.write(chunk)

    media_type = "image" if file.content_type in ALLOWED_IMAGE else \
                 "video" if file.content_type in ALLOWED_VIDEO else "audio"

    return {
        "id": filename,
        "type": media_type,
        "original_name": file.filename,
        "url": f"/api/media/file/{filename}"
    }


@router.get("/file/{filename}")
async def get_file(filename: str):
    path = UPLOAD_DIR / filename
    if not path.exists():
        raise HTTPException(404, "File not found")
    return FileResponse(path)


@router.delete("/file/{filename}")
async def delete_file(filename: str):
    path = UPLOAD_DIR / filename
    if path.exists():
        path.unlink()
    return {"deleted": filename}
