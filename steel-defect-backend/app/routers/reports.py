"""Reports API endpoints.
Provides downloadable CSV inspection reports.
"""

from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.services.report_service import ReportService

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get(
    "/csv",
    summary="Download comprehensive inspection audit log as CSV",
    description="Streams a CSV report of inspections matching specified date ranges and quality filters.",
)
def download_inspections_csv(
    start_date: Optional[str] = Query(None, description="Start date filter (YYYY-MM-DD or ISO 8601)"),
    end_date: Optional[str] = Query(None, description="End date filter (YYYY-MM-DD or ISO 8601)"),
    quality_decision: Optional[str] = Query(None, description="Filter by decision: APPROVED, REVIEW_REQUIRED, REJECTED"),
    defect_type: Optional[str] = Query(None, description="Filter by defect type: crazing, inclusion, patches, etc."),
):
    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"steel_inspection_report_{timestamp_str}.csv"

    csv_generator = ReportService.generate_inspection_csv_stream(
        start_date=start_date,
        end_date=end_date,
        quality_decision=quality_decision,
        defect_type=defect_type,
    )

    return StreamingResponse(
        csv_generator,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Cache-Control": "no-cache",
        },
    )
