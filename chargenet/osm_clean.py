from __future__ import annotations

import csv
import json
from pathlib import Path

from .ids import candidate_site_id, demand_zone_id, osm_object_id
from .paths import CLEAN_DIR, MART_DIR, ensure_project_dirs
from .transform import first_present, osm_tag_quality_score

ALL_LOG = MART_DIR / "osm_tile_execution_log_all.csv"
LATEST_LOG = MART_DIR / "osm_tile_execution_log_latest.csv"


def build_existing_chargers_from_tile_smoke(
    log_path: Path | None = None,
    output_path: Path | None = None,
) -> Path:
    ensure_project_dirs()
    source_log = log_path or (ALL_LOG if ALL_LOG.exists() else LATEST_LOG)
    target = output_path or CLEAN_DIR / "clean_existing_chargers_tile_smoke.csv"
    rows_by_id = {}
    for log_row in read_csv_rows(source_log):
        if log_row.get("status") != "fetched" or log_row.get("extract_slug") != "charging_stations":
            continue
        raw_path = Path(log_row["raw_path"])
        for element in parse_osm_elements(raw_path):
            coordinate = element_coordinate(element)
            if coordinate is None:
                continue
            lat, lon = coordinate
            tags = element.get("tags", {})
            source_id = osm_object_id(element.get("type", ""), element.get("id", ""))
            rows_by_id[source_id] = {
                "tile_run_id": log_row["run_id"],
                "tile_job_id": log_row["tile_job_id"],
                "charger_source_id": source_id,
                "source_record_id": source_id,
                "charger_source": "osm_overpass",
                "country_code": log_row["country_code"],
                "nuts_id": log_row["nuts_id"],
                "lat": lat,
                "lon": lon,
                "operator": tags.get("operator", ""),
                "brand": tags.get("brand", ""),
                "access": tags.get("access", ""),
                "capacity": tags.get("capacity", ""),
                "socket_type2": tags.get("socket:type2", ""),
                "socket_ccs": tags.get("socket:type2_combo", ""),
                "socket_chademo": tags.get("socket:chademo", ""),
                "max_power_kw_raw": first_present(tags, ["socket:type2_combo:output", "socket:type2:output", "socket:chademo:output"]),
                "missing_socket_flag": int(not any(key.startswith("socket:") and not key.endswith(":output") for key in tags)),
                "missing_power_flag": int(not any(key.startswith("socket:") and key.endswith(":output") for key in tags)),
                "data_quality_score": osm_tag_quality_score(tags),
                "raw_tags_json": json.dumps(tags, ensure_ascii=False, sort_keys=True),
                "proxy_assumption_label": "observed_public_osm_tile_smoke_not_full_pilot_supply",
            }
    rows = list(rows_by_id.values())
    rows.sort(key=lambda row: (row["country_code"], row["nuts_id"], row["charger_source_id"]))
    fieldnames = [
        "tile_run_id",
        "tile_job_id",
        "charger_source_id",
        "source_record_id",
        "charger_source",
        "country_code",
        "nuts_id",
        "lat",
        "lon",
        "operator",
        "brand",
        "access",
        "capacity",
        "socket_type2",
        "socket_ccs",
        "socket_chademo",
        "max_power_kw_raw",
        "missing_socket_flag",
        "missing_power_flag",
        "data_quality_score",
        "raw_tags_json",
        "proxy_assumption_label",
    ]
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return target


def build_candidate_sites_from_tile_smoke(
    log_path: Path | None = None,
    output_path: Path | None = None,
) -> Path:
    ensure_project_dirs()
    source_log = log_path or (ALL_LOG if ALL_LOG.exists() else LATEST_LOG)
    target = output_path or CLEAN_DIR / "clean_candidate_sites_tile_smoke.csv"
    rows_by_id = {}
    for log_row in read_csv_rows(source_log):
        if log_row.get("status") != "fetched" or log_row.get("extract_slug") not in {"candidate_fuel", "candidate_services"}:
            continue
        raw_path = Path(log_row["raw_path"])
        for element in parse_osm_elements(raw_path):
            coordinate = element_coordinate(element)
            if coordinate is None:
                continue
            lat, lon = coordinate
            tags = element.get("tags", {})
            osm_type = element.get("type", "")
            osm_id = element.get("id", "")
            source_id = osm_object_id(osm_type, osm_id)
            candidate_id = candidate_site_id(osm_type, osm_id)
            rows_by_id[candidate_id] = {
                "tile_run_id": log_row["run_id"],
                "tile_job_id": log_row["tile_job_id"],
                "candidate_site_id": candidate_id,
                "source_record_id": source_id,
                "candidate_source": "osm_overpass",
                "country_code": log_row["country_code"],
                "nearest_demand_zone_id": log_row.get("demand_zone_id") or demand_zone_id(log_row["nuts_id"]),
                "nuts_id": log_row["nuts_id"],
                "lat": lat,
                "lon": lon,
                "site_type": infer_candidate_site_type(log_row, tags),
                "candidate_proxy_flag": 1,
                "candidate_feasibility_note": "OSM tile smoke POI proxy; land, permit, grid, and commercial feasibility not validated.",
                "road_or_service_proxy": tags.get("highway", "") or tags.get("amenity", ""),
                "brand": tags.get("brand", ""),
                "operator": tags.get("operator", ""),
                "name": tags.get("name", ""),
                "estimated_capex_class": "tile_smoke_assumption",
                "rollout_risk_score": 0.5,
                "competition_score": 0.5,
                "data_quality_score": osm_tag_quality_score(tags),
                "raw_tags_json": json.dumps(tags, ensure_ascii=False, sort_keys=True),
                "proxy_assumption_label": "candidate_proxy_osm_tile_smoke_not_confirmed_feasible_site",
            }
    rows = list(rows_by_id.values())
    rows.sort(key=lambda row: (row["country_code"], row["nuts_id"], row["candidate_site_id"]))
    fieldnames = [
        "tile_run_id",
        "tile_job_id",
        "candidate_site_id",
        "source_record_id",
        "candidate_source",
        "country_code",
        "nearest_demand_zone_id",
        "nuts_id",
        "lat",
        "lon",
        "site_type",
        "candidate_proxy_flag",
        "candidate_feasibility_note",
        "road_or_service_proxy",
        "brand",
        "operator",
        "name",
        "estimated_capex_class",
        "rollout_risk_score",
        "competition_score",
        "data_quality_score",
        "raw_tags_json",
        "proxy_assumption_label",
    ]
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return target


def parse_osm_elements(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    elements = payload.get("elements", [])
    if not isinstance(elements, list):
        raise ValueError(f"Expected OSM payload with list field 'elements' in {path}")
    return elements


def element_coordinate(element: dict) -> tuple[float, float] | None:
    if element.get("lat") is not None and element.get("lon") is not None:
        return float(element["lat"]), float(element["lon"])
    center = element.get("center") or {}
    if center.get("lat") is not None and center.get("lon") is not None:
        return float(center["lat"]), float(center["lon"])
    return None


def infer_candidate_site_type(log_row: dict, tags: dict) -> str:
    extract_slug = log_row.get("extract_slug", "")
    if extract_slug == "candidate_fuel":
        return "fuel"
    if extract_slug == "candidate_services":
        return "services"
    return tags.get("amenity") or tags.get("highway", "")


def read_csv_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))
