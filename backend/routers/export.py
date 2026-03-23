import uuid
import asyncio
from pathlib import Path
from typing import Literal
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import random

router = APIRouter()
UPLOAD_DIR = Path("/app/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ASPECT_RATIOS = {
    "16:9": (1920, 1080),
    "9:16": (1080, 1920),
    "3:4": (1080, 1440),
    "1:1": (1080, 1080),
}


class TextOverlay(BaseModel):
    text: str
    x: float = 0.5          # 0.0 - 1.0 relative position
    y: float = 0.5
    font_size: int = 72
    color: str = "#ffffff"
    glitch: bool = True
    opacity: int = 255


class ExportRequest(BaseModel):
    media_id: str
    aspect: Literal["16:9", "9:16", "3:4", "1:1"] = "9:16"
    text: TextOverlay | None = None
    audio_id: str | None = None
    audio_start: float = 0.0
    audio_end: float | None = None


def draw_glitch_text(draw: ImageDraw.ImageDraw, text: str, x: int, y: int,
                     font: ImageFont.FreeTypeFont, color: str, img: Image.Image):
    """Draw text with a glitch/chromatic aberration effect."""
    r, g, b = Image.new("RGB", (1, 1), color).getpixel((0, 0))
    offset = random.randint(3, 8)

    # Shadow layers for glitch
    for dx, dy, c in [
        (-offset, 0, (255, 0, 80, 160)),
        (offset, 0, (0, 255, 220, 160)),
        (0, 0, (r, g, b, 255)),
    ]:
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        ld.text((x + dx, y + dy), text, font=font, fill=c)
        img.paste(layer, mask=layer)


@router.post("/render")
async def render_export(req: ExportRequest):
    src = UPLOAD_DIR / req.media_id
    if not src.exists():
        raise HTTPException(404, "Source media not found")

    w, h = ASPECT_RATIOS[req.aspect]
    suffix = src.suffix.lower()
    is_video = suffix in {".mp4", ".mov", ".webm"}
    out_id = uuid.uuid4().hex

    if is_video:
        return await _render_video(req, src, w, h, out_id)
    else:
        return await _render_image(req, src, w, h, out_id)


async def _render_image(req: ExportRequest, src: Path, w: int, h: int, out_id: str):
    def _process():
        img = Image.open(src).convert("RGBA")
        # Crop/resize to target aspect
        img_ratio = img.width / img.height
        target_ratio = w / h
        if img_ratio > target_ratio:
            new_w = int(img.height * target_ratio)
            left = (img.width - new_w) // 2
            img = img.crop((left, 0, left + new_w, img.height))
        else:
            new_h = int(img.width / target_ratio)
            top = (img.height - new_h) // 2
            img = img.crop((0, top, img.width, top + new_h))
        img = img.resize((w, h), Image.LANCZOS)

        if req.text and req.text.text:
            t = req.text
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                                          t.font_size)
            except Exception:
                font = ImageFont.load_default()

            draw = ImageDraw.Draw(img)
            bbox = font.getbbox(t.text)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            px = int(t.x * w - tw / 2)
            py = int(t.y * h - th / 2)

            if t.glitch:
                draw_glitch_text(draw, t.text, px, py, font, t.color, img)
            else:
                draw.text((px, py), t.text, font=font, fill=t.color)

        out_path = UPLOAD_DIR / f"{out_id}.png"
        img.convert("RGB").save(out_path, "PNG", optimize=True)
        return out_path

    loop = asyncio.get_event_loop()
    out_path = await loop.run_in_executor(None, _process)

    return {
        "id": out_path.name,
        "url": f"/api/media/file/{out_path.name}",
        "download": f"/api/export/download/{out_path.name}"
    }


async def _render_video(req: ExportRequest, src: Path, w: int, h: int, out_id: str):
    out_path = UPLOAD_DIR / f"{out_id}.mp4"

    # Build ffmpeg filter
    vf_parts = [f"scale={w}:{h}:force_original_aspect_ratio=increase",
                 f"crop={w}:{h}"]

    if req.text and req.text.text:
        t = req.text
        safe_text = t.text.replace("'", "'\\''").replace(":", "\\:")
        # parse hex color to ffmpeg format
        c = t.color.lstrip("#")
        r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
        fc = f"0x{c}ff"
        px_abs = int(t.x * w)
        py_abs = int(t.y * h)
        font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

        if t.glitch:
            # Chromatic aberration via offset text layers
            vf_parts.append(
                f"drawtext=fontfile={font_path}:text='{safe_text}':x={px_abs-6}:y={py_abs}:"
                f"fontsize={t.font_size}:fontcolor=0xff0050aa"
            )
            vf_parts.append(
                f"drawtext=fontfile={font_path}:text='{safe_text}':x={px_abs+6}:y={py_abs}:"
                f"fontsize={t.font_size}:fontcolor=0x00ffddaa"
            )

        vf_parts.append(
            f"drawtext=fontfile={font_path}:text='{safe_text}':x={px_abs}:y={py_abs}:"
            f"fontsize={t.font_size}:fontcolor={fc}"
        )

    vf = ",".join(vf_parts)
    cmd = ["ffmpeg", "-y", "-i", str(src)]

    if req.audio_id:
        audio_src = UPLOAD_DIR / req.audio_id
        if not audio_src.exists():
            raise HTTPException(404, "Audio file not found")
        audio_start = req.audio_start
        cmd += ["-ss", str(audio_start), "-i", str(audio_src)]
        if req.audio_end:
            duration = req.audio_end - audio_start
            cmd += ["-t", str(duration)]
        cmd += ["-filter_complex",
                f"[0:v]{vf}[v];[1:a]aformat=fltp:44100:stereo[a]",
                "-map", "[v]", "-map", "[a]",
                "-c:v", "libx264", "-c:a", "aac",
                "-shortest", str(out_path)]
    else:
        cmd += ["-vf", vf, "-c:v", "libx264", "-c:a", "copy", str(out_path)]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise HTTPException(500, f"FFmpeg error: {stderr.decode()[-500:]}")

    return {
        "id": out_path.name,
        "url": f"/api/media/file/{out_path.name}",
        "download": f"/api/export/download/{out_path.name}"
    }


@router.get("/download/{filename}")
async def download_file(filename: str):
    path = UPLOAD_DIR / filename
    if not path.exists():
        raise HTTPException(404, "File not found")
    return FileResponse(
        path,
        media_type="application/octet-stream",
        filename=filename
    )
