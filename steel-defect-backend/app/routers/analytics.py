"""Analytics API endpoints.
Provides real-time production quality KPIs: Total Inspections, FPY,
Rejection Rate, Defect Distribution, and Historical Defect Trends.
"""

from typing import List
from fastapi import APIRouter, Query

from app.models.schemas import (
    AnalyticsOverviewResponse,
    DefectDistributionItem,
    DefectTrendItem,
)
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get(
    "/overview",
    response_model=AnalyticsOverviewResponse,
    summary="Get overall production quality KPIs",
    description="Returns First-Pass Yield (FPY), Rejection Rate, defect frequencies, and average latency from real SQLite records.",
)
def get_analytics_overview():
    return AnalyticsService.get_overview()


@router.get(
    "/defect-distribution",
    response_model=List[DefectDistributionItem],
    summary="Get defect class distribution and average confidences",
    description="Calculates frequency and percentage breakdown for each of the six NEU-DET defect classes.",
)
def get_defect_distribution():
    return AnalyticsService.get_defect_distribution()


@router.get(
    "/trends",
    response_model=List[DefectTrendItem],
    summary="Get daily defect trends and yield progression",
    description="Returns day-by-day inspection volumes, quality decisions, and First-Pass Yield percentages.",
)
def get_defect_trends(
    days: int = Query(30, ge=1, le=365, description="Number of past calendar days to aggregate"),
):
    return AnalyticsService.get_defect_trends(days=days)
