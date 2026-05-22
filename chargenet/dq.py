from __future__ import annotations

import csv
import json
import hashlib
from pathlib import Path

from .paths import CLEAN_DIR, CONFIG_DIR, RAW_DIR, REPORT_DIR, ensure_project_dirs


def validate_raw_snapshots() -> dict:
    checks = []
    license_ids = load_license_ids()
    required_raw = [
        RAW_DIR / "osm_chargers_brussels_sample.json",
        RAW_DIR / "osm_candidate_pois_brussels_sample.json",
        RAW_DIR / "gisco_nuts_2024_level0.geojson",
        RAW_DIR / "gisco_nuts_2024_attributes.csv",
        RAW_DIR / "eurostat_population_be100_2025_sample.json",
        RAW_DIR / "open_charge_map_no_key_probe.json",
    ]
    for path in required_raw:
        checks.append(check_exists(path))
        manifest = RAW_DIR / f"{path.stem}.manifest.json"
        checks.append(check_exists(manifest))
        if path.exists() and manifest.exists():
            checks.append(validate_manifest_hash(path, manifest))
            checks.append(validate_manifest_license(manifest, license_ids))
            checks.append(validate_manifest_immutable_path(manifest))

    optional_pilot_raw = [
        RAW_DIR / "gisco_nuts_2024_level3.geojson",
        RAW_DIR / "eurostat_population_nuts3_2025_pilot.json",
    ]
    for path in optional_pilot_raw:
        if not path.exists():
            continue
        checks.append(check_exists(path))
        manifest = RAW_DIR / f"{path.stem}.manifest.json"
        checks.append(check_exists(manifest))
        if manifest.exists():
            checks.append(validate_manifest_hash(path, manifest))
            checks.append(validate_manifest_license(manifest, license_ids))
            checks.append(validate_manifest_immutable_path(manifest))

    known_stale_raw = [RAW_DIR / "eurostat_population_de212_2025_sample.json"]
    for stale_path in known_stale_raw:
        checks.append(
            {
                "check": "stale_raw_absent",
                "path": str(stale_path.as_posix()),
                "passed": not stale_path.exists(),
                "detail": "stale raw sample must be removed" if stale_path.exists() else "no stale raw sample",
            }
        )

    for path in [RAW_DIR / "osm_chargers_brussels_sample.json", RAW_DIR / "osm_candidate_pois_brussels_sample.json"]:
        if path.exists():
            checks.extend(validate_osm_json(path))

    return summarize_checks(checks)


def validate_clean_samples() -> dict:
    checks = []
    checks.extend(validate_csv_required_fields(CLEAN_DIR / "clean_existing_chargers_sample.csv", ["charger_source_id", "lat", "lon", "missing_socket_flag", "missing_power_flag", "data_quality_score", "proxy_assumption_label"]))
    checks.extend(validate_csv_required_fields(CLEAN_DIR / "clean_candidate_sites_sample.csv", ["candidate_site_id", "country_code", "nearest_demand_zone_id", "candidate_proxy_flag", "estimated_capex_class", "rollout_risk_score", "competition_score", "data_quality_score", "proxy_assumption_label"]))
    checks.extend(validate_csv_required_fields(CLEAN_DIR / "clean_demand_zones_sample.csv", ["demand_zone_id", "demand_weight", "baseline_nearest_charger_distance_km", "baseline_charger_count_within_radius", "underserved_zone_flag", "proxy_assumption_label"]))
    checks.extend(validate_csv_required_fields(CLEAN_DIR.parent / "marts" / "fact_candidate_zone_coverage_sample.csv", ["candidate_site_id", "demand_zone_id", "coverage_radius_km", "distance_km", "a_ij", "pair_eligible_flag", "proxy_assumption_label"]))
    checks.extend(
        validate_csv_required_fields(
            CLEAN_DIR.parent / "marts" / "fact_scenario_inputs_sample.csv",
            ["scenario_id", "entity_type", "entity_id", "d_i", "c_j", "b", "k", "service_radius_km", "classification", "allowed_use_note"],
            not_blank_fields=["scenario_id", "entity_type", "entity_id", "b", "k", "service_radius_km", "classification", "allowed_use_note"],
        )
    )
    checks.extend(validate_csv_required_fields(CLEAN_DIR.parent / "marts" / "data_dictionary_sample.csv", ["table_name", "column_name", "classification", "allowed_use_note", "license_key"]))
    checks.extend(validate_referential_integrity())
    checks.extend(validate_radius_and_scenario_consistency())
    checks.extend(validate_dictionary_coverage())
    checks.extend(validate_optional_pilot_nuts3())
    checks.extend(validate_optional_powerbi_exports())
    checks.extend(validate_optional_osm_tile_plan())
    checks.extend(validate_optional_osm_tile_smoke_log())
    checks.extend(validate_optional_osm_tile_smoke_clean())
    checks.extend(validate_optional_osm_candidate_smoke_clean())
    checks.extend(validate_optional_tile_smoke_coverage())
    checks.extend(validate_optional_tile_smoke_scenario_inputs())
    checks.extend(validate_optional_baseline_scores_tile_smoke())
    checks.extend(validate_optional_baseline_sensitivity_tile_smoke())
    checks.extend(validate_optional_optimization_sensitivity_tile_smoke())
    checks.extend(validate_optional_optimization_results_tile_smoke())
    checks.extend(validate_optional_optimization_zone_trace_tile_smoke())
    checks.extend(validate_optional_optimization_country_diagnostics_tile_smoke())
    checks.extend(validate_optional_method_comparison_narrative_tile_smoke())
    checks.extend(validate_optional_candidate_lineage_trace_tile_smoke())
    checks.extend(validate_optional_business_scenario_library_tile_smoke())
    checks.extend(validate_optional_pipeline_snapshot_metrics_tile_smoke())
    checks.extend(validate_optional_pipeline_snapshot_drift_tile_smoke())
    checks.extend(validate_optional_pipeline_snapshot_certification_tile_smoke())
    return summarize_checks(checks)


def write_quality_report() -> Path:
    ensure_project_dirs()
    report = {
        "raw": validate_raw_snapshots(),
        "clean": validate_clean_samples(),
        "notes": [
            "Sample checks demonstrate the Phase 3 skeleton, not full-country data completeness.",
            "All proxy and assumption fields must remain labeled in downstream marts and BI exports.",
        ],
    }
    target = REPORT_DIR / "phase3_sample_quality_report.json"
    target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return target


def check_exists(path: Path) -> dict:
    return {
        "check": "exists",
        "path": str(path.as_posix()),
        "passed": path.exists(),
        "detail": "file exists" if path.exists() else "missing required file",
    }


def validate_osm_json(path: Path) -> list[dict]:
    checks = []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [{"check": "json_valid", "path": str(path.as_posix()), "passed": False, "detail": str(exc)}]
    elements = payload.get("elements", [])
    checks.append({"check": "osm_elements_nonempty", "path": str(path.as_posix()), "passed": len(elements) > 0, "detail": f"{len(elements)} elements"})
    valid_coordinates = [
        element
        for element in elements
        if ("lat" in element and "lon" in element) or ("center" in element and "lat" in element["center"] and "lon" in element["center"])
    ]
    checks.append(
        {
            "check": "coordinate_presence",
            "path": str(path.as_posix()),
            "passed": len(valid_coordinates) == len(elements),
            "detail": f"{len(valid_coordinates)} of {len(elements)} elements have coordinates or centers",
        }
    )
    ids = [f"{element.get('type')}:{element.get('id')}" for element in elements]
    checks.append({"check": "unique_osm_ids", "path": str(path.as_posix()), "passed": len(ids) == len(set(ids)), "detail": f"{len(set(ids))} unique ids"})
    return checks


def validate_manifest_hash(path: Path, manifest_path: Path) -> dict:
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"check": "manifest_json_valid", "path": str(manifest_path.as_posix()), "passed": False, "detail": str(exc)}
    expected = manifest.get("content_sha256")
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "check": "manifest_content_hash_matches",
        "path": str(path.as_posix()),
        "passed": expected == actual,
        "detail": "hash matches" if expected == actual else f"expected {expected}, got {actual}",
    }


def validate_manifest_immutable_path(manifest_path: Path) -> dict:
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"check": "manifest_immutable_path", "path": str(manifest_path.as_posix()), "passed": False, "detail": str(exc)}
    immutable_path = manifest.get("immutable_run_path", "")
    passed = bool(immutable_path) and Path(immutable_path).exists()
    return {
        "check": "manifest_immutable_path",
        "path": str(manifest_path.as_posix()),
        "passed": passed,
        "detail": immutable_path if immutable_path else "missing immutable_run_path",
    }


def validate_manifest_license(manifest_path: Path, license_ids: set[str]) -> dict:
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"check": "manifest_license_mapping", "path": str(manifest_path.as_posix()), "passed": False, "detail": str(exc)}
    source_id = manifest.get("source_id")
    return {
        "check": "manifest_license_mapping",
        "path": str(manifest_path.as_posix()),
        "passed": source_id in license_ids,
        "detail": f"{source_id} mapped to license manifest" if source_id in license_ids else f"{source_id} missing from license manifest",
    }


def validate_csv_required_fields(path: Path, fields: list[str], *, not_blank_fields: list[str] | None = None) -> list[dict]:
    if not path.exists():
        return [check_exists(path)]
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        header = reader.fieldnames or []
    checks = [
        {"check": "csv_nonempty", "path": str(path.as_posix()), "passed": len(rows) > 0, "detail": f"{len(rows)} rows"},
    ]
    not_blank = fields if not_blank_fields is None else not_blank_fields
    for field in fields:
        checks.append({"check": f"field_present:{field}", "path": str(path.as_posix()), "passed": field in header, "detail": ",".join(header)})
    for field in not_blank:
        checks.append(
            {
                "check": f"field_not_blank:{field}",
                "path": str(path.as_posix()),
                "passed": all(str(row.get(field, "")).strip() for row in rows),
                "detail": f"{field} checked across {len(rows)} rows",
            }
        )
    return checks


def validate_referential_integrity() -> list[dict]:
    checks = []
    candidate_path = CLEAN_DIR / "clean_candidate_sites_sample.csv"
    demand_path = CLEAN_DIR / "clean_demand_zones_sample.csv"
    coverage_path = CLEAN_DIR.parent / "marts" / "fact_candidate_zone_coverage_sample.csv"
    if not (candidate_path.exists() and demand_path.exists() and coverage_path.exists()):
        return checks

    candidates = read_csv_rows(candidate_path)
    zones = read_csv_rows(demand_path)
    coverage = read_csv_rows(coverage_path)
    candidate_ids = {row["candidate_site_id"] for row in candidates}
    zone_ids = {row["demand_zone_id"] for row in zones}
    coverage_candidate_ids = {row["candidate_site_id"] for row in coverage}
    coverage_zone_ids = {row["demand_zone_id"] for row in coverage}
    radius_count = len({row.get("coverage_radius_km", "") for row in coverage})
    expected_pairs = len(candidate_ids) * len(zone_ids) * radius_count

    checks.extend(
        [
            {
                "check": "coverage_candidate_fk",
                "path": str(coverage_path.as_posix()),
                "passed": coverage_candidate_ids.issubset(candidate_ids),
                "detail": f"{len(coverage_candidate_ids)} coverage candidates, {len(candidate_ids)} clean candidates",
            },
            {
                "check": "coverage_demand_zone_fk",
                "path": str(coverage_path.as_posix()),
                "passed": coverage_zone_ids.issubset(zone_ids),
                "detail": f"{len(coverage_zone_ids)} coverage zones, {len(zone_ids)} clean zones",
            },
            {
                "check": "coverage_pair_count_complete_for_sample_radius",
                "path": str(coverage_path.as_posix()),
                "passed": len(coverage) == expected_pairs,
                "detail": f"{len(coverage)} rows, expected {expected_pairs}",
            },
            {
                "check": "candidate_ids_unique",
                "path": str(candidate_path.as_posix()),
                "passed": len(candidate_ids) == len(candidates),
                "detail": f"{len(candidate_ids)} unique ids across {len(candidates)} rows",
            },
            {
                "check": "demand_zone_ids_unique",
                "path": str(demand_path.as_posix()),
                "passed": len(zone_ids) == len(zones),
                "detail": f"{len(zone_ids)} unique ids across {len(zones)} rows",
            },
        ]
    )
    return checks


def validate_radius_and_scenario_consistency() -> list[dict]:
    checks = []
    coverage_path = CLEAN_DIR.parent / "marts" / "fact_candidate_zone_coverage_sample.csv"
    scenario_path = CLEAN_DIR.parent / "marts" / "fact_scenario_inputs_sample.csv"
    radius_config_path = CONFIG_DIR / "service_radius_scenarios.json"
    candidate_path = CLEAN_DIR / "clean_candidate_sites_sample.csv"
    demand_path = CLEAN_DIR / "clean_demand_zones_sample.csv"
    if not (coverage_path.exists() and scenario_path.exists() and radius_config_path.exists()):
        return checks

    coverage = read_csv_rows(coverage_path)
    scenario_rows = read_csv_rows(scenario_path)
    candidates = read_csv_rows(candidate_path) if candidate_path.exists() else []
    zones = read_csv_rows(demand_path) if demand_path.exists() else []
    radii = sorted({str(item["coverage_radius_km"]) for item in json.loads(radius_config_path.read_text(encoding="utf-8"))})
    coverage_radii = sorted({row["coverage_radius_km"] for row in coverage})
    scenario_radii = sorted({row["service_radius_km"] for row in scenario_rows})
    checks.append(
        {
            "check": "coverage_radii_match_config",
            "path": str(coverage_path.as_posix()),
            "passed": coverage_radii == radii,
            "detail": f"coverage={coverage_radii}, config={radii}",
        }
    )
    checks.append(
        {
            "check": "scenario_radii_match_config",
            "path": str(scenario_path.as_posix()),
            "passed": scenario_radii == radii,
            "detail": f"scenario={scenario_radii}, config={radii}",
        }
    )
    for radius in radii:
        rows_for_radius = [row for row in coverage if row["coverage_radius_km"] == radius]
        expected = len(candidates) * len(zones)
        checks.append(
            {
                "check": f"coverage_pair_count_complete_radius:{radius}",
                "path": str(coverage_path.as_posix()),
                "passed": len(rows_for_radius) == expected,
                "detail": f"{len(rows_for_radius)} rows, expected {expected}",
            }
        )
    scenario_ids = {row["scenario_id"] for row in scenario_rows}
    candidate_ids = {row["candidate_site_id"] for row in candidates}
    zone_ids = {row["demand_zone_id"] for row in zones}
    for scenario_id in scenario_ids:
        candidate_entities = {row["entity_id"] for row in scenario_rows if row["scenario_id"] == scenario_id and row["entity_type"] == "candidate_site"}
        zone_entities = {row["entity_id"] for row in scenario_rows if row["scenario_id"] == scenario_id and row["entity_type"] == "demand_zone"}
        checks.append(
            {
                "check": f"scenario_candidate_set_complete:{scenario_id}",
                "path": str(scenario_path.as_posix()),
                "passed": candidate_entities == candidate_ids,
                "detail": f"{len(candidate_entities)} candidate entities, expected {len(candidate_ids)}",
            }
        )
        checks.append(
            {
                "check": f"scenario_demand_zone_set_complete:{scenario_id}",
                "path": str(scenario_path.as_posix()),
                "passed": zone_entities == zone_ids,
                "detail": f"{len(zone_entities)} demand-zone entities, expected {len(zone_ids)}",
            }
        )
        checks.append(
            {
                "check": f"scenario_candidate_cj_complete:{scenario_id}",
                "path": str(scenario_path.as_posix()),
                "passed": all(row.get("c_j") for row in scenario_rows if row["scenario_id"] == scenario_id and row["entity_type"] == "candidate_site"),
                "detail": "all candidate rows have c_j",
            }
        )
        checks.append(
            {
                "check": f"scenario_demand_di_complete:{scenario_id}",
                "path": str(scenario_path.as_posix()),
                "passed": all(row.get("d_i") for row in scenario_rows if row["scenario_id"] == scenario_id and row["entity_type"] == "demand_zone"),
                "detail": "all demand-zone rows have d_i",
            }
        )
    return checks


def validate_dictionary_coverage() -> list[dict]:
    dictionary_path = CLEAN_DIR.parent / "marts" / "data_dictionary_sample.csv"
    if not dictionary_path.exists():
        return [check_exists(dictionary_path)]
    dictionary_rows = read_csv_rows(dictionary_path)
    dictionary_keys = {(row["table_name"], row["column_name"]) for row in dictionary_rows}
    checks = []
    table_paths = {
        "clean_existing_chargers": CLEAN_DIR / "clean_existing_chargers_sample.csv",
        "clean_existing_chargers_tile_smoke": CLEAN_DIR / "clean_existing_chargers_tile_smoke.csv",
        "clean_candidate_sites": CLEAN_DIR / "clean_candidate_sites_sample.csv",
        "clean_candidate_sites_tile_smoke": CLEAN_DIR / "clean_candidate_sites_tile_smoke.csv",
        "clean_demand_zones": CLEAN_DIR / "clean_demand_zones_sample.csv",
        "fact_candidate_zone_coverage": CLEAN_DIR.parent / "marts" / "fact_candidate_zone_coverage_sample.csv",
        "fact_scenario_inputs": CLEAN_DIR.parent / "marts" / "fact_scenario_inputs_sample.csv",
        "clean_demand_zones_nuts3_pilot": CLEAN_DIR / "clean_demand_zones_nuts3_pilot.csv",
        "fact_candidate_zone_coverage_tile_smoke": CLEAN_DIR.parent / "marts" / "fact_candidate_zone_coverage_tile_smoke.csv",
        "fact_scenario_inputs_tile_smoke": CLEAN_DIR.parent / "marts" / "fact_scenario_inputs_tile_smoke.csv",
        "mart_candidate_baseline_scores_tile_smoke": CLEAN_DIR.parent / "marts" / "mart_candidate_baseline_scores_tile_smoke.csv",
        "mart_baseline_sensitivity_tile_smoke": CLEAN_DIR.parent / "marts" / "mart_baseline_sensitivity_tile_smoke.csv",
        "mart_optimization_results_tile_smoke": CLEAN_DIR.parent / "marts" / "mart_optimization_results_tile_smoke.csv",
        "fact_optimization_selected_sites_tile_smoke": CLEAN_DIR.parent / "marts" / "fact_optimization_selected_sites_tile_smoke.csv",
        "mart_optimization_constraint_diagnostics_tile_smoke": CLEAN_DIR.parent / "marts" / "mart_optimization_constraint_diagnostics_tile_smoke.csv",
    }
    for table_name, table_path in table_paths.items():
        if not table_path.exists():
            continue
        with table_path.open(newline="", encoding="utf-8") as handle:
            header = next(csv.reader(handle))
        missing = [column for column in header if (table_name, column) not in dictionary_keys]
        checks.append(
            {
                "check": f"dictionary_covers_table:{table_name}",
                "path": str(dictionary_path.as_posix()),
                "passed": not missing,
                "detail": "all columns covered" if not missing else "missing: " + ",".join(missing),
            }
        )
    return checks


def validate_optional_pilot_nuts3() -> list[dict]:
    checks = []
    pilot_path = CLEAN_DIR / "clean_demand_zones_nuts3_pilot.csv"
    if not pilot_path.exists():
        return checks
    rows = read_csv_rows(pilot_path)
    scope_path = CONFIG_DIR / "pilot_scope.json"
    scope = json.loads(scope_path.read_text(encoding="utf-8")) if scope_path.exists() else {}
    countries = set(scope.get("pilot_countries", []))
    country_counts = {country: 0 for country in countries}
    for row in rows:
        if row.get("country_code") in country_counts:
            country_counts[row["country_code"]] += 1
    checks.append(
        {
            "check": "pilot_nuts3_nonempty",
            "path": str(pilot_path.as_posix()),
            "passed": len(rows) > 0,
            "detail": f"{len(rows)} NUTS3 rows",
        }
    )
    checks.append(
        {
            "check": "pilot_nuts3_country_coverage",
            "path": str(pilot_path.as_posix()),
            "passed": bool(countries) and all(count > 0 for count in country_counts.values()),
            "detail": json.dumps(country_counts, sort_keys=True),
        }
    )
    population_raw_exists = (RAW_DIR / "eurostat_population_nuts3_2025_pilot.json").exists()
    if population_raw_exists:
        populated_rows = [
            row
            for row in rows
            if row.get("population") and row.get("demand_weight") and row.get("base_demand_weight") and row.get("population_missing_flag") == "0"
        ]
        checks.append(
            {
                "check": "pilot_nuts3_population_join_complete",
                "path": str(pilot_path.as_posix()),
                "passed": len(populated_rows) == len(rows),
                "detail": f"{len(populated_rows)} populated rows of {len(rows)}",
            }
        )
        checks.append(
            {
                "check": "pilot_nuts3_population_positive",
                "path": str(pilot_path.as_posix()),
                "passed": all(int(float(row["population"])) > 0 for row in populated_rows),
                "detail": "population values are positive where joined",
            }
        )
    else:
        checks.append(
            {
                "check": "pilot_nuts3_population_join_pending_labeled",
                "path": str(pilot_path.as_posix()),
                "passed": all(row.get("population_missing_flag") == "1" and row.get("proxy_assumption_label") for row in rows),
                "detail": "population join pending is labeled on every pilot row",
            }
        )
    checks.append(
        {
            "check": "pilot_nuts3_centroids_present",
            "path": str(pilot_path.as_posix()),
            "passed": all(row.get("centroid_lat") and row.get("centroid_lon") and row.get("centroid_method") for row in rows),
            "detail": "centroid proxy fields checked",
        }
    )
    return checks


def read_csv_rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def validate_optional_powerbi_exports() -> list[dict]:
    export_dir = REPORT_DIR / "powerbi_exports"
    if not export_dir.exists():
        return []
    checks = []
    required = [
        export_dir / "dim_demand_zone.csv",
        export_dir / "dim_candidate_site_sample.csv",
        export_dir / "dim_scenario.csv",
        export_dir / "fact_candidate_zone_coverage_sample.csv",
        export_dir / "fact_scenario_inputs_sample.csv",
        export_dir / "model_relationships.csv",
        export_dir / "export_manifest.json",
    ]
    source_export_pairs = [
        (CLEAN_DIR / "clean_candidate_sites_tile_smoke.csv", export_dir / "dim_candidate_site_tile_smoke.csv"),
        (CLEAN_DIR.parent / "marts" / "fact_candidate_zone_coverage_tile_smoke.csv", export_dir / "fact_candidate_zone_coverage_tile_smoke.csv"),
        (CLEAN_DIR.parent / "marts" / "fact_scenario_inputs_tile_smoke.csv", export_dir / "fact_scenario_inputs_tile_smoke.csv"),
        (CLEAN_DIR.parent / "marts" / "mart_candidate_baseline_scores_tile_smoke.csv", export_dir / "mart_candidate_baseline_scores_tile_smoke.csv"),
        (CLEAN_DIR.parent / "marts" / "mart_baseline_sensitivity_tile_smoke.csv", export_dir / "mart_baseline_sensitivity_tile_smoke.csv"),
        (CLEAN_DIR.parent / "marts" / "mart_optimization_results_tile_smoke.csv", export_dir / "mart_optimization_results_tile_smoke.csv"),
        (CLEAN_DIR.parent / "marts" / "mart_optimization_constraint_diagnostics_tile_smoke.csv", export_dir / "mart_optimization_constraint_diagnostics_tile_smoke.csv"),
        (CLEAN_DIR.parent / "marts" / "fact_optimization_selected_sites_tile_smoke.csv", export_dir / "fact_optimization_selected_sites_tile_smoke.csv"),
    ]
    required.extend(export_path for source_path, export_path in source_export_pairs if source_path.exists())
    for path in required:
        checks.append(check_exists(path))
        if path.suffix == ".csv" and path.exists():
            rows = read_csv_rows(path)
            checks.append(
                {
                    "check": "powerbi_export_nonempty",
                    "path": str(path.as_posix()),
                    "passed": len(rows) > 0,
                    "detail": f"{len(rows)} rows",
                }
            )
    relationship_path = export_dir / "model_relationships.csv"
    if relationship_path.exists():
        relationships = read_csv_rows(relationship_path)
        relationship_keys = {(row["from_table"], row["from_column"], row["to_table"], row["to_column"]) for row in relationships}
        checks.append(
            {
                "check": "powerbi_relationships_documented",
                "path": str(relationship_path.as_posix()),
                "passed": len(relationships) >= 4,
                "detail": f"{len(relationships)} relationships",
            }
        )
        if (export_dir / "mart_optimization_constraint_diagnostics_tile_smoke.csv").exists():
            expected = (
                "mart_optimization_constraint_diagnostics_tile_smoke",
                "scenario_method_id",
                "mart_optimization_results_tile_smoke",
                "scenario_method_id",
            )
            checks.append(
                {
                    "check": "powerbi_optimization_diagnostics_relationship",
                    "path": str(relationship_path.as_posix()),
                    "passed": expected in relationship_keys,
                    "detail": "diagnostics join to optimization summary at scenario-method grain",
                }
            )
    return checks


def validate_optional_osm_tile_plan() -> list[dict]:
    tile_plan_path = CLEAN_DIR.parent / "marts" / "osm_pilot_tile_plan.csv"
    demand_zone_path = CLEAN_DIR / "clean_demand_zones_nuts3_pilot.csv"
    if not tile_plan_path.exists():
        return []
    rows = read_csv_rows(tile_plan_path)
    zones = read_csv_rows(demand_zone_path) if demand_zone_path.exists() else []
    extract_slugs = {row.get("extract_slug") for row in rows}
    expected_extract_count = 3
    expected_rows = len(zones) * expected_extract_count
    checks = [
        {
            "check": "osm_tile_plan_nonempty",
            "path": str(tile_plan_path.as_posix()),
            "passed": len(rows) > 0,
            "detail": f"{len(rows)} tile jobs",
        },
        {
            "check": "osm_tile_plan_expected_extracts",
            "path": str(tile_plan_path.as_posix()),
            "passed": extract_slugs == {"charging_stations", "candidate_fuel", "candidate_services"},
            "detail": ",".join(sorted(extract_slugs)),
        },
        {
            "check": "osm_tile_plan_row_count",
            "path": str(tile_plan_path.as_posix()),
            "passed": len(rows) == expected_rows,
            "detail": f"{len(rows)} rows, expected {expected_rows}",
        },
        {
            "check": "osm_tile_plan_not_run",
            "path": str(tile_plan_path.as_posix()),
            "passed": all(row.get("status") == "planned_not_run" for row in rows),
            "detail": "tile plan only; no broad OSM extraction executed",
        },
    ]
    return checks


def validate_optional_osm_tile_smoke_log() -> list[dict]:
    log_path = CLEAN_DIR.parent / "marts" / "osm_tile_execution_log_all.csv"
    if not log_path.exists():
        log_path = CLEAN_DIR.parent / "marts" / "osm_tile_execution_log_latest.csv"
    if not log_path.exists():
        return []
    rows = read_csv_rows(log_path)
    statuses = {row.get("status") for row in rows}
    fetched_tile_ids = {row.get("tile_job_id") for row in rows if row.get("status") == "fetched"}
    unresolved_failed_attempts = sum(
        1
        for row in rows
        if row.get("status") == "fetch_failed" and row.get("tile_job_id") not in fetched_tile_ids
    )
    historical_failed_attempts = sum(1 for row in rows if row.get("status") == "fetch_failed")
    checks = [
        {
            "check": "osm_tile_smoke_log_nonempty",
            "path": str(log_path.as_posix()),
            "passed": len(rows) > 0,
            "detail": f"{len(rows)} smoke-run rows",
        },
        {
            "check": "osm_tile_log_safe_batch_size",
            "path": str(log_path.as_posix()),
            "passed": max_run_size(rows) <= 25,
            "detail": f"largest tile run has {max_run_size(rows)} jobs",
        },
        {
            "check": "osm_tile_smoke_status_terminal",
            "path": str(log_path.as_posix()),
            "passed": statuses.issubset({"fetched", "fetch_failed"}),
            "detail": ",".join(sorted(status for status in statuses if status)),
        },
        {
            "check": "osm_tile_unresolved_fetch_failures_absent",
            "path": str(log_path.as_posix()),
            "passed": unresolved_failed_attempts == 0,
            "detail": f"{unresolved_failed_attempts} unresolved failed attempts; {historical_failed_attempts} historical failed attempts",
        },
    ]
    fetched_rows = [row for row in rows if row.get("status") == "fetched"]
    pilot_countries = set(load_pilot_countries())
    fetched_countries = {row.get("country_code") for row in fetched_rows if row.get("country_code")}
    fetched_extracts = {row.get("extract_slug") for row in fetched_rows if row.get("extract_slug")}
    if pilot_countries:
        checks.append(
            {
                "check": "osm_tile_smoke_pilot_country_coverage",
                "path": str(log_path.as_posix()),
                "passed": pilot_countries.issubset(fetched_countries),
                "detail": f"fetched={sorted(fetched_countries)}, expected={sorted(pilot_countries)}",
            }
        )
    checks.append(
        {
            "check": "osm_tile_smoke_extract_coverage",
            "path": str(log_path.as_posix()),
            "passed": {"charging_stations", "candidate_fuel", "candidate_services"}.issubset(fetched_extracts),
            "detail": f"fetched={sorted(fetched_extracts)}",
        }
    )
    for row in fetched_rows:
        raw_path = Path(row.get("raw_path", ""))
        manifest_path = Path(row.get("manifest_path", ""))
        checks.append(check_exists(raw_path))
        checks.append(check_exists(manifest_path))
        if raw_path.exists() and manifest_path.exists():
            checks.append(validate_manifest_hash(raw_path, manifest_path))
            checks.append(validate_manifest_immutable_path(manifest_path))
    return checks


def max_run_size(rows: list[dict]) -> int:
    counts: dict[str, int] = {}
    for row in rows:
        run_id = row.get("run_id", "")
        counts[run_id] = counts.get(run_id, 0) + 1
    return max(counts.values(), default=0)


def validate_optional_osm_tile_smoke_clean() -> list[dict]:
    path = CLEAN_DIR / "clean_existing_chargers_tile_smoke.csv"
    if not path.exists():
        return []
    checks = validate_csv_required_fields(
        path,
        ["tile_run_id", "tile_job_id", "charger_source_id", "country_code", "nuts_id", "lat", "lon", "data_quality_score", "proxy_assumption_label"],
    )
    rows = read_csv_rows(path)
    ids = [row.get("charger_source_id") for row in rows]
    checks.append(
        {
            "check": "osm_tile_smoke_clean_unique_charger_ids",
            "path": str(path.as_posix()),
            "passed": len(ids) == len(set(ids)),
            "detail": f"{len(set(ids))} unique ids across {len(rows)} rows",
        }
    )
    checks.append(
        {
            "check": "osm_tile_smoke_clean_labeled_scope",
            "path": str(path.as_posix()),
            "passed": all("tile_smoke" in row.get("proxy_assumption_label", "") for row in rows),
            "detail": "every row is labeled as smoke-run scope",
        }
    )
    return checks


def validate_optional_osm_candidate_smoke_clean() -> list[dict]:
    path = CLEAN_DIR / "clean_candidate_sites_tile_smoke.csv"
    if not path.exists():
        return []
    checks = validate_csv_required_fields(
        path,
        [
            "tile_run_id",
            "tile_job_id",
            "candidate_site_id",
            "country_code",
            "nearest_demand_zone_id",
            "nuts_id",
            "lat",
            "lon",
            "candidate_proxy_flag",
            "estimated_capex_class",
            "rollout_risk_score",
            "competition_score",
            "data_quality_score",
            "proxy_assumption_label",
        ],
    )
    rows = read_csv_rows(path)
    ids = [row.get("candidate_site_id") for row in rows]
    checks.append(
        {
            "check": "osm_candidate_smoke_clean_unique_candidate_ids",
            "path": str(path.as_posix()),
            "passed": len(ids) == len(set(ids)),
            "detail": f"{len(set(ids))} unique ids across {len(rows)} rows",
        }
    )
    checks.append(
        {
            "check": "osm_candidate_smoke_clean_labeled_scope",
            "path": str(path.as_posix()),
            "passed": all("tile_smoke" in row.get("proxy_assumption_label", "") for row in rows),
            "detail": "every row is labeled as smoke-run scope",
        }
    )
    checks.append(
        {
            "check": "osm_candidate_smoke_site_type_normalized",
            "path": str(path.as_posix()),
            "passed": {row.get("site_type", "") for row in rows}.issubset({"fuel", "services"}),
            "detail": ",".join(sorted({row.get("site_type", "") for row in rows})),
        }
    )
    return checks


def validate_optional_tile_smoke_coverage() -> list[dict]:
    path = CLEAN_DIR.parent / "marts" / "fact_candidate_zone_coverage_tile_smoke.csv"
    if not path.exists():
        return []
    checks = validate_csv_required_fields(
        path,
        ["candidate_site_id", "demand_zone_id", "coverage_radius_km", "distance_km", "a_ij", "pair_eligible_flag", "proxy_assumption_label"],
    )
    rows = read_csv_rows(path)
    candidates = read_csv_rows(CLEAN_DIR / "clean_candidate_sites_tile_smoke.csv")
    zones = read_csv_rows(CLEAN_DIR / "clean_demand_zones_nuts3_pilot.csv")
    radius_config_path = CONFIG_DIR / "service_radius_scenarios.json"
    radii = sorted({str(item["coverage_radius_km"]) for item in json.loads(radius_config_path.read_text(encoding="utf-8"))}) if radius_config_path.exists() else []
    coverage_radii = sorted({row["coverage_radius_km"] for row in rows})
    candidate_ids = {row["candidate_site_id"] for row in candidates}
    zone_ids = {row["demand_zone_id"] for row in zones}
    expected_rows = len(candidate_ids) * len(zone_ids) * len(radii)
    checks.extend(
        [
            {
                "check": "tile_smoke_coverage_row_count",
                "path": str(path.as_posix()),
                "passed": len(rows) == expected_rows,
                "detail": f"{len(rows)} rows, expected {expected_rows}",
            },
            {
                "check": "tile_smoke_coverage_radii_match_config",
                "path": str(path.as_posix()),
                "passed": coverage_radii == radii,
                "detail": f"coverage={coverage_radii}, config={radii}",
            },
            {
                "check": "tile_smoke_coverage_candidate_fk",
                "path": str(path.as_posix()),
                "passed": {row["candidate_site_id"] for row in rows}.issubset(candidate_ids),
                "detail": f"{len(candidate_ids)} smoke candidates",
            },
            {
                "check": "tile_smoke_coverage_demand_zone_fk",
                "path": str(path.as_posix()),
                "passed": {row["demand_zone_id"] for row in rows}.issubset(zone_ids),
                "detail": f"{len(zone_ids)} pilot demand zones",
            },
            {
                "check": "tile_smoke_coverage_labeled_scope",
                "path": str(path.as_posix()),
                "passed": all("tile_smoke" in row.get("proxy_assumption_label", "") for row in rows),
                "detail": "every row is labeled as smoke-run scope",
            },
        ]
    )
    return checks


def validate_optional_tile_smoke_scenario_inputs() -> list[dict]:
    path = CLEAN_DIR.parent / "marts" / "fact_scenario_inputs_tile_smoke.csv"
    if not path.exists():
        return []
    checks = validate_csv_required_fields(
        path,
        ["scenario_id", "entity_type", "entity_id", "d_i", "c_j", "b", "k", "service_radius_km", "classification", "allowed_use_note"],
        not_blank_fields=["scenario_id", "entity_type", "entity_id", "b", "k", "service_radius_km", "classification", "allowed_use_note"],
    )
    rows = read_csv_rows(path)
    candidates = read_csv_rows(CLEAN_DIR / "clean_candidate_sites_tile_smoke.csv")
    zones = read_csv_rows(CLEAN_DIR / "clean_demand_zones_nuts3_pilot.csv")
    candidate_ids = {row["candidate_site_id"] for row in candidates}
    zone_ids = {row["demand_zone_id"] for row in zones}
    scenario_ids = {row["scenario_id"] for row in rows}
    expected_rows = len(scenario_ids) * (len(candidate_ids) + len(zone_ids))
    checks.append(
        {
            "check": "tile_smoke_scenario_row_count",
            "path": str(path.as_posix()),
            "passed": len(rows) == expected_rows,
            "detail": f"{len(rows)} rows, expected {expected_rows}",
        }
    )
    for scenario_id in scenario_ids:
        scenario_rows = [row for row in rows if row["scenario_id"] == scenario_id]
        scenario_candidate_ids = {row["entity_id"] for row in scenario_rows if row["entity_type"] == "candidate_site"}
        scenario_zone_ids = {row["entity_id"] for row in scenario_rows if row["entity_type"] == "demand_zone"}
        checks.extend(
            [
                {
                    "check": f"tile_smoke_scenario_candidate_set_complete:{scenario_id}",
                    "path": str(path.as_posix()),
                    "passed": scenario_candidate_ids == candidate_ids,
                    "detail": f"{len(scenario_candidate_ids)} candidate rows, expected {len(candidate_ids)}",
                },
                {
                    "check": f"tile_smoke_scenario_demand_set_complete:{scenario_id}",
                    "path": str(path.as_posix()),
                    "passed": scenario_zone_ids == zone_ids,
                    "detail": f"{len(scenario_zone_ids)} demand rows, expected {len(zone_ids)}",
                },
                {
                    "check": f"tile_smoke_scenario_candidate_cj_complete:{scenario_id}",
                    "path": str(path.as_posix()),
                    "passed": all(row.get("c_j") for row in scenario_rows if row["entity_type"] == "candidate_site"),
                    "detail": "all smoke candidate rows have c_j",
                },
                {
                    "check": f"tile_smoke_scenario_demand_di_complete:{scenario_id}",
                    "path": str(path.as_posix()),
                    "passed": all(row.get("d_i") for row in scenario_rows if row["entity_type"] == "demand_zone"),
                    "detail": "all pilot demand rows have d_i",
                },
            ]
        )
    candidate_rows = [row for row in rows if row["entity_type"] == "candidate_site"]
    candidate_costs = [float(row.get("c_j") or 0) for row in candidate_rows]
    checks.extend(
        [
            {
                "check": "tile_smoke_candidate_costs_positive",
                "path": str(path.as_posix()),
                "passed": bool(candidate_costs) and all(cost > 0 for cost in candidate_costs),
                "detail": f"{len(candidate_costs)} candidate cost rows checked",
            },
            {
                "check": "tile_smoke_candidate_costs_variable",
                "path": str(path.as_posix()),
                "passed": len(set(candidate_costs)) > 1,
                "detail": f"{len(set(candidate_costs))} unique c_j values",
            },
            {
                "check": "tile_smoke_candidate_cost_model_version",
                "path": str(path.as_posix()),
                "passed": all(row.get("capex_assumption_version") == "tile_smoke_capex_proxy_v2" for row in candidate_rows),
                "detail": "candidate rows use tile_smoke_capex_proxy_v2",
            },
        ]
    )
    return checks


def validate_optional_baseline_scores_tile_smoke() -> list[dict]:
    path = CLEAN_DIR.parent / "marts" / "mart_candidate_baseline_scores_tile_smoke.csv"
    if not path.exists():
        return []
    checks = validate_csv_required_fields(
        path,
        [
            "scenario_id",
            "candidate_site_id",
            "coverage_radius_km",
            "covered_demand_weight",
            "baseline_score",
            "rank_within_scenario",
            "action_bucket",
            "allowed_use_note",
            "proxy_assumption_label",
        ],
    )
    rows = read_csv_rows(path)
    candidates = read_csv_rows(CLEAN_DIR / "clean_candidate_sites_tile_smoke.csv")
    scenario_ids = {row["scenario_id"] for row in rows}
    expected_rows = len(candidates) * len(scenario_ids)
    checks.extend(
        [
            {
                "check": "baseline_tile_smoke_row_count",
                "path": str(path.as_posix()),
                "passed": len(rows) == expected_rows,
                "detail": f"{len(rows)} rows, expected {expected_rows}",
            },
            {
                "check": "baseline_tile_smoke_score_range",
                "path": str(path.as_posix()),
                "passed": all(0 <= float(row["baseline_score"]) <= 1 for row in rows),
                "detail": "baseline_score checked in [0,1]",
            },
            {
                "check": "baseline_tile_smoke_no_build_language",
                "path": str(path.as_posix()),
                "passed": not any(("build" + " now") in row.get("action_bucket", "").lower() or ("depl" + "oy") in row.get("allowed_use_note", "").lower() for row in rows),
                "detail": "baseline output uses diligence language",
            },
        ]
    )
    return checks


def validate_optional_baseline_sensitivity_tile_smoke() -> list[dict]:
    path = CLEAN_DIR.parent / "marts" / "mart_baseline_sensitivity_tile_smoke.csv"
    if not path.exists():
        return []
    checks = validate_csv_required_fields(
        path,
        [
            "weight_set_id",
            "scenario_id",
            "candidate_site_id",
            "weighted_score",
            "rank_within_weight_set_scenario",
            "base_rank_within_scenario",
            "rank_delta_vs_base",
            "stable_top10_flag",
            "allowed_use_note",
            "proxy_assumption_label",
        ],
    )
    rows = read_csv_rows(path)
    baseline_rows = read_csv_rows(CLEAN_DIR.parent / "marts" / "mart_candidate_baseline_scores_tile_smoke.csv")
    weight_sets = {row["weight_set_id"] for row in rows}
    expected_rows = len(baseline_rows) * len(weight_sets)
    weight_sum_ok = all(
        abs(
            sum(
                float(row.get(field) or 0)
                for field in ["coverage_weight", "data_quality_weight", "risk_weight", "competition_weight"]
            )
            - 1.0
        )
        < 0.000001
        for row in rows
    )
    base_rows = [row for row in rows if row.get("weight_set_id") == "weights:base"]
    checks.extend(
        [
            {
                "check": "baseline_sensitivity_row_count",
                "path": str(path.as_posix()),
                "passed": len(rows) == expected_rows,
                "detail": f"{len(rows)} rows, expected {expected_rows}",
            },
            {
                "check": "baseline_sensitivity_weight_sums",
                "path": str(path.as_posix()),
                "passed": weight_sum_ok,
                "detail": f"{len(weight_sets)} weight sets",
            },
            {
                "check": "baseline_sensitivity_score_range",
                "path": str(path.as_posix()),
                "passed": all(0 <= float(row["weighted_score"]) <= 1 for row in rows),
                "detail": "weighted_score checked in [0,1]",
            },
            {
                "check": "baseline_sensitivity_base_delta_zero",
                "path": str(path.as_posix()),
                "passed": bool(base_rows) and all(str(row.get("rank_delta_vs_base")) == "0" for row in base_rows),
                "detail": f"{len(base_rows)} base-weight rows checked",
            },
            {
                "check": "baseline_sensitivity_no_build_language",
                "path": str(path.as_posix()),
                "passed": not any(("build" + " now") in row.get("allowed_use_note", "").lower() or ("depl" + "oy") in row.get("allowed_use_note", "").lower() for row in rows),
                "detail": "sensitivity output uses diligence language",
            },
        ]
    )
    return checks


def validate_optional_optimization_sensitivity_tile_smoke() -> list[dict]:
    path = CLEAN_DIR.parent / "marts" / "mart_optimization_sensitivity_tile_smoke.csv"
    if not path.exists():
        return []
    checks = []
    checks.extend(
        validate_csv_required_fields(
            path,
            [
                "sensitivity_run_id",
                "scenario_id",
                "weight_set_id",
                "method_id",
                "solver_status",
                "shortlist_size",
                "candidate_pool_count",
                "selected_candidate_count",
                "objective_covered_demand_weight",
                "base_weight_set_objective",
                "objective_delta_vs_base_weight_set",
                "overlap_with_base_solution_count",
                "total_candidate_cost",
                "budget",
                "k",
                "allowed_use_note",
                "proxy_assumption_label",
            ],
        )
    )
    rows = read_csv_rows(path)
    sensitivity_source = CLEAN_DIR.parent / "marts" / "mart_baseline_sensitivity_tile_smoke.csv"
    source_rows = read_csv_rows(sensitivity_source)
    expected_pairs = {(row["scenario_id"], row["weight_set_id"]) for row in source_rows}
    run_ids = {row["sensitivity_run_id"] for row in rows}
    actual_pairs = {(row["scenario_id"], row["weight_set_id"]) for row in rows}
    base_rows = [row for row in rows if row.get("weight_set_id") == "weights:base"]
    checks.extend(
        [
            {
                "check": "optimization_sensitivity_grain_unique",
                "path": str(path.as_posix()),
                "passed": len(run_ids) == len(rows),
                "detail": "one row per scenario, weight set, and method",
            },
            {
                "check": "optimization_sensitivity_pairs_complete",
                "path": str(path.as_posix()),
                "passed": expected_pairs.issubset(actual_pairs),
                "detail": f"{len(actual_pairs)} rows for {len(expected_pairs)} expected scenario-weight pairs",
            },
            {
                "check": "optimization_sensitivity_status_values",
                "path": str(path.as_posix()),
                "passed": all(row["solver_status"] == "optimal_milp" for row in rows),
                "detail": "all current weight-set shortlist solves reached an optimal MILP status",
            },
            {
                "check": "optimization_sensitivity_budget_constraint",
                "path": str(path.as_posix()),
                "passed": all(float(row["total_candidate_cost"]) <= float(row["budget"]) for row in rows),
                "detail": "total candidate cost checked against budget",
            },
            {
                "check": "optimization_sensitivity_site_count_constraint",
                "path": str(path.as_posix()),
                "passed": all(int(row["selected_candidate_count"]) <= int(row["k"]) for row in rows),
                "detail": "selected candidate count checked against k",
            },
            {
                "check": "optimization_sensitivity_objective_nonnegative",
                "path": str(path.as_posix()),
                "passed": all(float(row["objective_covered_demand_weight"]) >= 0 for row in rows),
                "detail": "objective covered demand checked",
            },
            {
                "check": "optimization_sensitivity_base_delta_zero",
                "path": str(path.as_posix()),
                "passed": bool(base_rows) and all(abs(float(row["objective_delta_vs_base_weight_set"])) < 0.000001 for row in base_rows),
                "detail": f"{len(base_rows)} base-weight optimization rows checked",
            },
            {
                "check": "optimization_sensitivity_overlap_pct_range",
                "path": str(path.as_posix()),
                "passed": all(0 <= float(row["overlap_with_base_solution_pct"]) <= 1 for row in rows),
                "detail": "overlap percentage checked in [0,1]",
            },
            {
                "check": "optimization_sensitivity_no_build_language",
                "path": str(path.as_posix()),
                "passed": not any(("build" + " now") in row.get("allowed_use_note", "").lower() or ("depl" + "oy") in row.get("allowed_use_note", "").lower() for row in rows),
                "detail": "optimization sensitivity output uses diligence language",
            },
        ]
    )
    return checks


def validate_optional_optimization_results_tile_smoke() -> list[dict]:
    summary_path = CLEAN_DIR.parent / "marts" / "mart_optimization_results_tile_smoke.csv"
    selected_path = CLEAN_DIR.parent / "marts" / "fact_optimization_selected_sites_tile_smoke.csv"
    diagnostics_path = CLEAN_DIR.parent / "marts" / "mart_optimization_constraint_diagnostics_tile_smoke.csv"
    if not summary_path.exists() and not selected_path.exists() and not diagnostics_path.exists():
        return []
    checks = []
    checks.extend(
        validate_csv_required_fields(
            summary_path,
            [
                "scenario_method_id",
                "scenario_id",
                "method_id",
                "solver_status",
                "selected_candidate_count",
                "objective_covered_demand_weight",
                "total_candidate_cost",
                "budget",
                "k",
                "candidate_pool_count",
                "allowed_use_note",
                "proxy_assumption_label",
            ],
        )
    )
    checks.extend(
        validate_csv_required_fields(
            selected_path,
            [
                "scenario_method_id",
                "scenario_id",
                "method_id",
                "selection_rank",
                "candidate_site_id",
                "baseline_rank_within_scenario",
                "baseline_score",
                "c_j",
                "allowed_use_note",
                "proxy_assumption_label",
            ],
        )
    )
    checks.extend(
        validate_csv_required_fields(
            diagnostics_path,
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
            not_blank_fields=[
                "scenario_method_id",
                "scenario_id",
                "method_id",
                "constraint_name",
                "constraint_status",
                "lhs_value",
                "operator",
                "rhs_value",
                "diagnostic_note",
                "allowed_use_note",
                "proxy_assumption_label",
            ],
        )
    )
    if not (summary_path.exists() and selected_path.exists() and diagnostics_path.exists()):
        return checks
    summary_rows = read_csv_rows(summary_path)
    selected_rows = read_csv_rows(selected_path)
    diagnostics_rows = read_csv_rows(diagnostics_path)
    scenario_ids = {row["scenario_id"] for row in read_csv_rows(CLEAN_DIR.parent / "marts" / "mart_candidate_baseline_scores_tile_smoke.csv")}
    candidate_ids = {row["candidate_site_id"] for row in read_csv_rows(CLEAN_DIR / "clean_candidate_sites_tile_smoke.csv")}
    methods_by_scenario: dict[str, set[str]] = {}
    for row in summary_rows:
        methods_by_scenario.setdefault(row["scenario_id"], set()).add(row["method_id"])
    expected_diagnostics = {"budget", "site_count", "solver_status", "objective_nonnegative", "coverage_floor"}
    diagnostics_by_summary: dict[tuple[str, str], set[str]] = {}
    diagnostics_keys = []
    for row in diagnostics_rows:
        key = (row["scenario_id"], row["method_id"])
        diagnostics_by_summary.setdefault(key, set()).add(row["constraint_name"])
        diagnostics_keys.append((row["scenario_id"], row["method_id"], row["constraint_name"]))
    summary_by_key = {(row["scenario_id"], row["method_id"]): row for row in summary_rows}
    summary_scenario_method_ids = {row["scenario_method_id"] for row in summary_rows}
    selected_scenario_method_ids = {row["scenario_method_id"] for row in selected_rows}
    diagnostics_scenario_method_ids = {row["scenario_method_id"] for row in diagnostics_rows}
    reconciliation_errors = selected_site_reconciliation_errors(summary_rows, selected_rows)
    checks.extend(
        [
            {
                "check": "optimization_summary_scenario_method_unique",
                "path": str(summary_path.as_posix()),
                "passed": len(summary_scenario_method_ids) == len(summary_rows),
                "detail": "one summary row per scenario-method key",
            },
            {
                "check": "optimization_selected_scenario_method_fk",
                "path": str(selected_path.as_posix()),
                "passed": selected_scenario_method_ids.issubset(summary_scenario_method_ids),
                "detail": f"{len(summary_scenario_method_ids)} known scenario-method summary keys",
            },
            {
                "check": "optimization_diagnostics_scenario_method_fk",
                "path": str(diagnostics_path.as_posix()),
                "passed": diagnostics_scenario_method_ids.issubset(summary_scenario_method_ids),
                "detail": f"{len(summary_scenario_method_ids)} known scenario-method summary keys",
            },
            {
                "check": "optimization_summary_methods_complete",
                "path": str(summary_path.as_posix()),
                "passed": all({"method:baseline-topk", "method:mclp-shortlist-exact", "method:mclp-pulp-cbc", "method:min-cost-coverage-pulp"}.issubset(methods_by_scenario.get(scenario_id, set())) for scenario_id in scenario_ids),
                "detail": json.dumps({key: sorted(value) for key, value in sorted(methods_by_scenario.items())}),
            },
            {
                "check": "optimization_selected_candidate_fk",
                "path": str(selected_path.as_posix()),
                "passed": {row["candidate_site_id"] for row in selected_rows}.issubset(candidate_ids),
                "detail": f"{len(candidate_ids)} known smoke candidates",
            },
            {
                "check": "optimization_selected_sites_reconcile_summary",
                "path": str(selected_path.as_posix()),
                "passed": not reconciliation_errors,
                "detail": "selected-site count and cost reconcile to summary rows" if not reconciliation_errors else "; ".join(reconciliation_errors[:10]),
            },
            {
                "check": "optimization_budget_constraint",
                "path": str(summary_path.as_posix()),
                "passed": all(float(row["total_candidate_cost"]) <= float(row["budget"]) for row in summary_rows),
                "detail": "total candidate cost checked against budget",
            },
            {
                "check": "optimization_site_count_constraint",
                "path": str(summary_path.as_posix()),
                "passed": all(int(row["selected_candidate_count"]) <= int(row["k"]) for row in summary_rows),
                "detail": "selected candidate count checked against k",
            },
            {
                "check": "optimization_objective_nonnegative",
                "path": str(summary_path.as_posix()),
                "passed": all(float(row["objective_covered_demand_weight"]) >= 0 for row in summary_rows),
                "detail": "objective covered demand checked",
            },
            {
                "check": "optimization_diagnostics_row_count",
                "path": str(diagnostics_path.as_posix()),
                "passed": len(diagnostics_rows) == len(summary_rows) * len(expected_diagnostics),
                "detail": f"{len(diagnostics_rows)} diagnostics rows, expected {len(summary_rows) * len(expected_diagnostics)}",
            },
            {
                "check": "optimization_diagnostics_grain_unique",
                "path": str(diagnostics_path.as_posix()),
                "passed": len(diagnostics_keys) == len(set(diagnostics_keys)),
                "detail": "one diagnostic row per scenario, method, and constraint",
            },
            {
                "check": "optimization_diagnostics_constraint_set_complete",
                "path": str(diagnostics_path.as_posix()),
                "passed": all(diagnostics_by_summary.get((row["scenario_id"], row["method_id"]), set()) == expected_diagnostics for row in summary_rows),
                "detail": json.dumps({f"{key[0]}|{key[1]}": sorted(value) for key, value in sorted(diagnostics_by_summary.items())}),
            },
            {
                "check": "optimization_diagnostics_status_values",
                "path": str(diagnostics_path.as_posix()),
                "passed": all(row["constraint_status"] in {"pass", "fail", "warning"} for row in diagnostics_rows),
                "detail": "constraint_status checked against pass/fail/warning",
            },
            {
                "check": "optimization_diagnostics_values_match_summary",
                "path": str(diagnostics_path.as_posix()),
                "passed": diagnostics_values_match_summary(diagnostics_rows, summary_by_key),
                "detail": "diagnostic lhs/rhs/slack values match optimization summary rows",
            },
            {
                "check": "optimization_diagnostics_all_pass",
                "path": str(diagnostics_path.as_posix()),
                "passed": all(row["constraint_status"] == "pass" for row in diagnostics_rows),
                "detail": "all generated optimization diagnostics pass under current smoke scenario outputs",
            },
            {
                "check": "optimization_no_build_language",
                "path": str(summary_path.as_posix()),
                "passed": not any(("build" + " now") in row.get("allowed_use_note", "").lower() or ("depl" + "oy") in row.get("allowed_use_note", "").lower() for row in summary_rows + selected_rows + diagnostics_rows),
                "detail": "optimization output uses diligence language",
            },
        ]
    )
    return checks


def selected_site_reconciliation_errors(summary_rows: list[dict], selected_rows: list[dict], *, cost_tolerance: float = 0.01) -> list[str]:
    errors = []
    selected_by_method: dict[str, list[dict]] = {}
    for row in selected_rows:
        selected_by_method.setdefault(str(row.get("scenario_method_id") or ""), []).append(row)

    seen_selected_keys = set()
    for row in selected_rows:
        selected_key = (row.get("scenario_method_id"), row.get("candidate_site_id"))
        if selected_key in seen_selected_keys:
            errors.append(f"{row.get('scenario_method_id')} duplicate selected candidate {row.get('candidate_site_id')}")
        seen_selected_keys.add(selected_key)

    for summary in summary_rows:
        scenario_method_id = str(summary.get("scenario_method_id") or "")
        selected = selected_by_method.get(scenario_method_id, [])
        expected_count = int(round(safe_float(summary.get("selected_candidate_count"))))
        actual_count = len(selected)
        if actual_count != expected_count:
            errors.append(f"{scenario_method_id} count mismatch: summary {expected_count}, selected rows {actual_count}")

        expected_cost = round(safe_float(summary.get("total_candidate_cost")), 2)
        actual_cost = round(sum(safe_float(row.get("c_j")) for row in selected), 2)
        if abs(actual_cost - expected_cost) > cost_tolerance:
            errors.append(f"{scenario_method_id} cost mismatch: summary {expected_cost:.2f}, selected rows {actual_cost:.2f}")

        ranks = sorted(int(round(safe_float(row.get("selection_rank")))) for row in selected)
        expected_ranks = list(range(1, actual_count + 1))
        if ranks != expected_ranks:
            errors.append(f"{scenario_method_id} rank sequence mismatch: expected {expected_ranks}, found {ranks}")

    known_summary_ids = {str(row.get("scenario_method_id") or "") for row in summary_rows}
    for scenario_method_id in selected_by_method:
        if scenario_method_id not in known_summary_ids:
            errors.append(f"{scenario_method_id} selected rows have no summary row")
    return errors


def validate_optional_candidate_lineage_trace_tile_smoke() -> list[dict]:
    path = CLEAN_DIR.parent / "marts" / "mart_candidate_lineage_trace_tile_smoke.csv"
    if not path.exists():
        return []
    checks = []
    checks.extend(
        validate_csv_required_fields(
            path,
            [
                "trace_id",
                "scenario_id",
                "method_id",
                "selection_rank",
                "candidate_site_id",
                "source_record_id",
                "tile_run_id",
                "tile_job_id",
                "raw_tag_keys",
                "baseline_rank_within_scenario",
                "baseline_score",
                "coverage_radius_km",
                "covered_zone_count",
                "covered_demand_weight",
                "coverage_trace_zone_ids",
                "scenario_candidate_cost",
                "allowed_use_note",
                "proxy_assumption_label",
            ],
            not_blank_fields=[
                "trace_id",
                "scenario_id",
                "method_id",
                "selection_rank",
                "candidate_site_id",
                "source_record_id",
                "tile_run_id",
                "tile_job_id",
                "baseline_rank_within_scenario",
                "baseline_score",
                "coverage_radius_km",
                "covered_zone_count",
                "covered_demand_weight",
                "scenario_candidate_cost",
                "allowed_use_note",
                "proxy_assumption_label",
            ],
        )
    )
    rows = read_csv_rows(path)
    trace_ids = {row["trace_id"] for row in rows}
    candidate_ids = {row["candidate_site_id"] for row in read_csv_rows(CLEAN_DIR / "clean_candidate_sites_tile_smoke.csv")}
    selected_keys = {
        (row["scenario_id"], row["method_id"], row["candidate_site_id"])
        for row in read_csv_rows(CLEAN_DIR.parent / "marts" / "fact_optimization_selected_sites_tile_smoke.csv")
    }
    checks.extend(
        [
            {
                "check": "candidate_lineage_trace_grain_unique",
                "path": str(path.as_posix()),
                "passed": len(trace_ids) == len(rows),
                "detail": "one trace row per scenario, method, and candidate",
            },
            {
                "check": "candidate_lineage_trace_candidate_fk",
                "path": str(path.as_posix()),
                "passed": {row["candidate_site_id"] for row in rows}.issubset(candidate_ids),
                "detail": f"{len(candidate_ids)} known tile-smoke candidates",
            },
            {
                "check": "candidate_lineage_trace_selected_site_fk",
                "path": str(path.as_posix()),
                "passed": {
                    (row["scenario_id"], row["method_id"], row["candidate_site_id"])
                    for row in rows
                }.issubset(selected_keys),
                "detail": f"{len(selected_keys)} selected scenario-method-candidate keys",
            },
            {
                "check": "candidate_lineage_trace_numeric_ranges",
                "path": str(path.as_posix()),
                "passed": all(
                    int(float(row["selection_rank"])) >= 1
                    and int(float(row["covered_zone_count"])) >= 0
                    and float(row["covered_demand_weight"]) >= 0
                    and float(row["scenario_candidate_cost"]) >= 0
                    for row in rows
                ),
                "detail": "rank, coverage, and cost fields checked",
            },
            {
                "check": "candidate_lineage_trace_no_build_language",
                "path": str(path.as_posix()),
                "passed": not any(("build" + " now") in row.get("allowed_use_note", "").lower() or ("depl" + "oy") in row.get("allowed_use_note", "").lower() for row in rows),
                "detail": "lineage output uses diligence language",
            },
        ]
    )
    return checks


def validate_optional_optimization_zone_trace_tile_smoke() -> list[dict]:
    path = CLEAN_DIR.parent / "marts" / "fact_optimization_zone_trace_tile_smoke.csv"
    if not path.exists():
        return []
    checks = []
    checks.extend(
        validate_csv_required_fields(
            path,
            [
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
            ],
            not_blank_fields=[
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
            ],
        )
    )
    rows = read_csv_rows(path)
    trace_ids = {row["zone_trace_id"] for row in rows}
    selected_keys = {
        (row["scenario_id"], row["method_id"], row["candidate_site_id"])
        for row in read_csv_rows(CLEAN_DIR.parent / "marts" / "fact_optimization_selected_sites_tile_smoke.csv")
    }
    coverage_keys = {
        (row["candidate_site_id"], row["demand_zone_id"], row["coverage_radius_km"])
        for row in read_csv_rows(CLEAN_DIR.parent / "marts" / "fact_candidate_zone_coverage_tile_smoke.csv")
        if int(float(row.get("pair_eligible_flag") or 0)) == 1
    }
    checks.extend(
        [
            {
                "check": "optimization_zone_trace_grain_unique",
                "path": str(path.as_posix()),
                "passed": len(trace_ids) == len(rows),
                "detail": "one trace row per scenario, method, selected candidate, and demand zone",
            },
            {
                "check": "optimization_zone_trace_selected_site_fk",
                "path": str(path.as_posix()),
                "passed": {
                    (row["scenario_id"], row["method_id"], row["candidate_site_id"])
                    for row in rows
                }.issubset(selected_keys),
                "detail": f"{len(selected_keys)} selected scenario-method-candidate keys",
            },
            {
                "check": "optimization_zone_trace_coverage_fk",
                "path": str(path.as_posix()),
                "passed": {
                    (row["candidate_site_id"], row["demand_zone_id"], row["coverage_radius_km"])
                    for row in rows
                }.issubset(coverage_keys),
                "detail": f"{len(coverage_keys)} eligible candidate-zone-radius coverage keys",
            },
            {
                "check": "optimization_zone_trace_numeric_ranges",
                "path": str(path.as_posix()),
                "passed": all(
                    int(float(row["selection_rank"])) >= 1
                    and int(float(row["zone_coverage_rank"])) >= 1
                    and float(row["distance_km"]) >= 0
                    and float(row["zone_demand_weight"]) >= 0
                    and 0 <= float(row["zone_demand_share_of_candidate"]) <= 1
                    for row in rows
                ),
                "detail": "rank, distance, demand, and share fields checked",
            },
            {
                "check": "optimization_zone_trace_no_build_language",
                "path": str(path.as_posix()),
                "passed": not any(("build" + " now") in row.get("allowed_use_note", "").lower() or ("depl" + "oy") in row.get("allowed_use_note", "").lower() for row in rows),
                "detail": "zone trace output uses diligence language",
            },
        ]
    )
    return checks


def validate_optional_optimization_country_diagnostics_tile_smoke() -> list[dict]:
    path = CLEAN_DIR.parent / "marts" / "mart_optimization_country_diagnostics_tile_smoke.csv"
    if not path.exists():
        return []
    checks = []
    checks.extend(
        validate_csv_required_fields(
            path,
            [
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
            ],
            not_blank_fields=[
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
            ],
        )
    )
    rows = read_csv_rows(path)
    row_ids = {row["scenario_method_country_id"] for row in rows}
    method_keys = {(row["scenario_id"], row["method_id"]) for row in read_csv_rows(CLEAN_DIR.parent / "marts" / "mart_optimization_results_tile_smoke.csv")}
    checks.extend(
        [
            {
                "check": "optimization_country_diagnostics_grain_unique",
                "path": str(path.as_posix()),
                "passed": len(row_ids) == len(rows),
                "detail": "one country diagnostic row per scenario, method, and country",
            },
            {
                "check": "optimization_country_diagnostics_method_fk",
                "path": str(path.as_posix()),
                "passed": {(row["scenario_id"], row["method_id"]) for row in rows}.issubset(method_keys),
                "detail": f"{len(method_keys)} known scenario-method optimization rows",
            },
            {
                "check": "optimization_country_diagnostics_numeric_ranges",
                "path": str(path.as_posix()),
                "passed": all(
                    int(float(row["selected_candidate_count"])) >= 0
                    and int(float(row["covered_zone_count"])) >= 0
                    and float(row["covered_demand_weight"]) >= 0
                    and 0 <= float(row["covered_demand_share_of_method"]) <= 1
                    and float(row["total_candidate_cost"]) >= 0
                    and 0 <= float(row["candidate_cost_share_of_method"]) <= 1
                    for row in rows
                ),
                "detail": "country diagnostic count, coverage, cost, and share fields checked",
            },
            {
                "check": "optimization_country_diagnostics_no_build_language",
                "path": str(path.as_posix()),
                "passed": not any(("build" + " now") in row.get("allowed_use_note", "").lower() or ("depl" + "oy") in row.get("allowed_use_note", "").lower() for row in rows),
                "detail": "country diagnostics use diligence language",
            },
            {
                "check": "optimization_country_diagnostics_concentration_status",
                "path": str(path.as_posix()),
                "passed": country_concentration_statuses_match_threshold(rows),
                "detail": "country concentration warning status matches the configured threshold",
            },
            {
                "check": "optimization_country_diagnostics_concentration_review",
                "path": str(path.as_posix()),
                "passed": True,
                "detail": country_concentration_review(rows)[1],
            },
            {
                "check": "optimization_country_diagnostics_share_sum",
                "path": str(path.as_posix()),
                "passed": country_share_sums_valid(rows),
                "detail": "country demand shares sum to 1.0 per scenario-method when traced demand is positive",
            },
        ]
    )
    return checks


def country_concentration_review(rows: list[dict], *, warning_threshold: float = 0.75) -> tuple[int, str]:
    warning_count = sum(1 for row in rows if safe_float(row.get("covered_demand_share_of_method")) >= warning_threshold)
    if warning_count:
        return (
            warning_count,
            f"{warning_count} warning-grade country concentration row(s); this does not fail the gate because concentration can be a valid optimization outcome.",
        )
    return (0, "No warning-grade country concentration rows; review still remains analytical, not a rollout recommendation.")


def country_concentration_statuses_match_threshold(rows: list[dict], *, warning_threshold: float = 0.75) -> bool:
    for row in rows:
        share = safe_float(row.get("covered_demand_share_of_method"))
        expected = "warning" if share >= warning_threshold else "pass"
        if row.get("concentration_status") != expected:
            return False
    return True


def country_share_sums_valid(rows: list[dict], *, tolerance: float = 0.000005) -> bool:
    by_method: dict[str, float] = {}
    for row in rows:
        scenario_method_id = row.get("scenario_method_id") or f"{row.get('scenario_id')}|{row.get('method_id')}"
        by_method[scenario_method_id] = by_method.get(scenario_method_id, 0.0) + safe_float(row.get("covered_demand_share_of_method"))
    return all(abs(total - 1.0) <= tolerance or abs(total) <= tolerance for total in by_method.values())


def safe_float(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def validate_optional_method_comparison_narrative_tile_smoke() -> list[dict]:
    path = CLEAN_DIR.parent / "marts" / "mart_method_comparison_narrative_tile_smoke.csv"
    if not path.exists():
        return []
    checks = []
    checks.extend(
        validate_csv_required_fields(
            path,
            [
                "scenario_id",
                "baseline_method_id",
                "best_coverage_method_id",
                "lowest_cost_method_id",
                "baseline_covered_demand_weight",
                "mclp_covered_demand_weight",
                "min_cost_covered_demand_weight",
                "mclp_coverage_uplift_pct",
                "min_cost_saving_pct",
                "comparison_readout",
                "analyst_takeaway",
                "allowed_use_note",
                "proxy_assumption_label",
            ],
            not_blank_fields=[
                "scenario_id",
                "baseline_method_id",
                "best_coverage_method_id",
                "lowest_cost_method_id",
                "comparison_readout",
                "analyst_takeaway",
                "allowed_use_note",
                "proxy_assumption_label",
            ],
        )
    )
    rows = read_csv_rows(path)
    scenario_ids = {row["scenario_id"] for row in rows}
    known_scenario_ids = {row["scenario_id"] for row in read_csv_rows(CLEAN_DIR.parent / "marts" / "mart_optimization_results_tile_smoke.csv")}
    checks.extend(
        [
            {
                "check": "method_comparison_narrative_grain_unique",
                "path": str(path.as_posix()),
                "passed": len(scenario_ids) == len(rows),
                "detail": "one method-comparison narrative row per scenario",
            },
            {
                "check": "method_comparison_narrative_scenario_fk",
                "path": str(path.as_posix()),
                "passed": scenario_ids.issubset(known_scenario_ids),
                "detail": f"{len(known_scenario_ids)} known optimization scenarios",
            },
            {
                "check": "method_comparison_narrative_numeric_ranges",
                "path": str(path.as_posix()),
                "passed": all(
                    float(row["baseline_covered_demand_weight"]) >= 0
                    and float(row["mclp_covered_demand_weight"]) >= 0
                    and float(row["min_cost_covered_demand_weight"]) >= 0
                    and 0 <= float(row.get("dominant_coverage_country_share") or 0) <= 1
                    for row in rows
                ),
                "detail": "covered demand and dominant-country share fields checked",
            },
            {
                "check": "method_comparison_narrative_no_build_language",
                "path": str(path.as_posix()),
                "passed": not any(("build" + " now") in row.get("allowed_use_note", "").lower() or ("depl" + "oy") in row.get("allowed_use_note", "").lower() for row in rows),
                "detail": "method comparison narrative uses diligence language",
            },
        ]
    )
    return checks


def validate_optional_business_scenario_library_tile_smoke() -> list[dict]:
    path = CLEAN_DIR.parent / "marts" / "mart_business_scenario_library_tile_smoke.csv"
    if not path.exists():
        return []
    checks = []
    checks.extend(
        validate_csv_required_fields(
            path,
            [
                "business_scenario_id",
                "business_scenario_name",
                "business_question",
                "scenario_id",
                "method_id",
                "solver_status",
                "primary_metric",
                "primary_metric_value",
                "decision_readout",
                "recommended_next_action",
                "limitation_note",
                "allowed_use_note",
                "proxy_assumption_label",
            ],
            not_blank_fields=[
                "business_scenario_id",
                "business_scenario_name",
                "business_question",
                "scenario_id",
                "method_id",
                "solver_status",
                "primary_metric",
                "primary_metric_value",
                "decision_readout",
                "recommended_next_action",
                "limitation_note",
                "allowed_use_note",
                "proxy_assumption_label",
            ],
        )
    )
    rows = read_csv_rows(path)
    scenario_ids = {row["scenario_id"] for row in read_csv_rows(CLEAN_DIR.parent / "marts" / "mart_optimization_results_tile_smoke.csv")}
    scenario_ids.update(row["scenario_id"] for row in read_csv_rows(CLEAN_DIR.parent / "marts" / "mart_optimization_sensitivity_tile_smoke.csv"))
    business_ids = {row["business_scenario_id"] for row in rows}
    checks.extend(
        [
            {
                "check": "business_scenario_library_minimum_count",
                "path": str(path.as_posix()),
                "passed": len(rows) >= 5,
                "detail": f"{len(rows)} business scenarios",
            },
            {
                "check": "business_scenario_library_grain_unique",
                "path": str(path.as_posix()),
                "passed": len(business_ids) == len(rows),
                "detail": "one row per business scenario",
            },
            {
                "check": "business_scenario_library_scenario_fk",
                "path": str(path.as_posix()),
                "passed": {row["scenario_id"] for row in rows}.issubset(scenario_ids),
                "detail": f"{len(scenario_ids)} known optimization scenario ids",
            },
            {
                "check": "business_scenario_library_metric_nonnegative",
                "path": str(path.as_posix()),
                "passed": all(float(row["primary_metric_value"]) >= 0 for row in rows),
                "detail": "primary metric values checked",
            },
            {
                "check": "business_scenario_library_limitations_present",
                "path": str(path.as_posix()),
                "passed": all("public proxy" in row["limitation_note"].lower() for row in rows),
                "detail": "public-proxy limitation language checked",
            },
            {
                "check": "business_scenario_library_no_build_language",
                "path": str(path.as_posix()),
                "passed": not any(("build" + " now") in row.get("allowed_use_note", "").lower() or ("depl" + "oy") in row.get("allowed_use_note", "").lower() for row in rows),
                "detail": "business scenario output uses diligence language",
            },
        ]
    )
    return checks


def validate_optional_pipeline_snapshot_metrics_tile_smoke() -> list[dict]:
    path = CLEAN_DIR.parent / "marts" / "mart_pipeline_snapshot_metrics_tile_smoke.csv"
    if not path.exists():
        return []
    checks = []
    checks.extend(
        validate_csv_required_fields(
            path,
            ["snapshot_id", "metric_name", "metric_value", "metric_unit", "source_table", "allowed_use_note", "proxy_assumption_label"],
            not_blank_fields=["snapshot_id", "metric_name", "metric_value", "metric_unit", "source_table", "allowed_use_note", "proxy_assumption_label"],
        )
    )
    rows = read_csv_rows(path)
    metric_names = {row["metric_name"] for row in rows}
    required_metrics = {"candidate_site_count", "coverage_row_count", "eligible_coverage_pair_count", "baseline_score_row_count", "optimization_summary_row_count"}
    checks.extend(
        [
            {
                "check": "pipeline_snapshot_metrics_required_set",
                "path": str(path.as_posix()),
                "passed": required_metrics.issubset(metric_names),
                "detail": f"{len(metric_names)} metrics present",
            },
            {
                "check": "pipeline_snapshot_metrics_grain_unique",
                "path": str(path.as_posix()),
                "passed": len({(row["snapshot_id"], row["metric_name"]) for row in rows}) == len(rows),
                "detail": "one row per snapshot and metric",
            },
            {
                "check": "pipeline_snapshot_metrics_nonnegative",
                "path": str(path.as_posix()),
                "passed": all(float(row["metric_value"]) >= 0 for row in rows),
                "detail": "metric values checked",
            },
        ]
    )
    return checks


def validate_optional_pipeline_snapshot_drift_tile_smoke() -> list[dict]:
    path = CLEAN_DIR.parent / "marts" / "mart_pipeline_snapshot_drift_tile_smoke.csv"
    if not path.exists():
        return []
    checks = []
    checks.extend(
        validate_csv_required_fields(
            path,
            [
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
            ],
            not_blank_fields=[
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
            ],
        )
    )
    rows = read_csv_rows(path)
    checks.extend(
        [
            {
                "check": "pipeline_snapshot_drift_status_values",
                "path": str(path.as_posix()),
                "passed": all(row["drift_status"] in {"pass", "warning", "fail"} for row in rows),
                "detail": "drift statuses checked",
            },
            {
                "check": "pipeline_snapshot_drift_threshold_order",
                "path": str(path.as_posix()),
                "passed": all(float(row["warning_threshold_pct"]) <= float(row["fail_threshold_pct"]) for row in rows),
                "detail": "warning and fail thresholds checked",
            },
            {
                "check": "pipeline_snapshot_drift_no_build_language",
                "path": str(path.as_posix()),
                "passed": not any(("build" + " now") in row.get("allowed_use_note", "").lower() or ("depl" + "oy") in row.get("allowed_use_note", "").lower() for row in rows),
                "detail": "snapshot drift output uses review language",
            },
        ]
    )
    return checks


def validate_optional_pipeline_snapshot_certification_tile_smoke() -> list[dict]:
    reference_path = CLEAN_DIR.parent / "marts" / "mart_pipeline_snapshot_metrics_reference_tile_smoke.csv"
    log_path = CLEAN_DIR.parent / "marts" / "mart_pipeline_snapshot_certifications_tile_smoke.csv"
    if not reference_path.exists() and not log_path.exists():
        return []
    checks = []
    checks.extend(
        validate_csv_required_fields(
            reference_path,
            ["snapshot_id", "metric_name", "metric_value", "metric_unit", "source_table", "allowed_use_note", "proxy_assumption_label"],
            not_blank_fields=["snapshot_id", "metric_name", "metric_value", "metric_unit", "source_table", "allowed_use_note", "proxy_assumption_label"],
        )
    )
    checks.extend(
        validate_csv_required_fields(
            log_path,
            ["reference_snapshot_id", "source_snapshot_id", "certification_status", "reviewer", "certification_note", "metric_count", "allowed_use_note", "proxy_assumption_label"],
            not_blank_fields=["reference_snapshot_id", "source_snapshot_id", "certification_status", "reviewer", "certification_note", "metric_count", "allowed_use_note", "proxy_assumption_label"],
        )
    )
    if not (reference_path.exists() and log_path.exists()):
        return checks
    reference_rows = read_csv_rows(reference_path)
    log_rows = read_csv_rows(log_path)
    reference_snapshot_ids = {row["snapshot_id"] for row in reference_rows}
    checks.extend(
        [
            {
                "check": "pipeline_snapshot_reference_grain_unique",
                "path": str(reference_path.as_posix()),
                "passed": len({(row["snapshot_id"], row["metric_name"]) for row in reference_rows}) == len(reference_rows),
                "detail": "one reference row per snapshot and metric",
            },
            {
                "check": "pipeline_snapshot_reference_metric_values_nonnegative",
                "path": str(reference_path.as_posix()),
                "passed": all(float(row["metric_value"]) >= 0 for row in reference_rows),
                "detail": "reference metric values checked",
            },
            {
                "check": "pipeline_snapshot_certification_status_values",
                "path": str(log_path.as_posix()),
                "passed": all(row["certification_status"] in {"staged_for_review", "certified", "rejected"} for row in log_rows),
                "detail": "certification statuses checked",
            },
            {
                "check": "pipeline_snapshot_certification_reference_fk",
                "path": str(log_path.as_posix()),
                "passed": {row["reference_snapshot_id"] for row in log_rows}.issubset(reference_snapshot_ids),
                "detail": f"{len(reference_snapshot_ids)} reference snapshot ids",
            },
            {
                "check": "pipeline_snapshot_certification_metric_count_matches",
                "path": str(log_path.as_posix()),
                "passed": all(int(row["metric_count"]) == sum(1 for reference in reference_rows if reference["snapshot_id"] == row["reference_snapshot_id"]) for row in log_rows),
                "detail": "certification metric counts checked",
            },
        ]
    )
    return checks


def diagnostics_values_match_summary(diagnostics_rows: list[dict], summary_by_key: dict[tuple[str, str], dict]) -> bool:
    accepted_statuses = {"benchmark_feasible", "optimal_milp", "optimal_min_cost", "optimal_shortlist"}
    for row in diagnostics_rows:
        summary = summary_by_key.get((row["scenario_id"], row["method_id"]))
        if not summary:
            return False
        constraint_name = row["constraint_name"]
        if constraint_name == "budget":
            lhs = float(summary["total_candidate_cost"])
            rhs = float(summary["budget"])
            if not numeric_values_match(row, lhs, rhs, rhs - lhs):
                return False
        elif constraint_name == "site_count":
            lhs = float(summary["selected_candidate_count"])
            rhs = float(summary["k"])
            if not numeric_values_match(row, lhs, rhs, rhs - lhs):
                return False
        elif constraint_name == "objective_nonnegative":
            lhs = float(summary["objective_covered_demand_weight"])
            if not numeric_values_match(row, lhs, 0.0, lhs):
                return False
        elif constraint_name == "coverage_floor":
            lhs = float(summary["objective_covered_demand_weight"])
            rhs = float(summary.get("coverage_floor_demand_weight") or 0)
            if not numeric_values_match(row, lhs, rhs, lhs - rhs):
                return False
        elif constraint_name == "solver_status":
            rhs_values = set(row.get("rhs_value", "").split("|"))
            if row.get("lhs_value") != summary.get("solver_status") or rhs_values != accepted_statuses or row.get("slack_value", ""):
                return False
        else:
            return False
    return True


def numeric_values_match(row: dict, lhs: float, rhs: float, slack: float) -> bool:
    return (
        abs(float(row["lhs_value"]) - lhs) < 0.000001
        and abs(float(row["rhs_value"]) - rhs) < 0.000001
        and abs(float(row["slack_value"]) - slack) < 0.000001
    )


def load_license_ids() -> set[str]:
    manifest_path = CONFIG_DIR / "license_manifest.json"
    if not manifest_path.exists():
        return set()
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return set()
    return {item.get("source_id") for item in payload if item.get("source_id")}


def load_pilot_countries() -> list[str]:
    scope_path = CONFIG_DIR / "pilot_scope.json"
    if not scope_path.exists():
        return []
    try:
        payload = json.loads(scope_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return [item for item in payload.get("pilot_countries", []) if item]


def summarize_checks(checks: list[dict]) -> dict:
    failed = [check for check in checks if not check["passed"]]
    return {
        "passed": len(failed) == 0,
        "check_count": len(checks),
        "failure_count": len(failed),
        "failures": failed,
        "checks": checks,
    }
