"""Application configuration module.
Industrial AI Steel Surface Defect Detection Platform.
"""

from pathlib import Path
from typing import Dict, List, Set
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Project Info
    PROJECT_NAME: str = "Industrial AI Steel Surface Defect Detection Platform"
    PROJECT_DESCRIPTION: str = (
        "Enterprise-grade defect detection backend for hot-rolled steel surface inspection "
        "powered by fine-tuned YOLO11n on the NEU-DET industrial dataset."
    )
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # Base Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    WEIGHTS_DIR: Path = BASE_DIR / "weights"
    STORAGE_DIR: Path = BASE_DIR / "storage"
    UPLOADS_DIR: Path = STORAGE_DIR / "uploads"
    ANNOTATED_DIR: Path = STORAGE_DIR / "annotated"
    REPORTS_DIR: Path = STORAGE_DIR / "reports"
    SAMPLES_DIR: Path = BASE_DIR / "samples"

    # Model Settings
    DEFAULT_WEIGHTS_PATH: Path = WEIGHTS_DIR / "best_v2.pt"
    FALLBACK_WEIGHTS_PATH: Path = WEIGHTS_DIR / "best_finetuned.pt"
    
    # Six NEU-DET steel defect classes
    NEU_CLASSES: Dict[int, str] = {
        0: "crazing",
        1: "inclusion",
        2: "patches",
        3: "pitted_surface",
        4: "rolled-in_scale",
        5: "scratches",
    }
    
    # Class colors for visual bounding box annotation (BGR format for OpenCV)
    CLASS_COLORS: Dict[str, tuple] = {
        "crazing": (30, 144, 255),        # Dodger Blue / Orange in RGB
        "inclusion": (0, 0, 230),          # Bright Red (severe defect)
        "patches": (255, 140, 0),          # Dark Orange
        "pitted_surface": (0, 165, 255),    # Amber
        "rolled-in_scale": (0, 0, 180),    # Crimson Red (severe structural defect)
        "scratches": (0, 215, 255),        # Gold / Yellow
    }

    # Inference defaults
    DEVICE: str = "auto"  # "auto", "cuda", "cuda:0", or "cpu"
    DEFAULT_CONFIDENCE_THRESHOLD: float = 0.25
    DEFAULT_IOU_THRESHOLD: float = 0.45
    IMAGE_SIZE: int = 640

    # Video processing
    VIDEO_SAMPLE_STRIDE: int = 2  # Process every Nth frame to optimize throughput while maintaining defect coverage
    VIDEO_MAX_FRAMES: int = 5000  # Safety cap for continuous inspection video

    # Database
    DATABASE_PATH: Path = STORAGE_DIR / "steel_inspections.db"

    # File Upload Limits & Constraints
    ALLOWED_IMAGE_EXTENSIONS: Set[str] = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tiff"}
    ALLOWED_VIDEO_EXTENSIONS: Set[str] = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
    MAX_IMAGE_SIZE_MB: int = 50
    MAX_VIDEO_SIZE_MB: int = 500

    # Quality Decision Defaults
    DEFAULT_CRITICAL_DEFECTS: List[str] = ["rolled-in_scale", "inclusion", "pitted_surface"]
    DEFAULT_CRITICAL_CONFIDENCE: float = 0.50
    DEFAULT_REVIEW_CONFIDENCE_MIN: float = 0.25
    DEFAULT_REJECT_CONFIDENCE: float = 0.70
    DEFAULT_MAX_ALLOWED_DEFECTS: int = 2

    class Config:
        case_sensitive = True
        env_prefix = "STEEL_AI_"


settings = Settings()

# Ensure directories exist
for directory in [
    settings.WEIGHTS_DIR,
    settings.STORAGE_DIR,
    settings.UPLOADS_DIR,
    settings.ANNOTATED_DIR,
    settings.REPORTS_DIR,
    settings.SAMPLES_DIR,
]:
    directory.mkdir(parents=True, exist_ok=True)
