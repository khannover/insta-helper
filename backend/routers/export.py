import uuid
import asyncio
from pathlib import Path
from typing import Literal
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
import random
from app_paths import UPLOAD_DIR, get_ffmpeg_executable, get_font_path

router = APIRouter()

ASPECT_RATIOS = {
    "16:9": (1920, 1080),
    "9:16": (1080, 1920),
    "3:4": (1080, 1440),
    "1:1": (1080, 1080),
}

GIF_MAX_DURATION = 12.0
GIF_MAX_SIDE = 720
GIF_FPS = 12
FONT_PATH = get_font_path()


def _video_encode_args(w: int, h: int, codec: str = "h264", still_image: bool = False) -> list[str]:
    pixels = w * h

    if codec == "h265":
        if pixels >= 1920 * 1080:
            crf = "30"
            maxrate = "4M"
            bufsize = "8M"
        elif pixels >= 1080 * 1440:
            crf = "29"
            maxrate = "3500k"
            bufsize = "7M"
        else:
            crf = "28"
            maxrate = "3M"
            bufsize = "6M"

        return [
            "-c:v", "libx265",
            "-preset", "medium",
            "-tag:v", "hvc1",
            "-crf", crf,
            "-maxrate", maxrate,
            "-bufsize", bufsize,
            "-movflags", "+faststart",
            "-pix_fmt", "yuv420p",
        ]

    if pixels >= 1920 * 1080:
        crf = "28"
        maxrate = "6M"
        bufsize = "12M"
    elif pixels >= 1080 * 1440:
        crf = "27"
        maxrate = "5M"
        bufsize = "10M"
    else:
        crf = "26"
        maxrate = "4M"
        bufsize = "8M"

    args = [
        "-c:v", "libx264",
        "-preset", "slow",
        "-crf", crf,
        "-maxrate", maxrate,
        "-bufsize", bufsize,
        "-movflags", "+faststart",
        "-pix_fmt", "yuv420p",
    ]

    if still_image:
        args += ["-tune", "stillimage"]

    return args


def _gif_scale(w: int, h: int) -> tuple[int, int]:
    longest = max(w, h)
    if longest <= GIF_MAX_SIDE:
        return w, h

    scale = GIF_MAX_SIDE / longest
    gif_w = max(2, int(round(w * scale / 2) * 2))
    gif_h = max(2, int(round(h * scale / 2) * 2))
    return gif_w, gif_h


def _resolve_output_format(req: "ExportRequest", is_video: bool) -> str:
    if req.output_format == "auto":
        if is_video or req.audio_id or req.anim_fx:
            return "mp4"
        return "png"
    return req.output_format


def _build_image_anim_filter(req: "ExportRequest", w: int, h: int, total_frames: int) -> str:
    vf_parts: list[str] = []

    zooms = [a for a in req.anim_fx if "ken_burns" in a]
    if zooms:
        seg_len = total_frames / len(zooms)

        def zoom_expr(idx: int) -> str:
            anim = zooms[idx]
            offset = idx * seg_len
            if anim == "ken_burns_in":
                return "min(zoom+0.0015,1.5)"
            if anim == "ken_burns_out":
                return f"max(1.5-0.0015*(on-{offset}),1)"
            if anim == "ken_burns_constant":
                return "zoom+0.0025"
            return "1"

        z_expr = zoom_expr(len(zooms) - 1)
        for i in range(len(zooms) - 2, -1, -1):
            limit = (i + 1) * seg_len
            z_expr = f"if(lte(on,{limit}),{zoom_expr(i)},{z_expr})"
            
        x_expr, y_expr = 'iw/2-(iw/zoom)/2', 'ih/2-(ih/zoom)/2'
        if "ken_burns_constant" in zooms:
            # Dynamic oscillating zoom between 1.05 and 1.35
            z_expr = "1.2+0.15*sin(on/130)"
            # Smooth Lissajous curve for panning across the entire allowed area
            x_expr = "(iw/2-(iw/zoom)/2)*(1+cos(on/85))"
            y_expr = "(ih/2-(ih/zoom)/2)*(1+sin(on/115))"

        vf_parts.append(
            f"zoompan=z='{z_expr}':d={total_frames}:x='{x_expr}':"
            f"y='{y_expr}':s={w}x{h}"
        )

    for anim in req.anim_fx:
        if anim == "glitch_subtle":
            vf_parts.append("rgbashift=rh=3:bv=-3:gh=1,noise=alls=7:allf=t+u")
        elif anim == "glitch_heavy":
            vf_parts.append("rgbashift=rh=25:bv=-25:gv=15,noise=alls=50:allf=t+u,hue=h='sin(t*3)*30'")
        elif anim == "glitch_pulse":
            vf_parts.append("hue=h='sin(t*10)*20':s='sin(t*2)*2+1',noise=alls=30:allf=t+u")
        elif anim == "rgb_split":
            vf_parts.append("rgbashift=rh=10:bv=-10")
        elif anim == "shake":
            vf_parts.append(
                f"crop=iw-40:ih-40:20+20*sin(t*10):20+20*cos(t*12),pad={w}:{h}:(ow-iw)/2:(oh-ih)/2"
            )

    return ",".join(vf_parts)


def _build_video_filter(req: "ExportRequest", w: int, h: int) -> str:
    if req.crop_rect and len(req.crop_rect) == 4:
        x1, y1, x2, y2 = req.crop_rect
        vf_parts = [
            f"crop=iw*({x2-x1}):ih*({y2-y1}):iw*{x1}:ih*{y1}",
            f"scale={w}:{h}"
        ]
    else:
        vf_parts = [
            f"scale={w}:{h}:force_original_aspect_ratio=increase",
            f"crop={w}:{h}"
        ]

    for fx in req.fx:
        if fx == "grayscale":
            vf_parts.append("hue=s=0")
        elif fx == "sepia":
            vf_parts.append("colorchannelmixer=.393:.769:.189:0:.349:.686:.168:0:.272:.534:.131:0")
        elif fx == "blur":
            vf_parts.append("boxblur=10:1")
        elif fx == "invert":
            vf_parts.append("negate")
        elif fx == "vignette":
            vf_parts.append("vignette")

    zooms = [a for a in req.anim_fx if "ken_burns" in a]
    if zooms:
        duration = 10
        seg_len = duration / len(zooms)

        def zoom_expr_v(idx: int) -> str:
            anim = zooms[idx]
            offset = idx * seg_len
            if anim == "ken_burns_in":
                return "min(zoom+0.0015,1.5)"
            if anim == "ken_burns_out":
                return f"max(1.5-0.0015*(t-{offset})*25,1)"
            if anim == "ken_burns_constant":
                return "zoom+0.0025"
            return "1"

        z_expr = zoom_expr_v(len(zooms) - 1)
        for i in range(len(zooms) - 2, -1, -1):
            limit = (i + 1) * seg_len
            z_expr = f"if(lte(t,{limit}),{zoom_expr_v(i)},{z_expr})"

        x_expr, y_expr = 'iw/2-(iw/zoom)/2', 'ih/2-(ih/zoom)/2'
        if "ken_burns_constant" in zooms:
            # Dynamic oscillating zoom between 1.05 and 1.35
            z_expr = "1.2+0.15*sin(on/130)"
            # Smooth Lissajous curve for panning across the entire allowed area
            x_expr = "(iw/2-(iw/zoom)/2)*(1+cos(on/85))"
            y_expr = "(ih/2-(ih/zoom)/2)*(1+sin(on/115))"

        vf_parts.append(f"zoompan=z='{z_expr}':x='{x_expr}':y='{y_expr}':s={w}x{h}")

    for anim in req.anim_fx:
        if anim == "glitch_subtle":
            vf_parts.append("rgbashift=rh=3:bv=-3:gh=1,noise=alls=7:allf=t+u")
        elif anim == "glitch_heavy":
            vf_parts.append("rgbashift=rh=25:bv=-25:gv=15,noise=alls=50:allf=t+u,hue=h='sin(t*3)*30'")
        elif anim == "glitch_pulse":
            vf_parts.append("hue=h='sin(t*10)*20':s='sin(t*2)*2+1',noise=alls=30:allf=t+u")
        elif anim == "rgb_split":
            vf_parts.append("rgbashift=rh=10:bv=-10")
        elif anim == "shake":
            vf_parts.append(f"crop=iw-40:ih-40:20+20*sin(t*10):20+20*cos(t*12),pad={w}:{h}:(ow-iw)/2:(oh-ih)/2")

    if req.text and req.text.text:
        t = req.text
        if not FONT_PATH:
            raise HTTPException(500, "No usable font file found. Set INSTA_HELPER_FONT or bundle a TTF font.")
        c = t.color.lstrip("#")
        fc = f"0x{c}ff"
        px_abs = int(t.x * w)
        py_abs = int(t.y * h)
        
        lines = t.text.split("\n")
        line_height = t.font_size * 1.2
        total_height = len(lines) * line_height
        
        for i, line in enumerate(lines):
            safe_text = line.replace("'", "'\\\\''").replace(":", "\\\\:")
            if not safe_text:
                continue
            x_expr = f"({px_abs})-text_w/2"
            y_i = py_abs - (total_height / 2) + (i * line_height) + (line_height / 2)
            y_expr = f"({y_i})-text_h/2"
            
            if t.glitch:
                vf_parts.append(
                    f"drawtext=fontfile={FONT_PATH}:text='{safe_text}'"
                    f":x=({px_abs-6})-text_w/2:y={y_expr}:fontsize={t.font_size}:fontcolor=0xff0050aa"
                )
                vf_parts.append(
                    f"drawtext=fontfile={FONT_PATH}:text='{safe_text}'"
                    f":x=({px_abs+6})-text_w/2:y={y_expr}:fontsize={t.font_size}:fontcolor=0x00ffddaa"
                )
            vf_parts.append(
                f"drawtext=fontfile={FONT_PATH}:text='{safe_text}'"
                f":x={x_expr}:y={y_expr}:fontsize={t.font_size}:fontcolor={fc}"
            )

    return ",".join(vf_parts)


class TextOverlay(BaseModel):
    text: str
    x: float = 0.5  # 0.0 - 1.0 relative position
    y: float = 0.5
    font_size: int = 72
    color: str = "#ffffff"
    glitch: bool = True
    opacity: int = 255


class ExportRequest(BaseModel):
    media_id: str
    aspect: Literal["16:9", "9:16", "3:4", "1:1", "custom"] = "9:16"
    text: TextOverlay | None = None
    audio_id: str | None = None
    audio_start: float = 0.0
    audio_end: float | None = None
    fx: list[str] = []
    anim_fx: list[str] = []
    crop_mode: str = "center"  # legacy
    crop_rect: list[float] | None = None # [x1, y1, x2, y2] normalized
    output_format: Literal["auto", "mp4", "gif", "png"] = "auto"
    video_codec: Literal["h264", "h265"] = "h264"


def draw_glitch_text(draw: ImageDraw.ImageDraw, text: str, x: int, y: int,
                    font: ImageFont.FreeTypeFont, color: str, img: Image.Image):
    """Draw text with a glitch/chromatic aberration effect."""
    r, g, b = Image.new("RGB", (1, 1), color).getpixel((0, 0))
    offset = random.randint(3, 8)
    for dx, dy, c in [
        (-offset, 0, (255, 0, 80, 160)),
        (offset, 0, (0, 255, 220, 160)),
        (0, 0, (r, g, b, 255)),
    ]:
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        ld.multiline_text((x + dx, y + dy), text, font=font, fill=c, align="center")
        img.paste(layer, mask=layer)


def _crop_resize(img, w, h, crop_mode="center", crop_rect=None):
    """Crop and resize image to fit target aspect ratio."""
    iw, ih = img.size
    
    if crop_rect and len(crop_rect) == 4:
        x1, y1, x2, y2 = crop_rect
        sx = x1 * iw
        sy = y1 * ih
        sw = (x2 - x1) * iw
        sh = (y2 - y1) * ih
    else:
        ir = iw / ih
        cr = w / h
        if ir > cr:
            sw = ih * cr
            sh = ih
            sy = 0
            if crop_mode == "left":
                sx = 0
            elif crop_mode == "right":
                sx = iw - sw
            else: # center
                sx = (iw - sw) / 2
        else:
            sh = iw / cr
            sw = iw
            sx = 0
            if crop_mode == "top":
                sy = 0
            elif crop_mode == "bottom":
                sy = ih - sh
            else: # center
                sy = (ih - sh) / 2
            
    img = img.crop((sx, sy, sx + sw, sy + sh))
    return img.resize((w, h), Image.Resampling.LANCZOS)


def _apply_text(img: Image.Image, t: TextOverlay, w: int, h: int) -> Image.Image:
    """Apply text overlay to image."""
    try:
        if FONT_PATH:
            font = ImageFont.truetype(FONT_PATH, t.font_size)
        else:
            font = ImageFont.load_default()
    except Exception:
        font = ImageFont.load_default()
    draw = ImageDraw.Draw(img)
    if hasattr(draw, "multiline_textbbox"):
        bbox = draw.multiline_textbbox((0, 0), t.text, font=font, align="center")
    else:
        bbox = draw.textbbox((0, 0), t.text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    px = int(t.x * w - tw / 2)
    py = int(t.y * h - th / 2)
    if t.glitch:
        draw_glitch_text(draw, t.text, px, py, font, t.color, img)
    else:
        if hasattr(draw, "multiline_text"):
            draw.multiline_text((px, py), t.text, font=font, fill=t.color, align="center")
        else:
            draw.text((px, py), t.text, font=font, fill=t.color)
    return img


def _apply_fx_pil(img: Image.Image, fx_list: list[str]) -> Image.Image:
    """Apply multiple visual effects to PIL image."""
    for fx in fx_list:
        if fx == "grayscale":
            img = img.convert("L").convert("RGBA")
        elif fx == "sepia":
            # Sepia matrix
            sepia_img = img.convert("RGB")
            width, height = sepia_img.size
            pixels = sepia_img.load()
            for y in range(height):
                for x in range(width):
                    r, g, b = pixels[x, y]
                    tr = int(0.393 * r + 0.769 * g + 0.189 * b)
                    tg = int(0.349 * r + 0.686 * g + 0.168 * b)
                    tb = int(0.272 * r + 0.534 * g + 0.131 * b)
                    pixels[x, y] = (min(tr, 255), min(tg, 255), min(tb, 255))
            img = sepia_img.convert("RGBA")
        elif fx == "blur":
            img = img.filter(ImageFilter.GaussianBlur(radius=10))
        elif fx == "invert":
            # Invert only RGB channels, keep Alpha
            r, g, b, a = img.split()
            r, g, b = ImageOps.invert(r), ImageOps.invert(g), ImageOps.invert(b)
            img = Image.merge("RGBA", (r, g, b, a))
        elif fx == "vignette":
            # Simple vignette effect
            width, height = img.size
            vignette = Image.new("L", (width, height), 0)
            draw = ImageDraw.Draw(vignette)
            for i in range(min(width, height) // 2):
                val = int(255 * (i / (min(width, height) // 2)))
                draw.ellipse([i, i, width - i, height - i], outline=val)
            vignette = vignette.filter(ImageFilter.GaussianBlur(radius=width // 10))
            img_rgb = img.convert("RGB")
            img = Image.composite(img_rgb.convert("RGBA"), Image.new("RGBA", (width, height), (0, 0, 0, 255)), vignette).convert("RGBA")
    return img


@router.post("/render")
async def render_export(req: ExportRequest):
    src = UPLOAD_DIR / req.media_id
    if not src.exists():
        raise HTTPException(404, "Source media not found")

    suffix = src.suffix.lower()
    is_video = suffix in {".mp4", ".mov", ".webm"}
    
    if req.aspect == "custom" and req.crop_rect:
        x1, y1, x2, y2 = req.crop_rect
        norm_ratio = (x2 - x1) / (y2 - y1)
        iw, ih = 1080, 1080
        try:
            if is_video:
                import subprocess, json
                probe = subprocess.check_output([
                    "ffprobe", "-v", "error", "-select_streams", "v:0",
                    "-show_entries", "stream=width,height", "-of", "json", str(src)
                ])
                info = json.loads(probe)
                iw = int(info['streams'][0]['width'])
                ih = int(info['streams'][0]['height'])
            else:
                with Image.open(src) as img_info:
                    iw, ih = img_info.size
            real_ratio = norm_ratio * (iw / ih)
        except Exception:
            real_ratio = norm_ratio

        if real_ratio > 1:
            w, h = 1080, int(1080 / real_ratio)
        else:
            w, h = int(1080 * real_ratio), 1080
    else:
        w, h = ASPECT_RATIOS.get(req.aspect, (1080, 1920))
    out_id = uuid.uuid4().hex
    output_format = _resolve_output_format(req, is_video)

    if output_format == "gif" and req.audio_id:
        raise HTTPException(400, "GIF export does not support audio")

    if output_format == "png":
        if is_video or req.audio_id or req.anim_fx:
            raise HTTPException(400, "PNG export only supports still images without audio or animation")
        return await _render_image(req, src, w, h, out_id)

    if output_format == "gif":
        if is_video:
            return await _render_video_gif(req, src, w, h, out_id)
        return await _render_image_gif(req, src, w, h, out_id)

    if is_video:
        return await _render_video(req, src, w, h, out_id)

    if req.audio_id or req.anim_fx or output_format == "mp4":
        return await _render_image_with_audio(req, src, w, h, out_id)

    return await _render_image(req, src, w, h, out_id)


async def _render_image(req: ExportRequest, src: Path, w: int, h: int, out_id: str):
    def _process():
        img = Image.open(src).convert("RGBA")
        img = _crop_resize(img, w, h, req.crop_mode, req.crop_rect)
        if req.fx:
            img = _apply_fx_pil(img, req.fx)
        if req.text and req.text.text:
            img = _apply_text(img, req.text, w, h)
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


async def _render_image_with_audio(req: ExportRequest, src: Path, w: int, h: int, out_id: str):
    """Combine a static image with audio track using ffmpeg, producing an MP4."""
    out_path = UPLOAD_DIR / f"{out_id}.mp4"
    audio_src = UPLOAD_DIR / req.audio_id if req.audio_id else None
    
    # First render the image with text overlay
    def _process_img():
        img = Image.open(src).convert("RGBA")
        img = _crop_resize(img, w, h, req.crop_mode, req.crop_rect)
        if req.fx and req.fx != "none":
            img = _apply_fx_pil(img, req.fx)
        if req.text and req.text.text:
            img = _apply_text(img, req.text, w, h)
        tmp_path = UPLOAD_DIR / f"{out_id}_tmp.png"
        img.convert("RGB").save(tmp_path, "PNG")
        return tmp_path

    loop = asyncio.get_event_loop()
    tmp_img = await loop.run_in_executor(None, _process_img)

    audio_start = req.audio_start
    duration = 10.0 # default if no audio or auto
    if req.audio_id:
        # Actually need to get audio duration if we want exact.
        # For now let's assume 15s or based on audio_end
        if req.audio_end:
            duration = req.audio_end - audio_start
        else:
            # Fallback/Default
            duration = 15.0

    total_frames = int(duration * 25)

    anim_vf = _build_image_anim_filter(req, w, h, total_frames)
    vf_str = ",".join(part for part in ["format=yuv420p", anim_vf] if part)
    ffmpeg_bin = get_ffmpeg_executable()

    cmd = [
        ffmpeg_bin, "-y",
        "-loop", "1", "-i", str(tmp_img),
    ]
    if req.audio_id:
        cmd += ["-ss", str(audio_start), "-i", str(audio_src)]
        if req.audio_end:
            cmd += ["-t", str(duration)]
        cmd += ["-shortest"]
    else:
        # No audio, just render for the duration
        cmd += ["-t", str(duration), "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
        cmd += ["-t", str(duration)]

    cmd += [
        "-vf", vf_str,
        *_video_encode_args(w, h, codec=req.video_codec, still_image=True),
        "-c:a", "aac",
        "-b:a", "128k",
        str(out_path)
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    _, stderr = await proc.communicate()
    # Clean up temp image
    tmp_img.unlink(missing_ok=True)
    if proc.returncode != 0:
        raise HTTPException(500, f"FFmpeg error: {stderr.decode()[-500:]}")

    return {
        "id": out_path.name,
        "url": f"/api/media/file/{out_path.name}",
        "download": f"/api/export/download/{out_path.name}"
    }


async def _render_image_gif(req: ExportRequest, src: Path, w: int, h: int, out_id: str):
    if not req.anim_fx:
        def _process_static_gif():
            img = Image.open(src).convert("RGBA")
            img = _crop_resize(img, w, h, req.crop_mode, req.crop_rect)
            if req.fx:
                img = _apply_fx_pil(img, req.fx)
            if req.text and req.text.text:
                img = _apply_text(img, req.text, w, h)
            gif_w, gif_h = _gif_scale(w, h)
            if (gif_w, gif_h) != (w, h):
                img = img.resize((gif_w, gif_h), Image.Resampling.LANCZOS)
            out_path = UPLOAD_DIR / f"{out_id}.gif"
            img.convert("P", palette=Image.Palette.ADAPTIVE, colors=128).save(
                out_path,
                "GIF",
                optimize=True,
            )
            return out_path

        loop = asyncio.get_event_loop()
        out_path = await loop.run_in_executor(None, _process_static_gif)
        return {
            "id": out_path.name,
            "url": f"/api/media/file/{out_path.name}",
            "download": f"/api/export/download/{out_path.name}"
        }

    out_path = UPLOAD_DIR / f"{out_id}.gif"

    def _process_img():
        img = Image.open(src).convert("RGBA")
        img = _crop_resize(img, w, h, req.crop_mode, req.crop_rect)
        if req.fx and req.fx != "none":
            img = _apply_fx_pil(img, req.fx)
        if req.text and req.text.text:
            img = _apply_text(img, req.text, w, h)
        tmp_path = UPLOAD_DIR / f"{out_id}_tmp.png"
        img.convert("RGB").save(tmp_path, "PNG")
        return tmp_path

    loop = asyncio.get_event_loop()
    tmp_img = await loop.run_in_executor(None, _process_img)

    duration = min(GIF_MAX_DURATION, 10.0)
    total_frames = int(duration * GIF_FPS)
    gif_w, gif_h = _gif_scale(w, h)
    anim_vf = _build_image_anim_filter(req, w, h, total_frames)
    filter_parts = [part for part in [anim_vf, f"fps={GIF_FPS}", f"scale={gif_w}:{gif_h}:flags=lanczos"] if part]
    filter_chain = ",".join(filter_parts)
    filter_complex = (
        f"[0:v]{filter_chain},split[s0][s1];"
        f"[s0]palettegen=stats_mode=diff:max_colors=128[p];"
        f"[s1][p]paletteuse=dither=sierra2_4a"
    )
    ffmpeg_bin = get_ffmpeg_executable()

    cmd = [
        ffmpeg_bin, "-y",
        "-loop", "1", "-t", str(duration), "-i", str(tmp_img),
        "-filter_complex", filter_complex,
        "-loop", "0",
        str(out_path)
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    _, stderr = await proc.communicate()
    tmp_img.unlink(missing_ok=True)
    if proc.returncode != 0:
        raise HTTPException(500, f"FFmpeg error: {stderr.decode()[-500:]}")

    return {
        "id": out_path.name,
        "url": f"/api/media/file/{out_path.name}",
        "download": f"/api/export/download/{out_path.name}"
    }


async def _render_video(req: ExportRequest, src: Path, w: int, h: int, out_id: str):
    out_path = UPLOAD_DIR / f"{out_id}.mp4"
    vf = _build_video_filter(req, w, h)
    ffmpeg_bin = get_ffmpeg_executable()
    cmd = [ffmpeg_bin, "-y", "-i", str(src)]

    if req.audio_id:
        audio_src = UPLOAD_DIR / req.audio_id
        if not audio_src.exists():
            raise HTTPException(404, "Audio file not found")
        audio_start = req.audio_start
        cmd += ["-ss", str(audio_start), "-i", str(audio_src)]
        if req.audio_end:
            duration = req.audio_end - audio_start
            cmd += ["-t", str(duration)]
        cmd += [
            "-filter_complex", f"[0:v]{vf}[v];[1:a]aformat=fltp:44100:stereo[a]",
            "-map", "[v]", "-map", "[a]",
            *_video_encode_args(w, h, codec=req.video_codec),
            "-c:a", "aac",
            "-b:a", "128k",
            "-shortest",
            str(out_path)
        ]
    else:
        cmd += ["-vf", vf, *_video_encode_args(w, h, codec=req.video_codec), "-c:a", "copy", str(out_path)]

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


async def _render_video_gif(req: ExportRequest, src: Path, w: int, h: int, out_id: str):
    out_path = UPLOAD_DIR / f"{out_id}.gif"
    gif_w, gif_h = _gif_scale(w, h)
    vf = _build_video_filter(req, w, h)
    filter_parts = [part for part in [vf, f"fps={GIF_FPS}", f"scale={gif_w}:{gif_h}:flags=lanczos"] if part]
    filter_chain = ",".join(filter_parts)
    filter_complex = (
        f"[0:v]{filter_chain},split[s0][s1];"
        f"[s0]palettegen=stats_mode=diff:max_colors=128[p];"
        f"[s1][p]paletteuse=dither=sierra2_4a"
    )
    ffmpeg_bin = get_ffmpeg_executable()

    cmd = [
        ffmpeg_bin, "-y",
        "-t", str(GIF_MAX_DURATION),
        "-i", str(src),
        "-filter_complex", filter_complex,
        "-loop", "0",
        str(out_path)
    ]

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
