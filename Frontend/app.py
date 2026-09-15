import io

import requests
import streamlit as st
from PIL import Image, ImageDraw, ImageFont


st.set_page_config(page_title="Textile Defect Detection", layout="wide")

st.title("Textile Defect Detection")
st.subheader("Hangzhou 2026 POC")

sidebar = st.sidebar
backend_url = sidebar.text_input("FastAPI Backend URL", "http://127.0.0.1:8000")
sidebar.markdown("\nChange the backend URL if your FastAPI server runs on a different host or port.")


def check_backend(url: str) -> bool:
    try:
        requests.get(url, timeout=1)
        return True
    except requests.RequestException:
        return False


connected = check_backend(backend_url)
status_text = "Connected" if connected else "Not Connected"
st.info(f"FastAPI Backend: {status_text}")

image_tab, camera_tab = st.tabs(["Image Inference", "Multi-Camera Monitor"])

with camera_tab:
    st.subheader("SED-1 / SED-2 Multi-Camera Monitor")
    controls = st.columns([1, 1, 2])
    stream_count = controls[0].selectbox("Streams", [1, 2, 3, 4], index=2)
    queue_size = controls[1].number_input("Queue size", min_value=1, max_value=16, value=2)
    if controls[2].button("Start streams"):
        try:
            response = requests.post(
                backend_url.rstrip("/") + f"/streams/start?streams={stream_count}&queue_size={queue_size}",
                timeout=(5, 30),
            )
            if response.status_code == 200:
                st.success("Multi-camera streams started.")
            else:
                st.error(response.text)
        except requests.RequestException as exc:
            st.error(f"Unable to start streams: {exc}")
    if st.button("Stop streams"):
        try:
            response = requests.post(backend_url.rstrip("/") + "/streams/stop", timeout=(5, 10))
            if response.status_code == 200:
                st.success("Multi-camera streams stopped.")
            else:
                st.error(response.text)
        except requests.RequestException as exc:
            st.error(f"Unable to stop streams: {exc}")

    try:
        cameras_response = requests.get(backend_url.rstrip("/") + "/cameras", timeout=(3, 10))
        if cameras_response.status_code == 200:
            cameras = cameras_response.json().get("cameras", [])
            active_events = []
            camera_severity = {}
            try:
                active_response = requests.get(backend_url.rstrip("/") + "/alerts/active", timeout=(3, 10))
                if active_response.status_code == 200:
                    active_payload = active_response.json()
                    active_events = active_payload.get("events", [])
                    camera_severity = active_payload.get("camera_overall_severity", {})
            except requests.RequestException:
                active_events = []
            status_rows = []
            for camera in cameras:
                status = camera.get("status") or {}
                status_rows.append(
                    {
                        "Camera": camera["name"],
                        "ID": camera["camera_id"],
                        "Status": status.get("status", "not running"),
                        "Processed": status.get("processed", 0),
                        "FPS": round(float(status.get("processed_fps", 0.0)), 2),
                        "Drop %": round(float(status.get("drop_rate_pct", 0.0)), 2),
                        "Severity": camera_severity.get(camera["camera_id"], "normal").upper(),
                        "Classes": ", ".join(camera.get("monitored_classes", [])),
                    }
                )
            st.table(status_rows)
            critical_events = [event for event in active_events if event.get("severity") == "critical"]
            warning_events = [event for event in active_events if event.get("severity") == "warning"]
            info_events = [event for event in active_events if event.get("severity") == "info"]
            if critical_events:
                st.error("SIMULATED SAFETY SHUTDOWN TRIGGERED")
                st.table(critical_events)
            if warning_events:
                st.warning("Active warning-level safety events")
                st.table(warning_events)
            if info_events:
                st.info("Active info-level safety events")
                st.table(info_events)
        else:
            st.warning("Camera configuration is not available from the backend.")
    except requests.RequestException:
        st.warning("Start the FastAPI backend to view multi-camera status.")

    try:
        alerts_response = requests.get(backend_url.rstrip("/") + "/alerts", timeout=(3, 10))
        if alerts_response.status_code == 200:
            payload = alerts_response.json()
            alerts = payload.get("sed2_active_events", [])
            cme2_alerts = payload.get("cme2_alerts", [])
            st.subheader("Active SED-2 Alerts")
            st.table(alerts[-10:] if alerts else [])
            st.subheader("Recent CME-2 Confirmations")
            st.table(cme2_alerts[-10:] if cme2_alerts else [])
    except requests.RequestException:
        pass

    try:
        iot_response = requests.get(backend_url.rstrip("/") + "/iot/status", timeout=(3, 10))
        if iot_response.status_code == 200:
            iot = iot_response.json()
            if iot.get("state") == "SHUTDOWN_TRIGGERED":
                st.error(f"Mock IoT relay: {iot.get('state')} ({iot.get('trigger_count')} trigger)")
            else:
                st.caption(f"Mock IoT relay: {iot.get('state', 'not started')}")
    except requests.RequestException:
        pass

with image_tab:
    st.write("Upload a textile/fabric image to detect and visualize fabric defects.")
    uploaded_file = st.file_uploader("Upload an image (JPG, JPEG, PNG)", type=["jpg", "jpeg", "png"])

    if uploaded_file is not None:
        try:
            image_bytes = uploaded_file.read()
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        except Exception:
            st.error("Unable to read the uploaded image. Please upload a valid JPG/PNG file.")
            uploaded_file = None

    if uploaded_file is not None:
        cols = st.columns([1, 1])
        with cols[0]:
            st.image(image, caption="Original image", width="stretch")
            st.write(f"Dimensions: {image.width} x {image.height} pixels")

        detect = st.button("Detect Defects")

        if detect:
            predict_url = backend_url.rstrip("/") + "/predict"
            with st.spinner("Sending image to FastAPI for inference..."):
                try:
                    files = {"file": (uploaded_file.name, image_bytes, uploaded_file.type or "image/jpeg")}
                    resp = requests.post(predict_url, files=files, timeout=(5, 30))
                except requests.ConnectionError:
                    st.error("FastAPI backend is unavailable. Please start the backend and try again.")
                    st.stop()
                except requests.Timeout:
                    st.error("Request to backend timed out. Try again or increase timeout.")
                    st.stop()
                except requests.RequestException as e:
                    st.error(f"Request failed: {e}")
                    st.stop()

            if resp.status_code != 200:
                st.error(f"Backend returned status code {resp.status_code}")
            else:
                try:
                    data = resp.json()
                except Exception:
                    st.error("Backend returned an unexpected response (not valid JSON).")
                    st.stop()

                detections = data.get("detections", [])

                if not detections:
                    st.success("No defects detected.")
                else:
                    annotated = image.copy()
                    draw = ImageDraw.Draw(annotated)
                    try:
                        font = ImageFont.load_default()
                    except Exception:
                        font = None

                    for det in detections:
                        coords = det.get("coordinates", {})
                        x1 = coords.get("x1")
                        y1 = coords.get("y1")
                        x2 = coords.get("x2")
                        y2 = coords.get("y2")
                        cls = det.get("class_name", str(det.get("class_id", "?")))
                        conf = det.get("confidence", 0.0)

                        if None in (x1, y1, x2, y2):
                            continue

                        try:
                            box = [float(x1), float(y1), float(x2), float(y2)]
                        except Exception:
                            continue

                        draw.rectangle(box, outline="red", width=3)
                        label = f"{cls} - {round(float(conf) * 100, 1)}%"
                        text_bbox = draw.textbbox((0, 0), label, font=font) if font else (0, 0, 0, 0)
                        text_width = text_bbox[2] - text_bbox[0]
                        text_height = text_bbox[3] - text_bbox[1]
                        text_bg = [box[0], box[1] - text_height - 4, box[0] + text_width + 4, box[1]]
                        draw.rectangle(text_bg, fill="red")
                        draw.text((box[0] + 2, box[1] - text_height - 2), label, fill="white", font=font)

                    with cols[1]:
                        st.image(annotated, caption="Annotated result", width="stretch")

                    st.subheader("Detection Results")
                    st.write(f"Defects detected: {len(detections)}")
                    rows = []
                    for det in detections:
                        cls = det.get("class_name", str(det.get("class_id", "?")))
                        conf = det.get("confidence", 0.0)
                        rows.append({"Defect": cls, "Confidence": f"{round(float(conf) * 100, 1)}%"})

                    st.table(rows)
