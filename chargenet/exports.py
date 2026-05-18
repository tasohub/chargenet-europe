from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from .paths import CLEAN_DIR, CONFIG_DIR, MART_DIR, REPORT_DIR, ensure_project_dirs


POWERBI_EXPORT_DIR = REPORT_DIR / "powerbi_exports"


def write_powerbi_exports(output_dir: Path | None = None) -> list[Path]:
    ensure_project_dirs()
    target_dir = output_dir or POWERBI_EXPORT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    demand_source = CLEAN_DIR / "clean_demand_zones_nuts3_pilot.csv"
    if not demand_source.exists():
        demand_source = CLEAN_DIR / "clean_demand_zones_sample.csv"

    outputs = [
        write_projected_csv(
            demand_source,
            target_dir / "dim_demand_zone.csv",
            [
                "demand_zone_id",
                "nuts_id",
                "nuts_version",
                "country_code",
                "zone_name",
                "population",
                "population_year",
                "demand_weight",
                "base_demand_weight",
                "centroid_lat",
                "centroid_lon",
                "demand_confidence_score",
                "proxy_assumption_label",
            ],
        ),
        write_projected_csv(
            CLEAN_DIR / "clean_candidate_sites_sample.csv",
            target_dir / "dim_candidate_site_sample.csv",
            [
                "candidate_site_id",
                "source_record_id",
                "country_code",
                "nearest_demand_zone_id",
                "lat",
                "lon",
                "site_type",
                "candidate_proxy_flag",
                "estimated_capex_class",
                "rollout_risk_score",
                "competition_score",
                "data_quality_score",
                "proxy_assumption_label",
            ],
        ),
        write_projected_csv(
            MART_DIR / "fact_candidate_zone_coverage_sample.csv",
            target_dir / "fact_candidate_zone_coverage_sample.csv",
            [
                "candidate_site_id",
                "demand_zone_id",
                "coverage_radius_km",
                "distance_km",
                "a_ij",
                "within_radius_flag",
                "same_country_flag",
                "cross_border_allowed_flag",
                "pair_eligible_flag",
                "demand_weight_contribution",
                "proxy_assumption_label",
            ],
        ),
        write_projected_csv(
            MART_DIR / "fact_scenario_inputs_sample.csv",
            target_dir / "fact_scenario_inputs_sample.csv",
            [
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
                "classification",
                "allowed_use_note",
            ],
        ),
    ]
    include_tile_smoke = (CLEAN_DIR / "clean_candidate_sites_tile_smoke.csv").exists() and (MART_DIR / "fact_candidate_zone_coverage_tile_smoke.csv").exists()
    include_tile_smoke_scenarios = (MART_DIR / "fact_scenario_inputs_tile_smoke.csv").exists()
    if include_tile_smoke:
        outputs.extend(
            [
                write_projected_csv(
                    CLEAN_DIR / "clean_candidate_sites_tile_smoke.csv",
                    target_dir / "dim_candidate_site_tile_smoke.csv",
                    [
                        "candidate_site_id",
                        "source_record_id",
                        "country_code",
                        "nearest_demand_zone_id",
                        "nuts_id",
                        "lat",
                        "lon",
                        "site_type",
                        "candidate_proxy_flag",
                        "estimated_capex_class",
                        "rollout_risk_score",
                        "competition_score",
                        "data_quality_score",
                        "proxy_assumption_label",
                    ],
                ),
                write_projected_csv(
                    MART_DIR / "fact_candidate_zone_coverage_tile_smoke.csv",
                    target_dir / "fact_candidate_zone_coverage_tile_smoke.csv",
                    [
                        "candidate_site_id",
                        "demand_zone_id",
                        "coverage_radius_km",
                        "distance_km",
                        "a_ij",
                        "within_radius_flag",
                        "same_country_flag",
                        "cross_border_allowed_flag",
                        "pair_eligible_flag",
                        "demand_weight_contribution",
                        "proxy_assumption_label",
                    ],
                ),
            ]
        )
        if include_tile_smoke_scenarios:
            outputs.append(
                write_projected_csv(
                    MART_DIR / "fact_scenario_inputs_tile_smoke.csv",
                    target_dir / "fact_scenario_inputs_tile_smoke.csv",
                    [
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
                        "classification",
                        "allowed_use_note",
                    ],
                )
            )
        if (MART_DIR / "mart_candidate_baseline_scores_tile_smoke.csv").exists():
            outputs.append(
                write_projected_csv(
                    MART_DIR / "mart_candidate_baseline_scores_tile_smoke.csv",
                    target_dir / "mart_candidate_baseline_scores_tile_smoke.csv",
                    [
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
                        "action_bucket",
                        "allowed_use_note",
                        "proxy_assumption_label",
                    ],
                )
            )
        if (MART_DIR / "mart_baseline_sensitivity_tile_smoke.csv").exists():
            outputs.append(
                write_projected_csv(
                    MART_DIR / "mart_baseline_sensitivity_tile_smoke.csv",
                    target_dir / "mart_baseline_sensitivity_tile_smoke.csv",
                    [
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
                    ],
                )
            )
        if (MART_DIR / "mart_optimization_results_tile_smoke.csv").exists():
            outputs.append(
                write_projected_csv(
                    MART_DIR / "mart_optimization_results_tile_smoke.csv",
                    target_dir / "mart_optimization_results_tile_smoke.csv",
                    [
                        "scenario_method_id",
                        "scenario_id",
                        "method_id",
                        "solver_status",
                        "selected_candidate_count",
                        "objective_covered_demand_weight",
                        "covered_zone_count",
                        "total_candidate_cost",
                        "budget",
                        "k",
                        "candidate_pool_count",
                        "improvement_vs_baseline_demand_weight",
                        "improvement_vs_baseline_pct",
                        "solver_note",
                        "allowed_use_note",
                        "proxy_assumption_label",
                    ],
                )
            )
        if (MART_DIR / "mart_optimization_constraint_diagnostics_tile_smoke.csv").exists():
            outputs.append(
                write_projected_csv(
                    MART_DIR / "mart_optimization_constraint_diagnostics_tile_smoke.csv",
                    target_dir / "mart_optimization_constraint_diagnostics_tile_smoke.csv",
                    [
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
                    ],
                )
            )
        if (MART_DIR / "fact_optimization_selected_sites_tile_smoke.csv").exists():
            outputs.append(
                write_projected_csv(
                    MART_DIR / "fact_optimization_selected_sites_tile_smoke.csv",
                    target_dir / "fact_optimization_selected_sites_tile_smoke.csv",
                    [
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
                    ],
                )
            )
    outputs.extend(
        [
            write_dim_scenario(target_dir / "dim_scenario.csv"),
            write_relationships(
                target_dir / "model_relationships.csv",
                include_tile_smoke=include_tile_smoke,
                include_tile_smoke_scenarios=include_tile_smoke_scenarios,
            ),
            write_manifest(target_dir / "export_manifest.json", include_tile_smoke=include_tile_smoke, include_tile_smoke_scenarios=include_tile_smoke_scenarios),
        ]
    )
    return outputs


def write_projected_csv(source: Path, target: Path, columns: list[str]) -> Path:
    rows = read_csv_rows(source)
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})
    return target


def write_dim_scenario(target: Path) -> Path:
    config_path = CONFIG_DIR / "service_radius_scenarios.json"
    scenarios = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else []
    fieldnames = ["scenario_id", "scenario_slug", "coverage_radius_km", "classification", "allowed_use_note"]
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows({field: scenario.get(field, "") for field in fieldnames} for scenario in scenarios)
    return target


def write_relationships(target: Path, *, include_tile_smoke: bool = False, include_tile_smoke_scenarios: bool = False) -> Path:
    rows = [
        relationship("fact_candidate_zone_coverage_sample", "candidate_site_id", "dim_candidate_site_sample", "candidate_site_id", "many-to-one"),
        relationship("fact_candidate_zone_coverage_sample", "demand_zone_id", "dim_demand_zone", "demand_zone_id", "many-to-one"),
        relationship("fact_candidate_zone_coverage_sample", "coverage_radius_km", "dim_scenario", "coverage_radius_km", "many-to-one", "Radius-only scenario link for sample facts."),
        relationship("fact_scenario_inputs_sample", "scenario_id", "dim_scenario", "scenario_id", "many-to-one"),
    ]
    if include_tile_smoke:
        rows.extend(
            [
                relationship("fact_candidate_zone_coverage_tile_smoke", "candidate_site_id", "dim_candidate_site_tile_smoke", "candidate_site_id", "many-to-one"),
                relationship("fact_candidate_zone_coverage_tile_smoke", "demand_zone_id", "dim_demand_zone", "demand_zone_id", "many-to-one"),
            ]
        )
    if include_tile_smoke_scenarios:
        rows.append(relationship("fact_scenario_inputs_tile_smoke", "scenario_id", "dim_scenario", "scenario_id", "many-to-one"))
    if (MART_DIR / "mart_candidate_baseline_scores_tile_smoke.csv").exists():
        rows.extend(
            [
                relationship("mart_candidate_baseline_scores_tile_smoke", "candidate_site_id", "dim_candidate_site_tile_smoke", "candidate_site_id", "many-to-one"),
                relationship("mart_candidate_baseline_scores_tile_smoke", "scenario_id", "dim_scenario", "scenario_id", "many-to-one"),
            ]
        )
    if (MART_DIR / "mart_baseline_sensitivity_tile_smoke.csv").exists():
        rows.extend(
            [
                relationship("mart_baseline_sensitivity_tile_smoke", "candidate_site_id", "dim_candidate_site_tile_smoke", "candidate_site_id", "many-to-one"),
                relationship("mart_baseline_sensitivity_tile_smoke", "scenario_id", "dim_scenario", "scenario_id", "many-to-one"),
            ]
        )
    if (MART_DIR / "mart_optimization_results_tile_smoke.csv").exists():
        rows.append(relationship("mart_optimization_results_tile_smoke", "scenario_id", "dim_scenario", "scenario_id", "many-to-one"))
    if (MART_DIR / "mart_optimization_constraint_diagnostics_tile_smoke.csv").exists():
        rows.extend(
            [
                relationship("mart_optimization_constraint_diagnostics_tile_smoke", "scenario_id", "dim_scenario", "scenario_id", "many-to-one"),
                relationship("mart_optimization_constraint_diagnostics_tile_smoke", "scenario_method_id", "mart_optimization_results_tile_smoke", "scenario_method_id", "many-to-one"),
            ]
        )
    if (MART_DIR / "fact_optimization_selected_sites_tile_smoke.csv").exists():
        rows.extend(
            [
                relationship("fact_optimization_selected_sites_tile_smoke", "candidate_site_id", "dim_candidate_site_tile_smoke", "candidate_site_id", "many-to-one"),
                relationship("fact_optimization_selected_sites_tile_smoke", "scenario_id", "dim_scenario", "scenario_id", "many-to-one"),
                relationship("fact_optimization_selected_sites_tile_smoke", "scenario_method_id", "mart_optimization_results_tile_smoke", "scenario_method_id", "many-to-one"),
            ]
        )
    fieldnames = ["from_table", "from_column", "to_table", "to_column", "cardinality", "cross_filter", "active", "model_note"]
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return target


def relationship(
    from_table: str,
    from_column: str,
    to_table: str,
    to_column: str,
    cardinality: str,
    model_note: str = "",
) -> dict:
    return {
        "from_table": from_table,
        "from_column": from_column,
        "to_table": to_table,
        "to_column": to_column,
        "cardinality": cardinality,
        "cross_filter": "single",
        "active": "true",
        "model_note": model_note,
    }


def write_manifest(target: Path, *, include_tile_smoke: bool = False, include_tile_smoke_scenarios: bool = False) -> Path:
    tables = [
        "dim_demand_zone",
        "dim_candidate_site_sample",
        "dim_scenario",
        "fact_candidate_zone_coverage_sample",
        "fact_scenario_inputs_sample",
    ]
    if include_tile_smoke:
        tables.extend(["dim_candidate_site_tile_smoke", "fact_candidate_zone_coverage_tile_smoke"])
        if include_tile_smoke_scenarios:
            tables.append("fact_scenario_inputs_tile_smoke")
        if (MART_DIR / "mart_candidate_baseline_scores_tile_smoke.csv").exists():
            tables.append("mart_candidate_baseline_scores_tile_smoke")
        if (MART_DIR / "mart_baseline_sensitivity_tile_smoke.csv").exists():
            tables.append("mart_baseline_sensitivity_tile_smoke")
        if (MART_DIR / "mart_optimization_results_tile_smoke.csv").exists():
            tables.append("mart_optimization_results_tile_smoke")
        if (MART_DIR / "mart_optimization_constraint_diagnostics_tile_smoke.csv").exists():
            tables.append("mart_optimization_constraint_diagnostics_tile_smoke")
        if (MART_DIR / "fact_optimization_selected_sites_tile_smoke.csv").exists():
            tables.append("fact_optimization_selected_sites_tile_smoke")
    payload = {
        "export_schema_version": "powerbi_sample_v1",
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "tables": tables,
        "notes": [
            "Demand zones use pilot NUTS3 population when available.",
            "Sample candidate and coverage facts remain Brussels sample outputs.",
            "Tile-smoke candidate, coverage, baseline, sensitivity, and optimization exports are scoped test artifacts, not full pilot facts.",
            "Proxy and assumption labels must remain visible in BI visuals.",
        ],
    }
    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return target


def read_csv_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))
