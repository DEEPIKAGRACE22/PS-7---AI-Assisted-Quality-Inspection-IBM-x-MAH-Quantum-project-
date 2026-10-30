"""YOLO Inference Service for Steel Surface Defect Detection.
Wraps the recommended YOLO11n NEU-DET model (models/best_v2.pt).
Supports GPU and CPU inference, image/video processing, and clean industrial annotations.
"""

import logging
import os
import shutil
import subprocess
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
            "model_weights": str(self.weights_path),
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

    @staticmethod
    def _format_timestamp(seconds: float) -> str:
        """Video time as mm:ss.mmm."""
        minutes, secs = divmod(max(0.0, seconds), 60)
        return f"{int(minutes):02d}:{secs:06.3f}"

    def _annotate_image(
        self,
        img: np.ndarray,
        detections: List[DefectDetection],
        inference_time_ms: float = 0.0,
        frame_idx: Optional[int] = None,
        total_frames: Optional[int] = None,
        timestamp_s: Optional[float] = None,
        box_scale: float = 1.0,
    ) -> np.ndarray:
        """Render bounding boxes, confidence labels, a status HUD and, for video, the frame timestamp.

        box_scale maps detection coordinates onto img when the frame was resized before drawing.
        """
        h, w = img.shape[:2]
        annotated = img.copy()

        # Text and line sizes follow the frame width so the HUD fits small frames too
        ui = max(0.45, w / 900)
        font = cv2.FONT_HERSHEY_SIMPLEX
        thin = max(1, round(ui * 1.4))

        # Draw defect bounding boxes
        for det in detections:
            bbox = det.bbox
            x1, y1, x2, y2 = (int(v * box_scale) for v in (bbox.x1, bbox.y1, bbox.x2, bbox.y2))

            color = settings.CLASS_COLORS.get(det.class_name, (0, 255, 255))
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, max(2, thin + 1), cv2.LINE_AA)

            # Label banner
            label = f"{det.class_name} {det.confidence * 100:.0f}%"
            (label_w, label_h), _ = cv2.getTextSize(label, font, ui, thin)
            top_y = max(0, y1 - label_h - 8)
            left_x = min(max(0, x1), max(0, w - label_w - 8))
            cv2.rectangle(annotated, (left_x, top_y), (left_x + label_w + 8, top_y + label_h + 8), color, -1)
            cv2.putText(
                annotated,
                label,
                (left_x + 4, top_y + label_h + 3),
                font,
                ui,
                (255, 255, 255) if color[0] + color[1] + color[2] < 450 else (0, 0, 0),
                thin,
                cv2.LINE_AA,
            )

        # Top HUD: timestamp, frame, defect count, latency
        parts = []
        if timestamp_s is not None:
            parts.append(self._format_timestamp(timestamp_s))
        if frame_idx is not None and total_frames is not None:
            parts.append(f"F {frame_idx}/{total_frames}")
        parts.append(f"DEFECTS {len(detections)}")
        if inference_time_ms:
            parts.append(f"{inference_time_ms:.0f}ms")
        status_text = "  |  ".join(parts)

        (_, text_h), _ = cv2.getTextSize(status_text, font, ui, thin)
        hud_height = text_h + 16
        overlay = annotated.copy()
        cv2.rectangle(overlay, (0, 0), (w, hud_height), (20, 20, 25), -1)
        cv2.addWeighted(overlay, 0.85, annotated, 0.15, 0, annotated)

        alert_color = (0, 0, 230) if detections else (0, 200, 0)
        dot_r = max(4, text_h // 2)
        cv2.circle(annotated, (8 + dot_r, hud_height // 2), dot_r, alert_color, -1)
        cv2.putText(annotated, status_text, (16 + 2 * dot_r, hud_height // 2 + text_h // 2), font, ui, (240, 240, 240), thin, cv2.LINE_AA)

        # Bottom alert strip on frames with a defect
        if detections:
            top = max(detections, key=lambda d: d.confidence)
            alert = f"DEFECT ALERT  {top.class_name} {top.confidence * 100:.0f}%"
            if len(detections) > 1:
                alert += f"  +{len(detections) - 1}"
            (alert_w, alert_h), _ = cv2.getTextSize(alert, font, ui, thin + 1)
            strip = alert_h + 16
            cv2.rectangle(annotated, (0, h - strip), (w, h), (0, 0, 200), -1)
            cv2.putText(annotated, alert, (max(8, (w - alert_w) // 2), h - 8), font, ui, (255, 255, 255), thin + 1, cv2.LINE_AA)

        return annotated

    def _detections_from_result(self, result: Any, frame_idx: int, timestamp_s: float) -> List[DefectDetection]:
        """Convert one Ultralytics result into DefectDetection objects in source-frame pixels."""
        detections: List[DefectDetection] = []
        boxes = result.boxes
        if boxes is None:
            return detections
        for box in boxes:
            cls_id = int(box.cls[0].item())
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            w_box = max(0.0, x2 - x1)
            h_box = max(0.0, y2 - y1)
            detections.append(
                DefectDetection(
                    class_id=cls_id,
                    class_name=self.class_names.get(cls_id, f"defect_{cls_id}"),
                    confidence=round(float(box.conf[0].item()), 4),
                    bbox=BoundingBox(
                        x1=round(x1, 2),
                        y1=round(y1, 2),
                        x2=round(x2, 2),
                        y2=round(y2, 2),
                        width=round(w_box, 2),
                        height=round(h_box, 2),
                        area=round(w_box * h_box, 2),
                    ),
                    frame_number=frame_idx,
                    timestamp_s=round(timestamp_s, 3),
                )
            )
        return detections

    @staticmethod
    def _transcode_for_browser(src: Path, dst: Path) -> bool:
        """Re-encode OpenCV's MPEG-4 Part 2 output as H.264 so browsers can play it.

        Returns False when no ffmpeg binary is available.
        """
        try:
            import imageio_ffmpeg

            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            return False

        try:
            subprocess.run(
                [
                    ffmpeg, "-y", "-loglevel", "error", "-i", str(src),
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                    "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", str(dst),
                ],
                check=True,
                timeout=600,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            logger.warning(f"ffmpeg transcode failed: {e}")
            dst.unlink(missing_ok=True)
            return False
        return True

    def process_video(
        self,
        video_path: Path,
        output_video_path: Path,
        conf: Optional[float] = None,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        stride: int = 1,
    ) -> Dict[str, Any]:
        """Run frame-by-frame defect inspection on a video and write an annotated copy.

        Every detection carries the frame number and its time in the source video.
        The callback gets a progress update every 10 frames, and immediately on any
        frame with detections (under "new_detections").
        """
        conf_thresh = conf if conf is not None else settings.DEFAULT_CONFIDENCE_THRESHOLD
        stride = max(1, stride)

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise ValueError(f"Could not open video file at {video_path}")

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 15.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # Small sources are upscaled for the output so labels stay readable;
        # detections stay in source pixels.
        out_scale = max(1.0, settings.VIDEO_MIN_OUTPUT_WIDTH / max(1, width))
        out_size = (round(width * out_scale) // 2 * 2, round(height * out_scale) // 2 * 2)

        output_video_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path = output_video_path.with_name(output_video_path.stem + "_raw.mp4")
        out_writer = cv2.VideoWriter(str(raw_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, out_size)

        all_detections: List[DefectDetection] = []
        held: List[DefectDetection] = []  # last detections, redrawn on frames the stride skips
        held_ms = 0.0
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
                timestamp_s = (frame_idx - 1) / fps
                new_detections: List[DefectDetection] = []

                if (frame_idx - 1) % stride == 0:
                    f_start = time.perf_counter()
                    results = self.model(
                        frame,
                        conf=conf_thresh,
                        device=self.device,
                        imgsz=settings.IMAGE_SIZE,
                        verbose=False,
                    )
                    held_ms = round((time.perf_counter() - f_start) * 1000, 2)
                    new_detections = self._detections_from_result(results[0], frame_idx, timestamp_s) if results else []
                    held = new_detections
                    all_detections.extend(new_detections)
                    processed_count += 1

                display = frame if out_size == (width, height) else cv2.resize(frame, out_size, interpolation=cv2.INTER_CUBIC)
                annotated_frame = self._annotate_image(
                    display, held, held_ms, frame_idx, total_frames, timestamp_s, box_scale=out_size[0] / width
                )
                out_writer.write(annotated_frame)

                if progress_callback and (new_detections or frame_idx % 10 == 0 or frame_idx == total_frames):
                    elapsed = time.perf_counter() - start_time
                    progress_callback({
                        "frame_index": frame_idx,
                        "total_frames": total_frames,
                        "progress_percent": round((frame_idx / max(1, total_frames)) * 100, 1),
                        "fps": round(frame_idx / max(0.001, elapsed), 1),
                        "total_defects_so_far": len(all_detections),
                        "elapsed_seconds": round(elapsed, 1),
                        "timestamp_s": round(timestamp_s, 3),
                        "new_detections": new_detections,
                    })

                if frame_idx >= settings.VIDEO_MAX_FRAMES:
                    logger.warning(f"Hit max frames cap ({settings.VIDEO_MAX_FRAMES}).")
                    break

        finally:
            cap.release()
            out_writer.release()

        if self._transcode_for_browser(raw_path, output_video_path):
            raw_path.unlink(missing_ok=True)
        else:
            logger.warning("ffmpeg unavailable or failed; annotated video stays MPEG-4 Part 2 and may not play in browsers.")
            raw_path.replace(output_video_path)

        total_elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.info(
            f"Video inspection completed: {processed_count} frames processed in {total_elapsed_ms / 1000:.2f}s. "
            f"Total defects found: {len(all_detections)}"
        )

        return {
            "total_frames": total_frames,
            "processed_frames": frame_idx,
            "fps": fps,
            "detections": all_detections,
            "total_defects": len(all_detections),
            "inference_time_ms": total_elapsed_ms,
            "output_video_path": str(output_video_path),
        }


# Singleton accessor
def get_yolo_service() -> YOLOInferenceService:
    return YOLOInferenceService()
