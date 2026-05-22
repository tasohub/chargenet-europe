from __future__ import annotations

import csv
from pathlib import Path

from .paths import MART_DIR, ensure_project_dirs


BASELINE_METHOD_ID = "method:baseline-topk"
MCLP_METHOD_ID = "method:mclp-pulp-cbc"
MIN_COST_METHOD_ID = "method:min-cost-coverage-pulp"


def build_method_comparison_narrative_tile_smoke(
    *,
    optimization_path: Path | None = None,
    country_diagnostics_path: Path | None = None,
    output_path: Path | None = None,
) -> Path:
    ensure_project_dirs()
    optimization_rows = read_csv_rows(optimization_path or MART_DIR / "mart_optimization_results_tile_smoke.csv")
    country_rows = read_csv_rows(country_diagnostics_path or MART_DIR / "mart_optimization_country_diagnostics_tile_smoke.csv")
    target = output_path or MART_DIR / "mart_method_comparison_narrative_tile_smoke.csv"

    optimization_by_key = {(row.get("scenario_id", ""), row.get("method_id", "")): row for row in optimization_rows}
    country_by_key = dominant_country_by_scenario_method(country_rows)
    output_rows = []
    for scenario_id in sorted({row.get("scenario_id", "") for row in optimization_rows if row.get("scenario_id")}):
        baseline = optimization_by_key.get((scenario_id, BASELINE_METHOD_ID), {})
        mclp = optimization_by_key.get((scenario_id, MCLP_METHOD_ID), {})
        min_cost = optimization_by_key.get((scenario_id, MIN_COST_METHOD_ID), {})
        mclp_uplift = numeric(mclp.get("improvement_vs_baseline_pct"))
        min_cost_saving = numeric(min_cost.get("cost_saving_vs_baseline_pct"))
        dominant_country = country_by_key.get((scenario_id, MCLP_METHOD_ID), {})
        output_rows.append(
            {
                "scenario_id": scenario_id,
                "baseline_method_id": BASELINE_METHOD_ID,
                "best_coverage_method_id": MCLP_METHOD_ID if mclp else "",
                "lowest_cost_method_id": MIN_COST_METHOD_ID if min_cost else "",
                "baseline_covered_demand_weight": format_numeric(numeric(baseline.get("objective_covered_demand_weight"))),
                "mclp_covered_demand_weight": format_numeric(numeric(mclp.get("objective_covered_demand_weight"))),
                "min_cost_covered_demand_weight": format_numeric(numeric(min_cost.get("objective_covered_demand_weight"))),
                "mclp_coverage_uplift_pct": format_numeric(mclp_uplift),
                "min_cost_saving_pct": format_numeric(min_cost_saving),
                "baseline_selected_candidate_count": format_int(numeric(baseline.get("selected_candidate_count"))),
                "mclp_selected_candidate_count": format_int(numeric(mclp.get("selected_candidate_count"))),
                "min_cost_selected_candidate_count": format_int(numeric(min_cost.get("selected_candidate_count"))),
                "dominant_coverage_country_code": dominant_country.get("country_code", ""),
                "dominant_coverage_country_share": format_numeric(numeric(dominant_country.get("covered_demand_share_of_method"))),
                "comparison_readout": comparison_readout(mclp_uplift, min_cost_saving),
                "analyst_takeaway": analyst_takeaway(mclp_uplift, min_cost_saving),
                "allowed_use_note": "Method comparison narrative for interview explanation only; not a recommendation to select real sites.",
                "proxy_assumption_label": "tile_smoke_method_comparison_narrative_not_investment_grade",
            }
        )

    return write_csv(target, output_rows, METHOD_COMPARISON_FIELDNAMES)


def dominant_country_by_scenario_method(rows: list[dict]) -> dict[tuple[str, str], dict]:
    result: dict[tuple[str, str], dict] = {}
    for row in rows:
        key = (row.get("scenario_id", ""), row.get("method_id", ""))
        current = result.get(key)
        if current is None or numeric(row.get("covered_demand_share_of_method")) > numeric(current.get("covered_demand_share_of_method")):
            result[key] = row
    return result


def comparison_readout(mclp_uplift: float, min_cost_saving: float) -> str:
    if mclp_uplift > 0:
        return "mclp_expands_coverage"
    if min_cost_saving > 0:
        return "min_cost_reduces_proxy_cost"
    return "baseline_parity"


def analyst_takeaway(mclp_uplift: float, min_cost_saving: float) -> str:
    if mclp_uplift > 0 and min_cost_saving > 0:
        return "Use MCLP to explain coverage upside and min-cost to frame budget pressure under the public-proxy assumptions."
    if mclp_uplift > 0:
        return "Use MCLP as the coverage-upside case, then inspect zone trace and country diagnostics before narrowing candidates."
    if min_cost_saving > 0:
        return "Use min-cost as the budget-pressure case, then verify the coverage floor is acceptable for the business question."
    return "Baseline remains the simpler benchmark until stronger constraints or data justify optimization complexity."


def numeric(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def format_numeric(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")


def format_int(value: float) -> str:
    return str(int(round(value)))


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


METHOD_COMPARISON_FIELDNAMES = [
    "scenario_id",
    "baseline_method_id",
    "best_coverage_method_id",
    "lowest_cost_method_id",
    "baseline_covered_demand_weight",
    "mclp_covered_demand_weight",
    "min_cost_covered_demand_weight",
    "mclp_coverage_uplift_pct",
    "min_cost_saving_pct",
    "baseline_selected_candidate_count",
    "mclp_selected_candidate_count",
    "min_cost_selected_candidate_count",
    "dominant_coverage_country_code",
    "dominant_coverage_country_share",
    "comparison_readout",
    "analyst_takeaway",
    "allowed_use_note",
    "proxy_assumption_label",
]
