"""End-to-end integration tests for FastAPI backend endpoints.
Tests image upload, batch upload, video upload, quality decisions,
analytics calculations, CSV report download, and error validation.
"""

import os
import sys
import time
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from starlette.testclient import TestClient
from app.main import app
from app.config import settings

client = TestClient(app)


def test_system_and_health_endpoints():
    # Test Root
    res = client.get("/")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "OPERATIONAL"
    assert "neu_det_classes" in data
    assert len(data["neu_det_classes"]) == 6
    assert "device_info" in data

    # Test Health
    h_res = client.get("/health")
    assert h_res.status_code == 200
    h_data = h_res.json()
    assert h_data["status"] == "healthy"
    assert h_data["database"] == "connected"


def test_single_image_upload_and_inference():
    sample_img = settings.SAMPLES_DIR / "sample_frame_patches.jpg"
    assert sample_img.exists(), f"Sample image {sample_img} not found."

    with open(sample_img, "rb") as f:
        response = client.post(
            "/api/v1/inspections/upload/image",
            files={"file": ("sample_frame_patches.jpg", f, "image/jpeg")},
            data={"conf_threshold": "0.20", "device": "cpu"},
        )

    assert response.status_code == 200, f"Error: {response.text}"
    data = response.json()
    insp_id = data["id"]
    assert insp_id is not None
    assert data["status"] == "COMPLETED"
    assert data["quality_decision"] in ["APPROVED", "REVIEW_REQUIRED", "REJECTED"]
    assert data["inference_time_ms"] > 0
    assert len(data["defects"]) > 0 or data["total_defects"] == 0

    # Test retrieval by ID
    get_res = client.get(f"/api/v1/inspections/{insp_id}")
    assert get_res.status_code == 200
    get_data = get_res.json()
    assert get_data["id"] == insp_id
    assert get_data["quality_decision"] == data["quality_decision"]

    # Test annotated image retrieval
    img_res = client.get(f"/api/v1/inspections/{insp_id}/annotated-file")
    assert img_res.status_code == 200
    assert img_res.headers["content-type"].startswith("image/")
    assert len(img_res.content) > 1000

    # Test progress endpoint
    prog_res = client.get(f"/api/v1/inspections/{insp_id}/progress")
    assert prog_res.status_code == 200
    assert prog_res.json()["progress_percent"] == 100.0


def test_batch_image_upload():
    img1 = settings.SAMPLES_DIR / "sample_frame_crazing.jpg"
    img2 = settings.SAMPLES_DIR / "sample_frame_normal.jpg"
    assert img1.exists() and img2.exists()

    with open(img1, "rb") as f1, open(img2, "rb") as f2:
        response = client.post(
            "/api/v1/inspections/upload/batch",
            files=[
                ("files", ("crazing.jpg", f1, "image/jpeg")),
                ("files", ("normal.jpg", f2, "image/jpeg")),
            ],
            data={"batch_name": "Test Factory Batch #101"},
        )

    assert response.status_code == 200, f"Batch upload failed: {response.text}"
    data = response.json()
    assert data["batch_id"] is not None
    assert data["total_files"] == 2
    assert len(data["inspection_ids"]) == 2
    assert data["status"] == "COMPLETED"


def test_inspection_history_and_filters():
    # List all
    res = client.get("/api/v1/inspections?page=1&page_size=10")
    assert res.status_code == 200
    data = res.json()
    assert "total_count" in data
    assert data["total_count"] >= 3
    assert len(data["items"]) >= 3

    # Filter by decision
    filtered = client.get("/api/v1/inspections?quality_decision=APPROVED")
    assert filtered.status_code == 200
    f_data = filtered.json()
    for item in f_data["items"]:
        assert item["quality_decision"] == "APPROVED"


def test_analytics_endpoints():
    # Overview
    res = client.get("/api/v1/analytics/overview")
    assert res.status_code == 200
    data = res.json()
    assert data["total_inspections"] >= 3
    assert data["completed_inspections"] >= 3
    assert "first_pass_yield_pct" in data
    assert "rejection_rate_pct" in data
    assert "total_defects_detected" in data
    assert 0.0 <= data["first_pass_yield_pct"] <= 100.0
    assert 0.0 <= data["rejection_rate_pct"] <= 100.0

    # Defect distribution
    dist_res = client.get("/api/v1/analytics/defect-distribution")
    assert dist_res.status_code == 200
    dist_data = dist_res.json()
    assert len(dist_data) == 6  # All 6 NEU-DET classes present

    # Trends
    trend_res = client.get("/api/v1/analytics/trends?days=7")
    assert trend_res.status_code == 200
    trend_data = trend_res.json()
    assert isinstance(trend_data, list)
    if len(trend_data) > 0:
        assert "date" in trend_data[0]
        assert "total_inspections" in trend_data[0]
        assert "first_pass_yield_pct" in trend_data[0]


def test_quality_rules_api():
    # Get active rules
    res = client.get("/api/v1/quality-rules")
    assert res.status_code == 200
    rules = res.json()
    assert "confidence_threshold" in rules
    assert "critical_defects" in rules

    # Update rules
    rules["confidence_threshold"] = 0.30
    rules["max_allowed_defects"] = 3
    put_res = client.put("/api/v1/quality-rules", json=rules)
    assert put_res.status_code == 200
    updated = put_res.json()
    assert updated["confidence_threshold"] == 0.30
    assert updated["max_allowed_defects"] == 3

    # Reset rules
    reset_res = client.post("/api/v1/quality-rules/reset")
    assert reset_res.status_code == 200
    assert reset_res.json()["confidence_threshold"] == 0.25


def test_csv_report_download():
    res = client.get("/api/v1/reports/csv")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/csv")
    csv_text = res.text
    lines = csv_text.strip().split("\r\n") if "\r\n" in csv_text else csv_text.strip().split("\n")
    assert len(lines) >= 2  # Header + at least 1 row
    assert "Inspection ID" in lines[0]
    assert "Quality Decision" in lines[0]
    assert "Total Defects" in lines[0]


def test_file_validation_errors():
    # Invalid extension (.txt)
    response = client.post(
        "/api/v1/inspections/upload/image",
        files={"file": ("invalid_file.txt", b"not an image", "text/plain")},
    )
    assert response.status_code == 400
    assert "Invalid image format" in response.json()["detail"]


def test_video_upload():
    video_path = settings.SAMPLES_DIR / "sample_inspection_short.mp4"
    assert video_path.exists(), f"Sample video {video_path} not found."

    with open(video_path, "rb") as f:
        res = client.post(
            "/api/v1/inspections/upload/video",
            files={"file": ("sample_inspection_short.mp4", f, "video/mp4")},
            data={"stride": "5"},
        )
    assert res.status_code == 200, f"Video upload error: {res.text}"
    v_data = res.json()
    v_id = v_data["id"]
    assert v_data["file_type"] == "video"
    assert v_data["status"] in ["PENDING", "PROCESSING", "COMPLETED"]

    # Poll progress endpoint
    prog = client.get(f"/api/v1/inspections/{v_id}/progress")
    assert prog.status_code == 200
    assert "progress_percent" in prog.json()


if __name__ == "__main__":
    print("Running FastAPI integration test suite...")
    test_system_and_health_endpoints()
    print("-> test_system_and_health_endpoints: PASSED")
    test_single_image_upload_and_inference()
    print("-> test_single_image_upload_and_inference: PASSED")
    test_batch_image_upload()
    print("-> test_batch_image_upload: PASSED")
    test_inspection_history_and_filters()
    print("-> test_inspection_history_and_filters: PASSED")
    test_analytics_endpoints()
    print("-> test_analytics_endpoints: PASSED")
    test_quality_rules_api()
    print("-> test_quality_rules_api: PASSED")
    test_csv_report_download()
    print("-> test_csv_report_download: PASSED")
    test_file_validation_errors()
    print("-> test_file_validation_errors: PASSED")
    test_video_upload()
    print("-> test_video_upload: PASSED")
    print("\nALL FASTAPI INTEGRATION TESTS PASSED SUCCESSFULLY!")
