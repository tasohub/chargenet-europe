from __future__ import annotations

import csv
import json
from pathlib import Path

from .paths import CLEAN_DIR, MART_DIR, ensure_project_dirs


DEFAULT_TRACE_SCENARIO_ID = "scenario:radius-base"
DEFAULT_TRACE_METHOD_ID = "method:mclp-pulp-cbc"
DEFAULT_TRACE_CANDIDATE_LIMIT = 10


def build_candidate_lineage_trace_tile_smoke(
    *,
    clean_candidate_path: Path | None = None,
    baseline_path: Path | None = None,
    coverage_path: Path | None = None,
    scenario_path: Path | None = None,
    selected_path: Path | None = None,
    output_path: Path | None = None,
    scenario_id: str = DEFAULT_TRACE_SCENARIO_ID,
    method_id: str = DEFAULT_TRACE_METHOD_ID,
    candidate_limit: int = DEFAULT_TRACE_CANDIDATE_LIMIT,
) -> Path:
    ensure_project_dirs()
    clean_rows = read_csv_rows(clean_candidate_path or CLEAN_DIR / "clean_candidate_sites_tile_smoke.csv")
    baseline_rows = read_csv_rows(baseline_path or MART_DIR / "mart_candidate_baseline_scores_tile_smoke.csv")
    coverage_rows = read_csv_rows(coverage_path or MART_DIR / "fact_candidate_zone_coverage_tile_smoke.csv")
    scenario_rows = read_csv_rows(scenario_path or MART_DIR / "fact_scenario_inputs_tile_smoke.csv")
    selected_rows = read_csv_rows(selected_path or MART_DIR / "fact_optimization_selected_sites_tile_smoke.csv")
    target = output_path or MART_DIR / "mart_candidate_lineage_trace_tile_smoke.csv"

    clean_by_candidate = {row["candidate_site_id"]: row for row in clean_rows}
    baseline_by_key = {(row["scenario_id"], row["candidate_site_id"]): row for row in baseline_rows}
    scenario_costs = {
        (row["scenario_id"], row["entity_id"]): row
        for row in scenario_rows
        if row.get("entity_type") == "candidate_site"
    }
    selected = [
        row
        for row in selected_rows
        if row.get("scenario_id") == scenario_id and row.get("method_id") == method_id
    ]
    selected.sort(key=lambda row: int(float(row.get("selection_rank") or 0)))
    selected = selected[:candidate_limit]

    output_rows = []
    for selected_row in selected:
        candidate_id = selected_row["candidate_site_id"]
        clean = clean_by_candidate.get(candidate_id, {})
        baseline = baseline_by_key.get((scenario_id, candidate_id), {})
        scenario = scenario_costs.get((scenario_id, candidate_id), {})
        radius = str(baseline.get("coverage_radius_km") or scenario.get("service_radius_km") or "")
        coverage_summary = summarize_candidate_coverage(coverage_rows, candidate_id, radius)
        output_rows.append(
            {
                "trace_id": f"{scenario_id}|{method_id}|{candidate_id}",
                "scenario_id": scenario_id,
                "method_id": method_id,
                "selection_rank": selected_row.get("selection_rank", ""),
                "candidate_site_id": candidate_id,
                "source_record_id": clean.get("source_record_id", ""),
                "tile_run_id": clean.get("tile_run_id", ""),
                "tile_job_id": clean.get("tile_job_id", ""),
                "candidate_source": clean.get("candidate_source", ""),
                "country_code": clean.get("country_code", selected_row.get("country_code", "")),
                "nuts_id": clean.get("nuts_id", selected_row.get("nuts_id", "")),
                "lat": clean.get("lat", ""),
                "lon": clean.get("lon", ""),
                "site_type": clean.get("site_type", selected_row.get("site_type", "")),
                "brand": clean.get("brand", ""),
                "operator": clean.get("operator", ""),
                "name": clean.get("name", ""),
                "raw_tag_keys": raw_tag_keys(clean.get("raw_tags_json", "")),
                "baseline_rank_within_scenario": baseline.get("rank_within_scenario", selected_row.get("baseline_rank_within_scenario", "")),
                "baseline_score": baseline.get("baseline_score", selected_row.get("baseline_score", "")),
                "coverage_component": baseline.get("coverage_component", ""),
                "data_quality_component": baseline.get("data_quality_component", ""),
                "risk_component": baseline.get("risk_component", ""),
                "competition_component": baseline.get("competition_component", ""),
                "action_bucket": baseline.get("action_bucket", ""),
                "coverage_radius_km": radius,
                "covered_zone_count": coverage_summary["covered_zone_count"],
                "covered_demand_weight": coverage_summary["covered_demand_weight"],
                "coverage_trace_zone_ids": coverage_summary["coverage_trace_zone_ids"],
                "avg_distance_covered_km": coverage_summary["avg_distance_covered_km"],
                "scenario_candidate_cost": scenario.get("c_j", selected_row.get("c_j", "")),
                "scenario_budget": scenario.get("b", ""),
                "scenario_k": scenario.get("k", ""),
                "allowed_use_note": "Candidate lineage trace for audit and portfolio explanation only; not investment advice or a site feasibility claim.",
                "proxy_assumption_label": "tile_smoke_candidate_lineage_trace_not_investment_grade",
            }
        )

    return write_csv(target, output_rows, LINEAGE_FIELDNAMES)


def build_optimization_zone_trace_tile_smoke(
    *,
    selected_path: Path | None = None,
    coverage_path: Path | None = None,
    scenario_path: Path | None = None,
    output_path: Path | None = None,
) -> Path:
    ensure_project_dirs()
    selected_rows = read_csv_rows(selected_path or MART_DIR / "fact_optimization_selected_sites_tile_smoke.csv")
    coverage_rows = read_csv_rows(coverage_path or MART_DIR / "fact_candidate_zone_coverage_tile_smoke.csv")
    scenario_rows = read_csv_rows(scenario_path or MART_DIR / "fact_scenario_inputs_tile_smoke.csv")
    target = output_path or MART_DIR / "fact_optimization_zone_trace_tile_smoke.csv"

    scenario_radius = scenario_radius_map(scenario_rows)
    coverage_by_candidate_radius = group_eligible_coverage_by_candidate_radius(coverage_rows)
    output_rows = []
    for selected in sorted(
        selected_rows,
        key=lambda row: (
            row.get("scenario_id", ""),
            row.get("method_id", ""),
            int(float(row.get("selection_rank") or 0)),
            row.get("candidate_site_id", ""),
        ),
    ):
        candidate_id = selected.get("candidate_site_id", "")
        radius = scenario_radius.get(selected.get("scenario_id", ""), "")
        candidate_coverage = coverage_by_candidate_radius.get((candidate_id, radius), [])
        total_candidate_demand = sum(float(row.get("demand_weight_contribution") or 0) for row in candidate_coverage)
        for zone_rank, coverage in enumerate(candidate_coverage, start=1):
            demand_weight = float(coverage.get("demand_weight_contribution") or 0)
            output_rows.append(
                {
                    "zone_trace_id": "|".join(
                        [
                            selected.get("scenario_id", ""),
                            selected.get("method_id", ""),
                            candidate_id,
                            coverage.get("demand_zone_id", ""),
                        ]
                    ),
                    "scenario_method_id": selected.get("scenario_method_id", ""),
                    "scenario_id": selected.get("scenario_id", ""),
                    "method_id": selected.get("method_id", ""),
                    "selection_rank": selected.get("selection_rank", ""),
                    "candidate_site_id": candidate_id,
                    "demand_zone_id": coverage.get("demand_zone_id", ""),
                    "zone_coverage_rank": zone_rank,
                    "coverage_radius_km": coverage.get("coverage_radius_km", ""),
                    "distance_km": coverage.get("distance_km", ""),
                    "zone_demand_weight": format_numeric(demand_weight),
                    "zone_demand_share_of_candidate": format_numeric(demand_weight / total_candidate_demand if total_candidate_demand else 0.0),
                    "distance_method_version": coverage.get("distance_method_version", ""),
                    "allowed_use_note": "Selected-site zone trace for audit and portfolio explanation only; not investment advice or a site feasibility claim.",
                    "proxy_assumption_label": "tile_smoke_optimization_zone_trace_not_investment_grade",
                }
            )

    return write_csv(target, output_rows, ZONE_TRACE_FIELDNAMES)


def group_eligible_coverage_by_candidate(rows: list[dict]) -> dict[str, list[dict]]:
    return {
        candidate_id: candidate_rows
        for (candidate_id, _radius), candidate_rows in group_eligible_coverage_by_candidate_radius(rows).items()
    }


def group_eligible_coverage_by_candidate_radius(rows: list[dict]) -> dict[tuple[str, str], list[dict]]:
    grouped: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        if int(float(row.get("pair_eligible_flag") or 0)) != 1:
            continue
        grouped.setdefault((row.get("candidate_site_id", ""), str(row.get("coverage_radius_km", ""))), []).append(row)
    for candidate_rows in grouped.values():
        candidate_rows.sort(
            key=lambda row: (
                -float(row.get("demand_weight_contribution") or 0),
                float(row.get("distance_km") or 999999),
                row.get("demand_zone_id", ""),
            )
        )
    return grouped


def scenario_radius_map(rows: list[dict]) -> dict[str, str]:
    radii = {}
    for row in rows:
        scenario_id = row.get("scenario_id", "")
        radius = str(row.get("service_radius_km", ""))
        if scenario_id and radius:
            radii.setdefault(scenario_id, radius)
    return radii


def summarize_candidate_coverage(rows: list[dict], candidate_id: str, radius: str, top_n: int = 5) -> dict:
    eligible_rows = [
        row
        for row in rows
        if row.get("candidate_site_id") == candidate_id
        and str(row.get("coverage_radius_km")) == str(radius)
        and int(float(row.get("pair_eligible_flag") or 0)) == 1
    ]
    eligible_rows.sort(
        key=lambda row: (
            -float(row.get("demand_weight_contribution") or 0),
            float(row.get("distance_km") or 999999),
            row.get("demand_zone_id", ""),
        )
    )
    total_demand = sum(float(row.get("demand_weight_contribution") or 0) for row in eligible_rows)
    avg_distance = (
        sum(float(row.get("distance_km") or 0) for row in eligible_rows) / len(eligible_rows)
        if eligible_rows
        else 0.0
    )
    return {
        "covered_zone_count": len(eligible_rows),
        "covered_demand_weight": round(total_demand, 3),
        "coverage_trace_zone_ids": "|".join(row.get("demand_zone_id", "") for row in eligible_rows[:top_n]),
        "avg_distance_covered_km": round(avg_distance, 3),
    }


def raw_tag_keys(raw_tags_json: str) -> str:
    if not raw_tags_json:
        return ""
    try:
        payload = json.loads(raw_tags_json)
    except json.JSONDecodeError:
        return ""
    if not isinstance(payload, dict):
        return ""
    return "|".join(sorted(str(key) for key in payload.keys()))


def format_numeric(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")


def read_csv_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> Path:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


LINEAGE_FIELDNAMES = [
    "trace_id",
    "scenario_id",
    "method_id",
    "selection_rank",
    "candidate_site_id",
    "source_record_id",
    "tile_run_id",
    "tile_job_id",
    "candidate_source",
    "country_code",
    "nuts_id",
    "lat",
    "lon",
    "site_type",
    "brand",
    "operator",
    "name",
    "raw_tag_keys",
    "baseline_rank_within_scenario",
    "baseline_score",
    "coverage_component",
    "data_quality_component",
    "risk_component",
    "competition_component",
    "action_bucket",
    "coverage_radius_km",
    "covered_zone_count",
    "covered_demand_weight",
    "coverage_trace_zone_ids",
    "avg_distance_covered_km",
    "scenario_candidate_cost",
    "scenario_budget",
    "scenario_k",
    "allowed_use_note",
    "proxy_assumption_label",
]

ZONE_TRACE_FIELDNAMES = [
    "zone_trace_id",
    "scenario_method_id",
    "scenario_id",
    "method_id",
    "selection_rank",
    "candidate_site_id",
    "demand_zone_id",
    "zone_coverage_rank",
    "coverage_radius_km",
    "distance_km",
    "zone_demand_weight",
    "zone_demand_share_of_candidate",
    "distance_method_version",
    "allowed_use_note",
    "proxy_assumption_label",
]
