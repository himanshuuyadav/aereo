"""FastAPI application entry point.

Creates the FastAPI app, configures lifespan events for database
initialization/cleanup, and includes the API router.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db, close_db
from app.router import router

# ──────────────────────────────────────────
# Logging Configuration
# ──────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ──────────────────────────────────────────
# Application Lifespan
# ──────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown events."""
    # Startup
    logger.info("🚀 Starting %s v%s", settings.APP_NAME, settings.APP_VERSION)
    await init_db()
    logger.info("✅ Database initialized")
    yield
    # Shutdown
    logger.info("🛑 Shutting down...")
    await close_db()
    logger.info("✅ Database connections closed")


# ──────────────────────────────────────────
# FastAPI Application
# ──────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "A backend service that accepts geospatial files (Shapefile or KML), "
        "processes their features, and returns measurement information including "
        "area, length, and geometry details with proper CRS handling."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router)


@app.get("/", tags=["health"])
async def root():
    """Health check / root endpoint."""
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs",
    }
