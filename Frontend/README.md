# Textile Defect Detection - Frontend Dashboard

## Purpose

This Streamlit dashboard provides a simple UI for uploading textile or
industrial-scene images and visualizing detections returned by the FastAPI
backend.

## Architecture

```text
Frontend Streamlit
  |
FastAPI /predict
  |
YOLOv8 model
```

## Prerequisites

- Python 3.10+
- FastAPI backend running at `http://127.0.0.1:8000`
- Frontend dependencies installed from `Frontend/requirements.txt`

## Start the FastAPI Backend

From the repository root:

```bash
python -m uvicorn Backend.main:api_app --host 127.0.0.1 --port 8000
```

The backend loads `Backend/best.pt`, which should be the expanded 12-class
checkpoint.

## Run the Dashboard

From the repository root, in a second terminal:

```bash
pip install -r Frontend/requirements.txt
streamlit run Frontend/app.py
```

## Usage

1. Start the FastAPI backend.
2. Start the Streamlit frontend.
3. Open the Streamlit URL in your browser.
4. Upload a JPG, JPEG, or PNG image.
5. Click `Detect Defects`.
6. Review the annotated image and detection table.
