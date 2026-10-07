"""Comprehensive automated test script for Geospatial File Measurement API."""

import io
import json
import time
import zipfile
import urllib.request
import urllib.error


BASE_URL = "http://127.0.0.1:8000"


def make_multipart_body(field_name: str, filename: str, content: bytes) -> tuple[bytes, str]:
    """Build multipart/form-data request body."""
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    body = bytearray()
    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(
        f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'.encode(
            "utf-8"
        )
    )
    body.extend(b"Content-Type: application/octet-stream\r\n\r\n")
    body.extend(content)
    body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode("utf-8"))
    content_type = f"multipart/form-data; boundary={boundary}"
    return bytes(body), content_type


def test_endpoint():
    print("=" * 60)
    print("Testing Geospatial File Measurement API")
    print("=" * 60)

    # 1. Health check
    print("\n1. Testing GET / (Health Check)...")
    req = urllib.request.Request(f"{BASE_URL}/")
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        print(f"   Status 200 OK: {data}")

    # 2. Upload KML
    print("\n2. Testing POST /api/files/ with KML...")
    with open("test_sample.kml", "rb") as f:
        kml_bytes = f.read()

    body, ctype = make_multipart_body("file", "test_sample.kml", kml_bytes)
    req = urllib.request.Request(
        f"{BASE_URL}/api/files/",
        data=body,
        headers={"Content-Type": ctype},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 201
        file_info = json.loads(resp.read().decode("utf-8"))
        print(f"   File Uploaded: {json.dumps(file_info, indent=2)}")
        kml_id = file_info["id"]
        assert file_info["status"] == "COMPLETED"
        assert file_info["feature_count"] == 3

    # 3. GET /api/files/{id}/
    print(f"\n3. Testing GET /api/files/{kml_id}/ ...")
    req = urllib.request.Request(f"{BASE_URL}/api/files/{kml_id}/")
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        print(f"   Status 200 OK: feature_count={data['feature_count']}, crs={data['crs']}")

    # 4. GET /api/files/{id}/measurements/
    print(f"\n4. Testing GET /api/files/{kml_id}/measurements/ ...")
    req = urllib.request.Request(f"{BASE_URL}/api/files/{kml_id}/measurements/")
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        meas_data = json.loads(resp.read().decode("utf-8"))
        print(f"   Projected CRS selected: {meas_data['crs_projected']}")
        print(f"   Total features: {meas_data['feature_count']}")
        for f in meas_data["features"]:
            print(
                f"   - Feature {f['feature_index']} ({f['geometry_type']}): "
                f"type={f['measurement']['type']}, value={f['measurement']['value']} {f['measurement']['unit'] or ''}"
            )
            if f["geometry_type"] == "Polygon":
                assert f["measurement"]["type"] == "area"
                assert f["measurement"]["value"] > 0
                assert f["measurement"]["unit"] == "square meters"
            elif f["geometry_type"] == "LineString":
                assert f["measurement"]["type"] == "length"
                assert f["measurement"]["value"] > 0
                assert f["measurement"]["unit"] == "meters"
            elif f["geometry_type"] == "Point":
                assert f["measurement"]["type"] == "none"

    # 5. Upload Shapefile (.zip)
    print("\n5. Testing POST /api/files/ with Shapefile (.zip)...")
    with open("test_sample_shapefile.zip", "rb") as f:
        shp_bytes = f.read()

    body, ctype = make_multipart_body("file", "test_sample_shapefile.zip", shp_bytes)
    req = urllib.request.Request(
        f"{BASE_URL}/api/files/",
        data=body,
        headers={"Content-Type": ctype},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 201
        shp_info = json.loads(resp.read().decode("utf-8"))
        print(f"   Shapefile Uploaded: {json.dumps(shp_info, indent=2)}")
        shp_id = shp_info["id"]
        assert shp_info["status"] == "COMPLETED"
        assert shp_info["file_type"] == "shapefile"
        assert shp_info["feature_count"] == 2

    # 6. GET /api/files/{shp_id}/measurements/
    print(f"\n6. Testing GET /api/files/{shp_id}/measurements/ ...")
    req = urllib.request.Request(f"{BASE_URL}/api/files/{shp_id}/measurements/")
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        meas_data = json.loads(resp.read().decode("utf-8"))
        print(f"   Projected CRS selected: {meas_data['crs_projected']}")
        print(f"   Total features: {meas_data['feature_count']}")
        for f in meas_data["features"]:
            print(
                f"   - Feature {f['feature_index']} ({f['geometry_type']}): "
                f"properties={f['properties']}, "
                f"type={f['measurement']['type']}, value={f['measurement']['value']} {f['measurement']['unit'] or ''}"
            )
            assert f["measurement"]["type"] == "area"
            assert f["measurement"]["value"] > 0
            assert f["measurement"]["unit"] == "square meters"

    # 7. GET /api/files/ (List all files)
    print("\n7. Testing GET /api/files/ (List all files)...")
    req = urllib.request.Request(f"{BASE_URL}/api/files/")
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        files_list = json.loads(resp.read().decode("utf-8"))
        print(f"   Total files returned: {len(files_list)}")
        assert len(files_list) >= 2

    print("\n" + "=" * 60)
    print("ALL API TESTS PASSED SUCCESSFULLY! (KML + SHAPEFILE)")
    print("=" * 60)


if __name__ == "__main__":
    test_endpoint()
