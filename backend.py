"""FastAPI backend for the steel quality-inspection project.

Run with::

    uvicorn backend:app --reload --port 8000

The service exposes the dashboard evaluation payload and accepts steel-surface
images for YOLO defect detection. Model weights are loaded lazily on the first
prediction so the lightweight endpoints start quickly.
"""

from __future__ import annotations

import base64
from io import BytesIO
import json
import os
from pathlib import Path
from threading import RLock
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse


REPO_ROOT = Path(__file__).resolve().parent
EVALUATION_FILE = REPO_ROOT / "dashboard" / "data" / "evaluation.json"
MODELS_DIR = REPO_ROOT / "models"
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_MB", "10")) * 1024 * 1024
MAX_REQUEST_BYTES = MAX_UPLOAD_BYTES + 1024 * 1024
MAX_IMAGE_WIDTH = int(os.getenv("MAX_IMAGE_WIDTH", "4096"))
MAX_IMAGE_HEIGHT = int(os.getenv("MAX_IMAGE_HEIGHT", "4096"))
MAX_IMAGE_PIXELS = int(os.getenv("MAX_IMAGE_PIXELS", str(4096 * 4096)))
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/bmp"}


class RequestSizeLimitMiddleware:
    """Reject oversized prediction requests before multipart form parsing."""

    def __init__(self, application: Any, max_body_size: int) -> None:
        self.application = application
        self.max_body_size = max_body_size

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if (
            scope.get("type") != "http"
            or scope.get("method") != "POST"
            or scope.get("path") != "/predict"
        ):
            await self.application(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        content_length = headers.get(b"content-length")
        if content_length:
            try:
                if int(content_length) > self.max_body_size:
                    await self._reject(scope, receive, send)
                    return
            except ValueError:
                response = JSONResponse(
                    status_code=400, content={"detail": "Invalid Content-Length header."}
                )
                await response(scope, receive, send)
                return

        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            if message["type"] != "http.request":
                continue

            body.extend(message.get("body", b""))
            if len(body) > self.max_body_size:
                await self._reject(scope, receive, send)
                return
            if not message.get("more_body", False):
                break

        delivered = False

        async def replay_receive() -> dict[str, Any]:
            nonlocal delivered
            if delivered:
                return {"type": "http.request", "body": b"", "more_body": False}
            delivered = True
            return {"type": "http.request", "body": bytes(body), "more_body": False}

        await self.application(scope, replay_receive, send)

    async def _reject(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        response = JSONResponse(
            status_code=413,
            content={
                "detail": (
                    f"The request exceeds the {self.max_body_size // (1024 * 1024)} MB "
                    "multipart limit."
                )
            },
        )
        await response(scope, receive, send)

app = FastAPI(
    title="AI-Assisted Quality Inspection API",
    version="1.0.0",
    description="Evaluation data and YOLO inference for steel-surface defects.",
)

allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    ).split(",")
    if origin.strip()
]
app.add_middleware(RequestSizeLimitMiddleware, max_body_size=MAX_REQUEST_BYTES)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

_model_cache: dict[str, Any] = {}
_model_lock = RLock()


def _read_evaluation() -> dict[str, Any]:
    """Read the latest exported dashboard data from disk."""
    try:
        with EVALUATION_FILE.open(encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail="Evaluation data is unavailable. Run scripts/export_dashboard_json.py.",
        ) from exc
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=500, detail="Evaluation data is not valid JSON."
        ) from exc


def _available_models() -> dict[str, Path]:
    """Return safe public model names mapped to checkpoint paths."""
    models: dict[str, Path] = {}

    if not MODELS_DIR.exists():
        return models

    for checkpoint in MODELS_DIR.glob("*.pt"):
        if checkpoint.is_file():
            models[checkpoint.name] = checkpoint

    for version_dir in MODELS_DIR.iterdir():
        checkpoint = version_dir / "weights" / "best.pt"
        if version_dir.is_dir() and checkpoint.is_file():
            models[version_dir.name] = checkpoint

    return dict(sorted(models.items()))


def _default_model_name() -> str:
    models = _available_models()
    if not models:
        raise HTTPException(status_code=503, detail="No model checkpoints are available.")

    try:
        evaluation = _read_evaluation()
    except HTTPException:
        evaluation = {}

    for detector in evaluation.get("detectors", []):
        if detector.get("status") != "recommended":
            continue
        checkpoint = str(detector.get("checkpoint", "")).removeprefix("loose:")
        if checkpoint in models:
            return checkpoint
        break

    return next(iter(models))


def _validate_image_dimensions(payload: bytes) -> tuple[int, int]:
    """Inspect image headers before OpenCV allocates the decoded frame."""
    try:
        from PIL import Image, UnidentifiedImageError
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail="Pillow is not installed. Run pip install -r requirements.txt.",
        ) from exc

    try:
        with Image.open(BytesIO(payload)) as image:
            width, height = image.size
            if (
                width <= 0
                or height <= 0
                or width > MAX_IMAGE_WIDTH
                or height > MAX_IMAGE_HEIGHT
                or width * height > MAX_IMAGE_PIXELS
            ):
                raise HTTPException(
                    status_code=413,
                    detail=(
                        "Image dimensions exceed the configured limit of "
                        f"{MAX_IMAGE_WIDTH}x{MAX_IMAGE_HEIGHT} and "
                        f"{MAX_IMAGE_PIXELS:,} pixels."
                    ),
                )
            image.verify()
    except HTTPException:
        raise
    except (
        UnidentifiedImageError,
        OSError,
        SyntaxError,
        ValueError,
        Image.DecompressionBombError,
    ) as exc:
        raise HTTPException(
            status_code=400, detail="The uploaded file is not a valid image."
        ) from exc

    return width, height


def _get_model(model_name: str) -> tuple[Any, Path]:
    models = _available_models()
    checkpoint = models.get(model_name)
    if checkpoint is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": f"Unknown model '{model_name}'.",
                "available_models": list(models),
            },
        )

    with _model_lock:
        model = _model_cache.get(model_name)
        if model is None:
            try:
                from ultralytics import YOLO

                model = YOLO(str(checkpoint))
            except ImportError as exc:
                raise HTTPException(
                    status_code=503,
                    detail="Ultralytics is not installed. Run pip install -r requirements.txt.",
                ) from exc
            except Exception as exc:
                raise HTTPException(
                    status_code=500,
                    detail=f"Could not load model '{model_name}'.",
                ) from exc
            _model_cache[model_name] = model
    return model, checkpoint


@app.get("/", tags=["service"])
def service_info() -> dict[str, Any]:
    return {
        "name": app.title,
        "version": app.version,
        "status": "ready",
        "docs": "/docs",
        "endpoints": ["/health", "/evaluation", "/models", "/predict"],
    }


@app.get("/health", tags=["service"])
def health() -> dict[str, Any]:
    models = _available_models()
    return {
        "status": "ok" if EVALUATION_FILE.is_file() and models else "degraded",
        "evaluation_available": EVALUATION_FILE.is_file(),
        "model_count": len(models),
    }


@app.get("/evaluation", tags=["dashboard"])
def evaluation() -> dict[str, Any]:
    """Return the payload described in docs/DASHBOARD_API.md."""
    return _read_evaluation()


@app.get("/models", tags=["inference"])
def models() -> dict[str, Any]:
    available = _available_models()
    return {
        "default": _default_model_name(),
        "models": [
            {
                "name": name,
                "size_mb": round(path.stat().st_size / (1024 * 1024), 2),
            }
            for name, path in available.items()
        ],
    }


@app.post("/predict", tags=["inference"])
def predict(
    image: UploadFile = File(..., description="JPEG, PNG, WebP, or BMP image"),
    model_name: str | None = Form(
        default=None, description="A model name returned by GET /models"
    ),
    confidence: float = Query(default=0.25, ge=0.01, le=1.0),
    iou: float = Query(default=0.45, ge=0.01, le=1.0),
    image_size: int = Query(default=640, ge=128, le=1280),
    include_annotated_image: bool = Query(default=True),
) -> dict[str, Any]:
    """Detect steel defects in one uploaded image."""
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail="Image dependencies are not installed. Run pip install -r requirements.txt.",
        ) from exc

    if image.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=415,
            detail="Unsupported image type. Use JPEG, PNG, WebP, or BMP.",
        )

    payload = image.file.read(MAX_UPLOAD_BYTES + 1)
    if not payload:
        raise HTTPException(status_code=400, detail="The uploaded image is empty.")
    if len(payload) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"The image exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.",
        )

    _validate_image_dimensions(payload)
    frame = cv2.imdecode(np.frombuffer(payload, dtype=np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        raise HTTPException(status_code=400, detail="The uploaded file is not a valid image.")

    selected_model = model_name or _default_model_name()
    model, checkpoint = _get_model(selected_model)

    try:
        # Ultralytics model instances are not guaranteed to be safe for concurrent
        # prediction, so inference shares the same lock used by the model cache.
        with _model_lock:
            result = model.predict(
                source=frame,
                imgsz=image_size,
                conf=confidence,
                iou=iou,
                verbose=False,
            )[0]
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Model inference failed.") from exc

    detections = []
    for box in result.boxes:
        class_id = int(box.cls.item())
        detections.append(
            {
                "class_id": class_id,
                "class_name": result.names[class_id],
                "confidence": round(float(box.conf.item()), 6),
                "box_xyxy": [round(float(value), 2) for value in box.xyxy[0].tolist()],
            }
        )

    response: dict[str, Any] = {
        "filename": image.filename,
        "model": selected_model,
        "checkpoint": checkpoint.relative_to(REPO_ROOT).as_posix(),
        "image": {"width": int(frame.shape[1]), "height": int(frame.shape[0])},
        "defect_found": bool(detections),
        "detection_count": len(detections),
        "detections": detections,
    }

    if include_annotated_image:
        encoded_ok, encoded_image = cv2.imencode(".jpg", result.plot())
        if not encoded_ok:
            raise HTTPException(status_code=500, detail="Could not encode annotated image.")
        response["annotated_image"] = {
            "media_type": "image/jpeg",
            "base64": base64.b64encode(encoded_image.tobytes()).decode("ascii"),
        }

    return response


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("RELOAD", "false").lower() == "true",
    )
