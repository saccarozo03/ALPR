from typing import Optional, Dict, Any
from datetime import datetime
import cv2

from plate import normalize_and_fix_plate, format_plate_display

def run_yolo_ocr(yolo, ocr, img_bgr) -> Optional[Dict[str, Any]]:
    """
    Return dict: annotated, crop, raw_text, plate_canon, plate_display
    """
    results = yolo.predict(source=img_bgr, imgsz=640, conf=0.5, iou=0.5, verbose=False)
    res = results[0]
    boxes = res.boxes
    if boxes is None or len(boxes) == 0:
        return None

    best = max(boxes, key=lambda b: float(b.conf[0]))
    x1, y1, x2, y2 = best.xyxy[0].cpu().numpy()
    x1, y1, x2, y2 = map(int, [x1, y1, x2, y2])

    h, w = img_bgr.shape[:2]
    x1, y1, x2, y2 = max(0, x1), max(0, y1), min(w, x2), min(h, y2)

    crop = img_bgr[y1:y2, x1:x2].copy()
    annotated = img_bgr.copy()
    cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)

    ocr_out = ocr.predict(crop)

    raw_text = ""
    if ocr_out:
        item = ocr_out[0]
        texts = item.get("rec_texts", [])
        raw_text = " ".join(texts) if isinstance(texts, (list, tuple)) else str(texts)

    canon = normalize_and_fix_plate(raw_text)
    display = format_plate_display(canon)

    return {
        "annotated": annotated,
        "crop": crop,
        "raw_text": raw_text,
        "plate_canon": canon,
        "plate_display": display,
    }

def decide_in_out(db, plate_canon: str) -> str:
    last = db.latest_event(plate_canon)
    if last is None:
        return "IN"
    return "OUT" if last["action"] == "IN" else "IN"

def now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
