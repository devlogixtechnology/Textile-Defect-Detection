# Textile Defect Detection — Streamlit Dashboard

## Purpose

This Streamlit dashboard provides a simple, non-technical UI to upload textile
images and visualize defect detections produced by the project's FastAPI
inference backend.

## Architecture

Streamlit
   ↓
FastAPI `/predict`
   ↓
YOLOv8 Model

## Prerequisites

- Python 3.10+ (or matching your environment)
- FastAPI backend running and reachable (see below)

The FastAPI application object in `Backend_fastapi_endpoint/fastapi_endpoint.ipynb` is named
`api_app`. For local testing the Streamlit dashboard assumes the FastAPI server is
available at the default URL `http://127.0.0.1:8000`. You can change the backend
URL from the Streamlit sidebar.

## Start the FastAPI backend

The original notebook uses FastAPI's `TestClient` for in-notebook validation and
does not run a standalone server. To run a local server for the dashboard, start
Uvicorn with the application object `api_app` (module and app name may vary if
you convert the notebook to a module). A typical command (replace module path
as needed):

```bash
uvicorn main:api_app --host 127.0.0.1 --port 8000
```

If you keep the notebook as-is, run the notebook in an environment (Colab or
local Jupyter) and expose the app differently; the dashboard expects a reachable
HTTP endpoint at `/predict` that accepts `multipart/form-data` uploads with the
file field name `file`.

## Run the Dashboard

From the repository root:

```bash
pip install -r Streamlit/requirements.txt
streamlit run Streamlit/app.py
```

## Usage

1. Start the FastAPI backend (see above).
2. Start the Streamlit dashboard.
3. Open the Streamlit page in your browser.
4. Upload a JPG/PNG textile image.
5. Click `Detect Defects`.
6. View annotated image and detection table (class + confidence).
