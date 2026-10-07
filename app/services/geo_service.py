"""Geospatial processing service.

Handles parsing of Shapefiles and KML files, feature extraction,
CRS detection, coordinate transformation, and measurement calculation.
"""

import json
import math
import logging
from typing import Optional

import fiona
import geopandas as gpd
from pyproj import CRS, Transformer
from shapely import wkt
from shapely.geometry import shape, mapping
from shapely.ops import transform

logger = logging.getLogger(__name__)


class GeoService:
    """Service for geospatial file processing and measurement computation."""

    # Supported geometry types for measurement
    AREA_TYPES = {"Polygon", "MultiPolygon"}
    LENGTH_TYPES = {"LineString", "MultiLineString"}
    POINT_TYPES = {"Point", "MultiPoint"}

    @staticmethod
    def get_utm_epsg(longitude: float, latitude: float) -> int:
        """
        Determine the appropriate UTM EPSG code for a given coordinate.

        Uses the standard formula:
        - Zone number = floor((longitude + 180) / 6) + 1
        - EPSG = 32600 + zone (Northern hemisphere)
        - EPSG = 32700 + zone (Southern hemisphere)

        Args:
            longitude: Longitude in degrees.
            latitude: Latitude in degrees.

        Returns:
            EPSG code for the appropriate UTM zone.
        """
        zone_number = int(math.floor((longitude + 180) / 6)) + 1
        # Clamp zone number to valid range 1-60
        zone_number = max(1, min(60, zone_number))

        if latitude >= 0:
            return 32600 + zone_number  # Northern hemisphere
        else:
            return 32700 + zone_number  # Southern hemisphere

    @staticmethod
    def is_geographic_crs(crs: CRS) -> bool:
        """Check if a CRS uses geographic coordinates (degrees)."""
        return crs.is_geographic

    @classmethod
    def compute_measurement(
        cls,
        geometry_wkt_str: str,
        source_crs_str: Optional[str],
    ) -> dict:
        """
        Compute measurement for a geometry.

        For Polygons: calculates area in square meters.
        For LineStrings: calculates length in meters.
        For Points and unsupported types: returns no measurement.

        Automatically transforms geographic CRS (e.g., EPSG:4326) to
        the appropriate UTM projection before computing measurements.

        Args:
            geometry_wkt_str: WKT representation of the geometry.
            source_crs_str: Source CRS string (e.g., "EPSG:4326").

        Returns:
            Dictionary with measurement_type, measurement_value,
            measurement_unit, and projected_crs.
        """
        result = {
            "measurement_type": "none",
            "measurement_value": None,
            "measurement_unit": None,
            "projected_crs": None,
        }

        try:
            geom = wkt.loads(geometry_wkt_str)
        except Exception as e:
            logger.warning(f"Failed to parse WKT geometry: {e}")
            return result

        geom_type = geom.geom_type

        # Determine if measurement is needed
        if geom_type in cls.POINT_TYPES:
            result["measurement_type"] = "none"
            return result
        elif geom_type not in cls.AREA_TYPES and geom_type not in cls.LENGTH_TYPES:
            # Unsupported geometry type — handle gracefully
            result["measurement_type"] = "unsupported"
            logger.info(f"Unsupported geometry type for measurement: {geom_type}")
            return result

        # Transform if geographic CRS
        projected_geom = geom
        projected_crs_str = source_crs_str

        if source_crs_str:
            try:
                source_crs = CRS.from_user_input(source_crs_str)

                if cls.is_geographic_crs(source_crs):
                    # Get centroid for UTM zone selection
                    centroid = geom.centroid
                    utm_epsg = cls.get_utm_epsg(centroid.x, centroid.y)
                    target_crs = CRS.from_epsg(utm_epsg)
                    projected_crs_str = f"EPSG:{utm_epsg}"

                    # Create transformer and reproject
                    transformer = Transformer.from_crs(
                        source_crs, target_crs, always_xy=True
                    )
                    projected_geom = transform(transformer.transform, geom)
            except Exception as e:
                logger.warning(f"CRS transformation failed: {e}. Using original geometry.")

        result["projected_crs"] = projected_crs_str

        # Calculate measurement
        try:
            if geom_type in cls.AREA_TYPES:
                result["measurement_type"] = "area"
                result["measurement_value"] = round(projected_geom.area, 2)
                result["measurement_unit"] = "square meters"
            elif geom_type in cls.LENGTH_TYPES:
                result["measurement_type"] = "length"
                result["measurement_value"] = round(projected_geom.length, 2)
                result["measurement_unit"] = "meters"
        except Exception as e:
            logger.error(f"Measurement calculation failed: {e}")
            result["measurement_type"] = "error"

        return result

    @classmethod
    def parse_file(cls, file_path: str, file_type: str) -> dict:
        """
        Parse a geospatial file and extract features with measurements.

        Args:
            file_path: Path to the uploaded file.
            file_type: Type of file ("shapefile" or "kml").

        Returns:
            Dictionary containing:
                - crs: Original CRS string
                - features: List of feature dictionaries
                - feature_count: Number of features

        Raises:
            ValueError: If the file cannot be parsed.
        """
        features = []
        crs_str = None

        try:
            if file_type == "kml":
                try:
                    return cls.parse_kml_xml(file_path)
                except Exception as kml_err:
                    logger.warning(f"Native KML parsing failed: {kml_err}. Trying GeoPandas fallback...")
                    gdf = gpd.read_file(file_path, driver="KML")
            else:
                # Shapefile (from .zip or directory)
                gdf = gpd.read_file(file_path)

            # Extract CRS
            if gdf.crs is not None:
                crs_str = str(gdf.crs)
                # Normalize CRS representation
                try:
                    parsed_crs = CRS.from_user_input(gdf.crs)
                    epsg = parsed_crs.to_epsg()
                    if epsg:
                        crs_str = f"EPSG:{epsg}"
                except Exception:
                    pass  # Keep original string representation

            # Process each feature
            for idx, row in gdf.iterrows():
                geom = row.geometry

                if geom is None:
                    continue

                # Get geometry as WKT
                geometry_wkt_str = geom.wkt
                geometry_type = geom.geom_type

                # Extract properties (non-geometry columns)
                props = {}
                for col in gdf.columns:
                    if col == "geometry":
                        continue
                    val = row[col]
                    # Convert numpy types to native Python types
                    if hasattr(val, "item"):
                        val = val.item()
                    # Handle NaN values
                    if isinstance(val, float) and math.isnan(val):
                        val = None
                    props[col] = val

                # Compute measurements
                measurement = cls.compute_measurement(geometry_wkt_str, crs_str)

                feature_data = {
                    "feature_index": int(idx) if isinstance(idx, int) else len(features),
                    "geometry_type": geometry_type,
                    "geometry_wkt": geometry_wkt_str,
                    "properties": json.dumps(props),
                    "crs": crs_str,
                    "measurement_type": measurement["measurement_type"],
                    "measurement_value": measurement["measurement_value"],
                    "measurement_unit": measurement["measurement_unit"],
                    "projected_crs": measurement["projected_crs"],
                }

                features.append(feature_data)

            return {
                "crs": crs_str,
                "features": features,
                "feature_count": len(features),
            }

        except Exception as e:
            logger.error(f"Error parsing geospatial file: {e}")
            raise ValueError(f"Failed to parse geospatial file: {str(e)}")

    @classmethod
    def parse_kml_xml(cls, file_path: str) -> dict:
        """
        Parse KML file directly using standard XML parsing and Shapely.
        Extracts Placemarks (Polygon, LineString, Point) and computes measurements.
        """
        import xml.etree.ElementTree as ET
        from shapely.geometry import Polygon, LineString, Point

        tree = ET.parse(file_path)
        root = tree.getroot()

        def strip_ns(tag: str) -> str:
            return tag.split("}")[-1] if "}" in tag else tag

        features = []
        crs_str = "EPSG:4326"  # KML is always WGS84

        placemarks = []
        for elem in root.iter():
            if strip_ns(elem.tag) == "Placemark":
                placemarks.append(elem)

        for idx, pm in enumerate(placemarks):
            props = {}
            geom = None

            for child in pm:
                tag = strip_ns(child.tag)
                if tag in ("name", "description"):
                    if child.text:
                        props[tag] = child.text.strip()
                elif tag == "ExtendedData":
                    for data_elem in child:
                        d_name = data_elem.attrib.get("name")
                        val = None
                        for sub in data_elem:
                            if strip_ns(sub.tag) == "value" and sub.text:
                                val = sub.text.strip()
                                break
                        if d_name and val is not None:
                            props[d_name] = val

                elif tag == "Polygon":
                    coords_elem = None
                    for sub in child.iter():
                        if strip_ns(sub.tag) == "coordinates":
                            coords_elem = sub
                            break
                    if coords_elem is not None and coords_elem.text:
                        raw_coords = coords_elem.text.strip().split()
                        ring = []
                        for rc in raw_coords:
                            parts = rc.split(",")
                            if len(parts) >= 2:
                                ring.append((float(parts[0]), float(parts[1])))
                        if len(ring) >= 3:
                            geom = Polygon(ring)

                elif tag == "LineString":
                    coords_elem = None
                    for sub in child.iter():
                        if strip_ns(sub.tag) == "coordinates":
                            coords_elem = sub
                            break
                    if coords_elem is not None and coords_elem.text:
                        raw_coords = coords_elem.text.strip().split()
                        line_coords = []
                        for rc in raw_coords:
                            parts = rc.split(",")
                            if len(parts) >= 2:
                                line_coords.append((float(parts[0]), float(parts[1])))
                        if len(line_coords) >= 2:
                            geom = LineString(line_coords)

                elif tag == "Point":
                    coords_elem = None
                    for sub in child.iter():
                        if strip_ns(sub.tag) == "coordinates":
                            coords_elem = sub
                            break
                    if coords_elem is not None and coords_elem.text:
                        parts = coords_elem.text.strip().split(",")
                        if len(parts) >= 2:
                            geom = Point(float(parts[0]), float(parts[1]))

            if geom is None:
                continue

            geom_wkt = geom.wkt
            measurement = cls.compute_measurement(geom_wkt, crs_str)
            features.append({
                "feature_index": idx,
                "geometry_type": geom.geom_type,
                "geometry_wkt": geom_wkt,
                "properties": json.dumps(props),
                "crs": crs_str,
                "measurement_type": measurement["measurement_type"],
                "measurement_value": measurement["measurement_value"],
                "measurement_unit": measurement["measurement_unit"],
                "projected_crs": measurement["projected_crs"],
            })

        return {
            "crs": crs_str,
            "features": features,
            "feature_count": len(features),
        }
