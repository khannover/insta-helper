import os
import psutil
import httpx
import asyncio
import time
import logging

logger = logging.getLogger(__name__)

# Config from env
GRAFANA_URL = os.getenv("GRAFANA_URL")       # Influx metrics ingestion URL
GRAFANA_USERNAME = os.getenv("GRAFANA_USERNAME")
GRAFANA_API_KEY = os.getenv("GRAFANA_API_KEY") 

async def send_metrics_to_grafana():
    if not all([GRAFANA_URL, GRAFANA_API_KEY]):
        # No warning on every tick, just return silently if not configured
        return

    # InfluxDB line protocol format: measurement,tag1=val1 field1=val2 timestamp_ns
    timestamp_ns = int(time.time() * 1e9)
    cpu_percent = psutil.cpu_percent()
    mem_info = psutil.virtual_memory()

    lines = [
        f"system,host=insta-helper-backend cpu_percent={cpu_percent},memory_used_bytes={mem_info.used},memory_total_bytes={mem_info.total} {timestamp_ns}"
    ]
    payload = "\n".join(lines)

    headers = {
        "Authorization": f"Bearer {GRAFANA_API_KEY}",
        "Content-Type": "text/plain"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(GRAFANA_URL, content=payload, headers=headers, timeout=10)
            resp.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to push metrics to Grafana: {e}")

async def monitoring_loop(interval_seconds: int = 60):
    # wait a bit before starting the first collection
    await asyncio.sleep(5)
    while True:
        await send_metrics_to_grafana()
        await asyncio.sleep(interval_seconds)
