from __future__ import annotations

import csv
import json
import math
from pathlib import Path

from .ids import candidate_site_id, demand_zone_id, osm_object_id
from .paths import CLEAN_DIR, MART_DIR, RAW_DIR, ensure_project_dirs
from .scenarios import SERVICE_RADIUS_SCENARIOS


SAMPLE_COUNTRY_CODE = "BE"
SAMPLE_DEMAND_ZONE_NUTS_ID = "BE100"
SAMPLE_DEMAND_ZONE_ID = demand_zone_id(SAMPLE_DEMAND_ZONE_NUTS_ID)
SAMPLE_DEMAND_ZONE_CENTROID = (50.8503, 4.3517)
SAMPLE_POPULATION = 1271709
SAMPLE_SERVICE_RADIUS_KM = 50


def parse_osm_elements(path: Path) -> list[dict]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc
    elements = payload.get("elements", [])
    if not isinstance(elements, list):
        raise ValueError(f"Expected OSM payload with list field 'elements' in {path}")
    return elements


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> Path:
    ensure_project_dirs()
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})
    return path


def clean_osm_chargers(raw_path: Path | None = None) -> Path:
    raw_path = raw_path or RAW_DIR / "osm_chargers_brussels_sample.json"
    rows = []
    for element in parse_osm_elements(raw_path):
        tags = element.get("tags", {})
        osm_type = element.get("type")
        osm_id = element.get("id")
        source_id = osm_object_id(osm_type, osm_id)
        rows.append(
            {
                "charger_source_id": source_id,
                "source_record_id": source_id,
                "charger_source": "osm_overpass",
                "country_code": SAMPLE_COUNTRY_CODE,
                "lat": element.get("lat", ""),
                "lon": element.get("lon", ""),
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
                "proxy_assumption_label": "observed_but_incomplete_public_osm_tag",
            }
        )
    return write_csv(
        CLEAN_DIR / "clean_existing_chargers_sample.csv",
        rows,
        [
            "charger_source_id",
            "source_record_id",
            "charger_source",
            "country_code",
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
        ],
    )


def clean_candidate_pois(raw_path: Path | None = None) -> Path:
    raw_path = raw_path or RAW_DIR / "osm_candidate_pois_brussels_sample.json"
    rows = []
    for element in parse_osm_elements(raw_path):
        tags = element.get("tags", {})
        osm_type = element.get("type")
        osm_id = element.get("id")
        source_id = osm_object_id(osm_type, osm_id)
        center = element.get("center") or {}
        lat = element.get("lat", center.get("lat", ""))
        lon = element.get("lon", center.get("lon", ""))
        rows.append(
            {
                "candidate_site_id": candidate_site_id(osm_type, osm_id),
                "source_record_id": source_id,
                "candidate_source": "osm_overpass",
                "country_code": SAMPLE_COUNTRY_CODE,
                "nearest_demand_zone_id": SAMPLE_DEMAND_ZONE_ID,
                "lat": lat,
                "lon": lon,
                "site_type": tags.get("amenity") or tags.get("highway", ""),
                "candidate_proxy_flag": 1,
                "candidate_feasibility_note": "OSM POI proxy; land, permit, grid, and commercial feasibility not validated.",
                "road_or_service_proxy": tags.get("highway", "") or tags.get("amenity", ""),
                "brand": tags.get("brand", ""),
                "operator": tags.get("operator", ""),
                "name": tags.get("name", ""),
                "estimated_capex_class": "urban_standard_assumption",
                "rollout_risk_score": 0.5,
                "competition_score": 0.5,
                "data_quality_score": osm_tag_quality_score(tags),
                "raw_tags_json": json.dumps(tags, ensure_ascii=False, sort_keys=True),
                "proxy_assumption_label": "candidate_proxy_not_confirmed_feasible_site",
            }
        )
    return write_csv(
        CLEAN_DIR / "clean_candidate_sites_sample.csv",
        rows,
        [
            "candidate_site_id",
            "source_record_id",
            "candidate_source",
            "country_code",
            "nearest_demand_zone_id",
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
        ],
    )


def clean_demand_zone_sample() -> Path:
    centroid_lat, centroid_lon = SAMPLE_DEMAND_ZONE_CENTROID
    charger_distances = []
    raw_chargers = RAW_DIR / "osm_chargers_brussels_sample.json"
    if raw_chargers.exists():
        for element in parse_osm_elements(raw_chargers):
            if "lat" in element and "lon" in element:
                charger_distances.append(haversine_km(float(element["lat"]), float(element["lon"]), centroid_lat, centroid_lon))
    nearest_distance = min(charger_distances) if charger_distances else None
    charger_count_5km = sum(1 for distance in charger_distances if distance <= 5)
    row = {
        "demand_zone_id": SAMPLE_DEMAND_ZONE_ID,
        "nuts_id": SAMPLE_DEMAND_ZONE_NUTS_ID,
        "nuts_version": "2024",
        "country_code": SAMPLE_COUNTRY_CODE,
        "zone_name": "Arr. de Bruxelles-Capitale / Brussel-Hoofdstad",
        "population": SAMPLE_POPULATION,
        "population_year": 2025,
        "centroid_lat": centroid_lat,
        "centroid_lon": centroid_lon,
        "baseline_nearest_charger_distance_km": round(nearest_distance, 3) if nearest_distance is not None else "",
        "baseline_charger_count_within_radius": charger_count_5km,
        "underserved_zone_flag": int(charger_count_5km == 0),
        "demand_weight": SAMPLE_POPULATION,
        "base_demand_weight": SAMPLE_POPULATION,
        "urban_density_segment": "urban",
        "demand_confidence_score": 0.7,
        "proxy_assumption_label": "population_as_demand_proxy",
    }
    return write_csv(
        CLEAN_DIR / "clean_demand_zones_sample.csv",
        [row],
        [
            "demand_zone_id",
            "nuts_id",
            "nuts_version",
            "country_code",
            "zone_name",
            "population",
            "population_year",
            "centroid_lat",
            "centroid_lon",
            "baseline_nearest_charger_distance_km",
            "baseline_charger_count_within_radius",
            "underserved_zone_flag",
            "demand_weight",
            "base_demand_weight",
            "urban_density_segment",
            "demand_confidence_score",
            "proxy_assumption_label",
        ],
    )


def build_candidate_zone_coverage_sample() -> Path:
    candidates_path = CLEAN_DIR / "clean_candidate_sites_sample.csv"
    demand_zone_path = CLEAN_DIR / "clean_demand_zones_sample.csv"
    if not candidates_path.exists() or not demand_zone_path.exists():
        clean_candidate_pois()
        clean_demand_zone_sample()

    with candidates_path.open(newline="", encoding="utf-8") as handle:
        candidates = list(csv.DictReader(handle))
    with demand_zone_path.open(newline="", encoding="utf-8") as handle:
        zones = list(csv.DictReader(handle))

    # Sample centroid only. Phase 3 full build should replace this with GIS-based NUTS centroids.
    sample_zone_centroids = {SAMPLE_DEMAND_ZONE_NUTS_ID: SAMPLE_DEMAND_ZONE_CENTROID}
    candidate_country = {candidate["candidate_site_id"]: candidate.get("country_code", "") for candidate in candidates}
    rows = []
    for candidate in candidates:
        if not candidate.get("lat") or not candidate.get("lon"):
            continue
        for zone in zones:
            centroid = sample_zone_centroids.get(zone["nuts_id"])
            if not centroid:
                continue
            distance_km = haversine_km(float(candidate["lat"]), float(candidate["lon"]), centroid[0], centroid[1])
            same_country = int(candidate_country.get(candidate["candidate_site_id"], "") == zone["country_code"])
            for scenario in SERVICE_RADIUS_SCENARIOS:
                radius_km = scenario["coverage_radius_km"]
                within_radius = int(distance_km <= radius_km)
                rows.append(
                    {
                        "candidate_site_id": candidate["candidate_site_id"],
                        "demand_zone_id": zone["demand_zone_id"],
                        "coverage_radius_km": radius_km,
                        "distance_km": round(distance_km, 3),
                        "distance_method_version": "haversine_wgs84_v1",
                        "a_ij": within_radius,
                        "within_radius_flag": within_radius,
                        "same_country_flag": same_country,
                        "cross_border_allowed_flag": 0,
                        "pair_eligible_flag": int(within_radius == 1 and same_country == 1),
                        "pair_exclusion_reason": "" if within_radius == 1 and same_country == 1 else "outside_radius_or_cross_border_blocked",
                        "distance_confidence_flag": "sample_centroid_distance",
                        "demand_weight_contribution": zone["demand_weight"] if within_radius else 0,
                        "proxy_assumption_label": "sample_distance_matrix_for_pipeline_validation",
                    }
                )

    return write_csv(
        MART_DIR / "fact_candidate_zone_coverage_sample.csv",
        rows,
        [
            "candidate_site_id",
            "demand_zone_id",
            "coverage_radius_km",
            "distance_km",
            "distance_method_version",
            "a_ij",
            "within_radius_flag",
            "same_country_flag",
            "cross_border_allowed_flag",
            "pair_eligible_flag",
            "pair_exclusion_reason",
            "distance_confidence_flag",
            "demand_weight_contribution",
            "proxy_assumption_label",
        ],
    )


def first_present(mapping: dict, keys: list[str]) -> str:
    for key in keys:
        if mapping.get(key):
            return mapping[key]
    return ""


def osm_tag_quality_score(tags: dict) -> float:
    useful_fields = ["operator", "brand", "capacity", "access", "opening_hours", "socket:type2", "socket:type2_combo", "socket:chademo"]
    present = sum(1 for field in useful_fields if tags.get(field))
    return round(min(1.0, 0.3 + present / len(useful_fields)), 3)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0088
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    return radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def build_all_clean_samples() -> list[Path]:
    return [
        clean_osm_chargers(),
        clean_candidate_pois(),
        clean_demand_zone_sample(),
        build_candidate_zone_coverage_sample(),
    ]
