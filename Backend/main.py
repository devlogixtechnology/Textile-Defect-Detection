import tempfile
import os
import logging
import sys
from pathlib import Path
from typing import Optional
from dataclasses import asdict

from fastapi import FastAPI, File, UploadFile, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CME2_SCRIPTS = PROJECT_ROOT / "Confidence_Calibration" / "scripts"
if CME2_SCRIPTS.exists() and str(CME2_SCRIPTS) not in sys.path:
    sys.path.append(str(CME2_SCRIPTS))

try:
    from alert_policy import AlertPolicy, load_policy_config
except Exception:  # pragma: no cover - backend can still serve raw detections
    AlertPolicy = None
    load_policy_config = None

try:
    from SED_1_Multi_Camera.scripts.config import load_camera_configs
    from SED_1_Multi_Camera.scripts.detector import SharedYOLODetector
    from SED_1_Multi_Camera.scripts.stream_manager import MultiCameraStreamManager
except Exception:  # pragma: no cover - optional SED-1 demo layer
    load_camera_configs = None
    SharedYOLODetector = None
    MultiCameraStreamManager = None

logger = logging.getLogger("uvicorn.error")

api_app = FastAPI(title="Textile Defect Detection API")

api_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Lazy model holder
MODEL = None
MODEL_PATH: Optional[Path] = None
ALERT_POLICY = None
ALERT_CONFIG_PATH = PROJECT_ROOT / "Confidence_Calibration" / "configs" / "calibrated_thresholds.yaml"
CAMERA_CONFIG_PATH = PROJECT_ROOT / "SED_1_Multi_Camera" / "configs" / "cameras.yaml"
STREAM_MANAGER = None


def find_model_path() -> Optional[Path]:
    candidates = [Path("best.pt"), Path(__file__).parent / "best.pt"]
    for p in candidates:
        if p.exists():
            return p
    return None


@api_app.on_event("startup")
def load_model_on_startup():
    global MODEL, MODEL_PATH, ALERT_POLICY
    MODEL_PATH = find_model_path()
    if MODEL_PATH is None:
        logger.warning("No model file (best.pt) found; /predict will return 503 until a model is placed.")
        return

    try:
        # Import ultralytics only when model file exists
        from ultralytics import YOLO

        MODEL = YOLO(str(MODEL_PATH))
        logger.info(f"Loaded YOLO model from {MODEL_PATH}")
    except Exception as e:
        MODEL = None
        logger.warning(f"Failed to load ultralytics YOLO model: {e}")

    if AlertPolicy is not None and load_policy_config is not None:
        try:
            ALERT_POLICY = AlertPolicy(load_policy_config(ALERT_CONFIG_PATH))
            logger.info(f"Loaded alert policy from {ALERT_CONFIG_PATH}")
        except Exception as e:
            ALERT_POLICY = None
            logger.warning(f"Failed to load alert policy from {ALERT_CONFIG_PATH}: {e}")


def _require_stream_manager():
    if STREAM_MANAGER is None:
        raise HTTPException(status_code=404, detail="Multi-camera streams are not running. Call POST /streams/start first.")
    return STREAM_MANAGER


@api_app.post("/predict")
async def predict(
    file: UploadFile = File(...),
    apply_alert_policy: bool = Query(False, description="Apply CME-2 confidence calibration and temporal alert policy."),
    frame_index: int = Query(0, description="Frame index for temporal confirmation when apply_alert_policy=true."),
    timestamp_sec: Optional[float] = Query(None, description="Frame timestamp for temporal confirmation."),
):
    """Accepts multipart/form-data with field name 'file'. Returns detections in x1,y1,x2,y2 pixel coordinates."""
    if MODEL is None:
        raise HTTPException(status_code=503, detail="Model not available on server. Place best.pt in the backend folder and ensure ultralytics is installed.")

    # Save uploaded file to a temp file
    suffix = Path(file.filename).suffix or ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        results = MODEL.predict(source=str(tmp_path), verbose=False)
        res = results[0]
        api_detections = []
        if res.boxes is not None:
            for box, confidence, class_id in zip(
                res.boxes.xyxy.cpu().tolist(),
                res.boxes.conf.cpu().tolist(),
                res.boxes.cls.cpu().tolist(),
            ):
                class_id = int(class_id)
                api_detections.append({
                    "class_id": class_id,
                    "class_name": res.names.get(class_id, str(class_id)),
                    "confidence": float(confidence),
                    "coordinates": {
                        "x1": float(box[0]),
                        "y1": float(box[1]),
                        "x2": float(box[2]),
                        "y2": float(box[3]),
                    },
                })

        response = {"filename": file.filename, "detections": api_detections}
        if apply_alert_policy:
            if ALERT_POLICY is None:
                raise HTTPException(status_code=503, detail="Alert policy is not available. Check CME-2 configuration.")
            response["alert_policy"] = ALERT_POLICY.process_frame(
                api_detections,
                frame_index=frame_index,
                timestamp_sec=timestamp_sec,
            )
        return response
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass


@api_app.get("/cameras")
def list_cameras():
    if load_camera_configs is None:
        raise HTTPException(status_code=503, detail="SED-1 camera configuration loader is not available.")
    try:
        cameras = load_camera_configs(CAMERA_CONFIG_PATH)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    statuses = {status.camera_id: asdict(status) for status in STREAM_MANAGER.statuses()} if STREAM_MANAGER else {}
    return {
        "cameras": [
            {
                "camera_id": camera.camera_id,
                "name": camera.name,
                "source": camera.source,
                "enabled": camera.enabled,
                "monitored_classes": sorted(camera.monitored_classes),
                "geofences": [
                    {
                        "id": geofence.id,
                        "enabled": geofence.enabled,
                        "classes": sorted(geofence.classes),
                        "polygon": geofence.polygon,
                    }
                    for geofence in camera.geofences
                ],
                "status": statuses.get(camera.camera_id),
            }
            for camera in cameras
        ]
    }


@api_app.post("/streams/start")
def start_streams(
    streams: int = Query(3, ge=1, le=4),
    queue_size: int = Query(2, ge=1, le=16),
    imgsz: int = Query(640, ge=160, le=1280),
    device: Optional[str] = Query(None),
):
    global STREAM_MANAGER
    if MODEL_PATH is None:
        raise HTTPException(status_code=503, detail="Model checkpoint is not available.")
    if any(component is None for component in (load_camera_configs, SharedYOLODetector, MultiCameraStreamManager, AlertPolicy, load_policy_config)):
        raise HTTPException(status_code=503, detail="SED-1 stream dependencies are not available.")
    if STREAM_MANAGER is not None:
        STREAM_MANAGER.stop()
    cameras = load_camera_configs(CAMERA_CONFIG_PATH, limit=streams)
    detector = SharedYOLODetector(MODEL_PATH, device=device, imgsz=imgsz)
    STREAM_MANAGER = MultiCameraStreamManager(
        cameras,
        detector,
        alert_policy_factory=lambda: AlertPolicy(load_policy_config(ALERT_CONFIG_PATH)),
        queue_size=queue_size,
        micro_batch=True,
    )
    STREAM_MANAGER.start()
    return {"status": "started", "streams": len(cameras), "queue_size": queue_size, "imgsz": imgsz}


@api_app.post("/streams/stop")
def stop_streams():
    global STREAM_MANAGER
    manager = _require_stream_manager()
    manager.stop()
    STREAM_MANAGER = None
    return {"status": "stopped"}


@api_app.get("/cameras/{camera_id}/status")
def camera_status(camera_id: str):
    manager = _require_stream_manager()
    for status in manager.statuses():
        if status.camera_id == camera_id:
            return asdict(status)
    raise HTTPException(status_code=404, detail=f"Unknown camera: {camera_id}")


@api_app.get("/cameras/{camera_id}/latest")
def camera_latest(camera_id: str):
    manager = _require_stream_manager()
    result = manager.latest_results.get(camera_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"No result is available for {camera_id} yet.")
    return asdict(result)


@api_app.get("/alerts")
def list_alerts(limit: int = Query(50, ge=1, le=500)):
    manager = _require_stream_manager()
    return {"alerts": manager.active_alerts[-limit:]}
