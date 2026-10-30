"""Industrial Quality Decision Engine for Steel Surface Inspection.
Classifies inspections as APPROVED, REVIEW_REQUIRED, or REJECTED
based on configurable thresholds and domain-specific defect rules.
"""

import json
import logging
from typing import List, Dict, Any, Tuple
from datetime import datetime, timezone

from app.database import get_db_connection
from app.models.schemas import (
    DefectDetection,
    QualityDecisionEnum,
    QualityDecisionResult,
    QualityRuleConfig,
)
from app.config import settings

logger = logging.getLogger(__name__)


class QualityDecisionEngine:
    """Engine that applies industrial metallurgical defect rules to inspection outputs."""

    def __init__(self):
        self._cached_config: QualityRuleConfig = None
        self._load_active_rules()

    def _load_active_rules(self) -> QualityRuleConfig:
        """Load currently active quality rules from SQLite."""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='quality_rules';")
                if not cursor.fetchone():
                    self._cached_config = QualityRuleConfig()
                    return self._cached_config

                cursor.execute("""
                    SELECT rule_name, confidence_threshold, review_confidence_min,
                           critical_confidence_threshold, reject_confidence_threshold,
                           max_allowed_defects, critical_defects, per_defect_tolerances
                    FROM quality_rules
                    WHERE is_active = 1
                    ORDER BY updated_at DESC
                    LIMIT 1;
                """)
                row = cursor.fetchone()
                if row:
                    self._cached_config = QualityRuleConfig(
                        rule_name=row["rule_name"],
                        confidence_threshold=float(row["confidence_threshold"]),
                        review_confidence_min=float(row["review_confidence_min"]),
                        critical_confidence_threshold=float(row["critical_confidence_threshold"]),
                        reject_confidence_threshold=float(row["reject_confidence_threshold"]),
                        max_allowed_defects=int(row["max_allowed_defects"]),
                        critical_defects=json.loads(row["critical_defects"]),
                        per_defect_tolerances=json.loads(row["per_defect_tolerances"]),
                    )
                    return self._cached_config
        except Exception as e:
            logger.warning(f"Could not load quality rules from DB, using fallback defaults: {e}")

        # Fallback to defaults
        self._cached_config = QualityRuleConfig()
        return self._cached_config

    def get_config(self) -> QualityRuleConfig:
        """Get the current active configuration."""
        if self._cached_config is None:
            self._load_active_rules()
        return self._cached_config

    def update_config(self, new_config: QualityRuleConfig) -> QualityRuleConfig:
        """Update active quality rules in SQLite and refresh cache."""
        now = datetime.now(timezone.utc).isoformat()
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE quality_rules
                SET rule_name = ?,
                    confidence_threshold = ?,
                    review_confidence_min = ?,
                    critical_confidence_threshold = ?,
                    reject_confidence_threshold = ?,
                    max_allowed_defects = ?,
                    critical_defects = ?,
                    per_defect_tolerances = ?,
                    updated_at = ?
                WHERE is_active = 1;
            """, (
                new_config.rule_name,
                new_config.confidence_threshold,
                new_config.review_confidence_min,
                new_config.critical_confidence_threshold,
                new_config.reject_confidence_threshold,
                new_config.max_allowed_defects,
                json.dumps(new_config.critical_defects),
                json.dumps(new_config.per_defect_tolerances),
                now
            ))
        self._cached_config = new_config
        logger.info(f"Updated active quality rules: {new_config.rule_name}")
        return self._cached_config

    def reset_to_defaults(self) -> QualityRuleConfig:
        """Reset quality rules to factory industrial defaults."""
        default_config = QualityRuleConfig()
        return self.update_config(default_config)

    def evaluate(self, defects: List[DefectDetection], custom_rules: QualityRuleConfig = None) -> QualityDecisionResult:
        """Classify inspection results into APPROVED, REVIEW_REQUIRED, or REJECTED.
        
        Evaluation Hierarchy:
        1. REJECTED:
           - Presence of critical defect (e.g. rolled-in_scale, inclusion) with confidence >= critical_threshold
           - Any defect detected with confidence >= reject_confidence_threshold (e.g. >= 0.70)
           - Total defect count > max_allowed_defects
           - Defect count for a specific class exceeds class tolerance limit (e.g. inclusion > 0)
        2. REVIEW_REQUIRED:
           - Detections exist above review_confidence_min that did not breach hard rejection thresholds
           - Ambiguous surface flaws, minor crazing or faint scratches needing human verification
        3. APPROVED:
           - Zero defects detected above review_confidence_min
           - All surface readings within acceptable metallurgical tolerance
        """
        rules = custom_rules or self.get_config()

        # Filter defects by minimum confidence
        valid_defects = [d for d in defects if d.confidence >= rules.review_confidence_min]
        
        defect_counts: Dict[str, int] = {}
        max_confidence = 0.0

        for d in valid_defects:
            defect_counts[d.class_name] = defect_counts.get(d.class_name, 0) + 1
            if d.confidence > max_confidence:
                max_confidence = d.confidence

        total_defects = len(valid_defects)
        rules_triggered: List[str] = []

        # -------------------------------------------------------------
        # 1. Check for Immediate REJECT Conditions
        # -------------------------------------------------------------
        reasons_for_rejection: List[str] = []

        # Rule 1A: Critical Defect with Confidence Threshold
        for d in valid_defects:
            if d.class_name in rules.critical_defects and d.confidence >= rules.critical_confidence_threshold:
                reason = (
                    f"Critical defect '{d.class_name}' detected with high confidence "
                    f"({d.confidence * 100:.1f}% >= {rules.critical_confidence_threshold * 100:.0f}%)"
                )
                if reason not in reasons_for_rejection:
                    reasons_for_rejection.append(reason)
                    rules_triggered.append(f"CRITICAL_DEFECT_{d.class_name.upper()}")

        # Rule 1B: Severe Confidence Exceeded (any defect)
        for d in valid_defects:
            if d.confidence >= rules.reject_confidence_threshold:
                reason = (
                    f"Defect '{d.class_name}' exceeds maximum severity threshold "
                    f"({d.confidence * 100:.1f}% >= {rules.reject_confidence_threshold * 100:.0f}%)"
                )
                if reason not in reasons_for_rejection:
                    reasons_for_rejection.append(reason)
                    rules_triggered.append("HIGH_CONFIDENCE_BREACH")

        # Rule 1C: Defect Count Exceeds Global Allowance
        if total_defects > rules.max_allowed_defects:
            reason = (
                f"Total defect count ({total_defects}) exceeds maximum permissible limit "
                f"({rules.max_allowed_defects})"
            )
            reasons_for_rejection.append(reason)
            rules_triggered.append("MAX_DEFECTS_EXCEEDED")

        # Rule 1D: Per-Defect Tolerance Limits
        for class_name, count in defect_counts.items():
            max_tolerated = rules.per_defect_tolerances.get(class_name, rules.max_allowed_defects)
            if count > max_tolerated:
                reason = (
                    f"Defect class '{class_name}' count ({count}) exceeds tolerance ({max_tolerated})"
                )
                if reason not in reasons_for_rejection:
                    reasons_for_rejection.append(reason)
                    rules_triggered.append(f"TOLERANCE_EXCEEDED_{class_name.upper()}")

        if reasons_for_rejection:
            return QualityDecisionResult(
                decision=QualityDecisionEnum.REJECTED,
                reason=" | ".join(reasons_for_rejection),
                rules_triggered=rules_triggered,
                max_confidence=max_confidence,
                defect_counts=defect_counts,
            )

        # -------------------------------------------------------------
        # 2. Check for REVIEW_REQUIRED Conditions
        # -------------------------------------------------------------
        if total_defects > 0:
            defect_summary = ", ".join([f"{k}: {v}" for k, v in defect_counts.items()])
            reason = (
                f"Minor surface defects detected within acceptable tolerance limits "
                f"({defect_summary}, max conf: {max_confidence * 100:.1f}%). "
                f"Quality inspector review recommended."
            )
            rules_triggered.append("DEFECTS_DETECTED_WITHIN_TOLERANCE")
            return QualityDecisionResult(
                decision=QualityDecisionEnum.REVIEW_REQUIRED,
                reason=reason,
                rules_triggered=rules_triggered,
                max_confidence=max_confidence,
                defect_counts=defect_counts,
            )

        # -------------------------------------------------------------
        # 3. APPROVED Condition
        # -------------------------------------------------------------
        rules_triggered.append("ZERO_DEFECTS_DETECTED")
        return QualityDecisionResult(
            decision=QualityDecisionEnum.APPROVED,
            reason="Steel surface inspected with zero detected defects above baseline tolerance.",
            rules_triggered=rules_triggered,
            max_confidence=0.0,
            defect_counts={},
        )


# Global singleton instance
quality_engine = QualityDecisionEngine()
