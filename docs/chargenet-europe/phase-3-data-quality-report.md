# ChargeNet Europe - Phase 3 Data Quality Checkpoint

## Scope

This report covers the current certified Phase 3 checkpoint. It demonstrates the public-data pipeline skeleton, the pilot NUTS3 demand-zone foundation, and the BI export layer. It does not yet certify the full pilot-country OSM candidate and charger extraction.

## Current Artifacts

| Layer | Artifact | Current state |
|---|---|---|
| Config | `license_manifest.json` | Source decisions and attribution rules generated. |
| Config | `service_radius_scenarios.json` | 15, 30, and 50 km service-radius assumptions frozen. |
| Raw | Sample OSM/GISCO/Eurostat/Open Charge Map probe snapshots | Generated locally with manifests and immutable run paths. |
| Raw | GISCO NUTS3 2024 | Generated locally for pilot demand-zone foundation. |
| Raw | Eurostat 2025 regional population | Generated locally and joined to pilot NUTS3 rows. |
| Clean | `clean_demand_zones_nuts3_pilot.csv` | 585 BE/DE/FR/NL NUTS3 rows, 0 missing population values. |
| Mart | `fact_candidate_zone_coverage_sample.csv` | 60 sample coverage rows across all configured radii. |
| Mart | `fact_scenario_inputs_sample.csv` | 63 sample scenario input rows. |
| Mart | `osm_pilot_tile_plan.csv` | 1,755 planned-not-run OSM tile jobs. |
| Clean | `clean_existing_chargers_tile_smoke.csv` | 1,726 clean charger rows from controlled BE/DE/FR/NL smoke and batch tiles. |
| Clean | `clean_candidate_sites_tile_smoke.csv` | 1,973 clean candidate-site rows from controlled BE/DE/FR/NL fuel and services smoke/batch tiles. |
| Mart | `fact_candidate_zone_coverage_tile_smoke.csv` | 3,462,615 smoke/batch candidate-zone-radius rows. |
| Mart | `fact_scenario_inputs_tile_smoke.csv` | 7,674 smoke/batch scenario-entity rows. |
| Mart | `mart_candidate_baseline_scores_tile_smoke.csv` | 5,919 baseline diligence-score rows. |
| Mart | `mart_baseline_sensitivity_tile_smoke.csv` | 29,595 baseline sensitivity rows from 5 weight sets. |
| Mart | `mart_optimization_results_tile_smoke.csv` | 9 optimization summary rows, including PuLP/CBC MILP. |
| Mart | `mart_optimization_constraint_diagnostics_tile_smoke.csv` | 36 constraint diagnostic rows across scenario-method outputs. |
| Mart | `fact_optimization_selected_sites_tile_smoke.csv` | 63 selected-site rows. |
| BI | `reports/chargenet/powerbi_exports/` | 14 CSV exports plus manifest. |
| CLI | `run-osm-tile-batch` / `osm-tile-progress` | Full-gate dry-run and progress controls added; no broad extraction executed by default. |

## Quality Results

Machine-readable report: `reports/chargenet/phase3_sample_quality_report.json`.

The last certified 324-job model snapshot passed all checks. The current generated report also passes after the later `DE236` retry resolved the only failed request. The cumulative log still records one historical Overpass HTTP 429 attempt as a rate-limit warning.

| Section | Result |
|---|---|
| Raw snapshot checks | Passed: 47 checks, 0 failures. |
| Manifest hash checks | Passed for generated sample and optional pilot raw snapshots. |
| License manifest mapping | Passed for generated raw manifests. |
| Immutable run path checks | Passed for generated raw manifests. |
| Clean/mart required fields | Current generated report: 2,068 checks, 0 failures. Last certified 324-job snapshot: 1,711 checks, 0 failures. |
| Candidate/demand/coverage FK checks | Passed for current capped smoke/batch scope. |
| Scenario radius parity | Passed for 15, 30, and 50 km. |
| Pilot NUTS3 country coverage | Passed for BE, DE, FR, NL. |
| Pilot NUTS3 population completeness | Passed with 585 of 585 rows populated. |
| BI export completeness | Passed for current sample/pilot export folder. |
| OSM tile-plan completeness | Passed with 1,755 planned-not-run tile jobs. |
| OSM tile log | Last certified snapshot passed for 324 cumulative fetched smoke/batch jobs, 0 failed jobs, all pilot countries, and all three extract types. Current fetch-only log has 413 fetched jobs, 0 unresolved failed attempts, and 1 historical Overpass HTTP 429 that was later retried successfully. |
| OSM smoke clean tables | Passed for charger and candidate smoke tables. |
| Tile-smoke coverage matrix | Passed with 3,462,615 rows and all configured radii. |
| Tile-smoke scenario inputs | Passed with complete `d_i`, `c_j`, `b`, and `k` for smoke scope. |
| Tile-smoke candidate costs | Passed with positive, variable, version-labeled `c_j`; 6 unique values from 550,000 to 850,000. |
| Tile-smoke baseline scores | Passed with bounded scores and diligence-only action language. |
| Tile-smoke baseline sensitivity | Passed with 29,595 rows, 5 valid weight sets, bounded scores, and diligence-only language. |
| Tile-smoke optimization | Passed with budget, site-count, selected-candidate FK, scenario-method FK, method-coverage, non-negative objective, diagnostics value parity, and diligence-language checks. |

## Pilot Demand-Zone Summary

| Country | NUTS3 zones | Missing population | Population sum |
|---|---:|---:|---:|
| BE | 44 | 0 | 11,883,495 |
| DE | 400 | 0 | 83,577,140 |
| FR | 101 | 0 | 68,882,600 |
| NL | 40 | 0 | 18,044,027 |

Population remains a demand proxy, not observed EV charging demand.

## BI Export Summary

| Export | Rows |
|---|---:|
| `dim_demand_zone.csv` | 585 |
| `dim_candidate_site_sample.csv` | 20 |
| `dim_candidate_site_tile_smoke.csv` | 1,973 |
| `dim_scenario.csv` | 3 |
| `fact_candidate_zone_coverage_sample.csv` | 60 |
| `fact_candidate_zone_coverage_tile_smoke.csv` | 3,462,615 |
| `fact_scenario_inputs_sample.csv` | 63 |
| `fact_scenario_inputs_tile_smoke.csv` | 7,674 |
| `mart_candidate_baseline_scores_tile_smoke.csv` | 5,919 |
| `mart_baseline_sensitivity_tile_smoke.csv` | 29,595 |
| `mart_optimization_results_tile_smoke.csv` | 9 |
| `mart_optimization_constraint_diagnostics_tile_smoke.csv` | 36 |
| `fact_optimization_selected_sites_tile_smoke.csv` | 63 |
| `model_relationships.csv` | 17 |

The BI layer is usable for a demo dashboard, but candidate and coverage facts remain capped smoke/batch-scoped until full OSM tiled extraction completes.

## OSM Smoke/Batch Summary

| Smoke extract | Scope | Cumulative fetched jobs | Clean rows | Status |
|---|---|---:|---:|---|
| `charging_stations` | Controlled BE/DE/FR/NL smoke plus expanded BE/DE batch tiles | 108 | 1,726 | Raw snapshots, manifests, and clean charger table generated. |
| `candidate_fuel` | Controlled BE/DE/FR/NL smoke plus expanded BE/DE batch tiles | 108 | 1,754 | Raw snapshots, manifests, and clean candidate-site table generated. |
| `candidate_services` | Controlled BE/DE/FR/NL smoke plus expanded BE/DE batch tiles | 108 | 219 | Raw snapshots, manifests, and clean candidate-site table generated. |

These smoke/batch outputs validate the extraction and cleaning mechanics. They are not full pilot supply or candidate facts.

The last certified model snapshot stands at 324 fetched jobs out of 1,755 planned jobs, with 1,431 remaining and 0 failed attempts. That certified snapshot includes 207 requests capped at `output_limit=20`, so it remains a capped smoke/batch sample and cannot be described as complete OSM coverage.

Fetch-only progress later reached 413 fetched jobs, 1,342 remaining jobs, and 0 unresolved failed attempts. The log includes 1 historical Overpass `HTTP 429` on `osm_tile:candidate_fuel:DE236`; a later retry fetched that tile successfully. Because the 413-job state has not gone through a milestone rebuild, it is not a certified model snapshot and should not be used for downstream claims until a milestone rebuild passes.

Smoke/batch candidate coverage was built against all 585 pilot NUTS3 demand zones across 15, 30, and 50 km radius scenarios. That produces a useful optimization-readiness test, but it remains a capped batch matrix because the candidate set is still a small subset of the planned 1,755 OSM jobs, not the full candidate universe.

The baseline score ranks smoke candidates for diligence prioritization only. It is a portfolio demo layer, not a site rollout decision.

The baseline sensitivity mart tests five weight sets and shows rank movement versus the base baseline. It supports robustness discussion in BI and the Phase 4 scoring memo, but it remains smoke-scoped.

The optimization summary compares `method:baseline-topk`, `method:mclp-shortlist-exact`, and `method:mclp-pulp-cbc`. The diagnostics mart checks budget, site-count, solver status, and non-negative objective for every scenario-method row. It is a smoke-scope MILP checkpoint, not a full-pilot result.

## Open Gate Items

- Continue controlled OSM tiled extraction only while rate-limit behavior remains stable and every batch has 0 failed jobs.
- Convert OSM tile outputs into full pilot `clean_existing_chargers` and `clean_candidate_sites`.
- Regenerate candidate-zone coverage for the full pilot candidate and demand-zone sets.
- Regenerate Power BI exports from the full pilot facts.
- Replace or clearly caveat `bbox_midpoint_wgs84_v1` before final map screenshots.
- Run another specialist QA pass before declaring the full Phase 3 gate passed.
