from __future__ import annotations

import csv
from pathlib import Path

from .paths import MART_DIR, ensure_project_dirs


BUSINESS_SCENARIOS = [
    {
        "business_scenario_id": "biz:max-coverage-base",
        "business_scenario_name": "Base radius max coverage",
        "business_question": "Where does the MILP place a small candidate set when the goal is maximum unique covered demand under the base radius?",
        "scenario_id": "scenario:radius-base",
        "method_id": "method:mclp-pulp-cbc",
        "primary_metric": "covered_demand_weight",
    },
    {
        "business_scenario_id": "biz:min-cost-base",
        "business_scenario_name": "Base radius cost floor",
        "business_question": "How much cost proxy can be avoided while preserving most of the baseline covered demand?",
        "scenario_id": "scenario:radius-base",
        "method_id": "method:min-cost-coverage-pulp",
        "primary_metric": "cost_saving_vs_baseline_pct",
    },
    {
        "business_scenario_id": "biz:conservative-coverage",
        "business_scenario_name": "Conservative radius coverage",
        "business_question": "What happens if a stricter service radius is used for a more cautious accessibility assumption?",
        "scenario_id": "scenario:radius-conservative",
        "method_id": "method:mclp-pulp-cbc",
        "primary_metric": "covered_demand_weight",
    },
    {
        "business_scenario_id": "biz:aggressive-coverage",
        "business_scenario_name": "Aggressive radius coverage",
        "business_question": "What upper-bound coverage signal appears under a wider service-radius assumption?",
        "scenario_id": "scenario:radius-aggressive",
        "method_id": "method:mclp-pulp-cbc",
        "primary_metric": "covered_demand_weight",
    },
    {
        "business_scenario_id": "biz:assumption-robustness-base",
        "business_scenario_name": "Base radius assumption robustness",
        "business_question": "How much does the selected solution change when the baseline shortlist is generated from different scoring weights?",
        "scenario_id": "scenario:radius-base",
        "method_id": "method:mclp-weighted-shortlist-pulp-cbc",
        "primary_metric": "min_solution_overlap_pct",
    },
]


def build_business_scenario_library_tile_smoke(
    *,
    optimization_path: Path | None = None,
    sensitivity_path: Path | None = None,
    output_path: Path | None = None,
) -> Path:
    ensure_project_dirs()
    optimization_rows = read_csv_rows(optimization_path or MART_DIR / "mart_optimization_results_tile_smoke.csv")
    sensitivity_rows = read_csv_rows(sensitivity_path or MART_DIR / "mart_optimization_sensitivity_tile_smoke.csv")
    target = output_path or MART_DIR / "mart_business_scenario_library_tile_smoke.csv"

    optimization_by_key = {(row["scenario_id"], row["method_id"]): row for row in optimization_rows}
    output_rows = []
    for definition in BUSINESS_SCENARIOS:
        if definition["primary_metric"] == "min_solution_overlap_pct":
            output_rows.append(sensitivity_scenario_row(definition, sensitivity_rows))
        else:
            output_rows.append(optimization_scenario_row(definition, optimization_by_key))

    return write_csv(target, output_rows, BUSINESS_SCENARIO_FIELDNAMES)


def optimization_scenario_row(definition: dict, optimization_by_key: dict[tuple[str, str], dict]) -> dict:
    source = optimization_by_key.get((definition["scenario_id"], definition["method_id"]), {})
    metric_value = numeric(source.get(metric_source_field(definition["primary_metric"])))
    decision = optimization_decision_readout(definition, source)
    return common_row(definition) | {
        "solver_status": source.get("solver_status", ""),
        "selected_candidate_count": source.get("selected_candidate_count", ""),
        "primary_metric_value": metric_value,
        "covered_demand_weight": source.get("objective_covered_demand_weight", ""),
        "total_candidate_cost": source.get("total_candidate_cost", ""),
        "comparison_value": source.get("improvement_vs_baseline_pct", ""),
        "comparison_label": "coverage_uplift_vs_baseline_pct",
        "solution_stability_signal": "",
        "decision_readout": decision["decision_readout"],
        "recommended_next_action": decision["recommended_next_action"],
    }


def sensitivity_scenario_row(definition: dict, sensitivity_rows: list[dict]) -> dict:
    rows = [row for row in sensitivity_rows if row.get("scenario_id") == definition["scenario_id"]]
    overlap_values = [numeric(row.get("overlap_with_base_solution_pct")) for row in rows]
    delta_values = [numeric(row.get("objective_delta_vs_base_weight_set_pct")) for row in rows]
    min_overlap = min(overlap_values) if overlap_values else 0.0
    max_abs_delta = max((abs(value) for value in delta_values), default=0.0)
    return common_row(definition) | {
        "solver_status": "evaluated" if rows else "",
        "selected_candidate_count": "",
        "primary_metric_value": round(min_overlap, 6),
        "covered_demand_weight": "",
        "total_candidate_cost": "",
        "comparison_value": round(max_abs_delta, 6),
        "comparison_label": "max_abs_objective_delta_pct",
        "solution_stability_signal": stability_signal(min_overlap),
        "decision_readout": "assumption_sensitive" if min_overlap < 0.75 else "assumption_stable",
        "recommended_next_action": sensitivity_next_action(min_overlap),
    }


def common_row(definition: dict) -> dict:
    return {
        "business_scenario_id": definition["business_scenario_id"],
        "business_scenario_name": definition["business_scenario_name"],
        "business_question": definition["business_question"],
        "scenario_id": definition["scenario_id"],
        "method_id": definition["method_id"],
        "primary_metric": definition["primary_metric"],
        "limitation_note": "Public proxy scenario for early diligence only; not investment-grade and not a build recommendation.",
        "allowed_use_note": "Use as a business framing layer on top of Phase 5 public-proxy optimization outputs.",
        "proxy_assumption_label": "tile_smoke_business_scenario_library_not_investment_grade",
    }


def metric_source_field(metric: str) -> str:
    fields = {
        "covered_demand_weight": "objective_covered_demand_weight",
        "cost_saving_vs_baseline_pct": "cost_saving_vs_baseline_pct",
    }
    return fields[metric]


def optimization_decision_readout(definition: dict, source: dict) -> dict:
    if definition["primary_metric"] == "cost_saving_vs_baseline_pct":
        saving = numeric(source.get("cost_saving_vs_baseline_pct"))
        return {
            "decision_readout": "cost_floor_saving" if saving > 0 else "cost_floor_tradeoff",
            "recommended_next_action": (
                "Use as a cost-pressure scenario and validate which coverage zones are lost before treating savings as attractive."
                if saving > 0
                else "Treat as a cost tradeoff scenario and inspect whether the coverage floor is too strict for the current proxy inputs."
            ),
        }
    uplift = numeric(source.get("improvement_vs_baseline_pct"))
    return {
        "decision_readout": "coverage_uplift" if uplift > 0 else "coverage_parity",
        "recommended_next_action": (
            "Inspect selected-site zone trace and country diagnostics to understand where the coverage uplift comes from."
            if uplift > 0
            else "Use the baseline shortlist as the simpler benchmark unless other constraints justify the optimization run."
        ),
    }


def sensitivity_next_action(min_overlap: float) -> str:
    if min_overlap < 0.4:
        return "Do not present a single robust shortlist; compare weight-set solutions side by side before narrowing candidates."
    if min_overlap < 0.75:
        return "Use the overlapping candidates as the robust core and flag non-overlap candidates for assumption review."
    return "Treat the selected candidates as relatively stable under the tested weight sets, still within public-proxy limits."


def stability_signal(min_overlap: float) -> str:
    if min_overlap >= 0.75:
        return "high_candidate_overlap"
    if min_overlap >= 0.4:
        return "moderate_candidate_overlap"
    return "low_candidate_overlap"


def numeric(value: object) -> float:
    try:
        return round(float(value or 0), 6)
    except (TypeError, ValueError):
        return 0.0


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


BUSINESS_SCENARIO_FIELDNAMES = [
    "business_scenario_id",
    "business_scenario_name",
    "business_question",
    "scenario_id",
    "method_id",
    "solver_status",
    "selected_candidate_count",
    "primary_metric",
    "primary_metric_value",
    "covered_demand_weight",
    "total_candidate_cost",
    "comparison_label",
    "comparison_value",
    "solution_stability_signal",
    "decision_readout",
    "recommended_next_action",
    "limitation_note",
    "allowed_use_note",
    "proxy_assumption_label",
]
