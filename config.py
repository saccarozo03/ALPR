from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class AppConfig:
    model_path: str = r"C:\Users\Nguoi yeu cua Siim\Desktop\yolo\runs\detect\train3\weights\best.onnx"
    db_path: str = "parking.db"
    run_dir: str = "runs"
    users: dict = None

    def __post_init__(self):
        if self.users is None:
            object.__setattr__(self, "users", {"admin": "123456", "staff": "123456"})
        Path(self.run_dir).mkdir(parents=True, exist_ok=True)
