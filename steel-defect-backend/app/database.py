"""Database connection and schema management using SQLite.
Industrial AI Steel Surface Defect Detection Platform.
"""

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator, List, Optional, Dict, Any

from app.config import settings

logger = logging.getLogger(__name__)


def get_db_path() -> Path:
    return settings.DATABASE_PATH


@contextmanager
def get_db_connection() -> Generator[sqlite3.Connection, None, None]:
    """Context manager for SQLite database connection.
    Enables WAL mode, foreign keys, and dictionary-like row access.
    """
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(
        str(db_path),
        timeout=30.0,
    )
    conn.row_factory = sqlite3.Row
    try:
        # Performance & integrity pragma configurations
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA busy_timeout = 30000;")
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Database transaction error: {e}", exc_info=True)
        raise
    finally:
        conn.close()


def init_database() -> None:
    """Initialize database tables, indexes, and default quality rules."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # 1. Batches table (for batch uploads)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS batches (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                total_items INTEGER NOT NULL,
                processed_items INTEGER DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'PENDING',
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL
            );
        """)

        # 2. Inspections table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS inspections (
                id TEXT PRIMARY KEY,
                file_name TEXT NOT NULL,
                file_type TEXT NOT NULL, -- 'image', 'video', 'batch_item'
                file_path TEXT NOT NULL,
                annotated_path TEXT,
                file_size_bytes INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING', -- PENDING, PROCESSING, COMPLETED, FAILED
                quality_decision TEXT NOT NULL DEFAULT 'UNKNOWN', -- APPROVED, REVIEW_REQUIRED, REJECTED, UNKNOWN
                decision_reason TEXT,
                total_defects INTEGER DEFAULT 0,
                max_confidence REAL DEFAULT 0.0,
                inference_time_ms REAL DEFAULT 0.0,
                progress_percent REAL DEFAULT 0.0,
                frames_processed INTEGER DEFAULT 0,
                total_frames INTEGER DEFAULT 1,
                batch_id TEXT,
                error_message TEXT,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL,
                FOREIGN KEY (batch_id) REFERENCES batches(id) ON DELETE SET NULL
            );
        """)

        # 3. Defects table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS defects (
                id TEXT PRIMARY KEY,
                inspection_id TEXT NOT NULL,
                class_id INTEGER NOT NULL,
                class_name TEXT NOT NULL,
                confidence REAL NOT NULL,
                x1 REAL NOT NULL,
                y1 REAL NOT NULL,
                x2 REAL NOT NULL,
                y2 REAL NOT NULL,
                width REAL NOT NULL,
                height REAL NOT NULL,
                area REAL NOT NULL,
                frame_number INTEGER DEFAULT 0,
                created_at TIMESTAMP NOT NULL,
                FOREIGN KEY (inspection_id) REFERENCES inspections(id) ON DELETE CASCADE
            );
        """)

        # 4. Configurable Quality Rules table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS quality_rules (
                id TEXT PRIMARY KEY,
                rule_name TEXT UNIQUE NOT NULL,
                confidence_threshold REAL NOT NULL DEFAULT 0.25,
                review_confidence_min REAL NOT NULL DEFAULT 0.25,
                critical_confidence_threshold REAL NOT NULL DEFAULT 0.50,
                reject_confidence_threshold REAL NOT NULL DEFAULT 0.70,
                max_allowed_defects INTEGER NOT NULL DEFAULT 2,
                critical_defects TEXT NOT NULL, -- JSON list of critical defect class names
                per_defect_tolerances TEXT NOT NULL, -- JSON dict: {"crazing": 2, "scratches": 2, ...}
                is_active INTEGER DEFAULT 1,
                updated_at TIMESTAMP NOT NULL
            );
        """)

        # Indexes for fast industrial dashboard analytics & search queries
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_inspections_created_at ON inspections(created_at);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_inspections_decision ON inspections(quality_decision);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_inspections_status ON inspections(status);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_inspections_batch_id ON inspections(batch_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_defects_inspection_id ON defects(inspection_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_defects_class_name ON defects(class_name);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_defects_confidence ON defects(confidence);")

        # Insert default quality rules if none exist
        cursor.execute("SELECT COUNT(*) as count FROM quality_rules;")
        if cursor.fetchone()["count"] == 0:
            default_critical = json.dumps(settings.DEFAULT_CRITICAL_DEFECTS)
            default_tolerances = json.dumps({
                "crazing": 2,
                "inclusion": 0,
                "patches": 1,
                "pitted_surface": 0,
                "rolled-in_scale": 0,
                "scratches": 2
            })
            now = datetime.now(timezone.utc).isoformat()
            cursor.execute("""
                INSERT INTO quality_rules (
                    id, rule_name, confidence_threshold, review_confidence_min,
                    critical_confidence_threshold, reject_confidence_threshold,
                    max_allowed_defects, critical_defects, per_defect_tolerances,
                    is_active, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                "default_industrial_rule",
                "Standard Hot-Rolled Steel Quality Standard",
                settings.DEFAULT_CONFIDENCE_THRESHOLD,
                settings.DEFAULT_REVIEW_CONFIDENCE_MIN,
                settings.DEFAULT_CRITICAL_CONFIDENCE,
                settings.DEFAULT_REJECT_CONFIDENCE,
                settings.DEFAULT_MAX_ALLOWED_DEFECTS,
                default_critical,
                default_tolerances,
                1,
                now
            ))
            logger.info("Initialized default industrial quality rules.")

        logger.info("Database schema verified and successfully initialized.")
