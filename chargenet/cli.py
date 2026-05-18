from __future__ import annotations

import argparse
import json

from .baseline import build_baseline_scores_tile_smoke, build_baseline_sensitivity_tile_smoke
from .coverage import build_tile_smoke_coverage
from .dq import write_quality_report
from .ingest import ingest_all_samples
from .ingest import ingest_eurostat_population_pilot, ingest_gisco_nuts_level3
from .pilot import build_pilot_nuts3_demand_zones
from .dictionary import write_data_dictionary
from .paths import ensure_project_dirs
from .exports import write_powerbi_exports
from .osm_plan import build_osm_tile_plan
from .osm_extract import DEFAULT_EXTRACTS, DEFAULT_PILOT_COUNTRIES, current_osm_fetch_gate, current_osm_tile_progress, rebuild_osm_tile_execution_log_all, run_osm_pilot_smoke, run_osm_tile_batch, run_osm_tile_smoke
from .osm_clean import build_candidate_sites_from_tile_smoke, build_existing_chargers_from_tile_smoke
from .optimization import build_optimization_constraint_diagnostics_tile_smoke, build_optimization_results_tile_smoke
from .scenarios import build_scenario_inputs_sample, build_scenario_inputs_tile_smoke, write_service_radius_config
from .sources import write_license_manifest
from .transform import build_all_clean_samples, build_candidate_zone_coverage_sample


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="chargenet", description="ChargeNet Europe public-data pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init", help="Create data/config/report directories and license manifest")
    subparsers.add_parser("ingest-samples", help="Fetch small reproducible raw source samples")
    subparsers.add_parser("build-clean-samples", help="Build clean sample CSVs from raw snapshots")
    subparsers.add_parser("build-coverage-sample", help="Build sample candidate-zone coverage mart")
    subparsers.add_parser("build-scenario-inputs-sample", help="Build sample scenario input mart")
    subparsers.add_parser("write-data-dictionary", help="Write sample data dictionary")
    subparsers.add_parser("validate", help="Run sample data quality checks")
    subparsers.add_parser("ingest-gisco-nuts3", help="Fetch GISCO NUTS 2024 level-3 geometry for pilot demand-zone build")
    subparsers.add_parser("ingest-eurostat-population-pilot", help="Fetch Eurostat 2025 regional population for pilot NUTS3 join")
    subparsers.add_parser("build-pilot-nuts3", help="Build pilot-country NUTS3 demand-zone table, joining Eurostat population when available")
    subparsers.add_parser("export-powerbi-sample", help="Write relationship-ready Power BI CSV exports from current sample and pilot tables")
    subparsers.add_parser("build-osm-tile-plan", help="Build a planned-not-run Overpass tile job matrix from pilot NUTS3 bboxes")
    smoke_parser = subparsers.add_parser("run-osm-tile-smoke", help="Run a tiny, rate-limited subset of planned OSM tile jobs")
    smoke_parser.add_argument("--max-jobs", type=int, default=1, help="Number of tile jobs to run, hard-limited to 1..5")
    smoke_parser.add_argument("--country", default="BE", help="Country filter for smoke run")
    smoke_parser.add_argument("--extract", default="charging_stations", help="Extract slug filter for smoke run")
    smoke_parser.add_argument("--delay-seconds", type=float, default=2.0, help="Delay between tile requests")
    smoke_parser.add_argument("--output-limit", type=int, default=25, help="Overpass output limit per tile")
    pilot_smoke_parser = subparsers.add_parser("run-osm-pilot-smoke", help="Run controlled OSM smoke jobs across pilot countries and extract types")
    pilot_smoke_parser.add_argument("--countries", default=",".join(DEFAULT_PILOT_COUNTRIES), help="Comma-separated country codes")
    pilot_smoke_parser.add_argument("--extracts", default=",".join(DEFAULT_EXTRACTS), help="Comma-separated OSM extract slugs")
    pilot_smoke_parser.add_argument("--max-jobs-per-combo", type=int, default=1, help="Jobs per country/extract combo, hard-limited to 1..5")
    pilot_smoke_parser.add_argument("--delay-seconds", type=float, default=2.0, help="Delay between tile requests")
    pilot_smoke_parser.add_argument("--output-limit", type=int, default=25, help="Overpass output limit per tile")
    pilot_smoke_parser.add_argument("--dry-run", action="store_true", help="Show selected tile jobs without calling Overpass")
    batch_parser = subparsers.add_parser("run-osm-tile-batch", help="Run or dry-run a resumable batch of planned OSM tile jobs")
    batch_parser.add_argument("--max-jobs", type=int, default=9, help="Number of tile jobs to select, hard-limited to 1..25; default keeps three-extract tile triplets aligned")
    batch_parser.add_argument("--countries", default=",".join(DEFAULT_PILOT_COUNTRIES), help="Comma-separated country codes; empty means all")
    batch_parser.add_argument("--extracts", default=",".join(DEFAULT_EXTRACTS), help="Comma-separated OSM extract slugs; empty means all")
    batch_parser.add_argument("--delay-seconds", type=float, default=2.0, help="Delay between tile requests")
    batch_parser.add_argument("--output-limit", type=int, default=25, help="Overpass output limit per tile")
    batch_parser.add_argument("--timeout-seconds", type=int, default=60, help="Per-request timeout")
    batch_parser.add_argument("--execute", action="store_true", help="Actually call Overpass; default is dry-run planning only")
    batch_parser.add_argument("--skip-quality-report", action="store_true", help="Skip the full quality report side effect for fetch-only windows")
    progress_parser = subparsers.add_parser("osm-tile-progress", help="Summarize current OSM tile-plan progress from cumulative logs")
    progress_parser.add_argument("--skip-quality-report", action="store_true", help="Skip the full quality report side effect for fetch-only windows")
    gate_parser = subparsers.add_parser("osm-fetch-gate", help="Run lightweight raw/log validation for fetch-only OSM windows")
    gate_parser.add_argument("--latest-only", action="store_true", help="Validate only the latest tile execution log instead of the cumulative log")
    gate_parser.add_argument("--output-limit", type=int, default=20, help="Element count treated as an Overpass cap hit")
    rebuild_parser = subparsers.add_parser("rebuild-osm-tile-log", help="Rebuild cumulative OSM tile execution log from run folders")
    rebuild_parser.add_argument("--skip-quality-report", action="store_true", help="Skip the full quality report side effect for fetch-only windows")
    subparsers.add_parser("build-osm-tile-smoke-clean", help="Build a clean charger table from the latest OSM tile smoke run")
    subparsers.add_parser("build-osm-candidate-smoke-clean", help="Build a clean candidate-site table from the latest OSM tile smoke run")
    subparsers.add_parser("build-tile-smoke-coverage", help="Build candidate-zone-radius coverage for smoke candidates against pilot NUTS3 demand zones")
    subparsers.add_parser("build-tile-smoke-scenario-inputs", help="Build scenario inputs for smoke candidates and pilot NUTS3 demand zones")
    subparsers.add_parser("build-baseline-scores-tile-smoke", help="Build baseline diligence-shortlist scores for tile-smoke candidates")
    subparsers.add_parser("build-baseline-sensitivity-tile-smoke", help="Build baseline weight-sensitivity mart for tile-smoke candidates")
    subparsers.add_parser("build-optimization-results-tile-smoke", help="Build smoke-scope maximal coverage optimization results")
    subparsers.add_parser("build-optimization-diagnostics-tile-smoke", help="Build smoke-scope optimization constraint diagnostics")
    subparsers.add_parser("build-from-existing-samples", help="Rebuild clean/mart/report artifacts from existing raw samples without network fetches")
    subparsers.add_parser("run-phase3-sample", help="Run init, ingest, clean, coverage, and validation")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "init":
        ensure_project_dirs()
        manifest = write_license_manifest()
        radius_config = write_service_radius_config()
        print(json.dumps({"created": [str(manifest), str(radius_config)]}, indent=2))
        return 0

    if args.command == "ingest-samples":
        paths = ingest_all_samples()
        print(json.dumps({"raw_snapshots": [str(path) for path in paths]}, indent=2))
        return 0

    if args.command == "build-clean-samples":
        paths = build_all_clean_samples()
        print(json.dumps({"clean_outputs": [str(path) for path in paths]}, indent=2))
        return 0

    if args.command == "build-coverage-sample":
        path = build_candidate_zone_coverage_sample()
        print(json.dumps({"mart_output": str(path)}, indent=2))
        return 0

    if args.command == "build-scenario-inputs-sample":
        path = build_scenario_inputs_sample()
        print(json.dumps({"mart_output": str(path)}, indent=2))
        return 0

    if args.command == "write-data-dictionary":
        path = write_data_dictionary()
        print(json.dumps({"data_dictionary": str(path)}, indent=2))
        return 0

    if args.command == "validate":
        path = write_quality_report()
        print(json.dumps({"quality_report": str(path)}, indent=2))
        report = json.loads(path.read_text(encoding="utf-8"))
        return 0 if report.get("raw", {}).get("passed") and report.get("clean", {}).get("passed") else 1

    if args.command == "ingest-gisco-nuts3":
        path = ingest_gisco_nuts_level3()
        print(json.dumps({"raw_snapshot": str(path)}, indent=2))
        return 0

    if args.command == "ingest-eurostat-population-pilot":
        path = ingest_eurostat_population_pilot()
        print(json.dumps({"raw_snapshot": str(path)}, indent=2))
        return 0

    if args.command == "build-pilot-nuts3":
        path = build_pilot_nuts3_demand_zones()
        data_dictionary = write_data_dictionary()
        report = write_quality_report()
        print(json.dumps({"clean_output": str(path), "data_dictionary": str(data_dictionary), "quality_report": str(report)}, indent=2))
        return 0

    if args.command == "export-powerbi-sample":
        paths = write_powerbi_exports()
        report = write_quality_report()
        print(json.dumps({"powerbi_exports": [str(path) for path in paths], "quality_report": str(report)}, indent=2))
        return 0

    if args.command == "build-osm-tile-plan":
        path = build_osm_tile_plan()
        report = write_quality_report()
        print(json.dumps({"osm_tile_plan": str(path), "quality_report": str(report)}, indent=2))
        return 0

    if args.command == "run-osm-tile-smoke":
        result = run_osm_tile_smoke(
            max_jobs=args.max_jobs,
            country_code=args.country,
            extract_slug=args.extract,
            delay_seconds=args.delay_seconds,
            output_limit=args.output_limit,
        )
        report = write_quality_report()
        print(json.dumps({"osm_tile_smoke": result, "quality_report": str(report)}, indent=2))
        return 0

    if args.command == "run-osm-pilot-smoke":
        result = run_osm_pilot_smoke(
            countries=parse_csv_arg(args.countries),
            extracts=parse_csv_arg(args.extracts),
            max_jobs_per_combo=args.max_jobs_per_combo,
            delay_seconds=args.delay_seconds,
            output_limit=args.output_limit,
            dry_run=args.dry_run,
        )
        report = write_quality_report()
        print(json.dumps({"osm_pilot_smoke": result, "quality_report": str(report)}, indent=2))
        return 0

    if args.command == "run-osm-tile-batch":
        result = run_osm_tile_batch(
            countries=parse_csv_arg(args.countries),
            extracts=parse_csv_arg(args.extracts),
            max_jobs=args.max_jobs,
            delay_seconds=args.delay_seconds,
            output_limit=args.output_limit,
            timeout_seconds=args.timeout_seconds,
            dry_run=not args.execute,
        )
        payload = {"osm_tile_batch": result}
        if not args.skip_quality_report:
            payload["quality_report"] = str(write_quality_report())
        print(json.dumps(payload, indent=2))
        if args.execute and result.get("failed_jobs", 0):
            return 1
        return 0

    if args.command == "osm-tile-progress":
        progress = current_osm_tile_progress()
        payload = {"osm_tile_progress": progress}
        if not args.skip_quality_report:
            payload["quality_report"] = str(write_quality_report())
        print(json.dumps(payload, indent=2))
        return 0

    if args.command == "osm-fetch-gate":
        gate = current_osm_fetch_gate(latest_only=args.latest_only, output_limit=args.output_limit)
        print(json.dumps({"osm_fetch_gate": gate}, indent=2))
        return 0 if gate.get("passed") else 1

    if args.command == "rebuild-osm-tile-log":
        path = rebuild_osm_tile_execution_log_all()
        payload = {"osm_tile_log": str(path)}
        if not args.skip_quality_report:
            payload["quality_report"] = str(write_quality_report())
        print(json.dumps(payload, indent=2))
        return 0

    if args.command == "build-osm-tile-smoke-clean":
        path = build_existing_chargers_from_tile_smoke()
        report = write_quality_report()
        print(json.dumps({"clean_output": str(path), "quality_report": str(report)}, indent=2))
        return 0

    if args.command == "build-osm-candidate-smoke-clean":
        path = build_candidate_sites_from_tile_smoke()
        report = write_quality_report()
        print(json.dumps({"clean_output": str(path), "quality_report": str(report)}, indent=2))
        return 0

    if args.command == "build-tile-smoke-coverage":
        path = build_tile_smoke_coverage()
        report = write_quality_report()
        print(json.dumps({"mart_output": str(path), "quality_report": str(report)}, indent=2))
        return 0

    if args.command == "build-tile-smoke-scenario-inputs":
        path = build_scenario_inputs_tile_smoke()
        report = write_quality_report()
        print(json.dumps({"mart_output": str(path), "quality_report": str(report)}, indent=2))
        return 0

    if args.command == "build-baseline-scores-tile-smoke":
        path = build_baseline_scores_tile_smoke()
        report = write_quality_report()
        print(json.dumps({"mart_output": str(path), "quality_report": str(report)}, indent=2))
        return 0

    if args.command == "build-baseline-sensitivity-tile-smoke":
        path = build_baseline_sensitivity_tile_smoke()
        data_dictionary = write_data_dictionary()
        report = write_quality_report()
        print(json.dumps({"mart_output": str(path), "data_dictionary": str(data_dictionary), "quality_report": str(report)}, indent=2))
        return 0

    if args.command == "build-optimization-results-tile-smoke":
        paths = build_optimization_results_tile_smoke()
        data_dictionary = write_data_dictionary()
        report = write_quality_report()
        print(json.dumps({"mart_outputs": [str(path) for path in paths], "data_dictionary": str(data_dictionary), "quality_report": str(report)}, indent=2))
        return 0

    if args.command == "build-optimization-diagnostics-tile-smoke":
        path = build_optimization_constraint_diagnostics_tile_smoke()
        data_dictionary = write_data_dictionary()
        report = write_quality_report()
        print(json.dumps({"mart_output": str(path), "data_dictionary": str(data_dictionary), "quality_report": str(report)}, indent=2))
        return 0

    if args.command == "build-from-existing-samples":
        manifest = write_license_manifest()
        radius_config = write_service_radius_config()
        clean_paths = build_all_clean_samples()
        scenario_inputs = build_scenario_inputs_sample()
        data_dictionary = write_data_dictionary()
        report = write_quality_report()
        print(
            json.dumps(
                {
                    "license_manifest": str(manifest),
                    "service_radius_config": str(radius_config),
                    "clean_outputs": [str(path) for path in clean_paths],
                    "scenario_inputs": str(scenario_inputs),
                    "data_dictionary": str(data_dictionary),
                    "quality_report": str(report),
                },
                indent=2,
            )
        )
        return 0

    if args.command == "run-phase3-sample":
        ensure_project_dirs()
        manifest = write_license_manifest()
        radius_config = write_service_radius_config()
        raw_paths = ingest_all_samples()
        clean_paths = build_all_clean_samples()
        scenario_inputs = build_scenario_inputs_sample()
        data_dictionary = write_data_dictionary()
        report = write_quality_report()
        print(
            json.dumps(
                {
                    "license_manifest": str(manifest),
                    "service_radius_config": str(radius_config),
                    "raw_snapshots": [str(path) for path in raw_paths],
                    "clean_outputs": [str(path) for path in clean_paths],
                    "scenario_inputs": str(scenario_inputs),
                    "data_dictionary": str(data_dictionary),
                    "quality_report": str(report),
                },
                indent=2,
            )
        )
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


def parse_csv_arg(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


if __name__ == "__main__":
    raise SystemExit(main())
