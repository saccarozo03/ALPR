import os

def load_models(model_path: str):
    """
    Lazy import + lazy init:
    - KHÔNG import YOLO / PaddleOCR ở top-level
    - Chỉ load khi user bấm 'Load models'
    """
    os.environ["DISABLE_MODEL_SOURCE_CHECK"] = "True"

    # Lazy imports (quan trọng)
    from ultralytics import YOLO
    from paddleocr import PaddleOCR

    yolo = YOLO(model_path)
    ocr = PaddleOCR(
        lang="vi",
        text_recognition_model_name="PP-OCRv5_mobile_rec",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
    )
    return yolo, ocr
