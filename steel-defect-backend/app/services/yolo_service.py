"""YOLO Inference Service for Steel Surface Defect Detection.
Wraps the trained YOLO11n NEU-DET model ('best_v2.pt').
Supports GPU and CPU inference, image/video processing, and clean industrial annotations.
"""

import logging
import os
import time
from pathlib import Path
from typing import List, Tuple, Optional, Callable, Dict, Any
import cv2
import numpy as np
import torch
from ultralytics import YOLO

from app.config import settings
from app.models.schemas import BoundingBox, DefectDetection

logger = logging.getLogger(__name__)


class YOLOInferenceService:
    """Enterprise YOLO inference service for industrial steel quality inspection."""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, weights_path: Optional[Path] = None, device: Optional[str] = None):
        if getattr(self, "_initialized", False):
            return

        self.weights_path = Path(weights_path or settings.DEFAULT_WEIGHTS_PATH)
        if not self.weights_path.exists():
            if settings.FALLBACK_WEIGHTS_PATH.exists():
                logger.warning(
                    f"Default weights {self.weights_path} not found. Using fallback {settings.FALLBACK_WEIGHTS_PATH}"
                )
                self.weights_path = settings.FALLBACK_WEIGHTS_PATH
            else:
                raise FileNotFoundError(
                    f"YOLO weights file not found at {self.weights_path} or fallback."
                )

        # Device detection: CUDA vs CPU
        if device is None or device == "auto":
            self.device = "cuda:0" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        logger.info(f"Loading YOLO model from {self.weights_path} on device: {self.device}")
        self.model = YOLO(str(self.weights_path))

        # Validate NEU-DET classes
        self.class_names: Dict[int, str] = self.model.names if hasattr(self.model, "names") else settings.NEU_CLASSES
        logger.info(f"Loaded YOLO classes: {self.class_names}")

        # Warmup model
        self._warmup()
        self._initialized = True

    def _warmup(self) -> None:
        """Run a dummy forward pass to compile graph and initialize CUDA/CPU kernels."""
        try:
            dummy = np.zeros((settings.IMAGE_SIZE, settings.IMAGE_SIZE, 3), dtype=np.uint8)
            self.model(dummy, device=self.device, verbose=False, imgsz=settings.IMAGE_SIZE)
            logger.info("YOLO model warmup complete.")
        except Exception as e:
            logger.warning(f"YOLO warmup error: {e}")

    def get_device_info(self) -> Dict[str, Any]:
        """Return runtime hardware inference details."""
        cuda_avail = torch.cuda.is_available()
        gpu_name = torch.cuda.get_device_name(0) if cuda_avail else None
        return {
            "current_device": self.device,
            "cuda_available": cuda_avail,
            "gpu_name": gpu_name,
            "torch_version": torch.__version__,
            "model_weights": str(self.weights_path.name),
            "classes": self.class_names,
        }

    def detect_image(
        self,
        image_input: Any,  # file path, numpy array, or PIL image
        conf: Optional[float] = None,
        iou: Optional[float] = None,
        device: Optional[str] = None,
    ) -> Tuple[List[DefectDetection], np.ndarray, float]:
        """Perform YOLO defect detection on a single image.
        
        Returns:
            Tuple of:
            - List of DefectDetection objects
            - Annotated numpy image (BGR)
            - Inference duration in milliseconds
        """
        conf_thresh = conf if conf is not None else settings.DEFAULT_CONFIDENCE_THRESHOLD
        iou_thresh = iou if iou is not None else settings.DEFAULT_IOU_THRESHOLD
        infer_device = device or self.device

        # Read image to BGR numpy array if path provided
        if isinstance(image_input, (str, Path)):
            img = cv2.imread(str(image_input))
            if img is None:
                raise ValueError(f"Could not load image from path: {image_input}")
        elif isinstance(image_input, np.ndarray):
            img = image_input.copy()
        else:
            raise TypeError("Unsupported image input type")

        start_time = time.perf_counter()

        results = self.model(
            img,
            conf=conf_thresh,
            iou=iou_thresh,
            device=infer_device,
            imgsz=settings.IMAGE_SIZE,
            verbose=False,
        )

        inference_time_ms = round((time.perf_counter() - start_time) * 1000, 2)

        detections: List[DefectDetection] = []
        annotated_img = img.copy()

        if results and len(results) > 0:
            res = results[0]
            boxes = res.boxes
            if boxes is not None and len(boxes) > 0:
                for box in boxes:
                    cls_id = int(box.cls[0].item())
                    confidence = float(box.conf[0].item())
                    xyxy = box.xyxy[0].tolist()  # [x1, y1, x2, y2]
                    
                    x1, y1, x2, y2 = xyxy
                    width = max(0.0, x2 - x1)
                    height = max(0.0, y2 - y1)
                    area = width * height

                    class_name = self.class_names.get(cls_id, f"defect_{cls_id}")

                    detection = DefectDetection(
                        class_id=cls_id,
                        class_name=class_name,
                        confidence=round(confidence, 4),
                        bbox=BoundingBox(
                            x1=round(x1, 2),
                            y1=round(y1, 2),
                            x2=round(x2, 2),
                            y2=round(y2, 2),
                            width=round(width, 2),
                            height=round(height, 2),
                            area=round(area, 2),
                        ),
                        frame_number=0,
                    )
                    detections.append(detection)

            # Draw visual defect annotations on image
            annotated_img = self._annotate_image(annotated_img, detections, inference_time_ms)

        return detections, annotated_img, inference_time_ms

    def _annotate_image(
        self,
        img: np.ndarray,
        detections: List[DefectDetection],
        inference_time_ms: float = 0.0,
        frame_idx: Optional[int] = None,
        total_frames: Optional[int] = None,
    ) -> np.ndarray:
        """Render high-contrast, clear industrial bounding boxes and metadata overlays."""
        h, w = img.shape[:2]
        annotated = img.copy()

        # Draw defect bounding boxes
        for det in detections:
            bbox = det.bbox
            x1, y1, x2, y2 = int(bbox.x1), int(bbox.y1), int(bbox.x2), int(bbox.y2)

            color = settings.CLASS_COLORS.get(det.class_name, (0, 255, 255))
            
            # Thick rectangular border
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2, cv2.LINE_AA)

            # Label banner
            label = f"{det.class_name}: {det.confidence * 100:.1f}%"
            (label_w, label_h), baseline = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
            )
            
            top_y = max(0, y1 - label_h - 6)
            cv2.rectangle(
                annotated,
                (x1, top_y),
                (x1 + label_w + 8, top_y + label_h + 6),
                color,
                -1,
            )
            # Text in contrasting white / black
            cv2.putText(
                annotated,
                label,
                (x1 + 4, top_y + label_h + 2),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255) if color[0] + color[1] + color[2] < 450 else (0, 0, 0),
                1,
                cv2.LINE_AA,
            )

        # Draw top inspection HUD banner
        hud_height = 36
        overlay = annotated.copy()
        cv2.rectangle(overlay, (0, 0), (w, hud_height), (20, 20, 25), -1)
        cv2.addWeighted(overlay, 0.85, annotated, 0.15, 0, annotated)

        # Status text
        status_text = f"AI INSPECTOR  |  DEFECTS: {len(detections)}  |  LATENCY: {inference_time_ms:.1f}ms"
        if frame_idx is not None and total_frames is not None:
            status_text = f"FRAME: {frame_idx}/{total_frames}  |  " + status_text

        # Status pill color
        alert_color = (0, 0, 230) if len(detections) > 0 else (0, 200, 0)
        cv2.circle(annotated, (16, hud_height // 2), 6, alert_color, -1)
        cv2.putText(
            annotated,
            status_text,
            (32, 23),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (240, 240, 240),
            1,
            cv2.LINE_AA,
        )

        return annotated

    def process_video(
        self,
        video_path: Path,
        output_video_path: Path,
        conf: Optional[float] = None,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        stride: int = 1,
    ) -> Dict[str, Any]:
        """Perform frame-by-frame defect inspection on video and generate annotated video."""
        conf_thresh = conf if conf is not None else settings.DEFAULT_CONFIDENCE_THRESHOLD
        
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise ValueError(f"Could not open video file at {video_path}")

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 15.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        output_video_path.parent.mkdir(parents=True, exist_ok=True)
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out_writer = cv2.VideoWriter(str(output_video_path), fourcc, fps, (width, height))

        all_detections: List[DefectDetection] = []
        frame_idx = 0
        processed_count = 0
        start_time = time.perf_counter()

        logger.info(f"Starting video inspection: {total_frames} frames at {fps} fps ({width}x{height})")

        try:
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break

                frame_idx += 1
                
                # Check stride to accelerate processing
                should_run_yolo = (frame_idx % stride == 0) or (frame_idx == 1)

                if should_run_yolo:
                    f_start = time.perf_counter()
                    results = self.model(
                        frame,
                        conf=conf_thresh,
                        device=self.device,
                        imgsz=settings.IMAGE_SIZE,
                        verbose=False,
                    )
                    f_ms = round((time.perf_counter() - f_start) * 1000, 2)

                    frame_detections: List[DefectDetection] = []
                    if results and len(results) > 0:
                        boxes = results[0].boxes
                        if boxes is not None:
                            for box in boxes:
                                cls_id = int(box.cls[0].item())
                                confidence = float(box.conf[0].item())
                                x1, y1, x2, y2 = box.xyxy[0].tolist()
                                w_box = max(0.0, x2 - x1)
                                h_box = max(0.0, y2 - y1)
                                area = w_box * h_box
                                class_name = self.class_names.get(cls_id, f"defect_{cls_id}")

                                det = DefectDetection(
                                    class_id=cls_id,
                                    class_name=class_name,
                                    confidence=round(confidence, 4),
                                    bbox=BoundingBox(
                                        x1=round(x1, 2),
                                        y1=round(y1, 2),
                                        x2=round(x2, 2),
                                        y2=round(y2, 2),
                                        width=round(w_box, 2),
                                        height=round(h_box, 2),
                                        area=round(area, 2),
                                    ),
                                    frame_number=frame_idx,
                                )
                                frame_detections.append(det)
                                all_detections.append(det)

                    annotated_frame = self._annotate_image(
                        frame, frame_detections, f_ms, frame_idx, total_frames
                    )
                    processed_count += 1
                else:
                    # Write frame with light HUD update
                    annotated_frame = self._annotate_image(
                        frame, [], 0.0, frame_idx, total_frames
                    )

                out_writer.write(annotated_frame)

                # Report progress via callback
                if progress_callback and (frame_idx % 10 == 0 or frame_idx == total_frames):
                    elapsed = time.perf_counter() - start_time
                    percent = round((frame_idx / max(1, total_frames)) * 100, 1)
                    current_fps = round(frame_idx / max(0.001, elapsed), 1)
                    progress_callback({
                        "frame_index": frame_idx,
                        "total_frames": total_frames,
                        "progress_percent": percent,
                        "fps": current_fps,
                        "total_defects_so_far": len(all_detections),
                        "elapsed_seconds": round(elapsed, 1),
                    })

                if frame_idx >= settings.VIDEO_MAX_FRAMES:
                    logger.warning(f"Hit max frames cap ({settings.VIDEO_MAX_FRAMES}).")
                    break

        finally:
            cap.release()
            out_writer.release()

        total_elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.info(
            f"Video inspection completed: {processed_count} frames processed in {total_elapsed_ms / 1000:.2f}s. "
            f"Total defects found: {len(all_detections)}"
        )

        return {
            "total_frames": total_frames,
            "processed_frames": frame_idx,
            "detections": all_detections,
            "total_defects": len(all_detections),
            "inference_time_ms": total_elapsed_ms,
            "output_video_path": str(output_video_path),
        }


# Singleton accessor
def get_yolo_service() -> YOLOInferenceService:
    return YOLOInferenceService()
