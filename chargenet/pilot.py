from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterator

from .ids import demand_zone_id
from .paths import CLEAN_DIR, CONFIG_DIR, RAW_DIR, ensure_project_dirs


DEFAULT_PILOT_COUNTRIES = ["BE", "DE", "FR", "NL"]


def load_pilot_scope(path: Path | None = None) -> dict:
    scope_path = path or CONFIG_DIR / "pilot_scope.json"
    if not scope_path.exists():
        return {
            "pilot_countries": DEFAULT_PILOT_COUNTRIES,
            "nuts_version": "2024",
            "population_year": 2025,
        }
    return json.loads(scope_path.read_text(encoding="utf-8"))


def build_pilot_nuts3_demand_zones(
    raw_path: Path | None = None,
    population_path: Path | None = None,
    output_path: Path | None = None,
    scope_path: Path | None = None,
) -> Path:
    ensure_project_dirs()
    source = raw_path or RAW_DIR / "gisco_nuts_2024_level3.geojson"
    target = output_path or CLEAN_DIR / "clean_demand_zones_nuts3_pilot.csv"
    scope = load_pilot_scope(scope_path)
    countries = set(scope.get("pilot_countries", DEFAULT_PILOT_COUNTRIES))
    nuts_version = str(scope.get("nuts_version", "2024"))
    population_year = str(scope.get("population_year", "2025"))
    population_source = population_path or RAW_DIR / "eurostat_population_nuts3_2025_pilot.json"
    population_by_geo = load_eurostat_population_by_geo(population_source) if population_source.exists() else {}

    payload = json.loads(source.read_text(encoding="utf-8"))
    rows = []
    for feature in payload.get("features", []):
        properties = feature.get("properties", {})
        nuts_id = properties.get("NUTS_ID", "")
        country_code = properties.get("CNTR_CODE", nuts_id[:2])
        if str(properties.get("LEVL_CODE", "")) != "3" or country_code not in countries:
            continue
        centroid = geometry_bbox_midpoint(feature.get("geometry", {}))
        if centroid is None:
            continue
        centroid_lat, centroid_lon, min_lat, min_lon, max_lat, max_lon = centroid
        population = population_by_geo.get(nuts_id)
        population_joined = population is not None
        rows.append(
            {
                "demand_zone_id": demand_zone_id(nuts_id, nuts_version),
                "nuts_id": nuts_id,
                "nuts_version": nuts_version,
                "country_code": country_code,
                "zone_name": properties.get("NAME_LATN") or properties.get("NUTS_NAME", ""),
                "population": population if population_joined else "",
                "population_year": population_year,
                "centroid_lat": round(centroid_lat, 6),
                "centroid_lon": round(centroid_lon, 6),
                "centroid_method": "bbox_midpoint_wgs84_v1",
                "bbox_min_lat": round(min_lat, 6),
                "bbox_min_lon": round(min_lon, 6),
                "bbox_max_lat": round(max_lat, 6),
                "bbox_max_lon": round(max_lon, 6),
                "demand_weight": population if population_joined else "",
                "base_demand_weight": population if population_joined else "",
                "population_missing_flag": 0 if population_joined else 1,
                "demand_confidence_score": 0.75 if population_joined else 0.45,
                "proxy_assumption_label": "population_as_demand_proxy" if population_joined else "nuts3_geometry_ready_population_join_pending",
            }
        )

    rows.sort(key=lambda row: row["nuts_id"])
    fieldnames = [
        "demand_zone_id",
        "nuts_id",
        "nuts_version",
        "country_code",
        "zone_name",
        "population",
        "population_year",
        "centroid_lat",
        "centroid_lon",
        "centroid_method",
        "bbox_min_lat",
        "bbox_min_lon",
        "bbox_max_lat",
        "bbox_max_lon",
        "demand_weight",
        "base_demand_weight",
        "population_missing_flag",
        "demand_confidence_score",
        "proxy_assumption_label",
    ]
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return target


def load_eurostat_population_by_geo(path: Path) -> dict[str, int]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    geo_dimension = payload.get("dimension", {}).get("geo", {}).get("category", {}).get("index", {})
    values = payload.get("value", {})
    if not isinstance(geo_dimension, dict) or not isinstance(values, dict):
        raise ValueError(f"Unsupported Eurostat JSON-stat payload in {path}")
    population_by_geo: dict[str, int] = {}
    for geo_code, flat_index in geo_dimension.items():
        raw_value = values.get(str(flat_index))
        if raw_value is None:
            continue
        population_by_geo[geo_code] = int(raw_value)
    return population_by_geo


def geometry_bbox_midpoint(geometry: dict) -> tuple[float, float, float, float, float, float] | None:
    points = list(iter_lon_lat_pairs(geometry.get("coordinates", [])))
    if not points:
        return None
    lons = [point[0] for point in points]
    lats = [point[1] for point in points]
    min_lon = min(lons)
    max_lon = max(lons)
    min_lat = min(lats)
    max_lat = max(lats)
    return ((min_lat + max_lat) / 2, (min_lon + max_lon) / 2, min_lat, min_lon, max_lat, max_lon)


def iter_lon_lat_pairs(value: object) -> Iterator[tuple[float, float]]:
    if not isinstance(value, list):
        return
    if len(value) >= 2 and isinstance(value[0], (int, float)) and isinstance(value[1], (int, float)):
        yield (float(value[0]), float(value[1]))
        return
    for item in value:
        yield from iter_lon_lat_pairs(item)
