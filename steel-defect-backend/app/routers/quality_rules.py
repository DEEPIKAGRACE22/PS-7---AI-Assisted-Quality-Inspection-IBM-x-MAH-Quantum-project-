"""Quality Rules API endpoints.
Inspect and dynamically configure confidence thresholds, defect tolerances,
and rejection criteria.
"""

from fastapi import APIRouter
from app.models.schemas import QualityRuleConfig
from app.services.quality_service import quality_engine

router = APIRouter(prefix="/quality-rules", tags=["Quality Decisions"])


@router.get(
    "/",
    response_model=QualityRuleConfig,
    summary="Get currently active industrial quality rules and thresholds",
)
def get_current_quality_rules():
    return quality_engine.get_config()


@router.put(
    "/",
    response_model=QualityRuleConfig,
    summary="Update active quality thresholds and defect classification rules",
    description="Dynamically updates database rules. Subsequent inspections will immediately follow these criteria.",
)
def update_quality_rules(new_rules: QualityRuleConfig):
    return quality_engine.update_config(new_rules)


@router.post(
    "/reset",
    response_model=QualityRuleConfig,
    summary="Reset quality rules to factory industrial defaults",
)
def reset_quality_rules():
    return quality_engine.reset_to_defaults()
