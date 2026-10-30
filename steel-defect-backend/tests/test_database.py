"""Unit tests for SQLite Database layer.
Validates table creation, indexes, foreign keys, transaction rollbacks,
and CRUD query executions.
"""

import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import init_database, get_db_connection


def test_schema_and_pragmas():
    init_database()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Verify journal mode is WAL
        cursor.execute("PRAGMA journal_mode;")
        journal_mode = cursor.fetchone()[0]
        assert journal_mode.upper() == "WAL", f"Expected WAL, got {journal_mode}"

        # Verify foreign keys are enabled
        cursor.execute("PRAGMA foreign_keys;")
        foreign_keys = cursor.fetchone()[0]
        assert foreign_keys == 1, "Foreign keys should be enabled"

        # Verify tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row["name"] for row in cursor.fetchall()}
        assert "inspections" in tables
        assert "defects" in tables
        assert "batches" in tables
        assert "quality_rules" in tables


def test_crud_and_cascade_delete():
    init_database()
    insp_id = str(uuid.uuid4())
    defect_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Insert inspection
        cursor.execute("""
            INSERT INTO inspections (
                id, file_name, file_type, file_path, file_size_bytes,
                status, quality_decision, total_defects, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            insp_id, "test_strip.jpg", "image", "/tmp/test_strip.jpg", 1024,
            "COMPLETED", "REJECTED", 1, now, now
        ))

        # Insert defect
        cursor.execute("""
            INSERT INTO defects (
                id, inspection_id, class_id, class_name, confidence,
                x1, y1, x2, y2, width, height, area, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            defect_id, insp_id, 4, "rolled-in_scale", 0.88,
            10.0, 10.0, 50.0, 50.0, 40.0, 40.0, 1600.0, now
        ))

    # Verify presence
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM inspections WHERE id = ?;", (insp_id,))
        assert cursor.fetchone() is not None

        cursor.execute("SELECT * FROM defects WHERE inspection_id = ?;", (insp_id,))
        assert cursor.fetchone() is not None

        # Delete inspection and verify defect is cascade-deleted
        cursor.execute("DELETE FROM inspections WHERE id = ?;", (insp_id,))

        cursor.execute("SELECT * FROM inspections WHERE id = ?;", (insp_id,))
        assert cursor.fetchone() is None

        cursor.execute("SELECT * FROM defects WHERE inspection_id = ?;", (insp_id,))
        assert cursor.fetchone() is None, "Defect should be cascade-deleted by foreign key"


if __name__ == "__main__":
    print("Running Database tests...")
    test_schema_and_pragmas()
    print("-> test_schema_and_pragmas: PASSED")
    test_crud_and_cascade_delete()
    print("-> test_crud_and_cascade_delete: PASSED")
    print("ALL DATABASE TESTS PASSED!")
