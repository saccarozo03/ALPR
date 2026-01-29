# app.py
# Run: streamlit run app.py

import os
import streamlit as st

from config import AppConfig
from db import ParkingDB
from auth import is_logged_in, render_login, render_logout
from image_io import bgr_from_bytes, bgr_to_rgb, save_pair
from engine import run_yolo_ocr, decide_in_out, now_ts
from model_loader import load_models

CFG = AppConfig()

# ----------- Page config (UI first) -----------
st.set_page_config(page_title="Parking LPR Live", layout="wide")
st.title("Parking LPR — Live Camera Capture (Render-first + Lazy-load)")

# ----------- DB init (cheap, safe) -----------
db = ParkingDB(CFG.db_path)
db.init()

# ----------- Sidebar: Auth + Model + Rates (UI first) -----------
with st.sidebar:
    st.header("Tài khoản")
    if not is_logged_in():
        render_login(CFG.users)
    else:
        st.write(f"User: **{st.session_state.get('username','')}**")
        render_logout()

    st.divider()
    st.header("Model (Lazy load)")

    loaded = st.session_state.get("model_loaded", False)
    st.write("Trạng thái:", "Đã load" if loaded else "Chưa load")
    st.caption(CFG.model_path)

    colA, colB = st.columns(2)
    with colA:
        if st.button("Load models", key="btn_load_models"):
            try:
                with st.spinner("Loading YOLO + PaddleOCR..."):
                    yolo, ocr = load_models(CFG.model_path)
                st.session_state["yolo"] = yolo
                st.session_state["ocr"] = ocr
                st.session_state["model_loaded"] = True
                st.success("Load model OK.")
                st.rerun()
            except Exception as e:
                st.session_state["model_loaded"] = False
                st.error("Load model FAIL.")
                st.exception(e)

    with colB:
        if st.button("Unload", key="btn_unload_models"):
            st.session_state.pop("yolo", None)
            st.session_state.pop("ocr", None)
            st.session_state["model_loaded"] = False
            st.success("Unloaded.")
            st.rerun()

    st.divider()
    st.header("Giá theo ngày")

    if "rates" not in st.session_state:
        st.session_state["rates"] = {"motorbike": 5000, "car": 20000}

    rates = st.session_state["rates"]
    rates["motorbike"] = st.number_input(
        "Xe máy (VND/ngày)",
        min_value=0,
        value=int(rates["motorbike"]),
        step=1000,
        key="rate_motorbike",
    )
    rates["car"] = st.number_input(
        "Ô tô (VND/ngày)",
        min_value=0,
        value=int(rates["car"]),
        step=1000,
        key="rate_car",
    )
    st.session_state["rates"] = rates

# ----------- Dashboard today -----------
total_fee, counts = db.today_summary()
d1, d2, d3 = st.columns(3)
d1.metric("Doanh thu hôm nay (OUT)", f"{total_fee:,} VND")
d2.metric("Lượt OUT xe máy", counts.get("motorbike", 0))
d3.metric("Lượt OUT ô tô", counts.get("car", 0))

st.divider()

# ----------- Main UI (render first) -----------
st.subheader("Live Camera")

# (UI-first) init default vehicle type for fee calculation
if "vehicle_type" not in st.session_state:
    st.session_state["vehicle_type"] = "car"

vehicle_type = st.radio(
    "Loại xe (dùng để tính tiền khi OUT)",
    ["motorbike", "car"],
    index=0 if st.session_state["vehicle_type"] == "motorbike" else 1,
    format_func=lambda x: "Xe máy" if x == "motorbike" else "Ô tô",
    key="vehicle_type_widget",
)

# sync widget -> canonical state (avoid Streamlit key conflicts)
st.session_state["vehicle_type"] = st.session_state["vehicle_type_widget"]

shot = st.camera_input("Bấm chụp để nhận diện", key="camera_shot")

st.caption(
    "Luồng: Chụp → YOLO detect → OCR → chuẩn hoá → tra DB trong ngày → tự IN/OUT "
    "→ tính tiền theo loại xe (chọn tay) khi OUT → lưu & hiển thị so sánh khi OUT"
)

# If no shot, stop here
if shot is None:
    st.info("Mở camera và bấm chụp để hệ thống nhận diện.")
    st.stop()

# Validate model loaded
if not st.session_state.get("model_loaded", False):
    st.warning("Bạn chưa load model. Hãy bấm 'Load models' ở sidebar trước.")
    st.stop()

yolo = st.session_state.get("yolo")
ocr = st.session_state.get("ocr")
if yolo is None or ocr is None:
    st.warning("Model chưa sẵn sàng. Hãy Load lại.")
    st.stop()

# Decode image from camera
img_bgr = bgr_from_bytes(shot.getvalue())
if img_bgr is None:
    st.error("Không decode được ảnh từ camera.")
    st.stop()

# Inference with try/except
try:
    with st.spinner("Đang dự đoán YOLO + OCR..."):
        out = run_yolo_ocr(yolo, ocr, img_bgr)

    if out is None:
        st.warning("Không phát hiện biển số.")
        st.image(bgr_to_rgb(img_bgr), caption="Ảnh chụp", use_container_width=True)
        st.stop()

    # Use current vehicle_type (manual)
    vehicle_type = st.session_state.get("vehicle_type", "car")

    plate_canon = out["plate_canon"]
    plate_display = out["plate_display"]

    c1, c2 = st.columns(2)
    with c1:
        st.image(bgr_to_rgb(out["annotated"]), caption="Ảnh + bbox", use_container_width=True)
    with c2:
        st.image(bgr_to_rgb(out["crop"]), caption="Crop biển số", use_container_width=True)
        st.write("Raw:", out["raw_text"])
        st.write("Plate:", plate_display)
        st.write("Canon:", plate_canon)

    if not plate_canon:
        st.warning("OCR chưa ra biển số hợp lệ. Bạn chụp lại giúp.")
        st.stop()

    # Decide IN/OUT by DB (in-day)
    action = decide_in_out(db, plate_canon)
    last_in = db.latest_in_today(plate_canon) if action == "OUT" else None

    # Fee: only on OUT (manual vehicle_type)
    rates = st.session_state.get("rates", {"motorbike": 5000, "car": 20000})
    fee = int(rates.get(vehicle_type, 0)) if action == "OUT" else 0

    ts = now_ts()
    full_path, crop_path = save_pair(CFG.run_dir, out["annotated"], out["crop"])

    # IMPORTANT: insert_event signature MUST match db.py (vehicle_type + fee)
    db.insert_event(ts, action, vehicle_type, plate_canon, plate_display, fee, full_path, crop_path)

    vt_label = "Xe máy" if vehicle_type == "motorbike" else "Ô tô"
    st.success(
        f"Hệ thống xác định: **{action}** | **{plate_display}** | "
        f"loại={vt_label} | fee={fee:,} VND | time={ts}"
    )

    # Compare IN vs OUT
    if action == "OUT" and last_in is not None:
        st.subheader("So sánh IN vs OUT (trong ngày)")
        colA, colB = st.columns(2)

        with colA:
            st.markdown("### Ảnh lúc IN (gần nhất hôm nay)")
            if last_in.get("img_path") and os.path.exists(last_in["img_path"]):
                st.image(last_in["img_path"], caption=f"IN @ {last_in['ts']}", use_container_width=True)
            if last_in.get("crop_path") and os.path.exists(last_in["crop_path"]):
                st.image(last_in["crop_path"], caption="Crop IN", use_container_width=True)

        with colB:
            st.markdown("### Ảnh hiện tại (OUT)")
            st.image(bgr_to_rgb(out["annotated"]), caption=f"OUT @ {ts}", use_container_width=True)
            st.image(bgr_to_rgb(out["crop"]), caption="Crop OUT", use_container_width=True)

except Exception as e:
    st.error("Có lỗi khi chạy pipeline.")
    st.exception(e)

st.divider()
st.subheader("Nhật ký gần đây")
rows = db.recent_events(limit=20)
for ts, action, vtype, plate_disp, plate_canon, fee, img_path, crop_path in rows:
    vt = "Xe máy" if vtype == "motorbike" else "Ô tô"
    st.write(f"{ts} | {action} | {vt} | {plate_disp} | fee={int(fee):,} VND | canon={plate_canon}")
