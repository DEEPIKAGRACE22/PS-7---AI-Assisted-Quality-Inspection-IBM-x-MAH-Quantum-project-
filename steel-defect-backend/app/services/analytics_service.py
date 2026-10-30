"""Analytics Service for Industrial Quality Control Dashboard.
Executes real SQL aggregation queries on the SQLite database.
Computes Total Inspections, Defect Distribution, Rejection Rate, First-Pass Yield (FPY),
and chronological defect trends.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta

from app.database import get_db_connection
from app.models.schemas import (
    AnalyticsOverviewResponse,
    DefectDistributionItem,
    DefectTrendItem,
)
from app.config import settings

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Computes production line quality KPIs from actual SQLite inspection records."""

    @classmethod
    def get_overview(cls) -> AnalyticsOverviewResponse:
        """Calculate high-level production quality KPIs: FPY, Rejection Rate, Defect Rates."""
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Inspections status and quality decision aggregation
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'COMPLETED' THEN 1 ELSE 0 END) as completed,
                    SUM(CASE WHEN status = 'COMPLETED' AND quality_decision = 'APPROVED' THEN 1 ELSE 0 END) as approved,
                    SUM(CASE WHEN status = 'COMPLETED' AND quality_decision = 'REVIEW_REQUIRED' THEN 1 ELSE 0 END) as review_req,
                    SUM(CASE WHEN status = 'COMPLETED' AND quality_decision = 'REJECTED' THEN 1 ELSE 0 END) as rejected,
                    AVG(CASE WHEN status = 'COMPLETED' THEN inference_time_ms ELSE NULL END) as avg_latency
                FROM inspections;
            """)
            row = cursor.fetchone()

            total = row["total"] or 0
            completed = row["completed"] or 0
            approved = row["approved"] or 0
            review_req = row["review_req"] or 0
            rejected = row["rejected"] or 0
            avg_latency = round(row["avg_latency"] or 0.0, 2)

            # Defects aggregation
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_defects,
                    COUNT(DISTINCT inspection_id) as inspections_with_defects
                FROM defects;
            """)
            d_row = cursor.fetchone()
            total_defects = d_row["total_defects"] or 0
            inspections_with_defects = d_row["inspections_with_defects"] or 0

        # KPI formulas
        base = max(1, completed)
        approved_pct = round((approved / base) * 100, 2) if completed > 0 else 0.0
        review_req_pct = round((review_req / base) * 100, 2) if completed > 0 else 0.0
        rejected_pct = round((rejected / base) * 100, 2) if completed > 0 else 0.0
        
        # First-Pass Yield (FPY): Percentage of parts manufactured defect-free and approved on first inspection
        first_pass_yield = approved_pct
        rejection_rate = rejected_pct

        avg_defects_per_insp = round(total_defects / base, 2) if completed > 0 else 0.0
        defect_free_count = completed - inspections_with_defects
        defect_free_rate = round((defect_free_count / base) * 100, 2) if completed > 0 else 0.0

        return AnalyticsOverviewResponse(
            total_inspections=total,
            completed_inspections=completed,
            approved_count=approved,
            approved_pct=approved_pct,
            review_required_count=review_req,
            review_required_pct=review_req_pct,
            rejected_count=rejected,
            rejected_pct=rejected_pct,
            first_pass_yield_pct=first_pass_yield,
            rejection_rate_pct=rejection_rate,
            total_defects_detected=total_defects,
            avg_defects_per_inspection=avg_defects_per_insp,
            avg_inference_time_ms=avg_latency,
            defect_free_rate_pct=defect_free_rate,
        )

    @classmethod
    def get_defect_distribution(cls) -> List[DefectDistributionItem]:
        """Compute defect frequency, percentage breakdown, and average confidence per class."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Total defects count
            cursor.execute("SELECT COUNT(*) as total FROM defects;")
            total_defects = cursor.fetchone()["total"] or 0

            # Group by class
            cursor.execute("""
                SELECT 
                    class_id,
                    class_name,
                    COUNT(*) as count,
                    AVG(confidence) as avg_conf
                FROM defects
                GROUP BY class_id, class_name
                ORDER BY count DESC;
            """)
            rows = cursor.fetchall()

        results: List[DefectDistributionItem] = []
        for r in rows:
            cnt = r["count"]
            pct = round((cnt / max(1, total_defects)) * 100, 2) if total_defects > 0 else 0.0
            results.append(
                DefectDistributionItem(
                    class_id=r["class_id"],
                    class_name=r["class_name"],
                    count=cnt,
                    percentage=pct,
                    avg_confidence=round(r["avg_conf"] or 0.0, 4),
                )
            )

        # Include classes with 0 detections for completeness in industrial reporting
        seen_classes = {item.class_name for item in results}
        for class_id, class_name in settings.NEU_CLASSES.items():
            if class_name not in seen_classes:
                results.append(
                    DefectDistributionItem(
                        class_id=class_id,
                        class_name=class_name,
                        count=0,
                        percentage=0.0,
                        avg_confidence=0.0,
                    )
                )

        return results

    @classmethod
    def get_defect_trends(cls, days: int = 30) -> List[DefectTrendItem]:
        """Query defect frequency and First-Pass Yield trends grouped by calendar date."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    substr(created_at, 1, 10) as day,
                    COUNT(*) as total_inspections,
                    SUM(CASE WHEN quality_decision = 'APPROVED' THEN 1 ELSE 0 END) as approved,
                    SUM(CASE WHEN quality_decision = 'REVIEW_REQUIRED' THEN 1 ELSE 0 END) as review_req,
                    SUM(CASE WHEN quality_decision = 'REJECTED' THEN 1 ELSE 0 END) as rejected,
                    SUM(total_defects) as defects_count
                FROM inspections
                WHERE status = 'COMPLETED'
                GROUP BY substr(created_at, 1, 10)
                ORDER BY day ASC
                LIMIT ?;
            """, (days,))
            rows = cursor.fetchall()

        trends: List[DefectTrendItem] = []
        for r in rows:
            tot = r["total_inspections"] or 0
            appr = r["approved"] or 0
            fpy = round((appr / max(1, tot)) * 100, 2) if tot > 0 else 0.0

            trends.append(
                DefectTrendItem(
                    date=r["day"],
                    total_inspections=tot,
                    approved=appr,
                    review_required=r["review_req"] or 0,
                    rejected=r["rejected"] or 0,
                    defects_count=r["defects_count"] or 0,
                    first_pass_yield_pct=fpy,
                )
            )

        return trends
