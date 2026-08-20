import io
import requests
from PIL import Image, ImageDraw, ImageFont
import streamlit as st


st.set_page_config(page_title="Textile Defect Detection", layout="wide")

st.title("Textile Defect Detection")
st.subheader("Hangzhou 2026 POC")
st.write("Upload a textile/fabric image to detect and visualize fabric defects.")

sidebar = st.sidebar
backend_url = sidebar.text_input("FastAPI Backend URL", "http://127.0.0.1:8000")
sidebar.markdown("\nChange the backend URL if your FastAPI server runs on a different host or port.")


def check_backend(url: str) -> bool:
    try:
        # Treat any response as evidence the host is reachable
        requests.get(url, timeout=1)
        return True
    except requests.RequestException:
        return False


connected = check_backend(backend_url)
status_text = "Connected" if connected else "Not Connected"
st.info(f"FastAPI Backend: {status_text}")


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
        st.image(image, caption="Original image", use_column_width=True)
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
                # Draw boxes
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

                    # Ensure coordinates are floats
                    try:
                        box = [float(x1), float(y1), float(x2), float(y2)]
                    except Exception:
                        continue

                    # Draw rectangle and label
                    draw.rectangle(box, outline="red", width=3)
                    label = f"{cls} — {round(float(conf) * 100, 1)}%"
                    text_size = draw.textsize(label, font=font) if font else (0, 0)
                    text_bg = [box[0], box[1] - text_size[1] - 4, box[0] + text_size[0] + 4, box[1]]
                    draw.rectangle(text_bg, fill="red")
                    draw.text((box[0] + 2, box[1] - text_size[1] - 2), label, fill="white", font=font)

                with cols[1]:
                    st.image(annotated, caption="Annotated result", use_column_width=True)

                # Results table
                st.subheader("Detection Results")
                st.write(f"Defects detected: {len(detections)}")
                rows = []
                for det in detections:
                    cls = det.get("class_name", str(det.get("class_id", "?")))
                    conf = det.get("confidence", 0.0)
                    rows.append({"Defect": cls, "Confidence": f"{round(float(conf) * 100, 1)}%"})

                st.table(rows)
