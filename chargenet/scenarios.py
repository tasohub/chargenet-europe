from __future__ import annotations

import csv
import json
from pathlib import Path

from .paths import CLEAN_DIR, CONFIG_DIR, MART_DIR, ensure_project_dirs


SERVICE_RADIUS_SCENARIOS = [
    {
        "scenario_id": "scenario:radius-conservative",
        "scenario_slug": "radius_conservative",
        "coverage_radius_km": 15,
        "classification": "assumption",
        "allowed_use_note": "Sensitivity input for baseline and MILP; not observed driver behavior.",
    },
    {
        "scenario_id": "scenario:radius-base",
        "scenario_slug": "radius_base",
        "coverage_radius_km": 30,
        "classification": "assumption",
        "allowed_use_note": "Base V1 service-radius assumption shared by baseline and MILP.",
    },
    {
        "scenario_id": "scenario:radius-aggressive",
        "scenario_slug": "radius_aggressive",
        "coverage_radius_km": 50,
        "classification": "assumption",
        "allowed_use_note": "Aggressive coverage-radius assumption for sensitivity only.",
    },
]

CAPEX_BASE_BY_SITE_TYPE = {
    "fuel": 450000,
    "services": 650000,
}
DEFAULT_CAPEX_BASE = 550000
CAPEX_ASSUMPTION_VERSION = "tile_smoke_capex_proxy_v2"


def write_service_radius_config(path: Path | None = None) -> Path:
    ensure_project_dirs()
    target = path or CONFIG_DIR / "service_radius_scenarios.json"
    target.write_text(json.dumps(SERVICE_RADIUS_SCENARIOS, indent=2) + "\n", encoding="utf-8")
    return target


def build_scenario_inputs_sample() -> Path:
    ensure_project_dirs()
    target = MART_DIR / "fact_scenario_inputs_sample.csv"
    fieldnames = [
        "scenario_id",
        "entity_type",
        "entity_id",
        "d_i",
        "c_j",
        "b",
        "k",
        "r_j",
        "rho",
        "service_radius_km",
        "demand_weight_version",
        "capex_assumption_version",
        "risk_penalty_on",
        "competition_penalty_on",
        "classification",
        "allowed_use_note",
    ]
    candidates = read_csv_rows(CLEAN_DIR / "clean_candidate_sites_sample.csv")
    zones = read_csv_rows(CLEAN_DIR / "clean_demand_zones_sample.csv")
    rows = []
    for scenario in SERVICE_RADIUS_SCENARIOS:
        for zone in zones:
            rows.append(
                {
                    "scenario_id": scenario["scenario_id"],
                    "entity_type": "demand_zone",
                    "entity_id": zone["demand_zone_id"],
                    "d_i": zone["demand_weight"],
                    "c_j": "",
                    "b": 10000000,
                    "k": 10,
                    "r_j": "",
                    "rho": 0,
                    "service_radius_km": scenario["coverage_radius_km"],
                    "demand_weight_version": "population_2025_v1",
                    "capex_assumption_version": "capex_class_v1",
                    "risk_penalty_on": 0,
                    "competition_penalty_on": 0,
                    "classification": "derived_proxy",
                    "allowed_use_note": "Demand weight uses population as a proxy, not observed charging sessions.",
                }
            )
        for candidate in candidates:
            rows.append(
                {
                    "scenario_id": scenario["scenario_id"],
                    "entity_type": "candidate_site",
                    "entity_id": candidate["candidate_site_id"],
                    "d_i": "",
                    "c_j": estimate_candidate_capex(candidate),
                    "b": 10000000,
                    "k": 10,
                    "r_j": candidate.get("rollout_risk_score", "0.5"),
                    "rho": 0,
                    "service_radius_km": scenario["coverage_radius_km"],
                    "demand_weight_version": "population_2025_v1",
                    "capex_assumption_version": CAPEX_ASSUMPTION_VERSION,
                    "risk_penalty_on": 0,
                    "competition_penalty_on": 0,
                    "classification": "assumption",
                    "allowed_use_note": "CAPEX and rollout risk are assumptions for scenario testing, not observed site facts.",
                }
            )

    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return target


def build_scenario_inputs_tile_smoke() -> Path:
    ensure_project_dirs()
    target = MART_DIR / "fact_scenario_inputs_tile_smoke.csv"
    fieldnames = [
        "scenario_id",
        "entity_type",
        "entity_id",
        "d_i",
        "c_j",
        "b",
        "k",
        "r_j",
        "rho",
        "service_radius_km",
        "demand_weight_version",
        "capex_assumption_version",
        "risk_penalty_on",
        "competition_penalty_on",
        "classification",
        "allowed_use_note",
    ]
    candidates = read_csv_rows(CLEAN_DIR / "clean_candidate_sites_tile_smoke.csv")
    zones = read_csv_rows(CLEAN_DIR / "clean_demand_zones_nuts3_pilot.csv")
    rows = []
    for scenario in SERVICE_RADIUS_SCENARIOS:
        for zone in zones:
            rows.append(
                {
                    "scenario_id": scenario["scenario_id"],
                    "entity_type": "demand_zone",
                    "entity_id": zone["demand_zone_id"],
                    "d_i": zone["demand_weight"],
                    "c_j": "",
                    "b": 10000000,
                    "k": 10,
                    "r_j": "",
                    "rho": 0,
                    "service_radius_km": scenario["coverage_radius_km"],
                    "demand_weight_version": "population_2025_v1",
                    "capex_assumption_version": "tile_smoke_capex_class_v1",
                    "risk_penalty_on": 0,
                    "competition_penalty_on": 0,
                    "classification": "derived_proxy",
                    "allowed_use_note": "Demand uses NUTS3 population as a proxy; tile-smoke scope is not full pilot optimization.",
                }
            )
        for candidate in candidates:
            rows.append(
                {
                    "scenario_id": scenario["scenario_id"],
                    "entity_type": "candidate_site",
                    "entity_id": candidate["candidate_site_id"],
                    "d_i": "",
                    "c_j": estimate_candidate_capex(candidate),
                    "b": 10000000,
                    "k": 10,
                    "r_j": candidate.get("rollout_risk_score", "0.5"),
                    "rho": 0,
                    "service_radius_km": scenario["coverage_radius_km"],
                    "demand_weight_version": "population_2025_v1",
                    "capex_assumption_version": CAPEX_ASSUMPTION_VERSION,
                    "risk_penalty_on": 0,
                    "competition_penalty_on": 0,
                    "classification": "assumption",
                    "allowed_use_note": "Candidate CAPEX and risk are assumptions; tile-smoke candidates are not confirmed feasible sites.",
                }
            )

    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return target


def estimate_candidate_capex(candidate: dict) -> int:
    base = CAPEX_BASE_BY_SITE_TYPE.get(str(candidate.get("site_type", "")).strip().lower(), DEFAULT_CAPEX_BASE)
    rollout_risk = clamp(float_or_default(candidate.get("rollout_risk_score"), 0.5))
    data_quality = clamp(float_or_default(candidate.get("data_quality_score"), 0.5))
    risk_contingency = 1 + 0.30 * rollout_risk
    quality_contingency = 1 + 0.20 * (1 - data_quality)
    return round_to_nearest(base * risk_contingency * quality_contingency, 10000)


def cost_proxy_explanation_rows() -> list[dict]:
    shared_limit = "Public proxy assumption; not vendor quotes, not investment-grade, and excludes grid capacity, permits, land, traffic, utilization, and negotiated CAPEX."
    return [
        {
            "cost_proxy_driver": "site_type_base",
            "current_logic": f"fuel={CAPEX_BASE_BY_SITE_TYPE['fuel']}; services={CAPEX_BASE_BY_SITE_TYPE['services']}; default={DEFAULT_CAPEX_BASE}",
            "why_included": "Keeps service-area and fuel-site proxies directionally different before optimization.",
            "limitation": shared_limit,
        },
        {
            "cost_proxy_driver": "rollout_risk",
            "current_logic": "multiplier = 1 + 0.30 * rollout_risk_score",
            "why_included": "Adds a contingency for public-proxy rollout friction already present in the candidate mart.",
            "limitation": shared_limit,
        },
        {
            "cost_proxy_driver": "data_quality",
            "current_logic": "multiplier = 1 + 0.20 * (1 - data_quality_score)",
            "why_included": "Penalizes lower-confidence public records so missing or weak tags do not look artificially cheap.",
            "limitation": shared_limit,
        },
        {
            "cost_proxy_driver": "rounding",
            "current_logic": "round final proxy cost to nearest 10000",
            "why_included": "Prevents false precision in a public-data scenario cost proxy.",
            "limitation": shared_limit,
        },
    ]


def float_or_default(value: object, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def round_to_nearest(value: float, nearest: int) -> int:
    return int(round(value / nearest) * nearest)


def read_csv_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))
