"""Inspection router endpoints.
Supports single image, batch upload, video detection, inspection details,
history listing, file streaming, and progress tracking.
"""

import os
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Form, Query, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse

from app.models.schemas import (
    InspectionResponse,
    InspectionListResponse,
    InspectionProgressResponse,
    BatchUploadResponse,
)
from app.services.inspection_service import InspectionService

router = APIRouter(prefix="/inspections", tags=["Inspections"])


@router.post(
    "/upload/image",
    response_model=InspectionResponse,
    summary="Upload and inspect a single steel surface image",
    description="Processes an image using YOLO11n NEU-DET model, runs quality classification, and stores results.",
)
async def upload_single_image(
    file: UploadFile = File(..., description="Steel surface image file (.jpg, .png, etc.)"),
    conf_threshold: Optional[float] = Form(None, description="Detection confidence threshold override (0.05 - 1.0)"),
    iou_threshold: Optional[float] = Form(None, description="NMS IoU threshold override (0.1 - 1.0)"),
    device: Optional[str] = Form(None, description="Inference device: 'cpu', 'cuda', 'cuda:0', or 'auto'"),
):
    return await InspectionService.process_image_upload(
        file=file,
        conf_threshold=conf_threshold,
        iou_threshold=iou_threshold,
        device=device,
    )


@router.post(
    "/upload/batch",
    response_model=BatchUploadResponse,
    summary="Upload and inspect multiple steel surface images in batch",
    description="Uploads a collection of images, assigns a batch identifier, and processes each item.",
)
async def upload_batch_images(
    files: List[UploadFile] = File(..., description="List of steel surface images"),
    batch_name: Optional[str] = Form(None, description="Optional custom name for this inspection batch"),
    conf_threshold: Optional[float] = Form(None, description="Detection confidence threshold override"),
):
    return await InspectionService.process_batch_upload(
        files=files,
        batch_name=batch_name,
        conf_threshold=conf_threshold,
    )


@router.post(
    "/upload/video",
    response_model=InspectionResponse,
    summary="Upload steel surface inspection video for asynchronous processing",
    description="Accepts continuous inspection video, initiates asynchronous YOLO frame detection, and reports progress via WebSockets.",
)
async def upload_video(
    file: UploadFile = File(..., description="Continuous inspection video file (.mp4, .avi, etc.)"),
    conf_threshold: Optional[float] = Form(None, description="Detection confidence threshold override"),
    stride: Optional[int] = Form(None, description="Frame processing stride (default: 2)"),
):
    return await InspectionService.process_video_upload(
        file=file,
        conf_threshold=conf_threshold,
        stride=stride,
    )


@router.get(
    "/{inspection_id}",
    response_model=InspectionResponse,
    summary="Get full inspection details by ID",
    description="Returns inspection metadata, quality decision, defect bounding boxes, and media links.",
)
def get_inspection(inspection_id: str):
    return InspectionService.get_inspection_by_id(inspection_id)


@router.get(
    "/{inspection_id}/progress",
    response_model=InspectionProgressResponse,
    summary="Get real-time processing progress for an inspection",
)
def get_inspection_progress(inspection_id: str):
    return InspectionService.get_inspection_progress(inspection_id)


@router.get(
    "/",
    response_model=InspectionListResponse,
    summary="List inspection history with pagination and filters",
    description="Supports filtering by quality decision (APPROVED, REVIEW_REQUIRED, REJECTED), status, defect type, and date range.",
)
def list_inspections(
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    quality_decision: Optional[str] = Query(None, description="Filter by decision: APPROVED, REVIEW_REQUIRED, REJECTED"),
    status: Optional[str] = Query(None, description="Filter by status: PENDING, PROCESSING, COMPLETED, FAILED"),
    defect_type: Optional[str] = Query(None, description="Filter by defect type: crazing, inclusion, patches, pitted_surface, rolled-in_scale, scratches"),
    start_date: Optional[str] = Query(None, description="Start timestamp filter (ISO 8601)"),
    end_date: Optional[str] = Query(None, description="End timestamp filter (ISO 8601)"),
):
    return InspectionService.list_inspections(
        page=page,
        page_size=page_size,
        quality_decision=quality_decision,
        status=status,
        defect_type=defect_type,
        start_date=start_date,
        end_date=end_date,
    )


@router.get(
    "/{inspection_id}/annotated-file",
    summary="Download or stream the annotated inspection image/video",
)
def get_annotated_file(inspection_id: str):
    inspection = InspectionService.get_inspection_by_id(inspection_id)
    # Check if annotated file exists on disk
    from app.database import get_db_connection
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT annotated_path, file_type FROM inspections WHERE id = ?;", (inspection_id,))
        row = cursor.fetchone()
        if not row or not row["annotated_path"] or not os.path.exists(row["annotated_path"]):
            raise HTTPException(status_code=404, detail="Annotated file not found or still processing.")

    media_type = "video/mp4" if row["file_type"] == "video" else "image/jpeg"
    return FileResponse(path=row["annotated_path"], media_type=media_type)


@router.get(
    "/{inspection_id}/original-file",
    summary="Download or stream the original uploaded inspection file",
)
def get_original_file(inspection_id: str):
    from app.database import get_db_connection
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT file_path, file_type, file_name FROM inspections WHERE id = ?;", (inspection_id,))
        row = cursor.fetchone()
        if not row or not row["file_path"] or not os.path.exists(row["file_path"]):
            raise HTTPException(status_code=404, detail="Original upload file not found.")

    media_type = "video/mp4" if row["file_type"] == "video" else "image/jpeg"
    return FileResponse(path=row["file_path"], media_type=media_type, filename=row["file_name"])


@router.delete(
    "/{inspection_id}",
    summary="Delete inspection record and associated media files",
)
def delete_inspection(inspection_id: str):
    InspectionService.delete_inspection(inspection_id)
    return {"message": f"Inspection '{inspection_id}' successfully deleted."}
