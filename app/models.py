"""SQLAlchemy ORM models for geospatial file data."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey, Float
from sqlalchemy.orm import relationship

from app.database import Base


def generate_uuid() -> str:
    """Generate a new UUID4 string."""
    return str(uuid.uuid4())


class GeoFile(Base):
    """Represents an uploaded geospatial file."""

    __tablename__ = "geo_files"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    filename = Column(String(255), nullable=False)
    file_type = Column(String(20), nullable=False)  # "shapefile" or "kml"
    file_path = Column(String(500), nullable=False)
    feature_count = Column(Integer, default=0)
    crs = Column(String(50), nullable=True)
    status = Column(String(20), default="PROCESSING")  # PROCESSING, COMPLETED, FAILED
    error_message = Column(Text, nullable=True)
    uploaded_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationship to features
    features = relationship(
        "Feature",
        back_populates="geo_file",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<GeoFile(id={self.id}, filename={self.filename}, status={self.status})>"


class Feature(Base):
    """Represents a single geospatial feature extracted from an uploaded file."""

    __tablename__ = "features"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    file_id = Column(String(36), ForeignKey("geo_files.id", ondelete="CASCADE"), nullable=False)
    feature_index = Column(Integer, nullable=False)
    geometry_type = Column(String(50), nullable=False)
    geometry_wkt = Column(Text, nullable=False)  # Well-Known Text representation
    properties = Column(Text, nullable=True)  # JSON-serialized properties/attributes
    crs = Column(String(50), nullable=True)

    # Measurements (pre-computed or computed on-the-fly)
    measurement_type = Column(String(20), nullable=True)  # "area", "length", "none"
    measurement_value = Column(Float, nullable=True)
    measurement_unit = Column(String(30), nullable=True)
    projected_crs = Column(String(50), nullable=True)  # CRS used for measurement

    # Relationship back to file
    geo_file = relationship("GeoFile", back_populates="features")

    def __repr__(self) -> str:
        return f"<Feature(id={self.id}, index={self.feature_index}, type={self.geometry_type})>"
