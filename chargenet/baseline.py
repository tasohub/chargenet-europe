from __future__ import annotations

import csv
from pathlib import Path

from .paths import CLEAN_DIR, MART_DIR, ensure_project_dirs
from .scenarios import SERVICE_RADIUS_SCENARIOS


WEIGHTS = {
    "coverage": 0.55,
    "data_quality": 0.20,
    "risk": 0.15,
    "competition": 0.10,
}

SCORE_COMPONENTS = ("coverage", "data_quality", "risk", "competition")
SENSITIVITY_WEIGHT_SETS = [
    {
        "weight_set_id": "weights:base",
        "weight_set_name": "Base balanced",
        **WEIGHTS,
    },
    {
        "weight_set_id": "weights:coverage-led",
        "weight_set_name": "Coverage led",
        "coverage": 0.70,
        "data_quality": 0.10,
        "risk": 0.10,
        "competition": 0.10,
    },
    {
        "weight_set_id": "weights:risk-aware",
        "weight_set_name": "Risk aware",
        "coverage": 0.45,
        "data_quality": 0.15,
        "risk": 0.30,
        "competition": 0.10,
    },
    {
        "weight_set_id": "weights:competition-aware",
        "weight_set_name": "Competition aware",
        "coverage": 0.45,
        "data_quality": 0.15,
        "risk": 0.15,
        "competition": 0.25,
    },
    {
        "weight_set_id": "weights:data-quality-guardrail",
        "weight_set_name": "Data quality guardrail",
        "coverage": 0.45,
        "data_quality": 0.35,
        "risk": 0.10,
        "competition": 0.10,
    },
]


def build_baseline_scores_tile_smoke(
    candidate_path: Path | None = None,
    coverage_path: Path | None = None,
    output_path: Path | None = None,
) -> Path:
    ensure_project_dirs()
    candidates = read_csv_rows(candidate_path or CLEAN_DIR / "clean_candidate_sites_tile_smoke.csv")
    coverage = read_csv_rows(coverage_path or MART_DIR / "fact_candidate_zone_coverage_tile_smoke.csv")
    target = output_path or MART_DIR / "mart_candidate_baseline_scores_tile_smoke.csv"

    candidate_by_id = {row["candidate_site_id"]: row for row in candidates}
    scenario_by_radius = {str(item["coverage_radius_km"]): item["scenario_id"] for item in SERVICE_RADIUS_SCENARIOS}
    grouped = group_coverage_by_candidate_radius(coverage)
    max_covered_by_scenario: dict[str, float] = {}
    for (candidate_id, radius), rows in grouped.items():
        scenario_id = scenario_by_radius[str(radius)]
        covered = covered_demand(rows)
        max_covered_by_scenario[scenario_id] = max(max_covered_by_scenario.get(scenario_id, 0.0), covered)

    output_rows = []
    for candidate_id, candidate in candidate_by_id.items():
        for scenario in SERVICE_RADIUS_SCENARIOS:
            radius = str(scenario["coverage_radius_km"])
            scenario_id = scenario["scenario_id"]
            rows = grouped.get((candidate_id, radius), [])
            covered = covered_demand(rows)
            max_covered = max_covered_by_scenario.get(scenario_id, 0.0)
            coverage_component = covered / max_covered if max_covered > 0 else 0.0
            data_quality_component = clamp(float(candidate.get("data_quality_score") or 0))
            risk_component = 1 - clamp(float(candidate.get("rollout_risk_score") or 0.5))
            competition_component = 1 - clamp(float(candidate.get("competition_score") or 0.5))
            baseline_score = (
                WEIGHTS["coverage"] * coverage_component
                + WEIGHTS["data_quality"] * data_quality_component
                + WEIGHTS["risk"] * risk_component
                + WEIGHTS["competition"] * competition_component
            )
            output_rows.append(
                {
                    "scenario_id": scenario_id,
                    "candidate_site_id": candidate_id,
                    "country_code": candidate.get("country_code", ""),
                    "nuts_id": candidate.get("nuts_id", ""),
                    "site_type": candidate.get("site_type", ""),
                    "coverage_radius_km": radius,
                    "covered_demand_weight": round(covered, 3),
                    "covered_zone_count": sum(1 for row in rows if int(row.get("pair_eligible_flag") or 0) == 1),
                    "avg_distance_covered_km": average_distance(rows),
                    "coverage_component": round(coverage_component, 6),
                    "data_quality_component": round(data_quality_component, 6),
                    "risk_component": round(risk_component, 6),
                    "competition_component": round(competition_component, 6),
                    "baseline_score": round(baseline_score, 6),
                    "rank_metric_version": "tile_smoke_baseline_v1",
                    "action_bucket": action_bucket(covered, baseline_score),
                    "allowed_use_note": "Prioritize diligence only; smoke candidate set is not a full site rollout recommendation.",
                    "proxy_assumption_label": "tile_smoke_baseline_score_not_investment_grade",
                }
            )

    output_rows.sort(key=lambda row: (row["scenario_id"], -float(row["baseline_score"]), row["candidate_site_id"]))
    add_rank_within_scenario(output_rows)
    fieldnames = [
        "scenario_id",
        "candidate_site_id",
        "country_code",
        "nuts_id",
        "site_type",
        "coverage_radius_km",
        "covered_demand_weight",
        "covered_zone_count",
        "avg_distance_covered_km",
        "coverage_component",
        "data_quality_component",
        "risk_component",
        "competition_component",
        "baseline_score",
        "rank_within_scenario",
        "rank_metric_version",
        "action_bucket",
        "allowed_use_note",
        "proxy_assumption_label",
    ]
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)
    return target


def build_baseline_sensitivity_tile_smoke(
    baseline_path: Path | None = None,
    output_path: Path | None = None,
) -> Path:
    ensure_project_dirs()
    baseline_rows = read_csv_rows(baseline_path or MART_DIR / "mart_candidate_baseline_scores_tile_smoke.csv")
    target = output_path or MART_DIR / "mart_baseline_sensitivity_tile_smoke.csv"
    output_rows = []
    for weight_set in SENSITIVITY_WEIGHT_SETS:
        if not validate_weight_set(weight_set):
            raise ValueError(f"Invalid baseline sensitivity weight set: {weight_set.get('weight_set_id', '')}")
        for row in baseline_rows:
            output_rows.append(
                {
                    "weight_set_id": weight_set["weight_set_id"],
                    "weight_set_name": weight_set["weight_set_name"],
                    "scenario_id": row["scenario_id"],
                    "candidate_site_id": row["candidate_site_id"],
                    "country_code": row.get("country_code", ""),
                    "nuts_id": row.get("nuts_id", ""),
                    "site_type": row.get("site_type", ""),
                    "coverage_radius_km": row["coverage_radius_km"],
                    "coverage_weight": weight_set["coverage"],
                    "data_quality_weight": weight_set["data_quality"],
                    "risk_weight": weight_set["risk"],
                    "competition_weight": weight_set["competition"],
                    "weighted_score": sensitivity_score(row, weight_set),
                    "base_rank_within_scenario": int(row.get("rank_within_scenario") or 0),
                    "rank_within_weight_set_scenario": "",
                    "rank_delta_vs_base": "",
                    "stable_top10_flag": "",
                    "top_rank_band": "",
                    "allowed_use_note": "Sensitivity test for diligence prioritization only; not a full pilot rollout recommendation.",
                    "proxy_assumption_label": "tile_smoke_baseline_sensitivity_not_investment_grade",
                }
            )
    add_sensitivity_ranks(output_rows)
    fieldnames = [
        "weight_set_id",
        "weight_set_name",
        "scenario_id",
        "candidate_site_id",
        "country_code",
        "nuts_id",
        "site_type",
        "coverage_radius_km",
        "coverage_weight",
        "data_quality_weight",
        "risk_weight",
        "competition_weight",
        "weighted_score",
        "rank_within_weight_set_scenario",
        "base_rank_within_scenario",
        "rank_delta_vs_base",
        "stable_top10_flag",
        "top_rank_band",
        "allowed_use_note",
        "proxy_assumption_label",
    ]
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)
    return target


def validate_weight_set(weight_set: dict) -> bool:
    try:
        weights = [float(weight_set[component]) for component in SCORE_COMPONENTS]
    except (KeyError, TypeError, ValueError):
        return False
    return all(weight >= 0 for weight in weights) and abs(sum(weights) - 1.0) < 0.000001


def compute_weighted_score(row: dict, weights: dict) -> float:
    return sum(
        float(weights[component]) * clamp(float(row.get(f"{component}_component") or 0))
        for component in SCORE_COMPONENTS
    )


def sensitivity_score(row: dict, weight_set: dict) -> float:
    if weight_set.get("weight_set_id") == "weights:base" and row.get("baseline_score"):
        return round(float(row["baseline_score"]), 6)
    return round(compute_weighted_score(row, weight_set), 6)


def add_sensitivity_ranks(rows: list[dict]) -> None:
    groups: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        groups.setdefault((row["weight_set_id"], row["scenario_id"]), []).append(row)
    for (weight_set_id, _scenario_id), group_rows in groups.items():
        if weight_set_id == "weights:base":
            group_rows.sort(key=lambda row: (int(row["base_rank_within_scenario"]), row["candidate_site_id"]))
        else:
            group_rows.sort(key=lambda row: (-float(row["weighted_score"]), row["candidate_site_id"]))
        for rank, row in enumerate(group_rows, start=1):
            base_rank = int(row["base_rank_within_scenario"])
            row["rank_within_weight_set_scenario"] = rank
            row["rank_delta_vs_base"] = rank - base_rank if base_rank else ""
            row["stable_top10_flag"] = int(bool(base_rank) and base_rank <= 10 and rank <= 10)
            row["top_rank_band"] = rank_band(rank)


def rank_band(rank: int) -> str:
    if rank <= 10:
        return "Top 10"
    if rank <= 25:
        return "Top 25"
    return "Longlist"


def group_coverage_by_candidate_radius(rows: list[dict]) -> dict[tuple[str, str], list[dict]]:
    grouped: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        key = (row["candidate_site_id"], row["coverage_radius_km"])
        grouped.setdefault(key, []).append(row)
    return grouped


def covered_demand(rows: list[dict]) -> float:
    return sum(float(row.get("demand_weight_contribution") or 0) for row in rows if int(row.get("pair_eligible_flag") or 0) == 1)


def average_distance(rows: list[dict]) -> str:
    distances = [float(row["distance_km"]) for row in rows if int(row.get("pair_eligible_flag") or 0) == 1]
    if not distances:
        return ""
    return str(round(sum(distances) / len(distances), 3))


def action_bucket(covered_demand_weight: float, baseline_score: float) -> str:
    if covered_demand_weight <= 0:
        return "No current coverage signal"
    if baseline_score >= 0.75:
        return "Priority diligence shortlist"
    if baseline_score >= 0.45:
        return "Secondary diligence shortlist"
    return "Monitor as data improves"


def add_rank_within_scenario(rows: list[dict]) -> None:
    current_scenario = None
    rank = 0
    for row in rows:
        if row["scenario_id"] != current_scenario:
            current_scenario = row["scenario_id"]
            rank = 1
        else:
            rank += 1
        row["rank_within_scenario"] = rank


def clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def read_csv_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))
