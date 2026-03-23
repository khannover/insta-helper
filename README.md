# insta-helper

A self-hosted content creation tool for Instagram — image/video editor with glitch text overlays, AI image generation via Pollinations.ai, audio mixing, and multi-format export.

## Features

- Upload image or video as source media
- Generate images via [Pollinations.ai](https://pollinations.ai) (flux, turbo, flux-anime, ...)
- Optional text overlay with **Glitch / Chromatic Aberration** effect
- Freely positionable & scalable text
- Add audio with custom start/end time
- Export to **9:16**, **1:1**, **3:4**, **16:9** formats
- Download final image (PNG) or video (MP4)
- Dark UI, no external dependencies beyond the backend

## Stack

| Layer | Tech |
|-------|------|
| Frontend | Static HTML / CSS / JS (no framework) |
| Backend | Python 3.12, FastAPI, Uvicorn |
| Image processing | Pillow |
| Video processing | FFmpeg |
| Database | SQLite via SQLAlchemy |
| Containerization | Docker + Docker Compose |

## Quick Start

```bash
git clone https://github.com/khannover/insta-helper
cd insta-helper
docker compose up -d
```

- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000`
- API Docs: `http://localhost:8000/docs`

## Nginx Proxy Manager

Point your subdomain (e.g. `insta.yourdomain.de`) to `localhost:3000` for the UI and `localhost:8000` for the API (or use a single subdomain and proxy-path both).
