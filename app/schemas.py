"""Pydantic schemas for API request/response validation."""

from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel, Field


# ──────────────────────────────────────────
# File Schemas
# ──────────────────────────────────────────


class FileResponse(BaseModel):
    """Response schema for file information."""

    id: str
    filename: str
    file_type: str
    feature_count: int
    crs: Optional[str] = None
    status: str
    uploaded_at: datetime
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


# ──────────────────────────────────────────
# Measurement Schemas
# ──────────────────────────────────────────


class Measurement(BaseModel):
    """Measurement data for a single geometry."""

    type: str  # "area", "length", "none"
    value: Optional[float] = None
    unit: Optional[str] = None


class FeatureMeasurement(BaseModel):
    """Measurement result for a single feature."""

    feature_index: int
    geometry_type: str
    properties: Optional[dict[str, Any]] = None
    measurement: Measurement
    geometry_wkt: str


class MeasurementsResponse(BaseModel):
    """Response schema for file measurements endpoint."""

    file_id: str
    filename: str
    crs_original: Optional[str] = None
    crs_projected: Optional[str] = None
    feature_count: int
    features: list[FeatureMeasurement]
