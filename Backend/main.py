import tempfile
import os
import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware

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


def find_model_path() -> Optional[Path]:
    candidates = [Path("best.pt"), Path(__file__).parent / "best.pt"]
    for p in candidates:
        if p.exists():
            return p
    return None


@api_app.on_event("startup")
def load_model_on_startup():
    global MODEL, MODEL_PATH
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


@api_app.post("/predict")
async def predict(file: UploadFile = File(...)):
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

        return {"filename": file.filename, "detections": api_detections}
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass
