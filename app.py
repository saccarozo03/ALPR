# app.py
# Run: streamlit run app.py

import base64
import math
import os
from datetime import datetime
import streamlit as st
import streamlit.components.v1 as components

from config import AppConfig
from db import ParkingDB
from auth import is_logged_in, render_login, render_logout
from image_io import bgr_from_bytes, bgr_to_rgb, save_pair
from engine import run_yolo_ocr, decide_in_out, now_ts
from model_loader import load_models

CFG = AppConfig()
camera_selector = components.declare_component("camera_selector", path="camera_component")

def parse_ts(ts: str) -> datetime:
    return datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")

def compute_fee(duration_minutes: int, rate: dict, grace_minutes: int) -> int:
    if duration_minutes <= grace_minutes:
        return 0
    billable_minutes = max(0, duration_minutes - grace_minutes)
    billable_hours = math.ceil(billable_minutes / 60)
    fee = int(rate.get("first_hour", 0)) + max(0, billable_hours - 1) * int(rate.get("hourly", 0))
    daily_cap = int(rate.get("daily_cap", 0))
    if daily_cap > 0:
        fee = min(fee, daily_cap)
    return int(fee)

def bytes_from_data_url(data_url: str) -> bytes | None:
    if not data_url or "base64," not in data_url:
        return None
    _, encoded = data_url.split("base64,", 1)
    try:
        return base64.b64decode(encoded)
    except (ValueError, TypeError):
        return None

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
    is_admin = st.session_state.get("username") in CFG.admin_users

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
    st.header("Cấu hình giá")
    if not is_admin:
        st.info("Chỉ admin mới được chỉnh giá.")

    if "rates" not in st.session_state:
        st.session_state["rates"] = {
            "motorbike": {"first_hour": 5000, "hourly": 2000, "daily_cap": 20000},
            "car": {"first_hour": 20000, "hourly": 10000, "daily_cap": 100000},
            "grace_minutes": 10,
        }

    rates = st.session_state["rates"]
    rates["grace_minutes"] = st.number_input(
        "Miễn phí phút đầu (grace)",
        min_value=0,
        value=int(rates.get("grace_minutes", 0)),
        step=1,
        key="rate_grace_minutes",
        disabled=not is_admin,
    )

    st.subheader("Xe máy")
    rates["motorbike"]["first_hour"] = st.number_input(
        "Phí giờ đầu (VND)",
        min_value=0,
        value=int(rates["motorbike"]["first_hour"]),
        step=1000,
        key="rate_motorbike_first",
        disabled=not is_admin,
    )
    rates["motorbike"]["hourly"] = st.number_input(
        "Phí mỗi giờ tiếp theo (VND)",
        min_value=0,
        value=int(rates["motorbike"]["hourly"]),
        step=1000,
        key="rate_motorbike_hourly",
        disabled=not is_admin,
    )
    rates["motorbike"]["daily_cap"] = st.number_input(
        "Trần phí/ngày (0 = không giới hạn)",
        min_value=0,
        value=int(rates["motorbike"].get("daily_cap", 0)),
        step=1000,
        key="rate_motorbike_cap",
        disabled=not is_admin,
    )

    st.subheader("Ô tô")
    rates["car"]["first_hour"] = st.number_input(
        "Phí giờ đầu (VND)",
        min_value=0,
        value=int(rates["car"]["first_hour"]),
        step=1000,
        key="rate_car_first",
        disabled=not is_admin,
    )
    rates["car"]["hourly"] = st.number_input(
        "Phí mỗi giờ tiếp theo (VND)",
        min_value=0,
        value=int(rates["car"]["hourly"]),
        step=1000,
        key="rate_car_hourly",
        disabled=not is_admin,
    )
    rates["car"]["daily_cap"] = st.number_input(
        "Trần phí/ngày (0 = không giới hạn)",
        min_value=0,
        value=int(rates["car"].get("daily_cap", 0)),
        step=1000,
        key="rate_car_cap",
        disabled=not is_admin,
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

camera_source = st.selectbox(
    "Nguồn camera",
    ["Mặc định (trình duyệt)", "Chọn camera ngoài (USB/HDMI)"],
    key="camera_source",
)

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

shot_bytes = None
if camera_source == "Mặc định (trình duyệt)":
    shot = st.camera_input("Bấm chụp để nhận diện", key="camera_shot")
    if shot is not None:
        shot_bytes = shot.getvalue()
else:
    st.caption("Chọn camera ngoài từ danh sách bên dưới, bật camera rồi bấm chụp.")
    external_capture = camera_selector(label="Camera ngoài", key="external_camera")
    if isinstance(external_capture, dict):
        data_url = external_capture.get("data_url")
        shot_bytes = bytes_from_data_url(data_url)
        device_label = external_capture.get("device_label")
        if shot_bytes and device_label:
            st.success(f"Đã nhận ảnh từ: {device_label}")

st.caption(
    "Luồng: Chụp → YOLO detect → OCR → chuẩn hoá → tra DB mở phiên → tự IN/OUT "
    "→ tính tiền theo thời lượng khi OUT → lưu & hiển thị so sánh khi OUT"
)

# If no shot, stop here
if shot_bytes is None:
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
img_bgr = bgr_from_bytes(shot_bytes)
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

    # Decide IN/OUT by DB (open session)
    action = decide_in_out(db, plate_canon)
    last_in = db.latest_in(plate_canon) if action == "OUT" else None
    last_in_today = db.latest_in_today(plate_canon) if action == "OUT" else None

    rates = st.session_state.get("rates", {})
    grace_minutes = int(rates.get("grace_minutes", 0))

    ts = now_ts()

    duration_minutes = 0
    fee = 0
    vehicle_type_fee = vehicle_type
    if action == "OUT":
        if last_in is None:
            st.warning("Không tìm thấy lượt IN trước đó để tính phí.")
        else:
            in_time = parse_ts(last_in["ts"])
            out_time = parse_ts(ts)
            duration_minutes = max(0, int((out_time - in_time).total_seconds() // 60))
            fee = compute_fee(duration_minutes, rates.get(vehicle_type_fee, {}), grace_minutes)
            last_in_type = last_in.get("vehicle_type")
            if last_in_type and last_in_type != vehicle_type_fee:
                in_label = "Xe máy" if last_in_type == "motorbike" else "Ô tô"
                out_label = "Xe máy" if vehicle_type_fee == "motorbike" else "Ô tô"
                st.warning(
                    "Loại xe lúc IN khác lựa chọn hiện tại. "
                    f"IN: {in_label} → OUT: {out_label}. "
                    "Hệ thống đang tính phí theo lựa chọn hiện tại."
                )

    full_path, crop_path = save_pair(CFG.run_dir, out["annotated"], out["crop"])

    # IMPORTANT: insert_event signature MUST match db.py (vehicle_type + fee)
    db.insert_event(ts, action, vehicle_type_fee, plate_canon, plate_display, fee, full_path, crop_path)

    vt_label = "Xe máy" if vehicle_type_fee == "motorbike" else "Ô tô"
    duration_text = f"{duration_minutes} phút" if action == "OUT" else "N/A"
    st.success(
        f"Hệ thống xác định: **{action}** | **{plate_display}** | "
        f"loại={vt_label} | fee={fee:,} VND | thời lượng={duration_text} | time={ts}"
    )

    # Compare IN vs OUT
    if action == "OUT" and last_in_today is not None:
        st.subheader("So sánh IN vs OUT (trong ngày)")
        colA, colB = st.columns(2)

        with colA:
            st.markdown("### Ảnh lúc IN (gần nhất hôm nay)")
            if last_in_today.get("img_path") and os.path.exists(last_in_today["img_path"]):
                st.image(last_in_today["img_path"], caption=f"IN @ {last_in_today['ts']}", use_container_width=True)
            if last_in_today.get("crop_path") and os.path.exists(last_in_today["crop_path"]):
                st.image(last_in_today["crop_path"], caption="Crop IN", use_container_width=True)

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
