import requests
import json
import math


BASE_URL = "https://gisweb.newtonma.gov/server/rest/services/Browser/MapServer/identify"


def _lonlat_to_web_mercator(lon: float, lat: float):
    """
    Convert WGS84 lon/lat (degrees) to Web Mercator x/y (EPSG:3857 aka 102100).
    """
    # Clamp latitude to the Web Mercator max
    lat = max(min(lat, 85.05112878), -85.05112878)
    origin_shift = 20037508.342789244  # meters

    x = lon * origin_shift / 180.0
    y = math.log(math.tan((90.0 + lat) * math.pi / 360.0)) * origin_shift / math.pi
    return x, y


def identify_at_lonlat(
    lon: float,
    lat: float,
    buffer_m: float = 400.0,
    layer_ids=(13, 20, 21),
    timeout: int = 15,
):
    """
    Call Newton GIS Identify for a lon/lat point and return (owner, assessed_value_int, assessed_value_str).
    Prefers layer 20 (Property Boundaries), then 13 (Historic Property Status).
    """
    x, y = _lonlat_to_web_mercator(lon, lat)

    xmin = x - buffer_m
    ymin = y - buffer_m
    xmax = x + buffer_m
    ymax = y + buffer_m

    params = {
        "f": "json",
        "returnFieldName": "false",
        "returnGeometry": "false",
        "returnUnformattedValues": "false",
        "returnZ": "false",
        "tolerance": 3,
        "imageDisplay": "2560,1189,96",
        "geometry": json.dumps({"x": x, "y": y}),
        "geometryType": "esriGeometryPoint",
        "sr": 102100,
        "mapExtent": f"{xmin},{ymin},{xmax},{ymax}",
        "layers": "all:" + ",".join(str(i) for i in layer_ids),
    }

    resp = requests.get(BASE_URL, params=params, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()

    # Preferred order: Property Boundaries (20), then Historic Property Status (13)
    preferred_order = [20, 13]

    # Flatten results in preferred order
    results = data.get("results", [])
    results_sorted = sorted(
        results,
        key=lambda r: (
            preferred_order.index(r.get("layerId", 0))
            if r.get("layerId") in preferred_order
            else len(preferred_order)
        ),
    )

    owner = None
    assessed_val_str = None
    assessed_val_int = None

    for res in results_sorted:
        attrs = res.get("attributes") or {}
        # Find owner
        for k, v in attrs.items():
            if k.strip().lower().replace(" ", "") in (
                "currentowner",
                "owner",
                "ownername",
            ):
                owner = v
                break

        # Find assessed value
        for k, v in attrs.items():
            if k.strip().lower().replace(" ", "") in (
                "assessedvalue",
                "totalassessedvalue",
                "assessedvaluation",
            ):
                assessed_val_str = str(v)
                digits = "".join(ch for ch in assessed_val_str if ch.isdigit())
                assessed_val_int = int(digits) if digits else None
                break

        if owner and assessed_val_str:
            break

    return owner, assessed_val_int
