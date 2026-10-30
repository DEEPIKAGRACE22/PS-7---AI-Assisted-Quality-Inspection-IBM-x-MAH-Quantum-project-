"""Unit tests for Quality Decision Engine.
Validates classification logic: APPROVED, REVIEW_REQUIRED, REJECTED,
confidence thresholds, critical defect rules, and tolerance limits.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import init_database
from app.models.schemas import (
    DefectDetection,
    BoundingBox,
    QualityDecisionEnum,
    QualityRuleConfig,
)
from app.services.quality_service import quality_engine


def make_dummy_defect(class_name: str, confidence: float) -> DefectDetection:
    class_map = {
        "crazing": 0,
        "inclusion": 1,
        "patches": 2,
        "pitted_surface": 3,
        "rolled-in_scale": 4,
        "scratches": 5,
    }
    return DefectDetection(
        class_id=class_map.get(class_name, 0),
        class_name=class_name,
        confidence=confidence,
        bbox=BoundingBox(x1=10, y1=10, x2=50, y2=50, width=40, height=40, area=1600),
        frame_number=0,
    )


def test_approved_decision():
    # 1. Zero defects should always be APPROVED
    res = quality_engine.evaluate([])
    assert res.decision == QualityDecisionEnum.APPROVED
    assert "Zero" in res.reason or "zero" in res.reason

    # 2. Defects below review_confidence_min (0.25) should be filtered and APPROVED
    low_conf_defect = [make_dummy_defect("scratches", 0.15)]
    res = quality_engine.evaluate(low_conf_defect)
    assert res.decision == QualityDecisionEnum.APPROVED


def test_review_required_decision():
    # Minor scratch with moderate confidence (e.g., 0.35) should trigger REVIEW_REQUIRED
    defects = [make_dummy_defect("scratches", 0.35)]
    res = quality_engine.evaluate(defects)
    assert res.decision == QualityDecisionEnum.REVIEW_REQUIRED
    assert "review" in res.reason.lower()


def test_rejected_critical_defect():
    # Critical defect: rolled-in_scale at 0.55 confidence should immediately REJECT
    defects = [make_dummy_defect("rolled-in_scale", 0.55)]
    res = quality_engine.evaluate(defects)
    assert res.decision == QualityDecisionEnum.REJECTED
    assert "rolled-in_scale" in res.reason.lower()


def test_rejected_high_confidence():
    # High confidence defect (>= 0.70) should REJECT even if class is patches
    defects = [make_dummy_defect("patches", 0.75)]
    res = quality_engine.evaluate(defects)
    assert res.decision == QualityDecisionEnum.REJECTED


def test_rejected_max_defects_exceeded():
    # Max allowed defects is 2 by default. 4 defects should REJECT
    defects = [
        make_dummy_defect("crazing", 0.30),
        make_dummy_defect("crazing", 0.32),
        make_dummy_defect("scratches", 0.28),
        make_dummy_defect("scratches", 0.29),
    ]
    res = quality_engine.evaluate(defects)
    assert res.decision == QualityDecisionEnum.REJECTED
    assert "exceeds" in res.reason.lower()


def test_custom_rule_update():
    # Custom rule: tighten max defects to 1
    custom_rules = QualityRuleConfig(
        rule_name="Ultra Strict Aerospace Steel Standard",
        max_allowed_defects=1,
        review_confidence_min=0.20,
        critical_confidence_threshold=0.40,
        reject_confidence_threshold=0.60,
    )
    defects = [
        make_dummy_defect("scratches", 0.25),
        make_dummy_defect("scratches", 0.26),
    ]
    res = quality_engine.evaluate(defects, custom_rules=custom_rules)
    assert res.decision == QualityDecisionEnum.REJECTED


if __name__ == "__main__":
    init_database()
    print("Running Quality Decision Engine tests...")
    test_approved_decision()
    print("-> test_approved_decision: PASSED")
    test_review_required_decision()
    print("-> test_review_required_decision: PASSED")
    test_rejected_critical_defect()
    print("-> test_rejected_critical_defect: PASSED")
    test_rejected_high_confidence()
    print("-> test_rejected_high_confidence: PASSED")
    test_rejected_max_defects_exceeded()
    print("-> test_rejected_max_defects_exceeded: PASSED")
    test_custom_rule_update()
    print("-> test_custom_rule_update: PASSED")
    print("ALL QUALITY DECISION TESTS PASSED!")
