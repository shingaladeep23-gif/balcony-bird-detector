import os
import time
import logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import List, Dict, Any
from contextlib import asynccontextmanager

from detector import BirdDetector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("App")

# Global detector instance
detector = BirdDetector()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: load and start detector thread
    logger.info("Starting bird detector engine...")
    detector.start()
    yield
    # Shutdown: cleanly stop detector thread
    logger.info("Stopping bird detector engine...")
    detector.stop()

app = FastAPI(
    title="Balcony Bird Detector API", 
    version="1.0.0",
    lifespan=lifespan
)

# Ensure captures folder exists
os.makedirs("static/captures", exist_ok=True)

# Mount static folder for CSS, JS, Images, and Logs
app.mount("/static", StaticFiles(directory="static"), name="static")

# Request Models
class ZonePoint(BaseModel):
    x: float = Field(..., ge=0.0, le=1.0)
    y: float = Field(..., ge=0.0, le=1.0)

class ConfigUpdate(BaseModel):
    camera_url: str
    telegram_bot_token: str
    telegram_chat_id: str
    confidence_threshold: float = Field(..., ge=0.1, le=1.0)
    cooldown_minutes: int = Field(..., ge=1, le=1440)
    consecutive_frames: int = Field(..., ge=1, le=100)
    detection_zone: List[ZonePoint]
    arduino_port: str
    arduino_enabled: bool

@app.get("/")
async def serve_dashboard():
    """Serves the dashboard home HTML file directly at the root URL."""
    index_path = "static/index.html"
    if not os.path.exists(index_path):
        raise HTTPException(status_code=404, detail="Dashboard index.html not found.")
    return FileResponse(index_path)

@app.get("/api/config")
async def get_config():
    """Returns the current active detector configuration."""
    return detector.config

@app.post("/api/config")
async def post_config(new_config: ConfigUpdate):
    """Updates the config file and updates the active detector state in real time."""
    updated_dict = new_config.dict()
    detector.save_config(updated_dict)
    return {"status": "success", "message": "Configuration updated successfully."}

@app.get("/api/logs")
async def get_logs():
    """Returns historical bird visit log entries from logs.json."""
    logs_file = "static/captures/logs.json"
    if not os.path.exists(logs_file):
        return []
    try:
        with open(logs_file, "r") as f:
            import json
            return json.load(f)
    except Exception as e:
        logger.error(f"Error reading logs: {e}")
        return []

@app.get("/api/status")
async def get_status():
    """Returns connectivity and active runtime metrics."""
    return {
        "camera_status": detector.camera_status,
        "model_status": detector.model_status,
        "arduino_status": detector.arduino_status,
        "arduino_enabled": detector.config.get("arduino_enabled", False),
        "consecutive_counter": f"{detector.consecutive_frames_counter}/{detector.config.get('consecutive_frames', 5)}",
        "last_alert_time": detector.last_alert_time
    }

@app.post("/api/test-notification")
async def send_test():
    """Triggers an instant mock Telegram alert with a test image to verify bot credentials."""
    success, message = detector.send_test_telegram()
    if not success:
        return JSONResponse(status_code=400, content={"status": "error", "message": message})
    return {"status": "success", "message": message}

@app.post("/api/trigger-spray")
async def trigger_spray():
    """Manually triggers a test water spray command over serial."""
    success, message = detector.trigger_manual_spray()
    if not success:
        return JSONResponse(status_code=400, content={"status": "error", "message": message})
    return {"status": "success", "message": message}

# Stream Frame generator for video tags
def frame_generator():
    """Generator yielding annotated frames wrapped in MJPEG format."""
    while True:
        frame_bytes = detector.get_latest_frame_bytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        # Approximately 15 FPS stream output
        time.sleep(0.06)

@app.get("/api/stream")
async def get_stream():
    """Exposes real-time annotated live camera feed for standard HTML img tags."""
    return StreamingResponse(
        frame_generator(), 
        media_type="multipart/x-mixed-replace; boundary=frame"
    )
