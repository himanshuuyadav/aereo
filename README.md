# Geospatial File Measurement API

A production-quality backend service built with **FastAPI** that accepts geospatial files (Shapefile `.zip` or `.kml`), processes their features, and returns measurement information including area, length, and geometry details.

---

## 🚀 Setup & Installation

### Prerequisites

- **Python 3.10+**
- **pip** (Python package manager)
- **GDAL** system library (required by Fiona/GeoPandas)
  - **Windows**: `pip install GDAL` or use [OSGeo4W](https://trac.osgeo.org/osgeo4w/)
  - **macOS**: `brew install gdal`
  - **Ubuntu/Debian**: `sudo apt-get install gdal-bin libgdal-dev`

### Installation

```bash
# Clone the repository
git clone https://github.com/<your-username>/aereo.git
cd aereo

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the application
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

### Interactive API Docs

- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

### Running Automated Tests

A complete automated end-to-end test script is included:

```bash
# Ensure server is running in another terminal
python test_api.py
```

This script automatically tests:
- `GET /` — Service health check
- `POST /api/files/` — Uploading `test_sample.kml` (validating Polygon, LineString, and Point extraction)
- `GET /api/files/{id}/` — Inspecting parsed file status and metadata
- `GET /api/files/{id}/measurements/` — Verifying area (sq meters), length (meters), and UTM CRS transformation
- `POST /api/files/` — Uploading `test_sample_shapefile.zip`
- `GET /api/files/{id}/measurements/` — Verifying Shapefile polygon area measurements
- `GET /api/files/` — Listing all stored files

Sample files included for testing:
- `test_sample.kml`: Contains Polygon, LineString, Point in WGS84 (`EPSG:4326`) with properties.
- `test_sample_shapefile.zip`: Contains valid ESRI Shapefile components (`.shp`, `.shx`, `.dbf`, `.prj`).

---

## 📡 API Reference

### 1. Upload File

**`POST /api/files/`**

Uploads and processes a geospatial file.

**Request:**
- Content-Type: `multipart/form-data`
- Body: `file` — a `.zip` (containing Shapefile) or `.kml` file

```bash
# Upload a Shapefile (.zip)
curl -X POST "http://localhost:8000/api/files/" \
  -F "file=@survey_data.zip"

# Upload a KML file
curl -X POST "http://localhost:8000/api/files/" \
  -F "file=@boundaries.kml"
```

**Response (201 Created):**
```json
{
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "filename": "survey_data.zip",
    "file_type": "shapefile",
    "feature_count": 42,
    "crs": "EPSG:4326",
    "status": "COMPLETED",
    "uploaded_at": "2026-10-07T12:00:00Z",
    "error_message": null
}
```

**Error Response (400 Bad Request):**
```json
{
    "detail": "Unsupported file type. Accepted: .zip (Shapefile), .kml"
}
```

---

### 2. Get File Information

**`GET /api/files/{id}/`**

Returns metadata about an uploaded file.

```bash
curl "http://localhost:8000/api/files/a1b2c3d4-e5f6-7890-abcd-ef1234567890/"
```

**Response (200 OK):**
```json
{
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "filename": "survey_data.zip",
    "file_type": "shapefile",
    "feature_count": 42,
    "crs": "EPSG:4326",
    "status": "COMPLETED",
    "uploaded_at": "2026-10-07T12:00:00Z",
    "error_message": null
}
```

---

### 3. List All Files

**`GET /api/files/`**

Returns a list of all uploaded files.

```bash
curl "http://localhost:8000/api/files/"
```

**Response (200 OK):**
```json
[
    {
        "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "filename": "survey_data.zip",
        "file_type": "shapefile",
        "feature_count": 42,
        "crs": "EPSG:4326",
        "status": "COMPLETED",
        "uploaded_at": "2026-10-07T12:00:00Z",
        "error_message": null
    }
]
```

---

### 4. Get Measurements

**`GET /api/files/{id}/measurements/`**

Returns measurements for all features in the uploaded file.

```bash
curl "http://localhost:8000/api/files/a1b2c3d4-e5f6-7890-abcd-ef1234567890/measurements/"
```

**Response (200 OK):**
```json
{
    "file_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "filename": "survey_data.zip",
    "crs_original": "EPSG:4326",
    "crs_projected": "EPSG:32643",
    "feature_count": 3,
    "features": [
        {
            "feature_index": 0,
            "geometry_type": "Polygon",
            "properties": {"name": "Zone A", "category": "residential"},
            "measurement": {
                "type": "area",
                "value": 15234.56,
                "unit": "square meters"
            },
            "geometry_wkt": "POLYGON ((77.5 12.9, 77.6 12.9, 77.6 13.0, 77.5 13.0, 77.5 12.9))"
        },
        {
            "feature_index": 1,
            "geometry_type": "LineString",
            "properties": {"name": "Road B"},
            "measurement": {
                "type": "length",
                "value": 3421.78,
                "unit": "meters"
            },
            "geometry_wkt": "LINESTRING (77.5 12.9, 77.6 13.0)"
        },
        {
            "feature_index": 2,
            "geometry_type": "Point",
            "properties": {"name": "Station C"},
            "measurement": {
                "type": "none",
                "value": null,
                "unit": null
            },
            "geometry_wkt": "POINT (77.55 12.95)"
        }
    ]
}
```

---

## 🏗️ Architecture

### Application Structure

```
aereo/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application entry point & lifespan
│   ├── config.py             # Application settings (Pydantic Settings)
│   ├── database.py           # SQLAlchemy async engine & session setup
│   ├── models.py             # SQLAlchemy ORM models (File, Feature)
│   ├── schemas.py            # Pydantic request/response schemas
│   ├── router.py             # API route definitions
│   └── services/
│       ├── __init__.py
│       ├── file_service.py   # File storage, extraction & orchestration logic
│       └── geo_service.py    # Geospatial parsing & measurement engine
├── uploads/                  # Stored uploaded files (gitignored)
├── requirements.txt          # Python dependencies
├── README.md                 # Full documentation
├── test_api.py               # Automated end-to-end test suite
├── test_sample.kml           # Test KML dataset
├── test_sample_shapefile.zip # Test Shapefile dataset (.zip)
└── .gitignore
```

### File-Processing Flow

```
Upload Request ──► Validate File Extension (.zip / .kml)
                       │
                       ▼
                 Save to Disk (uploads/)
                       │
                       ▼
                 Create DB Record (status: PROCESSING)
                       │
                       ▼
              Parse Geospatial Data
              ├── .zip (Shapefile)
              │    └── Extract archive → Locate .shp → GeoPandas/Fiona read
              └── .kml (KML)
                   └── Native XML + Shapely parsing (with GeoPandas/GDAL fallback)
                       │
                       ▼
              Extract Features (geometry WKT, properties, CRS)
                       │
                       ▼
              Compute Measurements & Auto-reproject (UTM projection)
                       │
                       ▼
              Store Features in DB (Feature table)
                       │
                       ▼
              Update DB Record (status: COMPLETED, feature_count, crs)
```

### Measurement Calculation Flow

```
GET /measurements/ ──► Load Features from DB
                          │
                          ▼
                    For Each Feature:
                    ├── Reconstruct Shapely Geometry from WKT
                    ├── Determine Geometry Type
                    │   ├── Polygon/MultiPolygon → Calculate Area
                    │   ├── LineString/MultiLineString → Calculate Length
                    │   └── Point/Other → No measurement (handled gracefully)
                    ├── If CRS is Geographic (e.g., EPSG:4326):
                    │   └── Auto-select UTM zone from feature centroid
                    │       └── Transform geometry to projected CRS
                    └── Compute measurement in meters / square meters
```

### CRS Handling Strategy

The application uses a **dynamic UTM zone selection** strategy:

1. **Detection**: The original CRS is read from the file using Fiona/pyproj.
2. **Check**: If the CRS uses geographic coordinates (degrees), transformation is required.
3. **UTM Zone Selection**: For each feature, the centroid's longitude determines the appropriate UTM zone:
   - Formula: `zone = floor((longitude + 180) / 6) + 1`
   - Hemisphere (N/S) is determined by the centroid's latitude.
   - This results in an EPSG code like `326XX` (North) or `327XX` (South).
4. **Transformation**: `pyproj.Transformer` reprojects the geometry before measurement.
5. **Already Projected**: If the file already uses a projected CRS (meters), no transformation is applied — measurements are computed directly.

This approach ensures accurate measurements globally without requiring user-specified target CRS.

---

## 🧠 Design Decisions

### Why FastAPI?
- **Auto-generated OpenAPI docs** — Swagger UI and ReDoc out of the box
- **Pydantic integration** — type-safe request/response validation
- **Async support** — non-blocking file I/O ready
- **Modern Python** — leverages type hints and dataclasses

### Why SQLite + SQLAlchemy?
- **Zero-config database** — no external services needed
- **SQLAlchemy ORM** — clean data access layer, easily swappable to PostgreSQL/PostGIS in production
- **Async driver (aiosqlite)** — non-blocking database operations

### Why GeoPandas + Fiona + Shapely?
- **GeoPandas** — high-level geospatial DataFrame API
- **Fiona** — reliable file I/O for Shapefile and KML (via GDAL drivers)
- **Shapely** — geometry manipulation and WKT serialization
- **pyproj** — accurate CRS transformations

### Graceful Error Handling
- Unsupported geometry types (e.g., `GeometryCollection`) return `measurement: null` instead of crashing
- Corrupt or unreadable files return a `FAILED` status with an `error_message`
- All endpoints return structured JSON errors

### File Storage
- Uploaded files are stored on disk in `uploads/` for potential reprocessing
- File metadata and features are stored in SQLite for fast querying
- **Alternative considered**: Storing files as BLOBs in the database — rejected for simplicity and performance

---

