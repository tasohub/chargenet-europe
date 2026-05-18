from __future__ import annotations

import csv
from pathlib import Path

from .paths import CLEAN_DIR, MART_DIR, ensure_project_dirs
from .scenarios import SERVICE_RADIUS_SCENARIOS
from .transform import haversine_km


def build_tile_smoke_coverage(
    candidate_path: Path | None = None,
    demand_zone_path: Path | None = None,
    output_path: Path | None = None,
) -> Path:
    ensure_project_dirs()
    candidates = read_csv_rows(candidate_path or CLEAN_DIR / "clean_candidate_sites_tile_smoke.csv")
    zones = read_csv_rows(demand_zone_path or CLEAN_DIR / "clean_demand_zones_nuts3_pilot.csv")
    target = output_path or MART_DIR / "fact_candidate_zone_coverage_tile_smoke.csv"
    rows = []
    for candidate in candidates:
        if not candidate.get("lat") or not candidate.get("lon"):
            continue
        for zone in zones:
            if not zone.get("centroid_lat") or not zone.get("centroid_lon"):
                continue
            distance_km = haversine_km(float(candidate["lat"]), float(candidate["lon"]), float(zone["centroid_lat"]), float(zone["centroid_lon"]))
            same_country = int(candidate.get("country_code") == zone.get("country_code"))
            for scenario in SERVICE_RADIUS_SCENARIOS:
                radius_km = int(scenario["coverage_radius_km"])
                within_radius = int(distance_km <= radius_km)
                pair_eligible = int(within_radius == 1 and same_country == 1)
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
                        "pair_eligible_flag": pair_eligible,
                        "pair_exclusion_reason": "" if pair_eligible else "outside_radius_or_cross_border_blocked",
                        "distance_confidence_flag": "candidate_smoke_to_nuts3_bbox_midpoint",
                        "demand_weight_contribution": zone.get("demand_weight", "") if pair_eligible else 0,
                        "proxy_assumption_label": "tile_smoke_candidate_coverage_not_full_pilot_matrix",
                    }
                )
    fieldnames = [
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
