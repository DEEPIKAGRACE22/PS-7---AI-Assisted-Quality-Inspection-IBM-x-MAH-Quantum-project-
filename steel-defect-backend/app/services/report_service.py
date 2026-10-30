"""Report generation service for Steel Surface Defect Inspections.
Generates downloadable, audit-ready CSV reports directly from SQLite records.
"""

import csv
import io
import logging
from datetime import datetime, timezone
from typing import Optional, Generator, List, Any

from app.database import get_db_connection

logger = logging.getLogger(__name__)


class ReportService:
    """Generates standard industrial CSV inspection logs."""

    @classmethod
    def generate_inspection_csv_stream(
        cls,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        quality_decision: Optional[str] = None,
        defect_type: Optional[str] = None,
    ) -> Generator[str, None, None]:
        """Stream CSV rows directly to client with low memory footprint."""
        where_clauses: List[str] = ["i.status = 'COMPLETED'"]
        params: List[Any] = []

        if quality_decision:
            where_clauses.append("i.quality_decision = ?")
            params.append(quality_decision.upper())

        if start_date:
            where_clauses.append("i.created_at >= ?")
            params.append(start_date)

        if end_date:
            where_clauses.append("i.created_at <= ?")
            params.append(end_date)

        if defect_type:
            where_clauses.append("EXISTS (SELECT 1 FROM defects d WHERE d.inspection_id = i.id AND d.class_name = ?)")
            params.append(defect_type.lower())

        where_sql = f"WHERE {' AND '.join(where_clauses)}"

        query = f"""
            SELECT 
                i.id,
                i.created_at,
                i.file_name,
                i.file_type,
                i.status,
                i.quality_decision,
                i.decision_reason,
                i.total_defects,
                i.max_confidence,
                i.inference_time_ms,
                (
                    SELECT GROUP_CONCAT(DISTINCT d.class_name)
                    FROM defects d
                    WHERE d.inspection_id = i.id
                ) as defect_classes
            FROM inspections i
            {where_sql}
            ORDER BY i.created_at DESC;
        """

        output = io.StringIO()
        writer = csv.writer(output)

        # Write Header
        writer.writerow([
            "Inspection ID",
            "Timestamp (UTC)",
            "File Name",
            "File Type",
            "Status",
            "Quality Decision",
            "Decision Reason",
            "Total Defects",
            "Defect Classes Detected",
            "Max Confidence (%)",
            "Inference Latency (ms)",
        ])
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)

            while rows := cursor.fetchmany(100):
                for r in rows:
                    writer.writerow([
                        r["id"],
                        r["created_at"],
                        r["file_name"],
                        r["file_type"],
                        r["status"],
                        r["quality_decision"],
                        r["decision_reason"] or "",
                        r["total_defects"],
                        r["defect_classes"] or "None",
                        f"{r['max_confidence'] * 100:.1f}" if r["max_confidence"] else "0.0",
                        f"{r['inference_time_ms']:.1f}",
                    ])
                yield output.getvalue()
                output.seek(0)
                output.truncate(0)
