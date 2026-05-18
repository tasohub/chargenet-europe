# ChargeNet Europe - Phase 3 Data Model And Quality Plan

## Purpose

Phase 3 turns the Phase 2 source audit into a reproducible data foundation for algorithms, Excel, and Power BI. The phase does not try to solve the optimization problem yet. Its job is to freeze the data contracts that Phase 4 baseline scoring and Phase 5 MILP will both use.

## Implementation Status

**Current status:** Sample pipeline skeleton implemented and verified. This is a Phase 3 implementation checkpoint, not the final full-pilot Phase 3 gate.

**Current command:**

```powershell
python -m chargenet.cli run-phase3-sample
```

**Pilot NUTS3 geometry commands:**

```powershell
python -m chargenet.cli ingest-gisco-nuts3
python -m chargenet.cli ingest-eurostat-population-pilot
python -m chargenet.cli build-pilot-nuts3
python -m chargenet.cli export-powerbi-sample
python -m chargenet.cli build-osm-tile-plan
python -m chargenet.cli run-osm-tile-smoke --max-jobs 1 --country BE --extract charging_stations --delay-seconds 0 --output-limit 25
python -m chargenet.cli run-osm-tile-smoke --max-jobs 1 --country BE --extract candidate_fuel --delay-seconds 0 --output-limit 25
python -m chargenet.cli run-osm-tile-smoke --max-jobs 1 --country BE --extract candidate_services --delay-seconds 0 --output-limit 25
python -m chargenet.cli run-osm-pilot-smoke --countries DE,FR,NL --extracts charging_stations,candidate_fuel,candidate_services --max-jobs-per-combo 1 --delay-seconds 2 --output-limit 20
python -m chargenet.cli rebuild-osm-tile-log
python -m chargenet.cli build-osm-tile-smoke-clean
python -m chargenet.cli build-osm-candidate-smoke-clean
python -m chargenet.cli build-tile-smoke-coverage
python -m chargenet.cli build-tile-smoke-scenario-inputs
python -m chargenet.cli build-baseline-scores-tile-smoke
python -m chargenet.cli build-baseline-sensitivity-tile-smoke
python -m chargenet.cli build-optimization-results-tile-smoke
python -m chargenet.cli build-optimization-diagnostics-tile-smoke
python -m chargenet.cli export-powerbi-sample
python -m chargenet.cli osm-tile-progress
python -m chargenet.cli run-osm-tile-batch --max-jobs 9 --countries BE,DE,FR,NL --extracts charging_stations,candidate_fuel,candidate_services --output-limit 20
```

**Rebuild command without network fetch:**

```powershell
python -m chargenet.cli build-from-existing-samples
```

**Verified outputs:**

| Output | Path | Status |
|---|---|---|
| License manifest | `config/chargenet/license_manifest.json` | Generated |
| Service radius config | `config/chargenet/service_radius_scenarios.json` | Generated |
| Raw samples | `data/chargenet/raw/` | Generated locally, ignored from public repo |
| Immutable raw run snapshot | `data/chargenet/raw/runs/<run_id>/` | Generated locally and validated through manifest `immutable_run_path` |
| Clean samples | `data/chargenet/clean/` | Generated locally, ignored from public repo |
| Coverage mart sample | `data/chargenet/marts/fact_candidate_zone_coverage_sample.csv` | Generated for every configured radius: 15, 30, 50 km |
| Scenario input sample | `data/chargenet/marts/fact_scenario_inputs_sample.csv` | Generated for every sample candidate and demand zone across every configured radius |
| Pilot NUTS3 demand zones | `data/chargenet/clean/clean_demand_zones_nuts3_pilot.csv` | Generated for BE/DE/FR/NL; Eurostat population joined with 0 missing values |
| Data dictionary sample | `data/chargenet/marts/data_dictionary_sample.csv` | Generated for every clean and mart sample column |
| Quality report JSON | `reports/chargenet/phase3_sample_quality_report.json` | Generated locally, ignored from public repo |
| Power BI exports | `reports/chargenet/powerbi_exports/` | Generated locally with dimensions, facts, relationship manifest, and export manifest |
| OSM tile plan | `data/chargenet/marts/osm_pilot_tile_plan.csv` | Generated locally as planned-not-run Overpass job matrix |
| OSM tile batch dry-run | `python -m chargenet.cli run-osm-tile-batch ...` | Selects next unfetched jobs without calling Overpass unless `--execute` is passed |
| OSM tile smoke clean chargers | `data/chargenet/clean/clean_existing_chargers_tile_smoke.csv` | Generated locally from controlled BE/DE/FR/NL smoke runs |
| OSM tile smoke clean candidates | `data/chargenet/clean/clean_candidate_sites_tile_smoke.csv` | Generated locally from controlled BE/DE/FR/NL smoke runs |
| Tile-smoke coverage mart | `data/chargenet/marts/fact_candidate_zone_coverage_tile_smoke.csv` | Generated locally for smoke candidates against all pilot demand zones |
| Tile-smoke scenario inputs | `data/chargenet/marts/fact_scenario_inputs_tile_smoke.csv` | Generated locally for smoke candidates and pilot demand zones |
| Tile-smoke optimization diagnostics | `data/chargenet/marts/mart_optimization_constraint_diagnostics_tile_smoke.csv` | Generated locally for every scenario-method optimization result |

## Phase 3 Grain

**Pilot countries:** Germany, France, Netherlands, Belgium.

**Locked geography version:** NUTS 2024.

**V1 demand-zone grain:** NUTS3.

Raw data can store all available NUTS levels, but optimization facts and Power BI facts should use `dz:nuts2024:{NUTS_ID}` for NUTS3 demand zones.

## Build Order

1. Raw ingest.
2. Raw validation.
3. Clean normalization and NUTS joins.
4. Data dictionary generation.
5. Mart build.
6. Power BI CSV export.
7. Phase 3 data quality report.
8. Phase 3 specialist QA.

## Raw Tables

| Table | Grain | Primary key | Notes |
|---|---|---|---|
| `raw_osm_charging_stations` | One OSM object per row | `raw_osm_object_id` | Preserve raw tag JSON and source metadata. |
| `raw_osm_candidate_pois` | One OSM object per row | `raw_osm_object_id` | Candidate POIs are proxies, not feasible site confirmations. |
| `raw_gisco_nuts_geometries` | One NUTS feature per row | `nuts_version`, `nuts_id` | Store geometry or sidecar path and centroid. |
| `raw_gisco_nuts_attributes` | One NUTS attribute row | `nuts_version`, `nuts_id` | Store urban/coastal/mountain typology. |
| `raw_eurostat_population` | One JSON-stat dimension combination per row | `dataset`, `geo`, `time`, `unit`, `sex`, `age` | Store dimensions explicitly. |
| `raw_eafo_country_context` | Optional country-period-metric row | `country_code`, `period`, `metric_name` | Deck/context only until reproducible download is pinned. |

## Clean Tables

| Table | Grain | Required role |
|---|---|---|
| `clean_existing_chargers` | One cleaned charger object or cluster per row | Current supply baseline and competition proxy. |
| `clean_candidate_sites` | One candidate POI or candidate cluster per row | Candidate set `J` for scoring and MILP. |
| `clean_demand_zones` | One NUTS3 demand zone per row | Demand set `I` and demand weight `d_i`. |

Every clean table must include deterministic IDs, source lineage, and proxy/assumption labels where relevant.

## Optimization Input Freeze

Phase 3 must produce a frozen input set before Phase 4 or Phase 5 starts:

| Input | Source table | Required by |
|---|---|---|
| `candidate_site_id` | `clean_candidate_sites` | Baseline, MILP, Power BI |
| `demand_zone_id` | `clean_demand_zones` | Baseline, MILP, Power BI |
| `d_i` | `fact_scenario_inputs` | MILP objective |
| `a_ij` | `fact_candidate_zone_coverage` | MILP coverage relation |
| `c_j` | `fact_scenario_inputs` | Budget constraint |
| `b` | `fact_scenario_inputs` | Budget constraint |
| `k` | `fact_scenario_inputs` | Site-count constraint |
| `service_radius_km` | `service_radius_scenarios` and `fact_candidate_zone_coverage` | Baseline and MILP comparability |

Baseline and MILP must not create different IDs, different radii, or different candidate/demand sets.

## Required Marts

| Mart | Grain | Required fields |
|---|---|---|
| `fact_candidate_zone_coverage` | One row per `candidate_site_id + demand_zone_id + coverage_radius_km` | `distance_km`, `distance_method_version`, `a_ij`, `same_country_flag`, `cross_border_allowed_flag`, `pair_eligible_flag`, `pair_exclusion_reason`, `distance_confidence_flag` |
| `fact_scenario_inputs` | One scenario-entity input row | `scenario_id`, `entity_type`, `entity_id`, `d_i`, `c_j`, `b`, `k`, `r_j`, `rho`, `service_radius_km`, version fields, penalty flags |
| `data_dictionary` | One row per table column | Classification, allowed use, source, transformation rule, quality rule, license key |

## Distance Assumptions

V1 uses straight-line geodesic distance:

- Coordinate system: WGS84.
- Method: haversine.
- Distance method version: `haversine_wgs84_v1`.
- Demand-zone representative point: NUTS centroid.
- OSM ways/relations: use center coordinates where point coordinates are unavailable.
- Cross-border coverage: blocked by default in the sample until explicitly enabled by scenario.
- Rounded distance: three decimals in sample outputs.

This is a coverage proxy, not road-network travel time.

## Service Radius Scenarios

The sample config freezes three radius assumptions:

| Scenario | Radius | Treatment |
|---|---:|---|
| `scenario:radius-conservative` | 15 km | Assumption |
| `scenario:radius-base` | 30 km | Assumption |
| `scenario:radius-aggressive` | 50 km | Assumption |

These values are placeholders for sensitivity. They must be used consistently by baseline and MILP until changed through a named scenario revision.

## Access Equity Outputs

Phase 3 must make equity measurable, not narrative-only.

Required pre-optimization fields:
- `baseline_nearest_charger_distance_km`
- `baseline_charger_count_within_radius`
- `underserved_zone_flag`
- `urban_density_segment`

Post-selection/result fields should be produced after baseline or MILP outputs exist, not as Phase 3 input features:
- `coverage_after_selection_flag`
- `dense_market_coverage_share`
- `underserved_coverage_share`
- `access_gap_reduction`

The public wording should be **access-equity tradeoff**, not social-impact optimization.

## Public-Release Safety

Generated raw/clean/mart files are local working artifacts. Public materials should publish:

- Code.
- Source configs.
- License and attribution manifest.
- Data dictionary.
- Small illustrative samples only when license-safe.
- Screenshots or aggregates with source notes.

Large raw OSM extracts and derived OSM databases should not be casually committed.

The repository root and artifact folders include ignore rules for `__pycache__`, raw/clean/mart generated files, and generated reports. Track code, docs, configs, and explicit license-safe sample fixtures only.

## Current Verification Evidence

Commands run successfully:

```powershell
python -m unittest discover -s tests
python -m chargenet.cli --help
python -m chargenet.cli run-phase3-sample
python -m chargenet.cli ingest-gisco-nuts3
python -m chargenet.cli ingest-eurostat-population-pilot
python -m chargenet.cli build-pilot-nuts3
python -m chargenet.cli export-powerbi-sample
python -m chargenet.cli build-osm-tile-plan
python -m chargenet.cli run-osm-tile-smoke --max-jobs 1 --country BE --extract charging_stations --delay-seconds 0 --output-limit 25
python -m chargenet.cli run-osm-tile-smoke --max-jobs 1 --country BE --extract candidate_fuel --delay-seconds 0 --output-limit 25
python -m chargenet.cli run-osm-tile-smoke --max-jobs 1 --country BE --extract candidate_services --delay-seconds 0 --output-limit 25
python -m chargenet.cli run-osm-pilot-smoke --countries DE,FR,NL --extracts charging_stations,candidate_fuel,candidate_services --max-jobs-per-combo 1 --delay-seconds 2 --output-limit 20
python -m chargenet.cli rebuild-osm-tile-log
python -m chargenet.cli build-osm-tile-smoke-clean
python -m chargenet.cli build-osm-candidate-smoke-clean
python -m chargenet.cli build-tile-smoke-coverage
python -m chargenet.cli build-tile-smoke-scenario-inputs
python -m chargenet.cli build-baseline-scores-tile-smoke
python -m chargenet.cli build-baseline-sensitivity-tile-smoke
python -m chargenet.cli build-optimization-results-tile-smoke
python -m chargenet.cli build-optimization-diagnostics-tile-smoke
python -m chargenet.cli export-powerbi-sample
python -m chargenet.cli run-osm-tile-batch --max-jobs 9 --countries BE,DE,FR,NL --extracts charging_stations,candidate_fuel,candidate_services --output-limit 20
python -m chargenet.cli osm-tile-progress
python -m chargenet.cli validate
```

Latest quality report summary:

| Section | Passed | Failure count |
|---|---:|---:|
| Raw snapshots | true | 0 |
| Clean and mart samples | true | 0 |

The current generated quality report passes with 2,068 clean/mart checks. The cumulative fetch log includes one historical Overpass HTTP 429 attempt, but it has 0 unresolved failed attempts after the later retry. The last certified 324-job model snapshot had clean/mart 1,711 checks and 0 failures.

Latest sample output counts:

| Output | Count / coverage |
|---|---|
| Candidate-zone coverage rows | 60 rows |
| Coverage radii | 15, 30, 50 km |
| Scenario input rows | 63 rows |
| Candidate scenario rows | 60 rows |
| Data dictionary rows | 261 rows |
| Immutable manifest checks | 6 passed |
| Pilot NUTS3 demand-zone rows | 585 rows |
| Pilot NUTS3 country counts | BE 44, DE 400, FR 101, NL 40 |
| Pilot NUTS3 population missing values | 0 rows |
| Power BI export files | 14 CSV exports plus manifest |
| Power BI model relationships | 17 rows |
| OSM tile plan rows | 1,755 rows |
| Last certified OSM tile progress | 324 fetched, 0 failed, 1,431 remaining |
| Current fetch-only progress | 413 fetched, 0 unresolved failed, 1,342 remaining; 1 historical Overpass HTTP 429 retry resolved |
| OSM capped Overpass requests | 207 fetched requests hit `output_limit=20` |
| OSM charger smoke clean rows | 1,726 rows |
| OSM candidate smoke clean rows | 1,973 rows |
| Tile-smoke coverage rows | 3,462,615 rows |
| Tile-smoke scenario input rows | 7,674 rows |
| Tile-smoke baseline score rows | 5,919 rows |
| Tile-smoke baseline sensitivity rows | 29,595 rows |
| Tile-smoke optimization summary rows | 9 rows |
| Tile-smoke optimization diagnostics rows | 36 rows |
| Tile-smoke selected-site rows | 63 rows |

The latest quality report checks raw snapshot existence, manifest hash parity, license-manifest mapping, immutable run path existence, OSM JSON shape, FK integrity, radius parity, scenario candidate/demand completeness, data-dictionary coverage, optional pilot NUTS3 country coverage, pilot NUTS3 population completeness, BI export completeness, OSM tile-plan completeness, OSM tile log safety, and smoke clean table quality.

Future live OSM batches should prefer triplet-friendly batch sizes such as 9, 12, 15, or 24 so `charging_stations`, `candidate_fuel`, and `candidate_services` jobs stay aligned by tile when reviewing progress.

## Phase 3 Remaining Work

- Pause or slow resumable pilot-country tile batches because the log now includes one historical Overpass HTTP 429. Resume only with longer delay/backoff and keep using cumulative `osm-fetch-gate --output-limit 20`. The sample skeleton is deliberately not yet the full DE/FR/NL/BE OSM foundation.
- Add immutable run IDs to full pilot extracts, following the sample manifest pattern.
- Keep `build-from-existing-samples` behavior as the model for future build-from-run behavior.
- Flatten Eurostat raw payloads into full raw tables.
- Improve the current NUTS3 representative-point method beyond `bbox_midpoint_wgs84_v1` before using maps as final portfolio evidence.
- Regenerate BI exports from full pilot candidate and coverage facts after OSM tiling.
- Write a human-readable `phase-3-data-quality-report.md` after full sample expansion.
- Run Phase 3 specialist QA with Data Engineering QA, Data Source QA, Power BI QA, and Overclaim And Ethics QA.
