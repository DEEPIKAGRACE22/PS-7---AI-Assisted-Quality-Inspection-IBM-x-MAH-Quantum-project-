"""Inspection orchestration service.
Handles validation, storage, YOLO inference execution, database transactions,
and background video processing workflows.
"""

import asyncio
import logging
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any

import cv2
from fastapi import UploadFile, HTTPException

from app.config import settings
from app.database import get_db_connection
from app.models.schemas import (
    DefectDetection,
    InspectionResponse,
    InspectionListResponse,
    InspectionProgressResponse,
    InspectionStatusEnum,
    QualityDecisionEnum,
    BatchUploadResponse,
    BatchDetailResponse,
    BoundingBox,
)
from app.services.quality_service import quality_engine
from app.services.websocket_manager import ws_manager
from app.services.yolo_service import get_yolo_service

logger = logging.getLogger(__name__)


class InspectionService:
    """Manages the full lifecycle of steel surface defect inspections."""

    @staticmethod
    def _validate_image_file(file: UploadFile) -> str:
        """Validate uploaded image extension and basic format."""
        ext = Path(file.filename).suffix.lower()
        if ext not in settings.ALLOWED_IMAGE_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid image format '{ext}'. Allowed formats: {sorted(list(settings.ALLOWED_IMAGE_EXTENSIONS))}",
            )
        return ext

    @staticmethod
    def _validate_video_file(file: UploadFile) -> str:
        """Validate uploaded video extension."""
        ext = Path(file.filename).suffix.lower()
        if ext not in settings.ALLOWED_VIDEO_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid video format '{ext}'. Allowed formats: {sorted(list(settings.ALLOWED_VIDEO_EXTENSIONS))}",
            )
        return ext

    @classmethod
    async def process_image_upload(
        cls,
        file: UploadFile,
        conf_threshold: Optional[float] = None,
        iou_threshold: Optional[float] = None,
        device: Optional[str] = None,
        batch_id: Optional[str] = None,
    ) -> InspectionResponse:
        """Process a single image inspection immediately and record to database."""
        ext = cls._validate_image_file(file)
        inspection_id = str(uuid.uuid4())
        safe_filename = f"{inspection_id}_{Path(file.filename).name}"
        upload_path = settings.UPLOADS_DIR / safe_filename
        annotated_path = settings.ANNOTATED_DIR / f"{inspection_id}_annotated.jpg"

        # 1. Stream file to disk
        file_size = 0
        try:
            with open(upload_path, "wb") as buffer:
                while content := await file.read(1024 * 1024):  # 1MB chunks
                    file_size += len(content)
                    if file_size > settings.MAX_IMAGE_SIZE_MB * 1024 * 1024:
                        raise HTTPException(
                            status_code=413,
                            detail=f"Image exceeds maximum allowable size of {settings.MAX_IMAGE_SIZE_MB}MB",
                        )
                    buffer.write(content)
        except Exception as e:
            if upload_path.exists():
                upload_path.unlink()
            raise HTTPException(status_code=500, detail=f"Failed to save uploaded image: {e}")

        # Verify image readable with OpenCV
        test_img = cv2.imread(str(upload_path))
        if test_img is None:
            if upload_path.exists():
                upload_path.unlink()
            raise HTTPException(status_code=400, detail="Corrupted or unreadable image file.")

        now = datetime.now(timezone.utc).isoformat()

        # 2. Insert initial PENDING/PROCESSING record in DB
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO inspections (
                    id, file_name, file_type, file_path, annotated_path,
                    file_size_bytes, status, quality_decision, progress_percent,
                    batch_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                inspection_id,
                file.filename,
                "batch_item" if batch_id else "image",
                str(upload_path),
                str(annotated_path),
                file_size,
                InspectionStatusEnum.PROCESSING.value,
                QualityDecisionEnum.UNKNOWN.value,
                50.0,
                batch_id,
                now,
                now,
            ))

        # 3. Execute YOLO Inference
        yolo_service = get_yolo_service()
        try:
            detections, annotated_img, latency_ms = yolo_service.detect_image(
                image_input=upload_path,
                conf=conf_threshold,
                iou=iou_threshold,
                device=device,
            )

            # Save annotated image
            cv2.imwrite(str(annotated_path), annotated_img)

            # 4. Evaluate Industrial Quality Decision
            quality_result = quality_engine.evaluate(detections)

            max_conf = max([d.confidence for d in detections], default=0.0)
            completed_now = datetime.now(timezone.utc).isoformat()

            # 5. Persist defects & completed inspection record
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Save each detected defect
                for det in detections:
                    defect_id = str(uuid.uuid4())
                    cursor.execute("""
                        INSERT INTO defects (
                            id, inspection_id, class_id, class_name, confidence,
                            x1, y1, x2, y2, width, height, area, frame_number, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """, (
                        defect_id,
                        inspection_id,
                        det.class_id,
                        det.class_name,
                        det.confidence,
                        det.bbox.x1,
                        det.bbox.y1,
                        det.bbox.x2,
                        det.bbox.y2,
                        det.bbox.width,
                        det.bbox.height,
                        det.bbox.area,
                        0,
                        completed_now,
                    ))

                # Update inspection record
                cursor.execute("""
                    UPDATE inspections
                    SET status = ?,
                        quality_decision = ?,
                        decision_reason = ?,
                        total_defects = ?,
                        max_confidence = ?,
                        inference_time_ms = ?,
                        progress_percent = 100.0,
                        frames_processed = 1,
                        total_frames = 1,
                        updated_at = ?
                    WHERE id = ?;
                """, (
                    InspectionStatusEnum.COMPLETED.value,
                    quality_result.decision.value,
                    quality_result.reason,
                    len(detections),
                    round(max_conf, 4),
                    latency_ms,
                    completed_now,
                    inspection_id,
                ))

            # Broadcast event to WebSocket subscribers
            asyncio.create_task(
                ws_manager.broadcast_inspection_event(
                    inspection_id=inspection_id,
                    event_type="completed",
                    data={
                        "inspection_id": inspection_id,
                        "status": "COMPLETED",
                        "quality_decision": quality_result.decision.value,
                        "decision_reason": quality_result.reason,
                        "total_defects": len(detections),
                        "max_confidence": round(max_conf, 4),
                        "inference_time_ms": latency_ms,
                    },
                )
            )

            return cls.get_inspection_by_id(inspection_id)

        except Exception as e:
            logger.error(f"Inference error on inspection {inspection_id}: {e}", exc_info=True)
            failed_now = datetime.now(timezone.utc).isoformat()
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE inspections
                    SET status = ?, error_message = ?, updated_at = ?
                    WHERE id = ?;
                """, (
                    InspectionStatusEnum.FAILED.value,
                    str(e),
                    failed_now,
                    inspection_id,
                ))
            raise HTTPException(status_code=500, detail=f"Inference execution failed: {e}")

    @classmethod
    async def process_batch_upload(
        cls,
        files: List[UploadFile],
        batch_name: Optional[str] = None,
        conf_threshold: Optional[float] = None,
    ) -> BatchUploadResponse:
        """Process multiple images sequentially or in background."""
        if not files:
            raise HTTPException(status_code=400, detail="No files provided in batch upload.")

        batch_id = str(uuid.uuid4())
        name = batch_name or f"Inspection Batch {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}"
        now = datetime.now(timezone.utc).isoformat()

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO batches (id, name, total_items, processed_items, status, created_at, updated_at)
                VALUES (?, ?, ?, 0, 'PROCESSING', ?, ?);
            """, (batch_id, name, len(files), now, now))

        inspection_ids: List[str] = []

        # Process each item
        for file in files:
            try:
                res = await cls.process_image_upload(
                    file=file,
                    conf_threshold=conf_threshold,
                    batch_id=batch_id,
                )
                inspection_ids.append(res.id)
                # Increment processed count
                with get_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE batches
                        SET processed_items = processed_items + 1, updated_at = ?
                        WHERE id = ?;
                    """, (datetime.now(timezone.utc).isoformat(), batch_id))
            except Exception as e:
                logger.error(f"Error processing item '{file.filename}' in batch {batch_id}: {e}")

        # Update batch completion
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE batches
                SET status = 'COMPLETED', updated_at = ?
                WHERE id = ?;
            """, (datetime.now(timezone.utc).isoformat(), batch_id))

        return BatchUploadResponse(
            batch_id=batch_id,
            name=name,
            total_files=len(files),
            inspection_ids=inspection_ids,
            status="COMPLETED",
            created_at=now,
        )

    @classmethod
    async def process_video_upload(
        cls,
        file: UploadFile,
        conf_threshold: Optional[float] = None,
        stride: Optional[int] = None,
    ) -> InspectionResponse:
        """Upload video and launch asynchronous inspection processing."""
        ext = cls._validate_video_file(file)
        inspection_id = str(uuid.uuid4())
        safe_filename = f"{inspection_id}_{Path(file.filename).name}"
        upload_path = settings.UPLOADS_DIR / safe_filename
        annotated_path = settings.ANNOTATED_DIR / f"{inspection_id}_annotated.mp4"

        # Stream file to disk
        file_size = 0
        try:
            with open(upload_path, "wb") as buffer:
                while content := await file.read(2 * 1024 * 1024):  # 2MB chunks
                    file_size += len(content)
                    if file_size > settings.MAX_VIDEO_SIZE_MB * 1024 * 1024:
                        raise HTTPException(
                            status_code=413,
                            detail=f"Video exceeds maximum allowable size of {settings.MAX_VIDEO_SIZE_MB}MB",
                        )
                    buffer.write(content)
        except Exception as e:
            if upload_path.exists():
                upload_path.unlink()
            raise HTTPException(status_code=500, detail=f"Failed to save video upload: {e}")

        # Check video properties
        cap = cv2.VideoCapture(str(upload_path))
        if not cap.isOpened():
            if upload_path.exists():
                upload_path.unlink()
            raise HTTPException(status_code=400, detail="Corrupted or unsupported video file format.")
        
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()

        now = datetime.now(timezone.utc).isoformat()

        # Insert PENDING record in DB
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO inspections (
                    id, file_name, file_type, file_path, annotated_path,
                    file_size_bytes, status, quality_decision, progress_percent,
                    frames_processed, total_frames, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0.0, 0, ?, ?, ?);
            """, (
                inspection_id,
                file.filename,
                "video",
                str(upload_path),
                str(annotated_path),
                file_size,
                InspectionStatusEnum.PROCESSING.value,
                QualityDecisionEnum.UNKNOWN.value,
                max(1, total_frames),
                now,
                now,
            ))

        # Launch background processing task in asyncio loop / threadpool
        asyncio.create_task(
            cls._execute_video_pipeline(
                inspection_id=inspection_id,
                upload_path=upload_path,
                annotated_path=annotated_path,
                conf_threshold=conf_threshold,
                stride=stride or settings.VIDEO_SAMPLE_STRIDE,
                total_frames=total_frames,
            )
        )

        return cls.get_inspection_by_id(inspection_id)

    @classmethod
    async def _execute_video_pipeline(
        cls,
        inspection_id: str,
        upload_path: Path,
        annotated_path: Path,
        conf_threshold: Optional[float],
        stride: int,
        total_frames: int,
    ) -> None:
        """Background worker for frame-by-frame video inference, DB updates, and WebSocket broadcasting."""
        logger.info(f"Video pipeline started for inspection {inspection_id}")
        loop = asyncio.get_running_loop()
        yolo_service = get_yolo_service()

        def sync_progress_callback(prog_data: Dict[str, Any]):
            # Thread-safe dispatch of progress events
            pct = prog_data["progress_percent"]
            curr_frame = prog_data["frame_index"]
            tot_frame = prog_data["total_frames"]
            defects_found = prog_data["total_defects_so_far"]

            # Update DB progress
            try:
                with get_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE inspections
                        SET progress_percent = ?, frames_processed = ?, total_frames = ?, updated_at = ?
                        WHERE id = ?;
                    """, (pct, curr_frame, tot_frame, datetime.now(timezone.utc).isoformat(), inspection_id))
            except Exception as dbe:
                logger.debug(f"DB progress update error: {dbe}")

            # Send WebSocket frame update
            asyncio.run_coroutine_threadsafe(
                ws_manager.broadcast_inspection_event(
                    inspection_id=inspection_id,
                    event_type="progress",
                    data={
                        "inspection_id": inspection_id,
                        "status": "PROCESSING",
                        "frame_index": curr_frame,
                        "total_frames": tot_frame,
                        "progress_percent": pct,
                        "fps": prog_data["fps"],
                        "current_defects_found": defects_found,
                        "elapsed_seconds": prog_data["elapsed_seconds"],
                        "alert_status": "DEFECT ALERT" if defects_found > 0 else "NO HIGH-CONFIDENCE ALERT",
                    },
                ),
                loop,
            )

        try:
            # Run heavy video processing in executor thread to prevent blocking FastAPI event loop
            result = await loop.run_in_executor(
                None,
                lambda: yolo_service.process_video(
                    video_path=upload_path,
                    output_video_path=annotated_path,
                    conf=conf_threshold,
                    progress_callback=sync_progress_callback,
                    stride=stride,
                ),
            )

            detections: List[DefectDetection] = result["detections"]
            latency_ms = result["inference_time_ms"]
            total_defects = len(detections)

            # Evaluate Quality Decision
            quality_result = quality_engine.evaluate(detections)
            max_conf = max([d.confidence for d in detections], default=0.0)
            completed_now = datetime.now(timezone.utc).isoformat()

            # Persist defects and finalize inspection in DB
            with get_db_connection() as conn:
                cursor = conn.cursor()
                for det in detections:
                    defect_id = str(uuid.uuid4())
                    cursor.execute("""
                        INSERT INTO defects (
                            id, inspection_id, class_id, class_name, confidence,
                            x1, y1, x2, y2, width, height, area, frame_number, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """, (
                        defect_id,
                        inspection_id,
                        det.class_id,
                        det.class_name,
                        det.confidence,
                        det.bbox.x1,
                        det.bbox.y1,
                        det.bbox.x2,
                        det.bbox.y2,
                        det.bbox.width,
                        det.bbox.height,
                        det.bbox.area,
                        det.frame_number,
                        completed_now,
                    ))

                cursor.execute("""
                    UPDATE inspections
                    SET status = ?,
                        quality_decision = ?,
                        decision_reason = ?,
                        total_defects = ?,
                        max_confidence = ?,
                        inference_time_ms = ?,
                        progress_percent = 100.0,
                        frames_processed = ?,
                        total_frames = ?,
                        updated_at = ?
                    WHERE id = ?;
                """, (
                    InspectionStatusEnum.COMPLETED.value,
                    quality_result.decision.value,
                    quality_result.reason,
                    total_defects,
                    round(max_conf, 4),
                    latency_ms,
                    result["processed_frames"],
                    result["total_frames"],
                    completed_now,
                    inspection_id,
                ))

            # Broadcast completion event via WebSocket
            await ws_manager.broadcast_inspection_event(
                inspection_id=inspection_id,
                event_type="completed",
                data={
                    "inspection_id": inspection_id,
                    "status": "COMPLETED",
                    "quality_decision": quality_result.decision.value,
                    "decision_reason": quality_result.reason,
                    "total_defects": total_defects,
                    "max_confidence": round(max_conf, 4),
                    "inference_time_ms": latency_ms,
                    "annotated_video": f"/api/v1/inspections/{inspection_id}/annotated-file",
                },
            )
            logger.info(f"Video inspection {inspection_id} completed successfully.")

        except Exception as e:
            logger.error(f"Video background pipeline failed for {inspection_id}: {e}", exc_info=True)
            failed_now = datetime.now(timezone.utc).isoformat()
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE inspections
                    SET status = ?, error_message = ?, updated_at = ?
                    WHERE id = ?;
                """, (InspectionStatusEnum.FAILED.value, str(e), failed_now, inspection_id))

            await ws_manager.broadcast_inspection_event(
                inspection_id=inspection_id,
                event_type="error",
                data={"inspection_id": inspection_id, "error": str(e)},
            )

    @classmethod
    def get_inspection_by_id(cls, inspection_id: str) -> InspectionResponse:
        """Fetch inspection and its defects from SQLite."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM inspections WHERE id = ?;", (inspection_id,))
            insp_row = cursor.fetchone()
            if not insp_row:
                raise HTTPException(status_code=404, detail=f"Inspection '{inspection_id}' not found.")

            cursor.execute("""
                SELECT id, class_id, class_name, confidence, x1, y1, x2, y2, width, height, area, frame_number
                FROM defects
                WHERE inspection_id = ?
                ORDER BY confidence DESC;
            """, (inspection_id,))
            defect_rows = cursor.fetchall()

        defects = [
            DefectDetection(
                id=d["id"],
                class_id=d["class_id"],
                class_name=d["class_name"],
                confidence=round(d["confidence"], 4),
                bbox=BoundingBox(
                    x1=d["x1"],
                    y1=d["y1"],
                    x2=d["x2"],
                    y2=d["y2"],
                    width=d["width"],
                    height=d["height"],
                    area=d["area"],
                ),
                frame_number=d["frame_number"],
            )
            for d in defect_rows
        ]

        annotated_url = (
            f"/api/v1/inspections/{inspection_id}/annotated-file"
            if insp_row["annotated_path"] and Path(insp_row["annotated_path"]).exists()
            else None
        )
        original_url = f"/api/v1/inspections/{inspection_id}/original-file"

        return InspectionResponse(
            id=insp_row["id"],
            file_name=insp_row["file_name"],
            file_type=insp_row["file_type"],
            file_size_bytes=insp_row["file_size_bytes"],
            status=InspectionStatusEnum(insp_row["status"]),
            quality_decision=QualityDecisionEnum(insp_row["quality_decision"]),
            decision_reason=insp_row["decision_reason"],
            total_defects=insp_row["total_defects"],
            max_confidence=round(insp_row["max_confidence"], 4),
            inference_time_ms=insp_row["inference_time_ms"],
            progress_percent=insp_row["progress_percent"],
            frames_processed=insp_row["frames_processed"],
            total_frames=insp_row["total_frames"],
            batch_id=insp_row["batch_id"],
            error_message=insp_row["error_message"],
            created_at=insp_row["created_at"],
            updated_at=insp_row["updated_at"],
            defects=defects,
            annotated_url=annotated_url,
            original_url=original_url,
        )

    @classmethod
    def get_inspection_progress(cls, inspection_id: str) -> InspectionProgressResponse:
        """Fetch current processing progress for live polling."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, status, progress_percent, frames_processed, total_frames,
                       total_defects, quality_decision, inference_time_ms, error_message
                FROM inspections
                WHERE id = ?;
            """, (inspection_id,))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail=f"Inspection '{inspection_id}' not found.")

        return InspectionProgressResponse(
            inspection_id=row["id"],
            status=InspectionStatusEnum(row["status"]),
            progress_percent=round(row["progress_percent"], 1),
            frames_processed=row["frames_processed"],
            total_frames=row["total_frames"],
            current_defects_found=row["total_defects"],
            quality_decision=QualityDecisionEnum(row["quality_decision"]) if row["quality_decision"] != "UNKNOWN" else None,
            inference_time_ms=row["inference_time_ms"],
            message=row["error_message"],
        )

    @classmethod
    def list_inspections(
        cls,
        page: int = 1,
        page_size: int = 20,
        quality_decision: Optional[str] = None,
        status: Optional[str] = None,
        defect_type: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> InspectionListResponse:
        """Query inspection history with pagination and dynamic filtering."""
        page = max(1, page)
        page_size = min(100, max(1, page_size))
        offset = (page - 1) * page_size

        where_clauses: List[str] = []
        params: List[Any] = []

        if quality_decision:
            where_clauses.append("i.quality_decision = ?")
            params.append(quality_decision.upper())

        if status:
            where_clauses.append("i.status = ?")
            params.append(status.upper())

        if start_date:
            where_clauses.append("i.created_at >= ?")
            params.append(start_date)

        if end_date:
            where_clauses.append("i.created_at <= ?")
            params.append(end_date)

        if defect_type:
            where_clauses.append("EXISTS (SELECT 1 FROM defects d WHERE d.inspection_id = i.id AND d.class_name = ?)")
            params.append(defect_type.lower())

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        with get_db_connection() as conn:
            cursor = conn.cursor()
            # Count total matching rows
            count_query = f"SELECT COUNT(*) as total FROM inspections i {where_sql};"
            cursor.execute(count_query, params)
            total_count = cursor.fetchone()["total"]

            # Select paginated inspection IDs
            select_query = f"""
                SELECT i.id
                FROM inspections i
                {where_sql}
                ORDER BY i.created_at DESC
                LIMIT ? OFFSET ?;
            """
            cursor.execute(select_query, params + [page_size, offset])
            id_rows = cursor.fetchall()

        items = [cls.get_inspection_by_id(r["id"]) for r in id_rows]
        total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 1

        return InspectionListResponse(
            total_count=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            items=items,
        )

    @classmethod
    def delete_inspection(cls, inspection_id: str) -> None:
        """Delete inspection record, defect rows, and on-disk files."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT file_path, annotated_path FROM inspections WHERE id = ?;", (inspection_id,))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail=f"Inspection '{inspection_id}' not found.")

            file_path = row["file_path"]
            annotated_path = row["annotated_path"]

            cursor.execute("DELETE FROM inspections WHERE id = ?;", (inspection_id,))

        # Remove files from disk
        if file_path and os.path.exists(file_path):
            try:
                os.unlink(file_path)
            except OSError:
                pass

        if annotated_path and os.path.exists(annotated_path):
            try:
                os.unlink(annotated_path)
            except OSError:
                pass
