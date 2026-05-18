from __future__ import annotations

import csv
from pathlib import Path

from .paths import CLEAN_DIR, MART_DIR, ensure_project_dirs


FIELDNAMES = [
    "schema_version",
    "layer",
    "table_name",
    "column_name",
    "data_type",
    "nullable",
    "is_primary_key",
    "foreign_key_table",
    "foreign_key_column",
    "grain",
    "business_definition",
    "source_name",
    "source_field",
    "transformation_rule",
    "classification",
    "allowed_use_note",
    "quality_rule_id",
    "powerbi_export_flag",
    "license_key",
]

TABLES = [
    ("clean", "clean_existing_chargers", CLEAN_DIR / "clean_existing_chargers_sample.csv", "charger_source_id"),
    ("clean", "clean_existing_chargers_tile_smoke", CLEAN_DIR / "clean_existing_chargers_tile_smoke.csv", "charger_source_id"),
    ("clean", "clean_candidate_sites", CLEAN_DIR / "clean_candidate_sites_sample.csv", "candidate_site_id"),
    ("clean", "clean_candidate_sites_tile_smoke", CLEAN_DIR / "clean_candidate_sites_tile_smoke.csv", "candidate_site_id"),
    ("clean", "clean_demand_zones", CLEAN_DIR / "clean_demand_zones_sample.csv", "demand_zone_id"),
    ("clean", "clean_demand_zones_nuts3_pilot", CLEAN_DIR / "clean_demand_zones_nuts3_pilot.csv", "demand_zone_id"),
    ("mart", "fact_candidate_zone_coverage", MART_DIR / "fact_candidate_zone_coverage_sample.csv", ""),
    ("mart", "fact_candidate_zone_coverage_tile_smoke", MART_DIR / "fact_candidate_zone_coverage_tile_smoke.csv", ""),
    ("mart", "fact_scenario_inputs", MART_DIR / "fact_scenario_inputs_sample.csv", ""),
    ("mart", "fact_scenario_inputs_tile_smoke", MART_DIR / "fact_scenario_inputs_tile_smoke.csv", ""),
    ("mart", "mart_candidate_baseline_scores_tile_smoke", MART_DIR / "mart_candidate_baseline_scores_tile_smoke.csv", ""),
    ("mart", "mart_baseline_sensitivity_tile_smoke", MART_DIR / "mart_baseline_sensitivity_tile_smoke.csv", ""),
    ("mart", "mart_optimization_results_tile_smoke", MART_DIR / "mart_optimization_results_tile_smoke.csv", ""),
    ("mart", "fact_optimization_selected_sites_tile_smoke", MART_DIR / "fact_optimization_selected_sites_tile_smoke.csv", ""),
    ("mart", "mart_optimization_constraint_diagnostics_tile_smoke", MART_DIR / "mart_optimization_constraint_diagnostics_tile_smoke.csv", ""),
]

FIELD_OVERRIDES = {
    "candidate_site_id": ("derived_proxy", "Deterministic candidate ID; does not imply site feasibility.", "osm_overpass"),
    "candidate_proxy_flag": ("derived_proxy", "Candidate is a public POI proxy, not a validated feasible charging site.", "osm_overpass"),
    "candidate_feasibility_note": ("caveat_only", "Due-diligence caveat for land, permit, grid, and commercial feasibility.", "derived_or_assumption"),
    "demand_weight": ("derived_proxy", "Demand proxy from population, not observed charging-session demand.", "eurostat_population"),
    "base_demand_weight": ("derived_proxy", "Base demand proxy from population.", "eurostat_population"),
    "d_i": ("derived_proxy", "MILP demand weight; population-based proxy, not observed charging demand.", "eurostat_population"),
    "c_j": ("assumption", "Candidate CAPEX assumption for scenario testing, not observed site CAPEX.", "derived_or_assumption"),
    "b": ("assumption", "Scenario budget assumption.", "derived_or_assumption"),
    "k": ("assumption", "Scenario site-count assumption.", "derived_or_assumption"),
    "r_j": ("derived_proxy", "Risk proxy for scenario penalty testing.", "derived_or_assumption"),
    "rho": ("assumption", "Risk penalty weight assumption.", "derived_or_assumption"),
    "baseline_score": ("derived_proxy", "Weighted baseline score for diligence prioritization, not a site rollout recommendation.", "derived_or_assumption"),
    "rank_within_scenario": ("derived_proxy", "Rank within radius scenario for diligence prioritization only.", "derived_or_assumption"),
    "action_bucket": ("derived_proxy", "Diligence-prioritization bucket; not an investment or build recommendation.", "derived_or_assumption"),
    "covered_demand_weight": ("derived_proxy", "Population-weighted covered demand under a radius scenario.", "eurostat_population"),
    "covered_zone_count": ("derived_proxy", "Count of demand zones covered under a radius scenario.", "derived_or_assumption"),
    "coverage_component": ("derived_proxy", "Normalized coverage contribution to baseline score.", "derived_or_assumption"),
    "data_quality_component": ("derived_proxy", "OSM tag quality contribution to baseline score.", "osm_overpass"),
    "risk_component": ("derived_proxy", "Inverse rollout risk contribution to baseline score.", "derived_or_assumption"),
    "competition_component": ("derived_proxy", "Inverse competition proxy contribution to baseline score.", "derived_or_assumption"),
    "weight_set_id": ("assumption", "Sensitivity weight-set identifier for baseline robustness testing.", "derived_or_assumption"),
    "weight_set_name": ("assumption", "Human-readable sensitivity weight-set name.", "derived_or_assumption"),
    "coverage_weight": ("assumption", "Sensitivity weight applied to the coverage component.", "derived_or_assumption"),
    "data_quality_weight": ("assumption", "Sensitivity weight applied to the data quality component.", "derived_or_assumption"),
    "risk_weight": ("assumption", "Sensitivity weight applied to the risk component.", "derived_or_assumption"),
    "competition_weight": ("assumption", "Sensitivity weight applied to the competition component.", "derived_or_assumption"),
    "weighted_score": ("derived_proxy", "Sensitivity score for diligence prioritization under one weight set.", "derived_or_assumption"),
    "base_rank_within_scenario": ("derived_proxy", "Original baseline rank used as sensitivity comparison anchor.", "derived_or_assumption"),
    "rank_within_weight_set_scenario": ("derived_proxy", "Candidate rank within one scenario and sensitivity weight set.", "derived_or_assumption"),
    "rank_delta_vs_base": ("derived_proxy", "Rank movement versus the base baseline rank.", "derived_or_assumption"),
    "stable_top10_flag": ("derived_proxy", "Flags candidates that stay in the top 10 under the tested weight set.", "derived_or_assumption"),
    "top_rank_band": ("derived_proxy", "Rank band used for BI filtering and portfolio explanation.", "derived_or_assumption"),
    "scenario_method_id": ("derived_proxy", "Composite key joining a scenario to one optimization or benchmark method.", "derived_or_assumption"),
    "method_id": ("assumption", "Optimization or benchmark method identifier.", "derived_or_assumption"),
    "solver_status": ("derived_proxy", "Solver or benchmark status for the optimization checkpoint.", "derived_or_assumption"),
    "selected_candidate_count": ("derived_proxy", "Number of candidate proxies selected by the method.", "derived_or_assumption"),
    "selected_candidate_ids": ("derived_proxy", "Pipe-delimited selected candidate IDs for summary display.", "derived_or_assumption"),
    "objective_covered_demand_weight": ("derived_proxy", "Unique population-weighted demand covered by selected candidates.", "eurostat_population"),
    "total_candidate_cost": ("assumption", "Total assumed candidate cost under the scenario.", "derived_or_assumption"),
    "budget": ("assumption", "Scenario budget assumption.", "derived_or_assumption"),
    "candidate_pool_count": ("derived_proxy", "Number of candidate proxies considered by the method.", "derived_or_assumption"),
    "improvement_vs_baseline_demand_weight": ("derived_proxy", "Covered-demand difference versus baseline top-k benchmark.", "derived_or_assumption"),
    "improvement_vs_baseline_pct": ("derived_proxy", "Covered-demand percentage difference versus baseline top-k benchmark.", "derived_or_assumption"),
    "solver_note": ("caveat_only", "Method caveat and solver-scope explanation.", "derived_or_assumption"),
    "constraint_name": ("derived_proxy", "Optimization constraint or diagnostic check name.", "derived_or_assumption"),
    "constraint_status": ("derived_proxy", "Pass/fail status for an optimization constraint diagnostic.", "derived_or_assumption"),
    "lhs_value": ("derived_proxy", "Observed left-hand-side value for the diagnostic constraint.", "derived_or_assumption"),
    "operator": ("assumption", "Constraint comparison operator used for diagnostic display.", "derived_or_assumption"),
    "rhs_value": ("assumption", "Right-hand-side threshold or accepted status set for the diagnostic constraint.", "derived_or_assumption"),
    "slack_value": ("derived_proxy", "Constraint slack where numeric; positive means within the tested limit.", "derived_or_assumption"),
    "diagnostic_note": ("caveat_only", "Plain-language interpretation of the optimization constraint diagnostic.", "derived_or_assumption"),
    "selection_rank": ("derived_proxy", "Display rank for selected candidates within method and scenario.", "derived_or_assumption"),
    "baseline_rank_within_scenario": ("derived_proxy", "Baseline rank of the selected candidate for comparison.", "derived_or_assumption"),
    "service_radius_km": ("assumption", "Coverage radius assumption shared by baseline and MILP.", "derived_or_assumption"),
    "coverage_radius_km": ("assumption", "Coverage radius assumption used to compute a_ij.", "derived_or_assumption"),
    "distance_km": ("derived_proxy", "Haversine WGS84 straight-line distance, not road travel time.", "derived_or_assumption"),
    "a_ij": ("derived_proxy", "MILP coverage flag derived from distance and radius.", "derived_or_assumption"),
    "pair_eligible_flag": ("derived_proxy", "Candidate-zone pair eligibility based on radius and scenario rules.", "derived_or_assumption"),
    "estimated_capex_class": ("assumption", "CAPEX class assumption until finance model is built.", "derived_or_assumption"),
    "rollout_risk_score": ("derived_proxy", "Rollout risk proxy, not validated execution feasibility.", "derived_or_assumption"),
    "competition_score": ("derived_proxy", "Competition proxy from nearby public supply, not market share.", "derived_or_assumption"),
    "baseline_nearest_charger_distance_km": ("derived_proxy", "Access gap proxy based on observed public chargers.", "osm_overpass"),
    "baseline_charger_count_within_radius": ("derived_proxy", "Access gap proxy based on observed public chargers.", "osm_overpass"),
    "underserved_zone_flag": ("derived_proxy", "Access-gap flag; not socioeconomic fairness claim.", "derived_or_assumption"),
    "proxy_assumption_label": ("caveat_only", "Machine-readable caveat label for downstream outputs.", "derived_or_assumption"),
    "raw_tags_json": ("observed", "Raw OSM tag JSON retained for traceability; avoid Power BI CSV export.", "osm_overpass"),
    "centroid_method": ("derived_proxy", "Centroid method label; bbox midpoint is a proxy for planning only.", "gisco_nuts"),
    "population_missing_flag": ("derived_proxy", "Signals that Eurostat population has not yet been joined.", "eurostat_population"),
    "tile_run_id": ("lineage", "Immutable OSM tile smoke run identifier.", "osm_overpass"),
    "tile_job_id": ("lineage", "OSM tile-plan job identifier used for smoke-run lineage.", "osm_overpass"),
}


def write_data_dictionary(path: Path | None = None) -> Path:
    ensure_project_dirs()
    target = path or MART_DIR / "data_dictionary_sample.csv"
    rows = []
    for layer, table_name, table_path, primary_key in TABLES:
        if not table_path.exists():
            continue
        for column in read_header(table_path):
            rows.append(dictionary_row(layer, table_name, column, primary_key))
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    return target


def dictionary_row(layer: str, table_name: str, column: str, primary_key: str) -> dict:
    classification, allowed_use_note, license_key = classify_field(column)
    return {
        "schema_version": "phase3_sample_v1",
        "layer": layer,
        "table_name": table_name,
        "column_name": column,
        "data_type": infer_data_type(column),
        "nullable": "false" if column == primary_key or column.endswith("_id") else "true",
        "is_primary_key": str(column == primary_key).lower(),
        "foreign_key_table": infer_fk_table(column, table_name),
        "foreign_key_column": column if column.endswith("_id") else "",
        "grain": infer_grain(table_name),
        "business_definition": business_definition(column),
        "source_name": source_name_for_license(license_key),
        "source_field": infer_source_field(column),
        "transformation_rule": infer_transformation_rule(column),
        "classification": classification,
        "allowed_use_note": allowed_use_note,
        "quality_rule_id": "proxy_label_required" if classification in {"derived_proxy", "assumption", "caveat_only"} else "source_trace_required",
        "powerbi_export_flag": "false" if column.endswith("_json") else "true",
        "license_key": license_key,
    }


def classify_field(column: str) -> tuple[str, str, str]:
    if column in FIELD_OVERRIDES:
        return FIELD_OVERRIDES[column]
    if column in {"lat", "lon", "centroid_lat", "centroid_lon", "bbox_min_lat", "bbox_min_lon", "bbox_max_lat", "bbox_max_lon", "population"}:
        return ("observed", "Public source field; retain source and version metadata.", "eurostat_population" if column == "population" else "gisco_nuts")
    if column.endswith("_score") or column.endswith("_flag"):
        return ("derived_proxy", "Derived indicator for decision support, not a direct real-world fact.", "derived_or_assumption")
    if column.endswith("_version"):
        return ("assumption", "Version label used to freeze scenario inputs.", "derived_or_assumption")
    return ("observed", "Use with source caveats and attribution.", "derived_or_assumption")


def infer_data_type(column: str) -> str:
    if column.endswith("_flag") or column in {"k", "population", "base_demand_weight", "demand_weight", "d_i", "c_j", "b"}:
        return "number"
    if column.endswith("_km") or column.endswith("_score") or column in {"r_j", "rho", "lat", "lon", "centroid_lat", "centroid_lon", "bbox_min_lat", "bbox_min_lon", "bbox_max_lat", "bbox_max_lon"}:
        return "number"
    return "text"


def infer_fk_table(column: str, table_name: str) -> str:
    if column == "candidate_site_id" and table_name != "clean_candidate_sites":
        return "clean_candidate_sites"
    if column == "demand_zone_id" and table_name != "clean_demand_zones":
        return "clean_demand_zones"
    if column == "scenario_id":
        return "dim_scenario"
    return ""


def infer_grain(table_name: str) -> str:
    grains = {
        "clean_existing_chargers": "one cleaned charger object per row",
        "clean_candidate_sites": "one candidate POI proxy per row",
        "clean_demand_zones": "one demand zone per row",
        "clean_demand_zones_nuts3_pilot": "one NUTS3 pilot demand zone per row",
        "fact_candidate_zone_coverage": "one candidate-zone-radius row",
        "fact_candidate_zone_coverage_tile_smoke": "one smoke-candidate-zone-radius row",
        "fact_scenario_inputs": "one scenario-entity input row",
        "fact_scenario_inputs_tile_smoke": "one smoke scenario-entity input row",
        "mart_candidate_baseline_scores_tile_smoke": "one smoke candidate score per radius scenario",
        "mart_baseline_sensitivity_tile_smoke": "one smoke candidate sensitivity score per weight set and radius scenario",
        "mart_optimization_results_tile_smoke": "one smoke optimization summary row per scenario and method",
        "fact_optimization_selected_sites_tile_smoke": "one selected smoke candidate row per scenario and method",
        "mart_optimization_constraint_diagnostics_tile_smoke": "one optimization constraint diagnostic per scenario, method, and constraint",
    }
    return grains.get(table_name, "sample")


def business_definition(column: str) -> str:
    return column.replace("_", " ")


def source_name_for_license(license_key: str) -> str:
    names = {
        "osm_overpass": "OpenStreetMap / Overpass",
        "eurostat_population": "Eurostat regional population API",
        "gisco_nuts": "Eurostat/GISCO NUTS 2024",
        "derived_or_assumption": "Derived or scenario assumption",
    }
    return names.get(license_key, license_key)


def infer_source_field(column: str) -> str:
    if column == "raw_tags_json":
        return "OSM tags"
    if column in {"lat", "lon"}:
        return "OSM coordinate"
    if column == "population":
        return "Eurostat population value"
    if column.startswith("bbox_") or column.startswith("centroid_"):
        return "GISCO NUTS geometry"
    return ""


def infer_transformation_rule(column: str) -> str:
    rules = {
        "candidate_site_id": "candidate:osm:{type}:{id}",
        "demand_zone_id": "dz:nuts2024:{NUTS_ID}",
        "a_ij": "1 when distance_km <= coverage_radius_km, else 0",
        "distance_km": "haversine_wgs84_v1",
    }
    return rules.get(column, "")


def read_header(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        return next(reader)
