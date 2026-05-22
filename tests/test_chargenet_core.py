from __future__ import annotations

import csv
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from chargenet.ids import candidate_site_id, demand_zone_id, osm_object_id, scenario_id
from chargenet.app_summary import build_candidate_drilldown, build_country_concentration_guardrails, build_decision_flags, build_metric_glossary, build_optimization_takeaways, build_recruiter_kpis, build_scenario_cards, build_top_candidate_insights, build_weight_set_comparison, release_gate_headline
from chargenet.baseline import SENSITIVITY_WEIGHT_SETS, action_bucket, build_baseline_sensitivity_tile_smoke, clamp, compute_weighted_score, validate_weight_set
from chargenet.completion_gate import completion_gate_passed, evaluate_completion_gate, private_history_row
from chargenet.country_diagnostics import build_optimization_country_diagnostics_tile_smoke
from chargenet.dq import country_concentration_review, diagnostics_values_match_summary, selected_site_reconciliation_errors
from chargenet.drift import build_pipeline_snapshot_metrics_tile_smoke, compare_snapshot_metrics, drift_status, promote_reference_snapshot_metrics_tile_smoke, stage_reference_snapshot_metrics_tile_smoke, threshold_for_metric
from chargenet.lineage import build_candidate_lineage_trace_tile_smoke, build_optimization_zone_trace_tile_smoke
from chargenet.method_comparison import build_method_comparison_narrative_tile_smoke
from chargenet.named_optimization import NAMED_MCLP_METHOD_ID, build_named_optimization_scenario, load_named_scenario_configs, scenario_priority_score
from chargenet.osm_clean import element_coordinate, infer_candidate_site_type
from chargenet.cli import build_parser, main, parse_csv_arg
from chargenet.optimization import MIN_COST_METHOD_ID, SENSITIVITY_MCLP_METHOD_ID, build_optimization_results_tile_smoke, build_optimization_sensitivity_tile_smoke, constraint_diagnostics_rows, coverage_objective, solve_mclp_exact, solve_mclp_pulp, solve_min_cost_coverage_pulp
from chargenet.osm_extract import build_overpass_query, osm_fetch_gate_summary, osm_tile_progress_summary, parse_osm_filter, read_fetched_tile_job_ids, rebuild_osm_tile_execution_log_all, select_batch_jobs, select_jobs, write_log
from chargenet.paths import PROJECT_ROOT
from chargenet.pilot import geometry_bbox_midpoint, iter_lon_lat_pairs, load_eurostat_population_by_geo
from chargenet.portfolio_release import default_portfolio_release_steps, portfolio_release_check_passed, release_gate_pre_sync_passed, run_portfolio_release_check, write_portfolio_release_check
from chargenet.project_status import build_project_status_rows, project_status_passed, write_project_status_report
from chargenet.public_claims import default_public_claim_paths, scan_public_claims, write_public_claim_gate
from chargenet.release_gate import app_data_manifest_summary, evaluate_release_gate, gate_row, write_release_gate_report
from chargenet.scenario_library import build_business_scenario_library_tile_smoke
from chargenet.scenarios import cost_proxy_explanation_rows, estimate_candidate_capex
from chargenet.transform import haversine_km


class ChargeNetCoreTests(unittest.TestCase):
    def test_deterministic_ids(self) -> None:
        self.assertEqual(osm_object_id("node", 123), "osm:node:123")
        self.assertEqual(demand_zone_id("DE212"), "dz:nuts2024:DE212")
        self.assertEqual(candidate_site_id("node", 123), "candidate:osm:node:123")
        self.assertEqual(scenario_id("Base Budget"), "scenario:base-budget")

    def test_haversine_distance_reasonable_for_same_city(self) -> None:
        distance = haversine_km(48.1372, 11.5756, 48.1351, 11.5820)
        self.assertGreater(distance, 0)
        self.assertLess(distance, 1)

    def test_geojson_coordinate_flattening_and_bbox_midpoint(self) -> None:
        geometry = {
            "type": "MultiPolygon",
            "coordinates": [
                [
                    [
                        [4.0, 50.0],
                        [6.0, 50.0],
                        [6.0, 52.0],
                        [4.0, 52.0],
                        [4.0, 50.0],
                    ]
                ]
            ],
        }
        self.assertEqual(len(list(iter_lon_lat_pairs(geometry["coordinates"]))), 5)
        self.assertEqual(geometry_bbox_midpoint(geometry), (51.0, 5.0, 50.0, 4.0, 52.0, 6.0))

    def test_eurostat_population_mapping_from_single_geo_dimension(self) -> None:
        payload = {
            "id": ["freq", "unit", "sex", "age", "geo", "time"],
            "size": [1, 1, 1, 1, 2, 1],
            "value": {"0": 100, "1": 250},
            "dimension": {"geo": {"category": {"index": {"BE100": 0, "DE212": 1}}}},
        }
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "population.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            self.assertEqual(load_eurostat_population_by_geo(path), {"BE100": 100, "DE212": 250})

    def test_osm_filter_and_query_builder(self) -> None:
        self.assertEqual(parse_osm_filter('amenity="charging_station"'), ("amenity", "charging_station"))
        query = build_overpass_query(
            {
                "osm_filter": 'amenity="fuel"',
                "bbox_south": "50.0",
                "bbox_west": "4.0",
                "bbox_north": "51.0",
                "bbox_east": "5.0",
            },
            output_limit=10,
        )
        self.assertIn('node["amenity"="fuel"](50,4,51,5);', query)
        self.assertIn("out body center 10;", query)

    def test_osm_smoke_selection_is_capped_and_filtered(self) -> None:
        rows = [
            {"country_code": "BE", "extract_slug": "charging_stations", "tile_job_id": "a"},
            {"country_code": "DE", "extract_slug": "charging_stations", "tile_job_id": "b"},
            {"country_code": "BE", "extract_slug": "charging_stations", "tile_job_id": "c"},
        ]
        self.assertEqual(select_jobs(rows, max_jobs=1, country_code="BE", extract_slug="charging_stations")[0]["tile_job_id"], "a")
        self.assertEqual(
            select_jobs(rows, max_jobs=1, country_code="BE", extract_slug="charging_stations", exclude_tile_job_ids={"a"})[0]["tile_job_id"],
            "c",
        )
        with self.assertRaises(ValueError):
            select_jobs(rows, max_jobs=6, country_code="BE", extract_slug="charging_stations")

    def test_osm_log_writer_fills_missing_columns(self) -> None:
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "log.csv"
            write_log(path, [{"run_id": "r1", "tile_job_id": "j1"}])
            content = path.read_text(encoding="utf-8")
            self.assertIn("demand_zone_id", content)
            self.assertIn("r1,j1", content)

    def test_osm_fetched_tile_reader_and_csv_arg_parser(self) -> None:
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "log.csv"
            write_log(
                path,
                [
                    {"run_id": "r1", "tile_job_id": "j1", "status": "fetched"},
                    {"run_id": "r2", "tile_job_id": "j2", "status": "fetch_failed"},
                ],
            )
            self.assertEqual(read_fetched_tile_job_ids(path), {"j1"})
        self.assertEqual(parse_csv_arg("BE, DE,,FR "), ["BE", "DE", "FR"])

    def test_osm_batch_cli_default_is_triplet_friendly(self) -> None:
        args = build_parser().parse_args(["run-osm-tile-batch"])
        self.assertEqual(args.max_jobs, 9)

    def test_optimization_sensitivity_cli_exists(self) -> None:
        args = build_parser().parse_args(["build-optimization-sensitivity-tile-smoke"])
        self.assertEqual(args.command, "build-optimization-sensitivity-tile-smoke")

    def test_named_optimization_cli_accepts_scenario_argument(self) -> None:
        args = build_parser().parse_args(["optimize", "--scenario", "highway-corridor-focus"])
        self.assertEqual(args.command, "optimize")
        self.assertEqual(args.scenario, "highway-corridor-focus")

    def test_candidate_lineage_trace_cli_exists(self) -> None:
        args = build_parser().parse_args(["build-candidate-lineage-trace-tile-smoke"])
        self.assertEqual(args.command, "build-candidate-lineage-trace-tile-smoke")

    def test_optimization_zone_trace_cli_exists(self) -> None:
        args = build_parser().parse_args(["build-optimization-zone-trace-tile-smoke"])
        self.assertEqual(args.command, "build-optimization-zone-trace-tile-smoke")

    def test_optimization_country_diagnostics_cli_exists(self) -> None:
        args = build_parser().parse_args(["build-optimization-country-diagnostics-tile-smoke"])
        self.assertEqual(args.command, "build-optimization-country-diagnostics-tile-smoke")

    def test_method_comparison_narrative_cli_exists(self) -> None:
        args = build_parser().parse_args(["build-method-comparison-narrative-tile-smoke"])
        self.assertEqual(args.command, "build-method-comparison-narrative-tile-smoke")

    def test_business_scenario_library_cli_exists(self) -> None:
        args = build_parser().parse_args(["build-business-scenario-library-tile-smoke"])
        self.assertEqual(args.command, "build-business-scenario-library-tile-smoke")

    def test_snapshot_drift_cli_commands_exist(self) -> None:
        metrics_args = build_parser().parse_args(["build-pipeline-snapshot-metrics-tile-smoke"])
        drift_args = build_parser().parse_args(["compare-pipeline-snapshot-drift-tile-smoke"])
        stage_args = build_parser().parse_args(["stage-reference-snapshot-metrics-tile-smoke"])
        promote_args = build_parser().parse_args(["promote-reference-snapshot-metrics-tile-smoke"])
        public_claim_args = build_parser().parse_args(["build-public-claim-gate"])
        release_gate_args = build_parser().parse_args(["run-release-gate-tile-smoke"])
        portfolio_release_args = build_parser().parse_args(["run-portfolio-release-check"])
        self.assertEqual(metrics_args.command, "build-pipeline-snapshot-metrics-tile-smoke")
        self.assertEqual(drift_args.command, "compare-pipeline-snapshot-drift-tile-smoke")
        self.assertEqual(stage_args.command, "stage-reference-snapshot-metrics-tile-smoke")
        self.assertEqual(promote_args.command, "promote-reference-snapshot-metrics-tile-smoke")
        self.assertEqual(public_claim_args.command, "build-public-claim-gate")
        self.assertEqual(release_gate_args.command, "run-release-gate-tile-smoke")
        self.assertEqual(portfolio_release_args.command, "run-portfolio-release-check")
        completion_gate_args = build_parser().parse_args(["run-completion-gate"])
        self.assertEqual(completion_gate_args.command, "run-completion-gate")
        project_status_args = build_parser().parse_args(["build-project-status"])
        self.assertEqual(project_status_args.command, "build-project-status")

    def test_osm_fetch_only_cli_flags_do_not_require_quality_report(self) -> None:
        batch_args = build_parser().parse_args(["run-osm-tile-batch", "--skip-quality-report"])
        self.assertTrue(batch_args.skip_quality_report)
        progress_args = build_parser().parse_args(["osm-tile-progress", "--skip-quality-report"])
        self.assertTrue(progress_args.skip_quality_report)
        gate_args = build_parser().parse_args(["osm-fetch-gate", "--latest-only", "--output-limit", "20"])
        self.assertTrue(gate_args.latest_only)
        self.assertEqual(gate_args.output_limit, 20)

    def test_osm_fetch_gate_cli_returns_nonzero_when_gate_fails(self) -> None:
        with patch("chargenet.cli.current_osm_fetch_gate", return_value={"passed": False}):
            self.assertEqual(main(["osm-fetch-gate"]), 1)
        with patch("chargenet.cli.current_osm_fetch_gate", return_value={"passed": True}):
            self.assertEqual(main(["osm-fetch-gate"]), 0)

    def test_osm_tile_batch_cli_returns_nonzero_when_execute_has_failed_jobs(self) -> None:
        result = {"failed_jobs": 1, "fetched_jobs": 8}
        with patch("chargenet.cli.run_osm_tile_batch", return_value=result), patch("chargenet.cli.write_quality_report"):
            self.assertEqual(main(["run-osm-tile-batch", "--execute", "--skip-quality-report"]), 1)

    def test_osm_full_batch_selection_resumes_from_fetched_jobs(self) -> None:
        rows = [
            {"country_code": "BE", "extract_slug": "charging_stations", "tile_job_id": "be-charge-1"},
            {"country_code": "BE", "extract_slug": "candidate_fuel", "tile_job_id": "be-fuel-1"},
            {"country_code": "DE", "extract_slug": "candidate_fuel", "tile_job_id": "de-fuel-1"},
            {"country_code": "FR", "extract_slug": "candidate_fuel", "tile_job_id": "fr-fuel-1"},
        ]
        selected = select_batch_jobs(
            rows,
            max_jobs=2,
            countries=["BE", "DE"],
            extracts=["candidate_fuel"],
            exclude_tile_job_ids={"be-fuel-1"},
        )
        self.assertEqual([row["tile_job_id"] for row in selected], ["de-fuel-1"])
        with self.assertRaises(ValueError):
            select_batch_jobs(rows, max_jobs=26, countries=["BE"], extracts=["candidate_fuel"])

    def test_osm_tile_progress_summary_counts_unique_fetched_and_remaining_jobs(self) -> None:
        plan_rows = [
            {"tile_job_id": "a", "country_code": "BE", "extract_slug": "charging_stations"},
            {"tile_job_id": "b", "country_code": "BE", "extract_slug": "candidate_fuel"},
            {"tile_job_id": "c", "country_code": "DE", "extract_slug": "candidate_fuel"},
        ]
        log_rows = [
            {"tile_job_id": "a", "status": "fetched"},
            {"tile_job_id": "a", "status": "fetched"},
            {"tile_job_id": "b", "status": "fetch_failed"},
        ]

        summary = osm_tile_progress_summary(plan_rows, log_rows)
        self.assertEqual(summary["planned_jobs"], 3)
        self.assertEqual(summary["fetched_jobs"], 1)
        self.assertEqual(summary["failed_attempts"], 1)
        self.assertEqual(summary["remaining_jobs"], 2)
        self.assertEqual(summary["completion_pct"], 0.333333)

    def test_osm_tile_progress_treats_retried_failure_as_resolved(self) -> None:
        plan_rows = [{"tile_job_id": "a"}, {"tile_job_id": "b"}]
        log_rows = [
            {"tile_job_id": "a", "status": "fetch_failed"},
            {"tile_job_id": "a", "status": "fetched"},
        ]

        summary = osm_tile_progress_summary(plan_rows, log_rows)

        self.assertEqual(summary["fetched_jobs"], 1)
        self.assertEqual(summary["failed_attempts"], 0)
        self.assertEqual(summary["remaining_jobs"], 1)

    def test_osm_fetch_gate_flags_raw_manifest_and_duplicate_problems(self) -> None:
        with TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            raw_path = base / "tile.json"
            raw_path.write_text('{"elements": []}', encoding="utf-8")
            manifest_path = base / "tile.manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "content_sha256": "wrong",
                        "immutable_run_path": str(raw_path),
                    }
                ),
                encoding="utf-8",
            )
            plan_rows = [
                {"tile_job_id": "a"},
                {"tile_job_id": "b"},
                {"tile_job_id": "c"},
            ]
            log_rows = [
                {"tile_job_id": "a", "status": "fetched", "element_count": "20", "raw_path": str(raw_path), "manifest_path": str(manifest_path)},
                {"tile_job_id": "a", "status": "fetched", "element_count": "20", "raw_path": str(raw_path), "manifest_path": str(manifest_path)},
                {"tile_job_id": "b", "status": "fetched", "element_count": "1", "raw_path": "", "manifest_path": ""},
                {"tile_job_id": "unknown", "status": "fetched", "element_count": "1", "raw_path": str(raw_path), "manifest_path": str(manifest_path)},
                {"tile_job_id": "c", "status": "pending", "element_count": "0", "raw_path": "", "manifest_path": ""},
            ]

            gate = osm_fetch_gate_summary(plan_rows, log_rows, output_limit=20)

        self.assertFalse(gate["passed"])
        self.assertEqual(gate["progress"]["fetched_jobs"], 2)
        self.assertEqual(gate["failed_attempts"], 0)
        self.assertEqual(gate["historical_failed_attempts"], 0)
        self.assertEqual(gate["duplicate_fetched_tile_ids"], ["a"])
        self.assertEqual(gate["missing_raw_count"], 1)
        self.assertEqual(gate["missing_manifest_count"], 1)
        self.assertEqual(gate["manifest_hash_mismatch_count"], 2)
        self.assertEqual(gate["unknown_tile_ids"], ["unknown"])
        self.assertEqual(gate["nonterminal_status_count"], 1)
        self.assertEqual(gate["output_limit_hit_count"], 2)

    def test_osm_element_coordinate_prefers_point_then_center(self) -> None:
        self.assertEqual(element_coordinate({"lat": 50.1, "lon": 4.2}), (50.1, 4.2))
        self.assertEqual(element_coordinate({"center": {"lat": 50.3, "lon": 4.4}}), (50.3, 4.4))
        self.assertIsNone(element_coordinate({"type": "relation"}))

    def test_candidate_site_type_uses_extract_slug_over_noisy_amenity_tags(self) -> None:
        noisy_tags = {"amenity": "parking,fuel,toilets,cafe,restaurant", "highway": "services"}
        self.assertEqual(infer_candidate_site_type({"extract_slug": "candidate_fuel"}, noisy_tags), "fuel")
        self.assertEqual(infer_candidate_site_type({"extract_slug": "candidate_services"}, noisy_tags), "services")

    def test_baseline_helpers_keep_scores_and_language_bounded(self) -> None:
        self.assertEqual(clamp(-1), 0.0)
        self.assertEqual(clamp(2), 1.0)
        self.assertEqual(action_bucket(0, 0.9), "No current coverage signal")
        self.assertEqual(action_bucket(100, 0.8), "Priority diligence shortlist")

    def test_baseline_sensitivity_scores_and_rank_deltas_from_existing_components(self) -> None:
        self.assertTrue(all(validate_weight_set(weight_set) for weight_set in SENSITIVITY_WEIGHT_SETS))
        self.assertAlmostEqual(
            compute_weighted_score(
                {
                    "coverage_component": "1",
                    "data_quality_component": "0.5",
                    "risk_component": "0.25",
                    "competition_component": "0",
                },
                {"coverage": 0.5, "data_quality": 0.25, "risk": 0.25, "competition": 0},
            ),
            0.6875,
        )
        with TemporaryDirectory() as tmpdir:
            baseline_path = Path(tmpdir) / "baseline.csv"
            output_path = Path(tmpdir) / "sensitivity.csv"
            baseline_path.write_text(
                "\n".join(
                    [
                        "scenario_id,candidate_site_id,country_code,nuts_id,site_type,coverage_radius_km,coverage_component,data_quality_component,risk_component,competition_component,baseline_score,rank_within_scenario",
                        "scenario:base,candidate:b,BE,BE100,fuel,30,0,0,0,0,0.900000,1",
                        "scenario:base,candidate:a,BE,BE100,fuel,30,1,1,1,1,0.800000,2",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            build_baseline_sensitivity_tile_smoke(baseline_path=baseline_path, output_path=output_path)
            with output_path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 2 * len(SENSITIVITY_WEIGHT_SETS))
        base_rows = [row for row in rows if row["weight_set_id"] == "weights:base"]
        self.assertTrue(all(row["rank_delta_vs_base"] == "0" for row in base_rows))
        self.assertTrue(all("diligence" in row["allowed_use_note"].lower() for row in rows))

    def test_exact_mclp_solver_selects_union_coverage_not_individual_top_scores(self) -> None:
        coverage_by_candidate = {
            "candidate:a": {"zone:1": 10.0, "zone:2": 10.0},
            "candidate:b": {"zone:1": 10.0, "zone:2": 10.0, "zone:3": 10.0},
            "candidate:c": {"zone:4": 10.0},
        }
        result = solve_mclp_exact(
            ["candidate:a", "candidate:b", "candidate:c"],
            coverage_by_candidate,
            k=2,
            costs={"candidate:a": 1.0, "candidate:b": 1.0, "candidate:c": 1.0},
            budget=2.0,
        )
        self.assertEqual(result["selected_candidate_ids"], ["candidate:b", "candidate:c"])
        self.assertEqual(result["objective_covered_demand_weight"], 40.0)
        self.assertEqual(coverage_objective(["candidate:a", "candidate:b"], coverage_by_candidate), 30.0)

    def test_pulp_mclp_solver_respects_budget_and_site_count(self) -> None:
        coverage_by_candidate = {
            "candidate:a": {"zone:1": 10.0, "zone:2": 10.0},
            "candidate:b": {"zone:3": 20.0},
            "candidate:c": {"zone:4": 100.0},
        }
        result = solve_mclp_pulp(
            ["candidate:a", "candidate:b", "candidate:c"],
            coverage_by_candidate,
            k=2,
            costs={"candidate:a": 1.0, "candidate:b": 1.0, "candidate:c": 3.0},
            budget=2.0,
        )
        self.assertEqual(result["solver_status"], "optimal_milp")
        self.assertEqual(result["selected_candidate_ids"], ["candidate:a", "candidate:b"])
        self.assertEqual(result["objective_covered_demand_weight"], 40.0)

    def test_pulp_mclp_solver_does_not_emit_selection_when_nonoptimal(self) -> None:
        result = solve_mclp_pulp(
            ["candidate:a"],
            {"candidate:a": {"zone:1": 10.0}},
            k=1,
            costs={"candidate:a": 1.0},
            budget=-1.0,
        )

        self.assertEqual(result["solver_status"], "milp_infeasible")
        self.assertEqual(result["selected_candidate_ids"], [])
        self.assertEqual(result["objective_covered_demand_weight"], 0.0)
        self.assertEqual(result["selected_candidate_count"], 0)
        self.assertEqual(result["total_candidate_cost"], 0.0)

    def test_min_cost_coverage_solver_reaches_floor_at_lowest_cost(self) -> None:
        coverage_by_candidate = {
            "candidate:a": {"zone:1": 10.0, "zone:2": 10.0},
            "candidate:b": {"zone:2": 10.0, "zone:3": 10.0},
            "candidate:c": {"zone:1": 10.0, "zone:2": 10.0, "zone:3": 10.0},
        }
        result = solve_min_cost_coverage_pulp(
            ["candidate:a", "candidate:b", "candidate:c"],
            coverage_by_candidate,
            k=2,
            costs={"candidate:a": 2.0, "candidate:b": 2.0, "candidate:c": 5.0},
            budget=10.0,
            coverage_floor=30.0,
        )

        self.assertEqual(result["solver_status"], "optimal_min_cost")
        self.assertEqual(result["selected_candidate_ids"], ["candidate:a", "candidate:b"])
        self.assertEqual(result["objective_covered_demand_weight"], 30.0)
        self.assertEqual(result["total_candidate_cost"], 4.0)

    def test_min_cost_coverage_solver_reports_infeasible_floor(self) -> None:
        result = solve_min_cost_coverage_pulp(
            ["candidate:a"],
            {"candidate:a": {"zone:1": 10.0}},
            k=1,
            costs={"candidate:a": 1.0},
            budget=1.0,
            coverage_floor=20.0,
        )

        self.assertEqual(result["solver_status"], "milp_infeasible")
        self.assertEqual(result["selected_candidate_ids"], [])

    def test_optimization_builder_outputs_min_cost_method_and_floor_diagnostics(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            baseline_path = root / "baseline.csv"
            coverage_path = root / "coverage.csv"
            scenario_path = root / "scenario.csv"
            summary_path = root / "summary.csv"
            selected_path = root / "selected.csv"
            diagnostics_path = root / "diagnostics.csv"
            baseline_path.write_text(
                "\n".join(
                    [
                        "scenario_id,candidate_site_id,country_code,nuts_id,site_type,coverage_radius_km,baseline_score,rank_within_scenario",
                        "scenario:base,candidate:a,BE,BE100,fuel,30,0.9,1",
                        "scenario:base,candidate:b,BE,BE100,fuel,30,0.8,2",
                        "scenario:base,candidate:c,BE,BE100,fuel,30,0.7,3",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            coverage_path.write_text(
                "\n".join(
                    [
                        "candidate_site_id,demand_zone_id,coverage_radius_km,pair_eligible_flag,demand_weight_contribution",
                        "candidate:a,zone:1,30,1,10",
                        "candidate:a,zone:2,30,1,10",
                        "candidate:b,zone:2,30,1,10",
                        "candidate:b,zone:3,30,1,10",
                        "candidate:c,zone:1,30,1,10",
                        "candidate:c,zone:2,30,1,10",
                        "candidate:c,zone:3,30,1,10",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            scenario_path.write_text(
                "\n".join(
                    [
                        "scenario_id,entity_type,entity_id,c_j,b,k",
                        "scenario:base,candidate_site,candidate:a,2,10,2",
                        "scenario:base,candidate_site,candidate:b,2,10,2",
                        "scenario:base,candidate_site,candidate:c,5,10,2",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            build_optimization_results_tile_smoke(
                baseline_path=baseline_path,
                coverage_path=coverage_path,
                scenario_path=scenario_path,
                summary_output_path=summary_path,
                selected_output_path=selected_path,
                diagnostics_output_path=diagnostics_path,
                shortlist_size=3,
            )
            with summary_path.open(newline="", encoding="utf-8") as handle:
                summary_rows = list(csv.DictReader(handle))
            with diagnostics_path.open(newline="", encoding="utf-8") as handle:
                diagnostics_rows = list(csv.DictReader(handle))

        methods = {row["method_id"] for row in summary_rows}
        self.assertIn(MIN_COST_METHOD_ID, methods)
        min_cost = next(row for row in summary_rows if row["method_id"] == MIN_COST_METHOD_ID)
        self.assertEqual(min_cost["solver_status"], "optimal_min_cost")
        self.assertEqual(float(min_cost["coverage_floor_demand_weight"]), 27.0)
        self.assertEqual(float(min_cost["total_candidate_cost"]), 4.0)
        self.assertIn("coverage_floor", {row["constraint_name"] for row in diagnostics_rows})

    def test_optimization_sensitivity_builds_weight_set_shortlist_results(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            sensitivity_path = root / "sensitivity.csv"
            coverage_path = root / "coverage.csv"
            scenario_path = root / "scenario.csv"
            output_path = root / "optimization_sensitivity.csv"
            sensitivity_path.write_text(
                "\n".join(
                    [
                        "weight_set_id,weight_set_name,scenario_id,candidate_site_id,coverage_radius_km,rank_within_weight_set_scenario",
                        "weights:base,Base balanced,scenario:base,candidate:a,30,1",
                        "weights:base,Base balanced,scenario:base,candidate:b,30,2",
                        "weights:base,Base balanced,scenario:base,candidate:c,30,3",
                        "weights:coverage-led,Coverage led,scenario:base,candidate:c,30,1",
                        "weights:coverage-led,Coverage led,scenario:base,candidate:b,30,2",
                        "weights:coverage-led,Coverage led,scenario:base,candidate:a,30,3",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            coverage_path.write_text(
                "\n".join(
                    [
                        "candidate_site_id,demand_zone_id,coverage_radius_km,pair_eligible_flag,demand_weight_contribution",
                        "candidate:a,zone:1,30,1,10",
                        "candidate:b,zone:2,30,1,10",
                        "candidate:c,zone:1,30,1,10",
                        "candidate:c,zone:2,30,1,10",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            scenario_path.write_text(
                "\n".join(
                    [
                        "scenario_id,entity_type,entity_id,c_j,b,k",
                        "scenario:base,candidate_site,candidate:a,1,1,1",
                        "scenario:base,candidate_site,candidate:b,1,1,1",
                        "scenario:base,candidate_site,candidate:c,1,1,1",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            build_optimization_sensitivity_tile_smoke(
                sensitivity_path=sensitivity_path,
                coverage_path=coverage_path,
                scenario_path=scenario_path,
                output_path=output_path,
                shortlist_size=2,
            )
            with output_path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))

        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row["method_id"] == SENSITIVITY_MCLP_METHOD_ID for row in rows))
        base = next(row for row in rows if row["weight_set_id"] == "weights:base")
        coverage_led = next(row for row in rows if row["weight_set_id"] == "weights:coverage-led")
        self.assertEqual(float(base["objective_covered_demand_weight"]), 10.0)
        self.assertEqual(float(coverage_led["objective_covered_demand_weight"]), 20.0)
        self.assertEqual(float(coverage_led["objective_delta_vs_base_weight_set"]), 10.0)
        self.assertEqual(int(coverage_led["overlap_with_base_solution_count"]), 0)

    def test_candidate_lineage_trace_joins_selected_site_to_clean_score_and_coverage(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            clean_path = root / "clean_candidates.csv"
            baseline_path = root / "baseline.csv"
            coverage_path = root / "coverage.csv"
            scenario_path = root / "scenario.csv"
            selected_path = root / "selected.csv"
            output_path = root / "lineage.csv"
            clean_path.write_text(
                "\n".join(
                    [
                        "tile_run_id,tile_job_id,candidate_site_id,source_record_id,candidate_source,country_code,nuts_id,lat,lon,site_type,brand,operator,name,rollout_risk_score,competition_score,data_quality_score,raw_tags_json,proxy_assumption_label",
                        'run-1,job-1,candidate:a,osm:node:1,osm_overpass,BE,BE100,50.1,4.1,fuel,Brand A,Operator A,Station A,0.4,0.2,0.9,"{""amenity"": ""fuel"", ""opening_hours"": ""24/7""}",candidate_proxy',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            baseline_path.write_text(
                "\n".join(
                    [
                        "scenario_id,candidate_site_id,coverage_radius_km,covered_demand_weight,covered_zone_count,coverage_component,data_quality_component,risk_component,competition_component,baseline_score,rank_within_scenario,action_bucket",
                        "scenario:base,candidate:a,30,30,2,1,0.9,0.6,0.8,0.87,3,Priority diligence shortlist",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            coverage_path.write_text(
                "\n".join(
                    [
                        "candidate_site_id,demand_zone_id,coverage_radius_km,pair_eligible_flag,distance_km,demand_weight_contribution",
                        "candidate:a,dz:1,30,1,5.2,10",
                        "candidate:a,dz:2,30,1,7.4,20",
                        "candidate:a,dz:3,30,0,35.0,40",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            scenario_path.write_text(
                "\n".join(
                    [
                        "scenario_id,entity_type,entity_id,c_j,b,k,service_radius_km",
                        "scenario:base,candidate_site,candidate:a,550000,1000000,2,30",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            selected_path.write_text(
                "\n".join(
                    [
                        "scenario_method_id,scenario_id,method_id,selection_rank,candidate_site_id,c_j",
                        "scenario:base|method:mclp-pulp-cbc,scenario:base,method:mclp-pulp-cbc,1,candidate:a,550000",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            build_candidate_lineage_trace_tile_smoke(
                clean_candidate_path=clean_path,
                baseline_path=baseline_path,
                coverage_path=coverage_path,
                scenario_path=scenario_path,
                selected_path=selected_path,
                output_path=output_path,
                scenario_id="scenario:base",
                method_id="method:mclp-pulp-cbc",
            )
            with output_path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["source_record_id"], "osm:node:1")
        self.assertEqual(row["raw_tag_keys"], "amenity|opening_hours")
        self.assertEqual(row["coverage_trace_zone_ids"], "dz:2|dz:1")
        self.assertEqual(float(row["covered_demand_weight"]), 30.0)
        self.assertEqual(float(row["scenario_candidate_cost"]), 550000.0)
        self.assertIn("not investment advice", row["allowed_use_note"].lower())

    def test_optimization_zone_trace_expands_selected_sites_to_covered_zones(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            selected_path = root / "selected.csv"
            coverage_path = root / "coverage.csv"
            scenario_path = root / "scenario.csv"
            output_path = root / "zone_trace.csv"
            selected_path.write_text(
                "\n".join(
                    [
                        "scenario_method_id,scenario_id,method_id,selection_rank,candidate_site_id",
                        "scenario:base|method:mclp-pulp-cbc,scenario:base,method:mclp-pulp-cbc,1,candidate:a",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            coverage_path.write_text(
                "\n".join(
                    [
                        "candidate_site_id,demand_zone_id,coverage_radius_km,pair_eligible_flag,distance_km,demand_weight_contribution",
                        "candidate:a,dz:1,30,1,5.0,10",
                        "candidate:a,dz:2,30,1,3.0,30",
                        "candidate:a,dz:3,30,0,1.0,100",
                        "candidate:b,dz:9,30,1,2.0,90",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            scenario_path.write_text(
                "\n".join(
                    [
                        "scenario_id,entity_type,entity_id,service_radius_km",
                        "scenario:base,demand_zone,dz:1,30",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            build_optimization_zone_trace_tile_smoke(
                selected_path=selected_path,
                coverage_path=coverage_path,
                scenario_path=scenario_path,
                output_path=output_path,
            )
            with output_path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))

        self.assertEqual([row["demand_zone_id"] for row in rows], ["dz:2", "dz:1"])
        self.assertEqual(rows[0]["zone_trace_id"], "scenario:base|method:mclp-pulp-cbc|candidate:a|dz:2")
        self.assertEqual(rows[0]["zone_coverage_rank"], "1")
        self.assertEqual(float(rows[0]["zone_demand_weight"]), 30.0)
        self.assertEqual(float(rows[0]["zone_demand_share_of_candidate"]), 0.75)
        self.assertIn("not investment advice", rows[0]["allowed_use_note"].lower())

    def test_optimization_country_diagnostics_summarize_selected_country_balance(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            selected_path = root / "selected.csv"
            zone_trace_path = root / "zone_trace.csv"
            output_path = root / "country.csv"
            selected_path.write_text(
                "\n".join(
                    [
                        "scenario_id,method_id,candidate_site_id,country_code,c_j",
                        "scenario:base,method:mclp-pulp-cbc,candidate:a,BE,100",
                        "scenario:base,method:mclp-pulp-cbc,candidate:b,FR,300",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            zone_trace_path.write_text(
                "\n".join(
                    [
                        "scenario_id,method_id,candidate_site_id,demand_zone_id,zone_demand_weight",
                        "scenario:base,method:mclp-pulp-cbc,candidate:a,dz:nuts2024:BE100,10",
                        "scenario:base,method:mclp-pulp-cbc,candidate:b,dz:nuts2024:FR101,30",
                        "scenario:base,method:mclp-pulp-cbc,candidate:b,dz:nuts2024:FR101,20",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            build_optimization_country_diagnostics_tile_smoke(
                selected_path=selected_path,
                zone_trace_path=zone_trace_path,
                output_path=output_path,
            )
            with output_path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))

        by_country = {row["country_code"]: row for row in rows}
        self.assertEqual(by_country["BE"]["selected_candidate_count"], "1")
        self.assertEqual(float(by_country["BE"]["covered_demand_share_of_method"]), 0.25)
        self.assertEqual(float(by_country["FR"]["covered_demand_weight"]), 30.0)
        self.assertEqual(float(by_country["FR"]["candidate_cost_share_of_method"]), 0.75)
        self.assertEqual(by_country["FR"]["concentration_status"], "warning")
        self.assertEqual(float(by_country["FR"]["concentration_warning_threshold"]), 0.75)
        self.assertIn("review", by_country["FR"]["concentration_review_note"].lower())
        self.assertIn("not a fairness", by_country["FR"]["allowed_use_note"].lower())

    def test_business_scenario_library_uses_real_optimization_metrics(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            optimization_path = root / "optimization.csv"
            sensitivity_path = root / "sensitivity.csv"
            output_path = root / "library.csv"
            optimization_path.write_text(
                "\n".join(
                    [
                        "scenario_id,method_id,solver_status,objective_covered_demand_weight,total_candidate_cost,selected_candidate_count,improvement_vs_baseline_pct,cost_saving_vs_baseline_pct",
                        "scenario:radius-base,method:mclp-pulp-cbc,optimal_milp,200,110,2,0.25,-0.1",
                        "scenario:radius-base,method:min-cost-coverage-pulp,optimal_min_cost,100,50,1,0,0.5",
                        "scenario:radius-aggressive,method:mclp-pulp-cbc,optimal_milp,300,140,3,0.5,-0.2",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            sensitivity_path.write_text(
                "\n".join(
                    [
                        "scenario_id,weight_set_id,weight_set_name,objective_delta_vs_base_weight_set_pct,overlap_with_base_solution_pct",
                        "scenario:radius-base,weights:coverage-led,Coverage led,0.1,0.4",
                        "scenario:radius-base,weights:risk-aware,Risk aware,-0.2,0.6",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            build_business_scenario_library_tile_smoke(
                optimization_path=optimization_path,
                sensitivity_path=sensitivity_path,
                output_path=output_path,
            )
            with output_path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))

        max_coverage = next(row for row in rows if row["business_scenario_id"] == "biz:max-coverage-base")
        lowest_cost = next(row for row in rows if row["business_scenario_id"] == "biz:min-cost-base")
        robustness = next(row for row in rows if row["business_scenario_id"] == "biz:assumption-robustness-base")
        self.assertEqual(float(max_coverage["primary_metric_value"]), 200.0)
        self.assertEqual(float(lowest_cost["primary_metric_value"]), 0.5)
        self.assertEqual(float(robustness["primary_metric_value"]), 0.4)
        self.assertEqual(max_coverage["decision_readout"], "coverage_uplift")
        self.assertIn("coverage", max_coverage["recommended_next_action"].lower())
        self.assertEqual(lowest_cost["decision_readout"], "cost_floor_saving")
        self.assertEqual(robustness["decision_readout"], "assumption_sensitive")
        self.assertIn("public proxy", max_coverage["limitation_note"].lower())

    def test_method_comparison_narrative_compares_baseline_mclp_and_min_cost(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            optimization_path = root / "optimization.csv"
            country_path = root / "country.csv"
            output_path = root / "method_comparison.csv"
            optimization_path.write_text(
                "\n".join(
                    [
                        "scenario_id,method_id,solver_status,selected_candidate_count,objective_covered_demand_weight,covered_zone_count,total_candidate_cost,improvement_vs_baseline_pct,cost_saving_vs_baseline_pct",
                        "scenario:base,method:baseline-topk,benchmark_feasible,10,100,5,1000,0,0",
                        "scenario:base,method:mclp-pulp-cbc,optimal_milp,8,140,7,1200,0.4,-0.2",
                        "scenario:base,method:min-cost-coverage-pulp,optimal_min_cost,2,90,4,500,-0.1,0.5",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            country_path.write_text(
                "\n".join(
                    [
                        "scenario_id,method_id,country_code,covered_demand_share_of_method",
                        "scenario:base,method:mclp-pulp-cbc,DE,0.7",
                        "scenario:base,method:mclp-pulp-cbc,FR,0.3",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            build_method_comparison_narrative_tile_smoke(
                optimization_path=optimization_path,
                country_diagnostics_path=country_path,
                output_path=output_path,
            )
            with output_path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["scenario_id"], "scenario:base")
        self.assertEqual(row["comparison_readout"], "mclp_expands_coverage")
        self.assertEqual(row["best_coverage_method_id"], "method:mclp-pulp-cbc")
        self.assertEqual(row["lowest_cost_method_id"], "method:min-cost-coverage-pulp")
        self.assertEqual(float(row["mclp_coverage_uplift_pct"]), 0.4)
        self.assertEqual(float(row["min_cost_saving_pct"]), 0.5)
        self.assertEqual(row["dominant_coverage_country_code"], "DE")
        self.assertIn("not a recommendation", row["allowed_use_note"].lower())

    def test_pipeline_snapshot_metrics_are_built_from_real_csv_counts(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            candidates = root / "candidates.csv"
            coverage = root / "coverage.csv"
            baseline = root / "baseline.csv"
            optimization = root / "optimization.csv"
            output = root / "snapshot.csv"
            candidates.write_text("candidate_site_id\ncandidate:a\ncandidate:b\n", encoding="utf-8")
            coverage.write_text(
                "candidate_site_id,pair_eligible_flag,demand_weight_contribution\ncandidate:a,1,10\ncandidate:b,0,5\ncandidate:b,1,20\n",
                encoding="utf-8",
            )
            baseline.write_text("scenario_id,candidate_site_id\nscenario:base,candidate:a\n", encoding="utf-8")
            optimization.write_text(
                "scenario_id,method_id,objective_covered_demand_weight,total_candidate_cost\nscenario:base,method:mclp-pulp-cbc,30,100\n",
                encoding="utf-8",
            )

            build_pipeline_snapshot_metrics_tile_smoke(
                candidate_path=candidates,
                coverage_path=coverage,
                baseline_path=baseline,
                optimization_path=optimization,
                output_path=output,
                snapshot_id="test-snapshot",
            )
            with output.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))

        metrics = {row["metric_name"]: float(row["metric_value"]) for row in rows}
        self.assertEqual(metrics["candidate_site_count"], 2.0)
        self.assertEqual(metrics["coverage_row_count"], 3.0)
        self.assertEqual(metrics["eligible_coverage_pair_count"], 2.0)
        self.assertEqual(metrics["optimization_objective_mclp_base"], 30.0)

    def test_snapshot_drift_comparison_flags_warning_and_fail_thresholds(self) -> None:
        self.assertEqual(drift_status(105, 100, warning_pct=0.10, fail_pct=0.25), "pass")
        self.assertEqual(drift_status(115, 100, warning_pct=0.10, fail_pct=0.25), "warning")
        self.assertEqual(drift_status(130, 100, warning_pct=0.10, fail_pct=0.25), "fail")
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            current = root / "current.csv"
            reference = root / "reference.csv"
            output = root / "drift.csv"
            header = "snapshot_id,metric_name,metric_value,metric_unit,source_table,allowed_use_note,proxy_assumption_label\n"
            reference.write_text(header + "ref,unregistered_metric_count,100,count,clean_candidate_sites,reference,proxy\n", encoding="utf-8")
            current.write_text(header + "cur,unregistered_metric_count,130,count,clean_candidate_sites,current,proxy\n", encoding="utf-8")

            compare_snapshot_metrics(
                current_path=current,
                reference_path=reference,
                output_path=output,
                warning_pct=0.10,
                fail_pct=0.25,
            )
            with output.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))

        self.assertEqual(rows[0]["drift_status"], "fail")
        self.assertEqual(float(rows[0]["relative_delta_pct"]), 0.3)
        self.assertIn("not a source-data error by itself", rows[0]["allowed_use_note"])

    def test_snapshot_drift_uses_metric_specific_thresholds(self) -> None:
        thresholds = {
            "default": {"warning_pct": 0.2, "fail_pct": 0.4},
            "metrics": {
                "optimization_objective_mclp_base": {"warning_pct": 0.05, "fail_pct": 0.1}
            },
        }

        self.assertEqual(threshold_for_metric("candidate_site_count", thresholds), (0.2, 0.4))
        self.assertEqual(threshold_for_metric("optimization_objective_mclp_base", thresholds), (0.05, 0.1))
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            current = root / "current.csv"
            reference = root / "reference.csv"
            output = root / "drift.csv"
            header = "snapshot_id,metric_name,metric_value,metric_unit,source_table,allowed_use_note,proxy_assumption_label\n"
            reference.write_text(header + "ref,optimization_objective_mclp_base,100,demand_weight,optimization,reference,proxy\n", encoding="utf-8")
            current.write_text(header + "cur,optimization_objective_mclp_base,112,demand_weight,optimization,current,proxy\n", encoding="utf-8")

            compare_snapshot_metrics(
                current_path=current,
                reference_path=reference,
                output_path=output,
                thresholds=thresholds,
            )
            with output.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))

        self.assertEqual(rows[0]["drift_status"], "fail")
        self.assertEqual(float(rows[0]["warning_threshold_pct"]), 0.05)

    def test_stage_reference_snapshot_rewrites_snapshot_id_and_logs_review_status(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            current = root / "current.csv"
            reference = root / "reference.csv"
            log = root / "certification.csv"
            current.write_text(
                "\n".join(
                    [
                        "snapshot_id,metric_name,metric_value,metric_unit,source_table,allowed_use_note,proxy_assumption_label",
                        "current,candidate_site_count,100,count,clean_candidate_sites,current note,proxy",
                        "current,optimization_objective_mclp_base,200,demand_weight,optimization,current note,proxy",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            paths = stage_reference_snapshot_metrics_tile_smoke(
                current_path=current,
                reference_output_path=reference,
                certification_log_path=log,
                reference_snapshot_id="ref-2026-05-20",
                reviewer="codex",
                certification_note="Staged after local validation; human review still required.",
            )
            with reference.open(newline="", encoding="utf-8") as handle:
                reference_rows = list(csv.DictReader(handle))
            with log.open(newline="", encoding="utf-8") as handle:
                log_rows = list(csv.DictReader(handle))

        self.assertEqual(paths, [reference, log])
        self.assertTrue(all(row["snapshot_id"] == "ref-2026-05-20" for row in reference_rows))
        self.assertEqual(log_rows[0]["certification_status"], "staged_for_review")
        self.assertEqual(log_rows[0]["metric_count"], "2")
        self.assertIn("not a certification", log_rows[0]["allowed_use_note"].lower())

    def test_promote_reference_snapshot_certifies_only_when_all_drift_rows_pass(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            log = root / "certification.csv"
            drift = root / "drift.csv"
            output = root / "promoted.csv"
            log.write_text(
                "\n".join(
                    [
                        "reference_snapshot_id,source_snapshot_id,certification_status,reviewer,certification_note,metric_count,allowed_use_note,proxy_assumption_label",
                        "ref-2026-05-20,current,staged_for_review,codex,Staged for review,2,not certified,proxy",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            drift.write_text(
                "\n".join(
                    [
                        "metric_name,current_snapshot_id,reference_snapshot_id,current_metric_value,reference_metric_value,absolute_delta,relative_delta_pct,warning_threshold_pct,fail_threshold_pct,drift_status,source_table,allowed_use_note,proxy_assumption_label",
                        "candidate_site_count,current,ref-2026-05-20,100,100,0,0,0.1,0.25,pass,clean_candidate_sites,review,proxy",
                        "coverage_row_count,current,ref-2026-05-20,200,200,0,0,0.1,0.25,pass,fact_coverage,review,proxy",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            path = promote_reference_snapshot_metrics_tile_smoke(
                certification_log_path=log,
                drift_path=drift,
                output_path=output,
                reviewer="qa-gate",
            )
            with path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))

        self.assertEqual(path, output)
        self.assertEqual(rows[0]["certification_status"], "certified")
        self.assertEqual(rows[0]["reviewer"], "qa-gate")
        self.assertIn("all drift checks passed", rows[0]["certification_note"].lower())
        self.assertIn("certified", rows[0]["allowed_use_note"].lower())

    def test_promote_reference_snapshot_rejects_when_any_drift_row_needs_review(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            log = root / "certification.csv"
            drift = root / "drift.csv"
            output = root / "blocked.csv"
            log.write_text(
                "\n".join(
                    [
                        "reference_snapshot_id,source_snapshot_id,certification_status,reviewer,certification_note,metric_count,allowed_use_note,proxy_assumption_label",
                        "ref-2026-05-20,current,staged_for_review,codex,Staged for review,2,not certified,proxy",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            drift.write_text(
                "\n".join(
                    [
                        "metric_name,current_snapshot_id,reference_snapshot_id,current_metric_value,reference_metric_value,absolute_delta,relative_delta_pct,warning_threshold_pct,fail_threshold_pct,drift_status,source_table,allowed_use_note,proxy_assumption_label",
                        "candidate_site_count,current,ref-2026-05-20,100,115,15,0.15,0.1,0.25,warning,clean_candidate_sites,review,proxy",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            promote_reference_snapshot_metrics_tile_smoke(
                certification_log_path=log,
                drift_path=drift,
                output_path=output,
                reviewer="qa-gate",
            )
            with output.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))

        self.assertEqual(rows[0]["certification_status"], "rejected")
        self.assertIn("blocked by 1 drift row", rows[0]["certification_note"].lower())
        self.assertIn("not certified", rows[0]["allowed_use_note"].lower())

    def test_public_claim_gate_flags_overclaim_language_but_allows_disclaimers(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            safe = root / "safe.md"
            unsafe = root / "unsafe.md"
            output = root / "claims.csv"
            safe.write_text(
                "This is not investment advice and not investment-grade. It is a decision-support layer.\n",
                encoding="utf-8",
            )
            unsafe.write_text(
                "The model identifies guaranteed optimal sites with complete OSM coverage.\n",
                encoding="utf-8",
            )

            findings = scan_public_claims([safe, unsafe], root=root)
            report_path = write_public_claim_gate([safe, unsafe], output_path=output, root=root)
            with report_path.open(newline="", encoding="utf-8") as handle:
                report_rows = list(csv.DictReader(handle))

        self.assertEqual(len(findings), 3)
        self.assertEqual(report_path, output)
        self.assertTrue(all(row["claim_status"] == "needs_review" for row in report_rows))
        self.assertEqual({row["claim_phrase"] for row in report_rows}, {"complete OSM coverage", "guaranteed", "optimal sites"})

    def test_public_claim_gate_allows_guardrail_wording(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            guardrail = root / "guardrail.md"
            guardrail.write_text(
                "Public docs must not drift into investment-grade or complete-coverage claims.\n"
                "Public docs drift from capped wording into investment-grade claims.\n"
                "The gate flags certainty phrases such as guaranteed and optimal sites.\n"
                "The model is assumption-driven rather than investment-grade.\n",
                encoding="utf-8",
            )

            findings = scan_public_claims([guardrail], root=root)

        self.assertEqual(findings, [])

    def test_default_public_claim_paths_cover_public_artifacts_only(self) -> None:
        relative_paths = {path.relative_to(PROJECT_ROOT).as_posix() for path in default_public_claim_paths()}

        self.assertIn("docs/chargenet-europe/candidate-lineage-walkthrough.md", relative_paths)
        self.assertIn("docs/chargenet-europe/completion-gate.md", relative_paths)
        self.assertIn("docs/chargenet-europe/project-status.md", relative_paths)
        self.assertNotIn("docs/chargenet-europe/interview-pack.md", relative_paths)
        self.assertNotIn("docs/chargenet-europe/three-month-roadmap.md", relative_paths)

    def test_release_gate_passes_when_quality_drift_claims_and_app_fallback_align(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            quality = root / "quality.json"
            drift = root / "drift.csv"
            certification = root / "certification.csv"
            claims = root / "claims.csv"
            app_certification = root / "app_certification.csv"
            app_manifest = root / "manifest.json"
            app_file = root / "fallback.csv"
            output = root / "release_gate.csv"
            quality.write_text(json.dumps({"raw": {"passed": True}, "clean": {"passed": True}}), encoding="utf-8")
            drift.write_text(
                "metric_name,drift_status\ncandidate_site_count,pass\ncoverage_row_count,pass\n",
                encoding="utf-8",
            )
            certification.write_text(
                "reference_snapshot_id,certification_status,metric_count\nref,certified,2\n",
                encoding="utf-8",
            )
            claims.write_text("file_path,line_number,claim_phrase,claim_status,line_text,review_note\n", encoding="utf-8")
            app_certification.write_text(
                "reference_snapshot_id,certification_status,metric_count\nref,certified,2\n",
                encoding="utf-8",
            )
            app_file.write_text("id\n1\n", encoding="utf-8")
            app_manifest.write_text(json.dumps({"not_investment_grade": True, "files": {"fallback.csv": 1}}), encoding="utf-8")

            rows = evaluate_release_gate(
                quality_report_path=quality,
                drift_path=drift,
                certification_path=certification,
                public_claim_gate_path=claims,
                app_certification_path=app_certification,
                app_manifest_path=app_manifest,
            )
            report_path = write_release_gate_report(rows=rows, output_path=output)
            with report_path.open(newline="", encoding="utf-8") as handle:
                report_rows = list(csv.DictReader(handle))

        self.assertEqual(report_path, output)
        self.assertEqual({row["gate_status"] for row in report_rows}, {"pass"})
        self.assertEqual({row["gate_name"] for row in report_rows}, {"quality_report", "snapshot_drift", "snapshot_certification", "public_claims", "app_fallback_sync", "app_data_manifest"})
        certification_row = next(row for row in report_rows if row["gate_name"] == "snapshot_certification")
        self.assertIn("Demo drift reference", certification_row["detail"])

    def test_release_gate_blocks_uncertified_or_unsynced_app_fallback(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            quality = root / "quality.json"
            drift = root / "drift.csv"
            certification = root / "certification.csv"
            claims = root / "claims.csv"
            app_certification = root / "app_certification.csv"
            app_manifest = root / "manifest.json"
            quality.write_text(json.dumps({"raw": {"passed": True}, "clean": {"passed": True}}), encoding="utf-8")
            drift.write_text("metric_name,drift_status\ncandidate_site_count,warning\n", encoding="utf-8")
            certification.write_text("reference_snapshot_id,certification_status,metric_count\nref,rejected,1\n", encoding="utf-8")
            claims.write_text(
                "file_path,line_number,claim_phrase,claim_status,line_text,review_note\napp.py,1,guaranteed,needs_review,text,note\n",
                encoding="utf-8",
            )
            app_certification.write_text("reference_snapshot_id,certification_status,metric_count\nref,staged_for_review,1\n", encoding="utf-8")

            rows = evaluate_release_gate(
                quality_report_path=quality,
                drift_path=drift,
                certification_path=certification,
                public_claim_gate_path=claims,
                app_certification_path=app_certification,
                app_manifest_path=app_manifest,
            )

        status_by_gate = {row["gate_name"]: row["gate_status"] for row in rows}
        self.assertEqual(status_by_gate["quality_report"], "pass")
        self.assertEqual(status_by_gate["snapshot_drift"], "fail")
        self.assertEqual(status_by_gate["snapshot_certification"], "fail")
        self.assertEqual(status_by_gate["public_claims"], "fail")
        self.assertEqual(status_by_gate["app_fallback_sync"], "fail")
        self.assertEqual(status_by_gate["app_data_manifest"], "fail")

    def test_app_data_manifest_summary_validates_files_and_row_counts(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            app_dir = root / "app_data"
            app_dir.mkdir()
            (app_dir / "ok.csv").write_text("id,value\n1,a\n2,b\n", encoding="utf-8")
            (app_dir / "bad.csv").write_text("id,value\n1,a\n", encoding="utf-8")
            manifest = app_dir / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "not_investment_grade": True,
                        "files": {
                            "ok.csv": 2,
                            "bad.csv": 2,
                            "missing.csv": 1,
                        }
                    }
                ),
                encoding="utf-8",
            )

            summary = app_data_manifest_summary(manifest)

        self.assertFalse(summary["passed"])
        self.assertEqual(summary["expected_files"], 3)
        self.assertEqual(summary["valid_files"], 1)
        self.assertEqual(summary["blocker_count"], 2)
        self.assertIn("missing.csv", summary["detail"])
        self.assertIn("bad.csv expected 2 rows, found 1", summary["detail"])

    def test_app_data_manifest_summary_validates_required_columns(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            app_dir = root / "app_data"
            app_dir.mkdir()
            (app_dir / "ok.csv").write_text("id,value\n1,a\n", encoding="utf-8")
            (app_dir / "bad.csv").write_text("id,other\n1,a\n", encoding="utf-8")
            manifest = app_dir / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "not_investment_grade": True,
                        "files": {"ok.csv": 1, "bad.csv": 1},
                        "schemas": {
                            "ok.csv": ["id", "value"],
                            "bad.csv": ["id", "value"],
                        },
                    }
                ),
                encoding="utf-8",
            )

            summary = app_data_manifest_summary(manifest)

        self.assertFalse(summary["passed"])
        self.assertEqual(summary["expected_files"], 2)
        self.assertEqual(summary["valid_files"], 1)
        self.assertIn("bad.csv missing columns: value", summary["detail"])

    def test_app_data_manifest_summary_validates_public_proxy_semantics(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            app_dir = root / "app_data"
            app_dir.mkdir()
            (app_dir / "optimization_results_tile_smoke.csv").write_text(
                "\n".join(
                    [
                        "scenario_method_id,allowed_use_note,proxy_assumption_label",
                        "scenario:base|method:mclp-pulp-cbc,Use for public-proxy diligence only,tile_smoke_optimization_not_investment_grade",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (app_dir / "optimization_selected_sites_tile_smoke.csv").write_text(
                "\n".join(
                    [
                        "scenario_method_id,allowed_use_note,proxy_assumption_label",
                        "scenario:missing|method:mclp-pulp-cbc,,",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            manifest = app_dir / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "not_investment_grade": True,
                        "files": {
                            "optimization_results_tile_smoke.csv": 1,
                            "optimization_selected_sites_tile_smoke.csv": 1,
                        },
                        "schemas": {
                            "optimization_results_tile_smoke.csv": ["scenario_method_id", "allowed_use_note", "proxy_assumption_label"],
                            "optimization_selected_sites_tile_smoke.csv": ["scenario_method_id", "allowed_use_note", "proxy_assumption_label"],
                        },
                    }
                ),
                encoding="utf-8",
            )

            summary = app_data_manifest_summary(manifest)

        self.assertFalse(summary["passed"])
        self.assertIn("optimization_selected_sites_tile_smoke.csv row 1 missing allowed_use_note", summary["detail"])
        self.assertIn("optimization_selected_sites_tile_smoke.csv row 1 missing public proxy label", summary["detail"])
        self.assertIn("unknown scenario_method_id", summary["detail"])

    def test_app_data_manifest_summary_requires_not_investment_grade_manifest(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            app_dir = root / "app_data"
            app_dir.mkdir()
            (app_dir / "fallback.csv").write_text("id\n1\n", encoding="utf-8")
            manifest = app_dir / "manifest.json"
            manifest.write_text(json.dumps({"files": {"fallback.csv": 1}}), encoding="utf-8")

            summary = app_data_manifest_summary(manifest)

        self.assertFalse(summary["passed"])
        self.assertIn("manifest not_investment_grade must be true", summary["detail"])

    def test_app_data_manifest_summary_rejects_weak_labels_and_bad_parent_keys(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            app_dir = root / "app_data"
            app_dir.mkdir()
            (app_dir / "optimization_results_tile_smoke.csv").write_text(
                "\n".join(
                    [
                        "scenario_method_id,allowed_use_note,proxy_assumption_label",
                        "scenario:base|method:mclp-pulp-cbc,Not investment advice; public proxy only,tile_smoke_optimization_not_investment_grade",
                        "scenario:base|method:mclp-pulp-cbc,Not investment advice; public proxy only,tile_smoke_optimization_not_investment_grade",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (app_dir / "optimization_zone_trace_tile_smoke.csv").write_text(
                "\n".join(
                    [
                        "scenario_method_id,allowed_use_note,proxy_assumption_label",
                        ",Not investment advice; public proxy only,public_final",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            manifest = app_dir / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "not_investment_grade": True,
                        "files": {
                            "optimization_results_tile_smoke.csv": 2,
                            "optimization_zone_trace_tile_smoke.csv": 1,
                        },
                    }
                ),
                encoding="utf-8",
            )

            summary = app_data_manifest_summary(manifest)

        self.assertFalse(summary["passed"])
        self.assertIn("duplicate scenario_method_id", summary["detail"])
        self.assertIn("missing scenario_method_id", summary["detail"])
        self.assertIn("missing public proxy label", summary["detail"])

    def test_release_gate_includes_app_data_manifest_status(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            app_dir = root / "app_data"
            app_dir.mkdir()
            manifest = app_dir / "manifest.json"
            (app_dir / "fallback.csv").write_text("id\n1\n", encoding="utf-8")
            manifest.write_text(json.dumps({"not_investment_grade": True, "files": {"fallback.csv": 1}}), encoding="utf-8")

            rows = evaluate_release_gate(
                quality_report_path=root / "missing_quality.json",
                drift_path=root / "missing_drift.csv",
                certification_path=root / "missing_certification.csv",
                public_claim_gate_path=root / "missing_claims.csv",
                app_certification_path=root / "missing_app_certification.csv",
                app_manifest_path=manifest,
            )

        by_name = {row["gate_name"]: row for row in rows}
        self.assertEqual(by_name["app_data_manifest"]["gate_status"], "pass")
        self.assertEqual(by_name["app_data_manifest"]["blocker_count"], 0)
        self.assertIn("required columns", by_name["app_data_manifest"]["detail"])

    def test_release_gate_pre_sync_ignores_app_fallback_gates_until_app_data_build(self) -> None:
        rows = [
            {"gate_name": "quality_report", "gate_status": "pass"},
            {"gate_name": "public_claims", "gate_status": "pass"},
            {"gate_name": "app_fallback_sync", "gate_status": "fail"},
            {"gate_name": "app_data_manifest", "gate_status": "fail"},
        ]

        self.assertTrue(release_gate_pre_sync_passed(rows))

    def test_portfolio_release_check_writes_ordered_pass_report(self) -> None:
        with TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "portfolio_release_check.csv"
            rows = run_portfolio_release_check(
                steps=[
                    ("quality_report", lambda: {"passed": True, "evidence_path": "quality.json", "detail": "quality passed"}),
                    ("public_claims", lambda: {"passed": True, "evidence_path": "claims.csv", "detail": "claims clean"}),
                    ("streamlit_smoke", lambda: {"passed": True, "evidence_path": "app.py", "detail": "app rendered"}),
                ]
            )
            report_path = write_portfolio_release_check(rows=rows, output_path=output)
            with report_path.open(newline="", encoding="utf-8") as handle:
                report_rows = list(csv.DictReader(handle))

        self.assertTrue(portfolio_release_check_passed(rows))
        self.assertEqual(report_path, output)
        self.assertEqual([row["step_order"] for row in report_rows], ["1", "2", "3"])
        self.assertEqual({row["step_status"] for row in report_rows}, {"pass"})

    def test_default_portfolio_release_steps_refresh_phase5_derived_marts_first(self) -> None:
        self.assertEqual(default_portfolio_release_steps()[0][0], "phase5_derived_marts")
        self.assertIn("app_data_build", [name for name, _step in default_portfolio_release_steps()])

    def test_portfolio_release_check_skips_publish_steps_after_failure(self) -> None:
        rows = run_portfolio_release_check(
            steps=[
                ("quality_report", lambda: {"passed": True, "evidence_path": "quality.json", "detail": "quality passed"}),
                ("public_claims", lambda: {"passed": False, "evidence_path": "claims.csv", "detail": "1 claim finding"}),
                ("app_data_build", lambda: {"passed": True, "evidence_path": "manifest.json", "detail": "should not run"}),
            ]
        )

        self.assertFalse(portfolio_release_check_passed(rows))
        self.assertEqual([row["step_status"] for row in rows], ["pass", "fail", "skipped"])
        self.assertEqual(rows[2]["detail"], "Skipped because an earlier release check failed.")

    def test_completion_gate_summarizes_release_private_and_git_status(self) -> None:
        rows = evaluate_completion_gate(
            portfolio_rows=[
                {"step_name": "quality_report", "step_status": "pass", "evidence_path": "quality.json", "detail": "ok"},
                {"step_name": "streamlit_smoke", "step_status": "pass", "evidence_path": "app.py", "detail": "exceptions=0; tabs=5"},
            ],
            public_claim_paths=[Path("app.py"), Path("docs/chargenet-europe/candidate-lineage-walkthrough.md")],
            private_dir_ignored=True,
            git_status_lines=[],
            private_history_hits=[],
        )

        by_name = {row["gate_name"]: row for row in rows}
        self.assertTrue(completion_gate_passed(rows))
        self.assertEqual(by_name["portfolio_release"]["gate_status"], "pass")
        self.assertEqual(by_name["private_boundary"]["gate_status"], "pass")
        self.assertEqual(by_name["git_worktree"]["gate_status"], "pass")

    def test_completion_gate_blocks_tracked_private_prep_paths_and_dirty_git(self) -> None:
        rows = evaluate_completion_gate(
            portfolio_rows=[{"step_name": "quality_report", "step_status": "pass"}],
            public_claim_paths=[PROJECT_ROOT / "docs" / "chargenet-europe" / "interview-pack.md"],
            private_dir_ignored=False,
            git_status_lines=[" M app.py"],
        )

        by_name = {row["gate_name"]: row for row in rows}
        self.assertFalse(completion_gate_passed(rows))
        self.assertEqual(by_name["private_boundary"]["gate_status"], "fail")
        self.assertEqual(by_name["private_boundary"]["blocker_count"], 2)
        self.assertEqual(by_name["git_worktree"]["gate_status"], "fail")

    def test_project_status_rows_summarize_scope_metrics_and_gates(self) -> None:
        rows = build_project_status_rows(
            snapshot_rows=[
                {"metric_name": "candidate_site_count", "metric_value": "1973"},
                {"metric_name": "coverage_row_count", "metric_value": "3462615"},
            ],
            release_rows=[
                {"gate_name": "quality_report", "gate_status": "pass"},
                {"gate_name": "app_data_manifest", "gate_status": "pass"},
            ],
            completion_rows=[
                {"gate_name": "portfolio_release", "gate_status": "pass"},
                {"gate_name": "private_history", "gate_status": "pass"},
            ],
            app_manifest={"files": {"a.csv": 2, "b.csv": 3}},
        )

        by_key = {row["status_key"]: row for row in rows}
        self.assertTrue(project_status_passed(rows))
        self.assertEqual(by_key["pilot_scope"]["status_value"], "BE, DE, FR, NL")
        self.assertEqual(by_key["candidate_proxies"]["status_value"], "1,973")
        self.assertEqual(by_key["coverage_rows"]["status_value"], "3,462,615")
        self.assertEqual(by_key["release_gates"]["status_value"], "2/2")
        self.assertEqual(by_key["completion_gates"]["status_value"], "2/2")
        self.assertEqual(by_key["app_fallback_files"]["status_value"], "2")
        self.assertEqual(by_key["known_limits"]["status_state"], "info")

    def test_project_status_report_writes_csv(self) -> None:
        with TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "project_status.csv"
            rows = [{"status_key": "completion_gates", "status_label": "Completion gates", "status_value": "1/1", "status_state": "pass", "detail": "ok"}]

            path = write_project_status_report(rows=rows, output_path=output)
            with path.open(newline="", encoding="utf-8") as handle:
                report_rows = list(csv.DictReader(handle))

        self.assertEqual(path, output)
        self.assertEqual(report_rows[0]["status_key"], "completion_gates")

    def test_private_history_gate_flags_private_prep_paths_in_git_history(self) -> None:
        row = private_history_row(
            [
                "abc123 docs/chargenet-europe/interview-pack.md",
                "def456 docs/chargenet-europe/three-month-roadmap.md",
            ]
        )

        self.assertEqual(row["gate_name"], "private_history")
        self.assertEqual(row["gate_status"], "fail")
        self.assertEqual(row["blocker_count"], 2)
        self.assertIn("private prep path(s) in branch history", row["detail"])

    def test_private_history_gate_passes_when_history_has_no_private_paths(self) -> None:
        row = private_history_row([])

        self.assertEqual(row["gate_status"], "pass")
        self.assertEqual(row["blocker_count"], 0)

    def test_recruiter_kpis_are_derived_from_snapshot_optimization_and_release_rows(self) -> None:
        snapshot_rows = [
            {"metric_name": "candidate_site_count", "metric_value": "1973"},
            {"metric_name": "coverage_row_count", "metric_value": "3462615"},
        ]
        optimization_rows = [
            {
                "scenario_id": "scenario:radius-base",
                "method_id": "method:mclp-pulp-cbc",
                "solver_status": "optimal_milp",
                "improvement_vs_baseline_pct": "2.373",
            }
        ]
        release_rows = [
            {"gate_name": "quality_report", "gate_status": "pass"},
            {"gate_name": "streamlit_smoke", "gate_status": "pass"},
        ]

        kpis = build_recruiter_kpis(
            snapshot_rows=snapshot_rows,
            optimization_rows=optimization_rows,
            release_gate_rows=release_rows,
            demand_zone_count=585,
        )

        by_key = {row["key"]: row for row in kpis}
        self.assertEqual(by_key["scope"]["value"], "4 countries")
        self.assertEqual(by_key["demand_zones"]["label"], "Regions analyzed")
        self.assertEqual(by_key["demand_zones"]["value"], "585")
        self.assertEqual(by_key["candidate_proxies"]["label"], "Potential locations screened")
        self.assertEqual(by_key["candidate_proxies"]["value"], "1,973")
        self.assertEqual(by_key["milp_uplift"]["label"], "Coverage improvement")
        self.assertEqual(by_key["milp_uplift"]["value"], "+237.3%")
        self.assertEqual(by_key["release_gate"]["value"], "2/2")
        self.assertEqual(by_key["release_gate"]["status"], "pass")

    def test_recruiter_kpis_do_not_greenlight_nonoptimal_milp_uplift(self) -> None:
        kpis = build_recruiter_kpis(
            snapshot_rows=[{"metric_name": "candidate_site_count", "metric_value": "10"}],
            optimization_rows=[
                {
                    "scenario_id": "scenario:radius-base",
                    "method_id": "method:mclp-pulp-cbc",
                    "solver_status": "milp_infeasible",
                    "improvement_vs_baseline_pct": "9.9",
                }
            ],
            release_gate_rows=[{"gate_name": "quality_report", "gate_status": "pass"}],
            demand_zone_count=1,
        )

        by_key = {row["key"]: row for row in kpis}
        self.assertEqual(by_key["milp_uplift"]["value"], "n/a")
        self.assertEqual(by_key["milp_uplift"]["status"], "fail")
        self.assertIn("No optimal MILP", by_key["milp_uplift"]["caption"])

    def test_release_gate_headline_reports_failures(self) -> None:
        headline = release_gate_headline(
            [
                {"gate_name": "quality_report", "gate_status": "pass"},
                {"gate_name": "public_claims", "gate_status": "fail"},
                {"gate_name": "streamlit_smoke", "gate_status": "pass"},
            ]
        )

        self.assertEqual(headline["value"], "2/3")
        self.assertEqual(headline["status"], "fail")
        self.assertIn("1 blocker", headline["caption"])

    def test_top_candidate_insights_summarize_current_shortlist(self) -> None:
        rows = [
            {"country_code": "FR", "site_type": "fuel", "baseline_score": "0.81", "covered_demand_weight": "12549288"},
            {"country_code": "FR", "site_type": "services", "baseline_score": "0.72", "covered_demand_weight": "500"},
            {"country_code": "DE", "site_type": "fuel", "baseline_score": "0.65", "covered_demand_weight": "1000"},
        ]

        insights = build_top_candidate_insights(rows)

        by_key = {row["key"]: row for row in insights}
        self.assertEqual(by_key["top_country"]["value"], "FR")
        self.assertEqual(by_key["top_country"]["caption"], "2 of 3 visible candidates")
        self.assertEqual(by_key["top_site_type"]["value"], "fuel")
        self.assertEqual(by_key["best_score"]["value"], "0.810")
        self.assertEqual(by_key["largest_demand"]["value"], "12,549,288")

    def test_optimization_takeaways_compare_baseline_milp_and_min_cost(self) -> None:
        rows = [
            {
                "scenario_id": "scenario:radius-base",
                "method_id": "method:baseline-topk",
                "objective_covered_demand_weight": "8197709",
                "total_candidate_cost": "5570000",
                "selected_candidate_count": "10",
                "covered_zone_count": "5",
            },
            {
                "scenario_id": "scenario:radius-base",
                "method_id": "method:mclp-pulp-cbc",
                "objective_covered_demand_weight": "27652281",
                "total_candidate_cost": "5920000",
                "selected_candidate_count": "10",
                "covered_zone_count": "67",
            },
            {
                "scenario_id": "scenario:radius-base",
                "method_id": "method:min-cost-coverage-pulp",
                "objective_covered_demand_weight": "8197709",
                "total_candidate_cost": "550000",
                "selected_candidate_count": "1",
                "covered_zone_count": "5",
            },
        ]

        takeaways = build_optimization_takeaways(rows, "scenario:radius-base")

        by_key = {row["key"]: row for row in takeaways}
        self.assertEqual(by_key["coverage_uplift"]["value"], "+237.3%")
        self.assertEqual(by_key["milp_cost_delta"]["value"], "+6.3%")
        self.assertEqual(by_key["min_cost_sites"]["label"], "90% floor sites")
        self.assertEqual(by_key["min_cost_sites"]["value"], "1")
        self.assertEqual(by_key["zone_expansion"]["value"], "5 -> 67")

    def test_metric_glossary_explains_public_proxy_metrics(self) -> None:
        glossary = build_metric_glossary()

        by_key = {row["metric_key"]: row for row in glossary}
        self.assertIn("coverage_uplift", by_key)
        self.assertIn("min_cost_saving", by_key)
        self.assertIn("dominant_country_share", by_key)
        self.assertIn("proxy cost", by_key["proxy_cost"]["plain_english"].lower())
        self.assertTrue(all(row["metric_label"] and row["why_it_matters"] for row in glossary))
        caveats = " ".join(row["caveat"].lower() for row in glossary)
        self.assertIn("public proxy", caveats)
        self.assertIn("not investment-grade", caveats)

    def test_country_concentration_guardrails_surface_review_not_failure(self) -> None:
        rows = [
            {
                "scenario_id": "scenario:base",
                "method_id": "method:mclp-pulp-cbc",
                "country_code": "DE",
                "covered_demand_share_of_method": "0.81",
            },
            {
                "scenario_id": "scenario:base",
                "method_id": "method:mclp-pulp-cbc",
                "country_code": "FR",
                "covered_demand_share_of_method": "0.19",
            },
        ]

        guardrails = build_country_concentration_guardrails(rows)

        self.assertEqual(guardrails[0]["concentration_status"], "Review")
        self.assertEqual(guardrails[0]["dominant_country"], "DE")
        self.assertEqual(guardrails[0]["dominant_country_share"], "+81.0%")
        self.assertIn("not a failure", guardrails[0]["review_prompt"].lower())

    def test_country_concentration_review_is_warning_grade(self) -> None:
        count, detail = country_concentration_review(
            [
                {"covered_demand_share_of_method": "0.81"},
                {"covered_demand_share_of_method": "0.20"},
            ]
        )

        self.assertEqual(count, 1)
        self.assertIn("warning-grade", detail)
        self.assertIn("does not fail", detail)

    def test_decision_flags_turn_method_metrics_into_review_prompts(self) -> None:
        flags = build_decision_flags(
            [
                {
                    "scenario_id": "scenario:base",
                    "mclp_coverage_uplift_pct": "0.32",
                    "min_cost_saving_pct": "0.08",
                    "dominant_coverage_country_code": "DE",
                    "dominant_coverage_country_share": "0.81",
                },
                {
                    "scenario_id": "scenario:cost",
                    "mclp_coverage_uplift_pct": "0.01",
                    "min_cost_saving_pct": "0.27",
                    "dominant_coverage_country_code": "FR",
                    "dominant_coverage_country_share": "0.42",
                },
            ]
        )

        by_scenario = {row["scenario_id"]: row for row in flags}
        self.assertEqual(by_scenario["scenario:base"]["primary_flag"], "Coverage upside")
        self.assertIn("country concentration", by_scenario["scenario:base"]["review_prompt"].lower())
        self.assertEqual(by_scenario["scenario:cost"]["primary_flag"], "Cost-pressure case")
        self.assertIn("public-proxy", by_scenario["scenario:cost"]["allowed_use_note"])

    def test_decision_flags_do_not_interpret_missing_metrics_as_parity(self) -> None:
        flags = build_decision_flags(
            [
                {
                    "scenario_id": "scenario:missing",
                    "mclp_coverage_uplift_pct": "",
                    "min_cost_saving_pct": "nan",
                    "dominant_coverage_country_share": "nan",
                }
            ]
        )

        self.assertEqual(flags[0]["primary_flag"], "Metrics unavailable")
        self.assertEqual(flags[0]["coverage_uplift"], "n/a")
        self.assertEqual(flags[0]["min_cost_saving"], "n/a")
        self.assertIn("complete metric fields", flags[0]["review_prompt"])

    def test_scenario_cards_join_business_questions_to_best_method(self) -> None:
        optimization_rows = [
            {
                "scenario_id": "scenario:radius-base",
                "method_id": "method:baseline-topk",
                "method_label": "Baseline top-k",
                "solver_status": "benchmark_feasible",
                "objective_covered_demand_weight": "8197709",
                "total_candidate_cost": "5570000",
                "selected_candidate_count": "10",
            },
            {
                "scenario_id": "scenario:radius-base",
                "method_id": "method:mclp-pulp-cbc",
                "method_label": "MILP max coverage",
                "solver_status": "optimal_milp",
                "objective_covered_demand_weight": "27652281",
                "total_candidate_cost": "5920000",
                "selected_candidate_count": "10",
            },
        ]
        business_rows = [
            {
                "scenario_id": "scenario:radius-base",
                "business_scenario_name": "Base radius max coverage",
                "business_question": "Where should a constrained shortlist prioritize coverage?",
                "solution_stability_signal": "moderate",
                "decision_readout": "coverage_uplift",
                "recommended_next_action": "Inspect selected-site zone trace.",
            }
        ]

        cards = build_scenario_cards(optimization_rows, business_rows)

        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["scenario_id"], "scenario:radius-base")
        self.assertEqual(cards[0]["business_scenario_name"], "Base radius max coverage")
        self.assertEqual(cards[0]["best_method"], "MILP max coverage")
        self.assertEqual(cards[0]["covered_demand"], "27,652,281")
        self.assertEqual(cards[0]["selected_candidates"], "10")
        self.assertEqual(cards[0]["decision_readout"], "coverage_uplift")
        self.assertEqual(cards[0]["recommended_next_action"], "Inspect selected-site zone trace.")
        self.assertIn("constrained shortlist", cards[0]["business_question"])

    def test_candidate_drilldown_prefers_lineage_when_available(self) -> None:
        selected_rows = [
            {
                "candidate_site_id": "candidate:osm:node:1",
                "selection_rank": "2",
                "country_code": "BE",
                "nuts_id": "BE100",
                "site_type": "fuel",
                "baseline_rank_within_scenario": "27",
                "baseline_score": "0.484544",
                "c_j": "560000",
            }
        ]
        trace_rows = [
            {
                "candidate_site_id": "candidate:osm:node:1",
                "source_record_id": "osm:node:1",
                "tile_job_id": "osm_tile:candidate_fuel:BE100",
                "raw_tag_keys": "amenity|brand",
                "covered_zone_count": "9",
                "covered_demand_weight": "3719438",
                "coverage_trace_zone_ids": "dz:nuts2024:BE100|dz:nuts2024:BE241",
            }
        ]

        drilldown = build_candidate_drilldown("candidate:osm:node:1", selected_rows, trace_rows)

        self.assertEqual(drilldown["candidate_site_id"], "candidate:osm:node:1")
        self.assertEqual(drilldown["selection_rank"], "2")
        self.assertEqual(drilldown["source_record_id"], "osm:node:1")
        self.assertEqual(drilldown["covered_demand_weight"], "3,719,438")
        self.assertEqual(drilldown["scenario_candidate_cost"], "560,000")
        self.assertEqual(drilldown["top_covered_zones"], "dz:nuts2024:BE100, dz:nuts2024:BE241")

    def test_weight_set_comparison_aligns_candidate_ranks(self) -> None:
        rows = [
            {
                "weight_set_name": "Base balanced",
                "candidate_site_id": "candidate:a",
                "country_code": "BE",
                "nuts_id": "BE100",
                "site_type": "fuel",
                "rank_within_weight_set_scenario": "1",
                "weighted_score": "0.91",
            },
            {
                "weight_set_name": "Risk aware",
                "candidate_site_id": "candidate:a",
                "country_code": "BE",
                "nuts_id": "BE100",
                "site_type": "fuel",
                "rank_within_weight_set_scenario": "3",
                "weighted_score": "0.74",
            },
            {
                "weight_set_name": "Risk aware",
                "candidate_site_id": "candidate:b",
                "country_code": "DE",
                "nuts_id": "DE100",
                "site_type": "services",
                "rank_within_weight_set_scenario": "1",
                "weighted_score": "0.82",
            },
        ]

        comparison = build_weight_set_comparison(rows, "Base balanced", "Risk aware")
        by_candidate = {row["candidate_site_id"]: row for row in comparison}

        self.assertEqual(by_candidate["candidate:a"]["rank_a"], 1)
        self.assertEqual(by_candidate["candidate:a"]["rank_b"], 3)
        self.assertEqual(by_candidate["candidate:a"]["rank_shift_b_vs_a"], 2)
        self.assertEqual(by_candidate["candidate:a"]["weighted_score_a"], 0.91)
        self.assertIsNone(by_candidate["candidate:b"]["rank_a"])
        self.assertEqual(by_candidate["candidate:b"]["rank_b"], 1)

    def test_release_gate_evidence_paths_are_repo_relative(self) -> None:
        row = gate_row("quality_report", True, Path.cwd() / "reports" / "chargenet" / "quality.json", 0, "ok")

        self.assertEqual(row["evidence_path"], "reports/chargenet/quality.json")

    def test_constraint_diagnostics_flag_budget_site_status_and_objective(self) -> None:
        rows = [
            {
                "scenario_id": "scenario:base",
                "method_id": "method:mclp-pulp-cbc",
                "solver_status": "optimal_milp",
                "selected_candidate_count": "2",
                "objective_covered_demand_weight": "120",
                "total_candidate_cost": "900",
                "budget": "1000",
                "k": "3",
                "candidate_pool_count": "20",
            },
            {
                "scenario_id": "scenario:tight",
                "method_id": "method:mclp-pulp-cbc",
                "solver_status": "milp_infeasible",
                "selected_candidate_count": "4",
                "objective_covered_demand_weight": "-1",
                "total_candidate_cost": "1500",
                "budget": "1000",
                "k": "3",
                "candidate_pool_count": "20",
            },
        ]

        diagnostics = constraint_diagnostics_rows(rows)
        self.assertEqual(len(diagnostics), 10)
        by_key = {(row["scenario_id"], row["method_id"], row["constraint_name"]): row for row in diagnostics}

        budget = by_key[("scenario:base", "method:mclp-pulp-cbc", "budget")]
        self.assertEqual(budget["scenario_method_id"], "scenario:base|method:mclp-pulp-cbc")
        self.assertEqual(budget["constraint_status"], "pass")
        self.assertEqual(float(budget["slack_value"]), 100.0)

        tight_budget = by_key[("scenario:tight", "method:mclp-pulp-cbc", "budget")]
        self.assertEqual(tight_budget["constraint_status"], "fail")
        self.assertEqual(float(tight_budget["slack_value"]), -500.0)

        tight_site_count = by_key[("scenario:tight", "method:mclp-pulp-cbc", "site_count")]
        self.assertEqual(tight_site_count["constraint_status"], "fail")
        self.assertEqual(float(tight_site_count["lhs_value"]), 4.0)

        tight_solver = by_key[("scenario:tight", "method:mclp-pulp-cbc", "solver_status")]
        self.assertEqual(tight_solver["constraint_status"], "fail")
        self.assertIn("not an accepted feasible status", tight_solver["diagnostic_note"])

        coverage_floor = by_key[("scenario:base", "method:mclp-pulp-cbc", "coverage_floor")]
        self.assertEqual(coverage_floor["constraint_status"], "pass")
        self.assertEqual(float(coverage_floor["lhs_value"]), 120.0)

    def test_selected_site_reconciliation_errors_catch_count_and_cost_mismatch(self) -> None:
        summary_rows = [
            {
                "scenario_method_id": "scenario:base|method:mclp-pulp-cbc",
                "selected_candidate_count": "2",
                "total_candidate_cost": "300",
            }
        ]
        selected_rows = [
            {
                "scenario_method_id": "scenario:base|method:mclp-pulp-cbc",
                "selection_rank": "1",
                "candidate_site_id": "candidate:a",
                "c_j": "100",
            }
        ]

        errors = selected_site_reconciliation_errors(summary_rows, selected_rows)

        self.assertIn("count mismatch", errors[0])
        self.assertIn("cost mismatch", " ".join(errors))

    def test_selected_site_reconciliation_errors_require_unique_grain_and_contiguous_rank(self) -> None:
        summary_rows = [
            {
                "scenario_method_id": "scenario:base|method:mclp-pulp-cbc",
                "selected_candidate_count": "2",
                "total_candidate_cost": "200",
            }
        ]
        selected_rows = [
            {
                "scenario_method_id": "scenario:base|method:mclp-pulp-cbc",
                "selection_rank": "1",
                "candidate_site_id": "candidate:a",
                "c_j": "100",
            },
            {
                "scenario_method_id": "scenario:base|method:mclp-pulp-cbc",
                "selection_rank": "3",
                "candidate_site_id": "candidate:a",
                "c_j": "100",
            },
        ]

        errors = selected_site_reconciliation_errors(summary_rows, selected_rows)

        self.assertIn("duplicate selected candidate", " ".join(errors))
        self.assertIn("rank sequence mismatch", " ".join(errors))

    def test_dq_diagnostics_match_min_cost_coverage_floor(self) -> None:
        summary = {
            ("scenario:base", MIN_COST_METHOD_ID): {
                "scenario_id": "scenario:base",
                "method_id": MIN_COST_METHOD_ID,
                "solver_status": "optimal_min_cost",
                "selected_candidate_count": "2",
                "objective_covered_demand_weight": "30",
                "coverage_floor_demand_weight": "27",
                "total_candidate_cost": "4",
                "budget": "10",
                "k": "2",
            }
        }
        diagnostics = constraint_diagnostics_rows([summary[("scenario:base", MIN_COST_METHOD_ID)]])

        self.assertTrue(diagnostics_values_match_summary(diagnostics, summary))

    def test_candidate_capex_model_uses_site_type_risk_and_data_quality(self) -> None:
        low_risk_fuel = estimate_candidate_capex({"site_type": "fuel", "rollout_risk_score": "0.1", "data_quality_score": "0.9"})
        high_risk_fuel = estimate_candidate_capex({"site_type": "fuel", "rollout_risk_score": "0.9", "data_quality_score": "0.2"})
        service_area = estimate_candidate_capex({"site_type": "services", "rollout_risk_score": "0.1", "data_quality_score": "0.9"})
        self.assertGreater(high_risk_fuel, low_risk_fuel)
        self.assertGreater(service_area, low_risk_fuel)
        self.assertEqual(low_risk_fuel % 10000, 0)

    def test_cost_proxy_explanation_rows_disclose_formula_and_limits(self) -> None:
        rows = cost_proxy_explanation_rows()
        by_key = {row["cost_proxy_driver"]: row for row in rows}

        self.assertIn("site_type_base", by_key)
        self.assertIn("fuel=450000", by_key["site_type_base"]["current_logic"])
        self.assertIn("services=650000", by_key["site_type_base"]["current_logic"])
        self.assertIn("rollout_risk", by_key)
        self.assertIn("data_quality", by_key)
        self.assertIn("nearest 10000", by_key["rounding"]["current_logic"])
        limitations = " ".join(row["limitation"] for row in rows).lower()
        self.assertIn("not vendor quotes", limitations)
        self.assertIn("grid capacity", limitations)
        self.assertIn("not investment-grade", limitations)

    def test_named_optimization_config_exposes_required_scenarios(self) -> None:
        configs = load_named_scenario_configs()

        self.assertIn("highway-corridor-focus", configs)
        self.assertIn("rural-underserved", configs)
        self.assertIn("competitor-gap-focused", configs)
        self.assertTrue(all(config["base_scenario_id"] == "scenario:radius-base" for config in configs.values()))

    def test_named_scenario_priority_score_uses_scenario_specific_biases(self) -> None:
        base_candidate = {
            "baseline_score": "0.6",
            "coverage_component": "0.4",
            "site_type": "fuel",
            "raw_tags_json": "{}",
            "nearest_zone_population_score": 0.2,
            "charger_gap_score": 0.1,
            "high_demand_gap_score": 0.2,
        }
        highway_candidate = {**base_candidate, "site_type": "services", "raw_tags_json": '{"highway": "services"}'}
        highway_config = {
            "priority_weights": {
                "baseline_score": 0.4,
                "coverage_component": 0.1,
                "highway_corridor_proxy": 0.5,
            }
        }
        rural_config = {
            "priority_weights": {
                "baseline_score": 0.3,
                "low_population_proxy": 0.5,
                "charger_gap_proxy": 0.2,
            }
        }

        self.assertGreater(scenario_priority_score(highway_candidate, highway_config), scenario_priority_score(base_candidate, highway_config))
        self.assertGreater(scenario_priority_score({**base_candidate, "nearest_zone_population_score": 0.9}, rural_config), scenario_priority_score(base_candidate, rural_config))

    def test_named_optimization_builder_writes_summary_and_selected_outputs(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_path = root / "named_scenarios.json"
            baseline_path = root / "baseline.csv"
            coverage_path = root / "coverage.csv"
            scenario_path = root / "scenario.csv"
            clean_candidate_path = root / "clean_candidates.csv"
            demand_zone_path = root / "demand_zones.csv"
            existing_charger_path = root / "chargers.csv"
            summary_output_path = root / "named_summary.csv"
            selected_output_path = root / "named_selected.csv"
            config_path.write_text(
                json.dumps(
                    [
                        {
                            "scenario_slug": "test-highway",
                            "named_scenario_id": "named-scenario:test-highway",
                            "scenario_name": "Test highway",
                            "business_framing": "Tiny fixture.",
                            "base_scenario_id": "scenario:base",
                            "candidate_pool_size": 2,
                            "priority_weights": {
                                "baseline_score": 0.4,
                                "coverage_component": 0.1,
                                "highway_corridor_proxy": 0.5,
                            },
                        }
                    ]
                ),
                encoding="utf-8",
            )
            baseline_path.write_text(
                "\n".join(
                    [
                        "scenario_id,candidate_site_id,country_code,nuts_id,site_type,coverage_radius_km,coverage_component,baseline_score,rank_within_scenario",
                        "scenario:base,candidate:a,BE,BE100,fuel,30,0.8,0.9,1",
                        "scenario:base,candidate:b,BE,BE100,services,30,0.7,0.7,2",
                        "scenario:base,candidate:c,BE,BE211,fuel,30,0.6,0.6,3",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            coverage_path.write_text(
                "\n".join(
                    [
                        "candidate_site_id,demand_zone_id,coverage_radius_km,pair_eligible_flag,demand_weight_contribution",
                        "candidate:a,dz:1,30,1,10",
                        "candidate:b,dz:2,30,1,20",
                        "candidate:c,dz:3,30,1,30",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            scenario_path.write_text(
                "\n".join(
                    [
                        "scenario_id,entity_type,entity_id,c_j,b,k,service_radius_km",
                        "scenario:base,candidate_site,candidate:a,1,2,1,30",
                        "scenario:base,candidate_site,candidate:b,1,2,1,30",
                        "scenario:base,candidate_site,candidate:c,1,2,1,30",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            clean_candidate_path.write_text(
                "\n".join(
                    [
                        "candidate_site_id,nuts_id,site_type,raw_tags_json",
                        'candidate:a,BE100,fuel,"{""amenity"": ""fuel""}"',
                        'candidate:b,BE100,services,"{""highway"": ""services""}"',
                        'candidate:c,BE211,fuel,"{""amenity"": ""fuel""}"',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            demand_zone_path.write_text(
                "\n".join(
                    [
                        "demand_zone_id,nuts_id,population,demand_weight",
                        "dz:nuts2024:BE100,BE100,1000,1000",
                        "dz:nuts2024:BE211,BE211,100,100",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            existing_charger_path.write_text(
                "\n".join(["charger_source_id,nuts_id", "charger:1,BE100"]) + "\n",
                encoding="utf-8",
            )

            paths = build_named_optimization_scenario(
                "test-highway",
                config_path=config_path,
                baseline_path=baseline_path,
                coverage_path=coverage_path,
                scenario_path=scenario_path,
                clean_candidate_path=clean_candidate_path,
                demand_zone_path=demand_zone_path,
                existing_charger_path=existing_charger_path,
                summary_output_path=summary_output_path,
                selected_output_path=selected_output_path,
            )
            with summary_output_path.open(newline="", encoding="utf-8") as handle:
                summary_rows = list(csv.DictReader(handle))
            with selected_output_path.open(newline="", encoding="utf-8") as handle:
                selected_rows = list(csv.DictReader(handle))

        self.assertEqual(paths, [summary_output_path, selected_output_path])
        self.assertEqual(len(summary_rows), 1)
        self.assertEqual(summary_rows[0]["method_id"], NAMED_MCLP_METHOD_ID)
        self.assertEqual(summary_rows[0]["solver_status"], "optimal_milp")
        self.assertEqual(summary_rows[0]["named_scenario_id"], "named-scenario:test-highway")
        self.assertEqual(selected_rows[0]["candidate_site_id"], "candidate:b")
        self.assertEqual(float(selected_rows[0]["scenario_priority_score"]), scenario_priority_score({"baseline_score": "0.7", "coverage_component": "0.7", "site_type": "services", "raw_tags_json": '{"highway": "services"}'}, {"priority_weights": {"baseline_score": 0.4, "coverage_component": 0.1, "highway_corridor_proxy": 0.5}}))


if __name__ == "__main__":
    unittest.main()
