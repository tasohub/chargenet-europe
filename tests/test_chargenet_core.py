from __future__ import annotations

import csv
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from chargenet.ids import candidate_site_id, demand_zone_id, osm_object_id, scenario_id
from chargenet.baseline import SENSITIVITY_WEIGHT_SETS, action_bucket, build_baseline_sensitivity_tile_smoke, clamp, compute_weighted_score, validate_weight_set
from chargenet.osm_clean import element_coordinate, infer_candidate_site_type
from chargenet.cli import build_parser, main, parse_csv_arg
from chargenet.optimization import constraint_diagnostics_rows, coverage_objective, solve_mclp_exact, solve_mclp_pulp
from chargenet.osm_extract import build_overpass_query, osm_fetch_gate_summary, osm_tile_progress_summary, parse_osm_filter, read_fetched_tile_job_ids, rebuild_osm_tile_execution_log_all, select_batch_jobs, select_jobs, write_log
from chargenet.pilot import geometry_bbox_midpoint, iter_lon_lat_pairs, load_eurostat_population_by_geo
from chargenet.scenarios import estimate_candidate_capex
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
        self.assertEqual(len(diagnostics), 8)
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

    def test_candidate_capex_model_uses_site_type_risk_and_data_quality(self) -> None:
        low_risk_fuel = estimate_candidate_capex({"site_type": "fuel", "rollout_risk_score": "0.1", "data_quality_score": "0.9"})
        high_risk_fuel = estimate_candidate_capex({"site_type": "fuel", "rollout_risk_score": "0.9", "data_quality_score": "0.2"})
        service_area = estimate_candidate_capex({"site_type": "services", "rollout_risk_score": "0.1", "data_quality_score": "0.9"})
        self.assertGreater(high_risk_fuel, low_risk_fuel)
        self.assertGreater(service_area, low_risk_fuel)
        self.assertEqual(low_risk_fuel % 10000, 0)


if __name__ == "__main__":
    unittest.main()
