from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
MART_DIR = ROOT / "data" / "chargenet" / "marts"
APP_DATA_DIR = ROOT / "app_data"


def require_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing required ChargeNet mart: {path}")
    return pd.read_csv(path)


def main() -> None:
    APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    optimization_results = require_csv(MART_DIR / "mart_optimization_results_tile_smoke.csv")
    optimization_sensitivity = require_csv(MART_DIR / "mart_optimization_sensitivity_tile_smoke.csv")
    selected_sites = require_csv(MART_DIR / "fact_optimization_selected_sites_tile_smoke.csv")

    optimization_columns = [
        "scenario_method_id",
        "scenario_id",
        "method_id",
        "objective_type",
        "solver_status",
        "selected_candidate_count",
        "objective_covered_demand_weight",
        "coverage_floor_demand_weight",
        "covered_zone_count",
        "total_candidate_cost",
        "budget",
        "k",
        "candidate_pool_count",
        "improvement_vs_baseline_demand_weight",
        "improvement_vs_baseline_pct",
        "cost_saving_vs_baseline",
        "cost_saving_vs_baseline_pct",
        "solver_note",
        "allowed_use_note",
        "proxy_assumption_label",
    ]
    sensitivity_columns = [
        "sensitivity_run_id",
        "scenario_id",
        "weight_set_id",
        "weight_set_name",
        "method_id",
        "solver_status",
        "shortlist_size",
        "candidate_pool_count",
        "selected_candidate_count",
        "objective_covered_demand_weight",
        "base_weight_set_objective",
        "objective_delta_vs_base_weight_set",
        "objective_delta_vs_base_weight_set_pct",
        "overlap_with_base_solution_count",
        "overlap_with_base_solution_pct",
        "covered_zone_count",
        "total_candidate_cost",
        "budget",
        "k",
        "allowed_use_note",
        "proxy_assumption_label",
    ]
    selected_columns = [
        "scenario_method_id",
        "scenario_id",
        "method_id",
        "selection_rank",
        "candidate_site_id",
        "country_code",
        "nuts_id",
        "site_type",
        "baseline_rank_within_scenario",
        "baseline_score",
        "c_j",
        "allowed_use_note",
        "proxy_assumption_label",
    ]

    optimization_results[optimization_columns].to_csv(APP_DATA_DIR / "optimization_results_tile_smoke.csv", index=False)
    optimization_sensitivity[sensitivity_columns].to_csv(APP_DATA_DIR / "optimization_sensitivity_tile_smoke.csv", index=False)
    selected_sites[selected_columns].to_csv(APP_DATA_DIR / "optimization_selected_sites_tile_smoke.csv", index=False)

    manifest = {
        "source": "generated_from_local_chargeNet_marts",
        "scope": "Belgium, Germany, France, Netherlands tile-smoke Phase 5 outputs",
        "not_investment_grade": True,
        "files": {
            "optimization_results_tile_smoke.csv": int(len(optimization_results)),
            "optimization_sensitivity_tile_smoke.csv": int(len(optimization_sensitivity)),
            "optimization_selected_sites_tile_smoke.csv": int(len(selected_sites)),
        },
    }
    (APP_DATA_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
