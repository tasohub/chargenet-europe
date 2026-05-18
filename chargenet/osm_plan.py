from __future__ import annotations

import csv
from pathlib import Path

from .paths import CLEAN_DIR, MART_DIR, ensure_project_dirs


EXTRACT_SPECS = [
    {
        "extract_slug": "charging_stations",
        "osm_filter": 'amenity="charging_station"',
        "role": "existing_supply",
    },
    {
        "extract_slug": "candidate_fuel",
        "osm_filter": 'amenity="fuel"',
        "role": "candidate_proxy",
    },
    {
        "extract_slug": "candidate_services",
        "osm_filter": 'highway="services"',
        "role": "candidate_proxy",
    },
]


def build_osm_tile_plan(
    demand_zone_path: Path | None = None,
    output_path: Path | None = None,
) -> Path:
    ensure_project_dirs()
    source = demand_zone_path or CLEAN_DIR / "clean_demand_zones_nuts3_pilot.csv"
    target = output_path or MART_DIR / "osm_pilot_tile_plan.csv"
    zones = read_csv_rows(source)
    rows = []
    for zone in zones:
        if not all(zone.get(field) for field in ["bbox_min_lat", "bbox_min_lon", "bbox_max_lat", "bbox_max_lon"]):
            continue
        for spec in EXTRACT_SPECS:
            rows.append(
                {
                    "tile_job_id": f"osm_tile:{spec['extract_slug']}:{zone['nuts_id']}",
                    "extract_slug": spec["extract_slug"],
                    "osm_filter": spec["osm_filter"],
                    "extract_role": spec["role"],
                    "country_code": zone["country_code"],
                    "nuts_id": zone["nuts_id"],
                    "demand_zone_id": zone["demand_zone_id"],
                    "bbox_south": zone["bbox_min_lat"],
                    "bbox_west": zone["bbox_min_lon"],
                    "bbox_north": zone["bbox_max_lat"],
                    "bbox_east": zone["bbox_max_lon"],
                    "query_grain": "one_nuts3_bbox_per_extract",
                    "status": "planned_not_run",
                    "rate_limit_seconds": 2,
                    "max_retries": 2,
                    "split_on_timeout_flag": 1,
                    "public_release_note": "Tile plan is safe to publish; raw OSM extracts remain local pending ODbL review.",
                }
            )
    fieldnames = [
        "tile_job_id",
        "extract_slug",
        "osm_filter",
        "extract_role",
        "country_code",
        "nuts_id",
        "demand_zone_id",
        "bbox_south",
        "bbox_west",
        "bbox_north",
        "bbox_east",
        "query_grain",
        "status",
        "rate_limit_seconds",
        "max_retries",
        "split_on_timeout_flag",
        "public_release_note",
    ]
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return target


def read_csv_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))
