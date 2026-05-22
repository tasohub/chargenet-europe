from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
MART_DIR = ROOT / "data" / "chargenet" / "marts"
REPORT_DIR = ROOT / "reports" / "chargenet"
APP_DATA_DIR = ROOT / "app_data"


def require_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing required ChargeNet mart: {path}")
    return pd.read_csv(path)


def main() -> None:
    APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    optimization_results = require_csv(MART_DIR / "mart_optimization_results_tile_smoke.csv")
    optimization_sensitivity = require_csv(MART_DIR / "mart_optimization_sensitivity_tile_smoke.csv")
    optimization_diagnostics = require_csv(MART_DIR / "mart_optimization_constraint_diagnostics_tile_smoke.csv")
    selected_sites = require_csv(MART_DIR / "fact_optimization_selected_sites_tile_smoke.csv")
    zone_trace = require_csv(MART_DIR / "fact_optimization_zone_trace_tile_smoke.csv")
    country_diagnostics = require_csv(MART_DIR / "mart_optimization_country_diagnostics_tile_smoke.csv")
    method_comparison = require_csv(MART_DIR / "mart_method_comparison_narrative_tile_smoke.csv")
    lineage_trace = require_csv(MART_DIR / "mart_candidate_lineage_trace_tile_smoke.csv")
    business_scenarios = require_csv(MART_DIR / "mart_business_scenario_library_tile_smoke.csv")
    snapshot_metrics = require_csv(MART_DIR / "mart_pipeline_snapshot_metrics_tile_smoke.csv")
    snapshot_drift = require_csv(MART_DIR / "mart_pipeline_snapshot_drift_tile_smoke.csv")
    snapshot_certifications = require_csv(MART_DIR / "mart_pipeline_snapshot_certifications_tile_smoke.csv")
    release_gate = require_csv(REPORT_DIR / "release_gate_tile_smoke.csv")

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
    diagnostics_columns = [
        "scenario_method_id",
        "scenario_id",
        "method_id",
        "constraint_name",
        "constraint_status",
        "lhs_value",
        "operator",
        "rhs_value",
        "slack_value",
        "diagnostic_note",
        "allowed_use_note",
        "proxy_assumption_label",
    ]
    zone_trace_columns = [
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
        "allowed_use_note",
        "proxy_assumption_label",
    ]
    country_diagnostic_columns = [
        "scenario_method_country_id",
        "scenario_method_id",
        "scenario_id",
        "method_id",
        "country_code",
        "selected_candidate_count",
        "covered_zone_count",
        "covered_demand_weight",
        "covered_demand_share_of_method",
        "total_candidate_cost",
        "candidate_cost_share_of_method",
        "concentration_status",
        "concentration_warning_threshold",
        "concentration_review_note",
        "diagnostic_note",
        "allowed_use_note",
        "proxy_assumption_label",
    ]
    method_comparison_columns = [
        "scenario_id",
        "baseline_method_id",
        "best_coverage_method_id",
        "lowest_cost_method_id",
        "baseline_covered_demand_weight",
        "mclp_covered_demand_weight",
        "min_cost_covered_demand_weight",
        "mclp_coverage_uplift_pct",
        "min_cost_saving_pct",
        "dominant_coverage_country_code",
        "dominant_coverage_country_share",
        "comparison_readout",
        "analyst_takeaway",
        "allowed_use_note",
        "proxy_assumption_label",
    ]
    lineage_columns = [
        "trace_id",
        "scenario_id",
        "method_id",
        "selection_rank",
        "candidate_site_id",
        "source_record_id",
        "tile_run_id",
        "tile_job_id",
        "country_code",
        "nuts_id",
        "site_type",
        "brand",
        "operator",
        "name",
        "raw_tag_keys",
        "baseline_rank_within_scenario",
        "baseline_score",
        "covered_zone_count",
        "covered_demand_weight",
        "coverage_trace_zone_ids",
        "scenario_candidate_cost",
        "allowed_use_note",
        "proxy_assumption_label",
    ]
    business_scenario_columns = [
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
    snapshot_metric_columns = [
        "snapshot_id",
        "metric_name",
        "metric_value",
        "metric_unit",
        "source_table",
        "allowed_use_note",
        "proxy_assumption_label",
    ]
    snapshot_drift_columns = [
        "metric_name",
        "current_snapshot_id",
        "reference_snapshot_id",
        "current_metric_value",
        "reference_metric_value",
        "absolute_delta",
        "relative_delta_pct",
        "warning_threshold_pct",
        "fail_threshold_pct",
        "drift_status",
        "source_table",
        "allowed_use_note",
        "proxy_assumption_label",
    ]
    snapshot_certification_columns = [
        "reference_snapshot_id",
        "source_snapshot_id",
        "certification_status",
        "reviewer",
        "certification_note",
        "metric_count",
        "allowed_use_note",
        "proxy_assumption_label",
    ]
    release_gate_columns = [
        "gate_name",
        "gate_status",
        "evidence_path",
        "blocker_count",
        "detail",
    ]

    optimization_results[optimization_columns].to_csv(APP_DATA_DIR / "optimization_results_tile_smoke.csv", index=False)
    optimization_sensitivity[sensitivity_columns].to_csv(APP_DATA_DIR / "optimization_sensitivity_tile_smoke.csv", index=False)
    optimization_diagnostics[diagnostics_columns].to_csv(APP_DATA_DIR / "optimization_constraint_diagnostics_tile_smoke.csv", index=False)
    selected_sites[selected_columns].to_csv(APP_DATA_DIR / "optimization_selected_sites_tile_smoke.csv", index=False)
    zone_trace[zone_trace_columns].to_csv(APP_DATA_DIR / "optimization_zone_trace_tile_smoke.csv", index=False)
    country_diagnostics[country_diagnostic_columns].to_csv(APP_DATA_DIR / "optimization_country_diagnostics_tile_smoke.csv", index=False)
    method_comparison[method_comparison_columns].to_csv(APP_DATA_DIR / "method_comparison_narrative_tile_smoke.csv", index=False)
    lineage_trace[lineage_columns].to_csv(APP_DATA_DIR / "candidate_lineage_trace_tile_smoke.csv", index=False)
    business_scenarios[business_scenario_columns].to_csv(APP_DATA_DIR / "business_scenario_library_tile_smoke.csv", index=False)
    snapshot_metrics[snapshot_metric_columns].to_csv(APP_DATA_DIR / "pipeline_snapshot_metrics_tile_smoke.csv", index=False)
    snapshot_drift[snapshot_drift_columns].to_csv(APP_DATA_DIR / "pipeline_snapshot_drift_tile_smoke.csv", index=False)
    snapshot_certifications[snapshot_certification_columns].to_csv(APP_DATA_DIR / "pipeline_snapshot_certifications_tile_smoke.csv", index=False)
    release_gate[release_gate_columns].to_csv(APP_DATA_DIR / "release_gate_tile_smoke.csv", index=False)

    manifest = {
        "source": "generated_from_local_chargeNet_marts",
        "scope": "Belgium, Germany, France, Netherlands tile-smoke Phase 5 outputs",
        "not_investment_grade": True,
        "files": {
            "optimization_results_tile_smoke.csv": int(len(optimization_results)),
            "optimization_sensitivity_tile_smoke.csv": int(len(optimization_sensitivity)),
            "optimization_constraint_diagnostics_tile_smoke.csv": int(len(optimization_diagnostics)),
            "optimization_selected_sites_tile_smoke.csv": int(len(selected_sites)),
            "optimization_zone_trace_tile_smoke.csv": int(len(zone_trace)),
            "optimization_country_diagnostics_tile_smoke.csv": int(len(country_diagnostics)),
            "method_comparison_narrative_tile_smoke.csv": int(len(method_comparison)),
            "candidate_lineage_trace_tile_smoke.csv": int(len(lineage_trace)),
            "business_scenario_library_tile_smoke.csv": int(len(business_scenarios)),
            "pipeline_snapshot_metrics_tile_smoke.csv": int(len(snapshot_metrics)),
            "pipeline_snapshot_drift_tile_smoke.csv": int(len(snapshot_drift)),
            "pipeline_snapshot_certifications_tile_smoke.csv": int(len(snapshot_certifications)),
            "release_gate_tile_smoke.csv": int(len(release_gate)),
        },
        "schemas": {
            "optimization_results_tile_smoke.csv": optimization_columns,
            "optimization_sensitivity_tile_smoke.csv": sensitivity_columns,
            "optimization_constraint_diagnostics_tile_smoke.csv": diagnostics_columns,
            "optimization_selected_sites_tile_smoke.csv": selected_columns,
            "optimization_zone_trace_tile_smoke.csv": zone_trace_columns,
            "optimization_country_diagnostics_tile_smoke.csv": country_diagnostic_columns,
            "method_comparison_narrative_tile_smoke.csv": method_comparison_columns,
            "candidate_lineage_trace_tile_smoke.csv": lineage_columns,
            "business_scenario_library_tile_smoke.csv": business_scenario_columns,
            "pipeline_snapshot_metrics_tile_smoke.csv": snapshot_metric_columns,
            "pipeline_snapshot_drift_tile_smoke.csv": snapshot_drift_columns,
            "pipeline_snapshot_certifications_tile_smoke.csv": snapshot_certification_columns,
            "release_gate_tile_smoke.csv": release_gate_columns,
        },
    }
    (APP_DATA_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
