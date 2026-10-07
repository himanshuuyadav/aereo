"""File upload and management service.

Handles file validation, storage, and orchestration of geospatial processing.
"""

import os
import logging
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import GeoFile, Feature
from app.services.geo_service import GeoService

logger = logging.getLogger(__name__)


class FileService:
    """Service for file upload, validation, and processing orchestration."""

    ALLOWED_EXTENSIONS = {".zip", ".kml"}
    FILE_TYPE_MAP = {
        ".zip": "shapefile",
        ".kml": "kml",
    }

    @classmethod
    def validate_file(cls, filename: str) -> str:
        """
        Validate the uploaded file extension.

        Args:
            filename: Original filename from the upload.

        Returns:
            The file type string ("shapefile" or "kml").

        Raises:
            ValueError: If the file extension is not supported.
        """
        ext = Path(filename).suffix.lower()
        if ext not in cls.ALLOWED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file type '{ext}'. Accepted: .zip (Shapefile), .kml"
            )
        return cls.FILE_TYPE_MAP[ext]

    @staticmethod
    async def save_upload(file: UploadFile, filename: str) -> str:
        """
        Save an uploaded file to the uploads directory.

        Args:
            file: The FastAPI UploadFile object.
            filename: The filename to save as.

        Returns:
            Absolute path to the saved file.
        """
        file_path = os.path.join(settings.UPLOAD_DIR, filename)

        content = await file.read()

        # Check file size
        size_mb = len(content) / (1024 * 1024)
        if size_mb > settings.MAX_FILE_SIZE_MB:
            raise ValueError(
                f"File size ({size_mb:.1f} MB) exceeds maximum ({settings.MAX_FILE_SIZE_MB} MB)"
            )

        with open(file_path, "wb") as f:
            f.write(content)

        return file_path

    @classmethod
    async def process_file(
        cls,
        file: UploadFile,
        db: AsyncSession,
    ) -> GeoFile:
        """
        Full pipeline: validate, save, parse, compute measurements, and persist.

        Args:
            file: The uploaded file.
            db: Async database session.

        Returns:
            The created GeoFile ORM object with populated features.
        """
        # 1. Validate file type
        file_type = cls.validate_file(file.filename)

        # 2. Create initial DB record
        geo_file = GeoFile(
            filename=file.filename,
            file_type=file_type,
            file_path="",  # Will be updated after save
            status="PROCESSING",
        )
        db.add(geo_file)
        await db.flush()  # Get the generated ID

        try:
            # 3. Save file to disk with unique name
            safe_filename = f"{geo_file.id}_{file.filename}"
            file_path = await cls.save_upload(file, safe_filename)
            geo_file.file_path = file_path

            # 4. Parse geospatial file and extract features
            logger.info(f"Processing file: {file.filename} (type: {file_type})")

            # For shapefile archives, extract the zip and locate the .shp file
            parse_path = file_path
            if file_type == "shapefile":
                import zipfile
                extract_dir = os.path.join(settings.UPLOAD_DIR, f"{geo_file.id}_unzipped")
                os.makedirs(extract_dir, exist_ok=True)
                with zipfile.ZipFile(file_path, "r") as zf:
                    zf.extractall(extract_dir)

                # Find .shp file (including nested directories)
                shp_files = list(Path(extract_dir).rglob("*.shp"))
                if not shp_files:
                    raise ValueError("Uploaded zip file does not contain a .shp Shapefile.")
                parse_path = str(shp_files[0])

            result = GeoService.parse_file(parse_path, file_type)

            # 5. Update file record
            geo_file.crs = result["crs"]
            geo_file.feature_count = result["feature_count"]
            geo_file.status = "COMPLETED"

            # 6. Create Feature records
            for feature_data in result["features"]:
                feature = Feature(
                    file_id=geo_file.id,
                    feature_index=feature_data["feature_index"],
                    geometry_type=feature_data["geometry_type"],
                    geometry_wkt=feature_data["geometry_wkt"],
                    properties=feature_data["properties"],
                    crs=feature_data["crs"],
                    measurement_type=feature_data["measurement_type"],
                    measurement_value=feature_data["measurement_value"],
                    measurement_unit=feature_data["measurement_unit"],
                    projected_crs=feature_data["projected_crs"],
                )
                db.add(feature)

            logger.info(
                f"File processed successfully: {file.filename} "
                f"({result['feature_count']} features)"
            )

        except Exception as e:
            logger.error(f"File processing failed: {e}")
            geo_file.status = "FAILED"
            geo_file.error_message = str(e)

        return geo_file

    @staticmethod
    async def get_file(file_id: str, db: AsyncSession) -> GeoFile | None:
        """
        Retrieve a file record by ID.

        Args:
            file_id: The UUID of the file.
            db: Async database session.

        Returns:
            GeoFile object or None if not found.
        """
        result = await db.execute(
            select(GeoFile).where(GeoFile.id == file_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_all_files(db: AsyncSession) -> list[GeoFile]:
        """
        Retrieve all uploaded file records.

        Args:
            db: Async database session.

        Returns:
            List of GeoFile objects.
        """
        result = await db.execute(
            select(GeoFile).order_by(GeoFile.uploaded_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_features(file_id: str, db: AsyncSession) -> list[Feature]:
        """
        Retrieve all features for a specific file.

        Args:
            file_id: The UUID of the file.
            db: Async database session.

        Returns:
            List of Feature objects.
        """
        result = await db.execute(
            select(Feature)
            .where(Feature.file_id == file_id)
            .order_by(Feature.feature_index)
        )
        return list(result.scalars().all())
