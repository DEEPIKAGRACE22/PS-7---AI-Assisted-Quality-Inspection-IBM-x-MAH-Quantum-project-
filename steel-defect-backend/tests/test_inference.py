"""Unit tests for YOLO inference service.
Validates model loading, NEU-DET class preservation, inference latency, and bounding box formats.
"""

import os
import sys
from pathlib import Path
import cv2
import numpy as np

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.services.yolo_service import YOLOInferenceService, get_yolo_service


def test_yolo_service_initialization():
    service = get_yolo_service()
    assert service is not None
    assert service.model is not None
    assert service.weights_path.exists()
    
    # Verify all 6 NEU-DET classes are preserved
    expected_classes = {
        0: "crazing",
        1: "inclusion",
        2: "patches",
        3: "pitted_surface",
        4: "rolled-in_scale",
        5: "scratches",
    }
    for idx, expected_name in expected_classes.items():
        assert idx in service.class_names, f"Missing class ID {idx}"
        assert service.class_names[idx] == expected_name, f"Expected {expected_name}, got {service.class_names[idx]}"


def test_device_info():
    service = get_yolo_service()
    info = service.get_device_info()
    assert "current_device" in info
    assert "cuda_available" in info
    assert "classes" in info
    assert len(info["classes"]) == 6


def test_inference_on_sample_images():
    service = get_yolo_service()
    samples_dir = settings.SAMPLES_DIR
    sample_files = list(samples_dir.glob("*.jpg"))
    assert len(sample_files) > 0, "No sample images found for inference test."

    for sample_file in sample_files:
        detections, annotated_img, latency_ms = service.detect_image(
            image_input=sample_file,
            conf=0.20,
            iou=0.45,
        )
        assert isinstance(detections, list)
        assert isinstance(annotated_img, np.ndarray)
        assert annotated_img.shape[0] > 0
        assert annotated_img.shape[1] > 0
        assert latency_ms > 0

        # Validate bounding box coordinates if defects detected
        for d in detections:
            assert 0 <= d.class_id <= 5
            assert d.class_name in settings.NEU_CLASSES.values()
            assert 0.0 <= d.confidence <= 1.0
            assert d.bbox.x1 <= d.bbox.x2
            assert d.bbox.y1 <= d.bbox.y2
            assert d.bbox.width >= 0
            assert d.bbox.height >= 0
            assert d.bbox.area >= 0


def test_video_timestamps_and_browser_output(tmp_dir: Path = settings.STORAGE_DIR / "test_video"):
    service = get_yolo_service()
    events = []
    out_path = tmp_dir / "annotated.mp4"
    result = service.process_video(
        video_path=settings.SAMPLES_DIR / "sample_inspection_short.mp4",
        output_video_path=out_path,
        progress_callback=events.append,
        stride=2,
    )

    # Every detection knows when it happened in the source video
    fps = result["fps"]
    stamps = [d.timestamp_s for d in result["detections"]]
    assert stamps == sorted(stamps)
    for d in result["detections"]:
        assert abs(d.timestamp_s - (d.frame_number - 1) / fps) < 1e-3

    # The callback reports each frame with detections as it happens
    alerted = [d for e in events for d in e["new_detections"]]
    assert len(alerted) == len(result["detections"])

    # Output is H.264 so a browser <video> can play it, and keeps every frame
    cap = cv2.VideoCapture(str(out_path))
    fourcc = int(cap.get(cv2.CAP_PROP_FOURCC)).to_bytes(4, "little").decode()
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    assert fourcc in ("avc1", "h264"), fourcc
    assert frames == result["processed_frames"]
    assert not out_path.with_name("annotated_raw.mp4").exists()


if __name__ == "__main__":
    print("Running YOLO Inference tests...")
    test_yolo_service_initialization()
    print("-> YOLO Service Initialization: PASSED")
    test_device_info()
    print("-> Device Info: PASSED")
    test_inference_on_sample_images()
    print("-> Inference on Sample Images: PASSED")
    test_video_timestamps_and_browser_output()
    print("-> Video Timestamps & Browser Output: PASSED")
    print("ALL INFERENCE TESTS PASSED!")
