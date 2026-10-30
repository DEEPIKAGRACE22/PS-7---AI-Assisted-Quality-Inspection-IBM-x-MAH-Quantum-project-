"""Pydantic schemas for data validation and API contracts.
Industrial AI Steel Surface Defect Detection Platform.
"""

from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class QualityDecisionEnum(str, Enum):
    APPROVED = "APPROVED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"


class InspectionStatusEnum(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class BoundingBox(BaseModel):
    x1: float = Field(..., description="Top-left X coordinate in pixels")
    y1: float = Field(..., description="Top-left Y coordinate in pixels")
    x2: float = Field(..., description="Bottom-right X coordinate in pixels")
    y2: float = Field(..., description="Bottom-right Y coordinate in pixels")
    width: float = Field(..., description="Box width in pixels")
    height: float = Field(..., description="Box height in pixels")
    area: float = Field(..., description="Box area in square pixels")


class DefectDetection(BaseModel):
    id: Optional[str] = None
    class_id: int = Field(..., description="YOLO class index (0-5)")
    class_name: str = Field(..., description="NEU-DET class name: crazing, inclusion, patches, pitted_surface, rolled-in_scale, scratches")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Detection confidence score")
    bbox: BoundingBox
    frame_number: Optional[int] = Field(0, description="Frame index for video inspections")
    timestamp_s: Optional[float] = Field(0.0, description="Time of the frame in the source video, in seconds")


class QualityDecisionResult(BaseModel):
    decision: QualityDecisionEnum
    reason: str
    rules_triggered: List[str]
    max_confidence: float
    defect_counts: Dict[str, int]


class InspectionResponse(BaseModel):
    id: str
    file_name: str
    file_type: str
    file_size_bytes: int
    status: InspectionStatusEnum
    quality_decision: QualityDecisionEnum
    decision_reason: Optional[str] = None
    total_defects: int = 0
    max_confidence: float = 0.0
    inference_time_ms: float = 0.0
    progress_percent: float = 100.0
    frames_processed: int = 0
    total_frames: int = 1
    batch_id: Optional[str] = None
    error_message: Optional[str] = None
    created_at: str
    updated_at: str
    defects: List[DefectDetection] = []
    annotated_url: Optional[str] = None
    original_url: Optional[str] = None


class InspectionProgressResponse(BaseModel):
    inspection_id: str
    status: InspectionStatusEnum
    progress_percent: float
    frames_processed: int
    total_frames: int
    current_defects_found: int
    quality_decision: Optional[QualityDecisionEnum] = None
    inference_time_ms: float = 0.0
    message: Optional[str] = None


class InspectionListResponse(BaseModel):
    total_count: int
    page: int
    page_size: int
    total_pages: int
    items: List[InspectionResponse]


class BatchUploadResponse(BaseModel):
    batch_id: str
    name: str
    total_files: int
    inspection_ids: List[str]
    status: str
    created_at: str


class BatchDetailResponse(BaseModel):
    batch_id: str
    name: str
    total_items: int
    processed_items: int
    status: str
    created_at: str
    updated_at: str
    inspections: List[InspectionResponse]


class QualityRuleConfig(BaseModel):
    rule_name: str = "Standard Hot-Rolled Steel Quality Standard"
    confidence_threshold: float = Field(0.25, ge=0.05, le=1.0, description="Minimum confidence for general YOLO defect filtering")
    review_confidence_min: float = Field(0.25, ge=0.05, le=1.0, description="Detections below this are ignored; above this trigger at least REVIEW")
    critical_confidence_threshold: float = Field(0.50, ge=0.10, le=1.0, description="Confidence threshold that triggers immediate REJECTION for critical defects")
    reject_confidence_threshold: float = Field(0.70, ge=0.10, le=1.0, description="Confidence threshold that triggers immediate REJECTION regardless of class")
    max_allowed_defects: int = Field(2, ge=0, description="Maximum defects allowed before triggering REJECTED status")
    critical_defects: List[str] = Field(
        default=["rolled-in_scale", "inclusion", "pitted_surface"],
        description="Defect classes that cause immediate line rejection when detected with high confidence"
    )
    per_defect_tolerances: Dict[str, int] = Field(
        default={
            "crazing": 2,
            "inclusion": 0,
            "patches": 1,
            "pitted_surface": 0,
            "rolled-in_scale": 0,
            "scratches": 2
        },
        description="Maximum count allowed per defect class before forcing REJECTED"
    )


class AnalyticsOverviewResponse(BaseModel):
    total_inspections: int
    completed_inspections: int
    approved_count: int
    approved_pct: float
    review_required_count: int
    review_required_pct: float
    rejected_count: int
    rejected_pct: float
    first_pass_yield_pct: float = Field(..., description="FPY: (Approved / Total Completed) * 100")
    rejection_rate_pct: float = Field(..., description="Rejection Rate: (Rejected / Total Completed) * 100")
    total_defects_detected: int
    avg_defects_per_inspection: float
    avg_inference_time_ms: float
    defect_free_rate_pct: float


class DefectDistributionItem(BaseModel):
    class_id: int
    class_name: str
    count: int
    percentage: float
    avg_confidence: float


class DefectTrendItem(BaseModel):
    date: str
    total_inspections: int
    approved: int
    review_required: int
    rejected: int
    defects_count: int
    first_pass_yield_pct: float


class WebSocketProgressMessage(BaseModel):
    event: str  # 'progress', 'frame_detection', 'completed', 'error'
    inspection_id: str
    data: Dict[str, Any]
