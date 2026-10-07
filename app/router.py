"""API route definitions for the Geospatial File Measurement API."""

import json
import logging

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import FileResponse, MeasurementsResponse, FeatureMeasurement, Measurement
from app.services.file_service import FileService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["files"])


@router.post(
    "/files/",
    response_model=FileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a geospatial file",
    description=(
        "Upload a geospatial file (.zip containing a Shapefile or .kml) "
        "for processing. The service extracts features, detects CRS, "
        "and computes measurements for supported geometry types."
    ),
)
async def upload_file(
    file: UploadFile = File(
        ...,
        description="A .zip file containing a Shapefile or a .kml file",
    ),
    db: AsyncSession = Depends(get_db),
):
    """Upload and process a geospatial file."""
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided.",
        )

    try:
        geo_file = await FileService.process_file(file, db)
        return geo_file
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/files/",
    response_model=list[FileResponse],
    summary="List all uploaded files",
    description="Returns a list of all uploaded geospatial files with their metadata.",
)
async def list_files(db: AsyncSession = Depends(get_db)):
    """List all uploaded files."""
    files = await FileService.get_all_files(db)
    return files


@router.get(
    "/files/{file_id}/",
    response_model=FileResponse,
    summary="Get file information",
    description="Returns metadata about a specific uploaded geospatial file.",
)
async def get_file(
    file_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get information about an uploaded file."""
    geo_file = await FileService.get_file(file_id, db)
    if not geo_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File with id '{file_id}' not found.",
        )
    return geo_file


@router.get(
    "/files/{file_id}/measurements/",
    response_model=MeasurementsResponse,
    summary="Get measurements for a file",
    description=(
        "Returns measurement data for all features in the uploaded file. "
        "Polygons return area (sq meters), LineStrings return length (meters), "
        "Points return no measurement."
    ),
)
async def get_measurements(
    file_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get measurements for all features in a file."""
    # Get file record
    geo_file = await FileService.get_file(file_id, db)
    if not geo_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File with id '{file_id}' not found.",
        )

    if geo_file.status != "COMPLETED":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"File processing has not completed. Current status: {geo_file.status}",
        )

    # Get features
    features = await FileService.get_features(file_id, db)

    # Build response
    feature_measurements = []
    projected_crs = None

    for feature in features:
        # Parse properties JSON
        props = None
        if feature.properties:
            try:
                props = json.loads(feature.properties)
            except json.JSONDecodeError:
                props = {}

        # Track projected CRS (use the first non-None value)
        if feature.projected_crs and not projected_crs:
            projected_crs = feature.projected_crs

        measurement = Measurement(
            type=feature.measurement_type or "none",
            value=feature.measurement_value,
            unit=feature.measurement_unit,
        )

        feature_measurements.append(
            FeatureMeasurement(
                feature_index=feature.feature_index,
                geometry_type=feature.geometry_type,
                properties=props,
                measurement=measurement,
                geometry_wkt=feature.geometry_wkt,
            )
        )

    return MeasurementsResponse(
        file_id=geo_file.id,
        filename=geo_file.filename,
        crs_original=geo_file.crs,
        crs_projected=projected_crs,
        feature_count=len(feature_measurements),
        features=feature_measurements,
    )
