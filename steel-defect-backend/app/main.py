"""FastAPI application entrypoint.
Industrial AI Steel Surface Defect Detection Platform.
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import init_database
from app.services.yolo_service import get_yolo_service
from app.routers import inspections, analytics, quality_rules, reports, websockets

# Setup structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("steel_backend")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle management."""
    logger.info("Initializing Industrial Defect Detection Backend...")
    # 1. Initialize SQLite Database
    init_database()
    
    # 2. Warm up YOLO Inference Service
    try:
        yolo_service = get_yolo_service()
        device_info = yolo_service.get_device_info()
        logger.info(f"YOLO Inference Service Ready! Device info: {device_info}")
    except Exception as e:
        logger.error(f"Failed to load YOLO model: {e}", exc_info=True)

    logger.info(f"System ready: {settings.PROJECT_NAME} v{settings.VERSION}")
    yield
    logger.info("Shutting down Industrial Defect Detection Backend.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.PROJECT_DESCRIPTION,
    version=settings.VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Enable CORS for dashboard integration (React, Vue, Vite, etc.)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all unhandled exception handler returning clean JSON error responses."""
    logger.error(f"Unhandled error on {request.method} {request.url}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "InternalServerError",
            "message": str(exc),
            "path": str(request.url.path),
        },
    )


# Root system info endpoint
@app.get("/", tags=["System"])
def root_status():
    yolo_service = get_yolo_service()
    return {
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "OPERATIONAL",
        "device_info": yolo_service.get_device_info(),
        "neu_det_classes": list(settings.NEU_CLASSES.values()),
        "docs_url": "/docs",
        "api_v1": settings.API_V1_STR,
    }


# Health check endpoint
@app.get("/health", tags=["System"])
def health_check():
    return {
        "status": "healthy",
        "database": "connected",
        "yolo_model": str(settings.DEFAULT_WEIGHTS_PATH.name),
        "weights_present": settings.DEFAULT_WEIGHTS_PATH.exists(),
    }


# Include API Routers
app.include_router(inspections.router, prefix=settings.API_V1_STR)
app.include_router(analytics.router, prefix=settings.API_V1_STR)
app.include_router(quality_rules.router, prefix=settings.API_V1_STR)
app.include_router(reports.router, prefix=settings.API_V1_STR)
app.include_router(websockets.router)
