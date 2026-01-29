from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple

import cv2
import numpy as np

def bgr_from_bytes(data: bytes) -> Optional[np.ndarray]:
    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return img

def bgr_to_rgb(img_bgr: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

def save_pair(run_dir: str, full_bgr: np.ndarray, crop_bgr: Optional[np.ndarray]) -> Tuple[str, str]:
    Path(run_dir).mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    full_path = str(Path(run_dir) / f"{stamp}_full.jpg")
    crop_path = str(Path(run_dir) / f"{stamp}_crop.jpg") if crop_bgr is not None else ""
    cv2.imwrite(full_path, full_bgr)
    if crop_bgr is not None:
        cv2.imwrite(crop_path, crop_bgr)
    return full_path, crop_path
