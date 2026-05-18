# ChargeNet Europe - Phase 3 Pilot Expansion Plan

## Purpose

This plan defines how to move from the Brussels smoke-test sample to the full V1 pilot scope: Germany, France, Netherlands, and Belgium at NUTS3 demand-zone grain.

The goal is not to download everything as fast as possible. The goal is to expand safely without breaking public-source rate limits, licensing rules, or optimization input consistency.

## Current Baseline

The current implementation supports:

- Live sample ingest.
- Immutable raw run snapshots under `data/chargenet/raw/runs/<run_id>/`.
- Build-from-existing raw samples without network fetch.
- License manifest.
- Service radius config.
- Clean sample tables.
- `fact_candidate_zone_coverage_sample` for 15, 30, and 50 km.
- `fact_scenario_inputs_sample` for every sample candidate and demand zone.
- Data dictionary sample for every clean/mart sample column.
- JSON quality report with raw and clean/mart checks.
- GISCO NUTS 2024 level-3 ingest.
- Pilot NUTS3 demand-zone table for BE/DE/FR/NL with 585 rows and 0 missing Eurostat population values.
- Power BI relationship-ready export folder for the current sample/pilot scope.
- OSM planned-not-run tile matrix with 1,755 jobs.
- Controlled OSM smoke/batch runs across BE/DE/FR/NL. The last certified model snapshot totals 324 fetched jobs with expanded BE/DE batch tiles.
- Fetch-only progress later reached 413 fetched jobs with 0 unresolved failed attempts. The log includes one historical Overpass HTTP 429 that was later retried successfully. This later fetch-only state is not a certified model rebuild.
- `run-osm-pilot-smoke` orchestration with dry-run, country/extract lists, per-combo job caps, request delay, and previously fetched tile exclusion.
- `run-osm-tile-batch` and `osm-tile-progress` for full-gate extraction dry-runs, progress checks, and resumable batches.
- Tile-smoke coverage and scenario-input marts for optimization-readiness testing.
- Tile-smoke baseline diligence-score mart for Phase 4 scoring readiness.
- Tile-smoke baseline sensitivity mart for Phase 4 robustness discussion.
- Tile-smoke optimization summary and selected-site marts for Phase 5 MVP readiness.

This is a smoke-test skeleton, not the final Phase 3 pilot data foundation.

## Full Pilot Scope

| Dimension | V1 setting |
|---|---|
| Countries | BE, DE, FR, NL |
| NUTS version | 2024 |
| Demand-zone grain | NUTS3 |
| Demand proxy | Eurostat regional population, total sex, total age, unit number |
| Candidate source | OSM/Overpass POI proxies |
| Existing supply source | OSM/Overpass charging stations |
| Distance method | Haversine WGS84 |
| Coverage radii | 15, 30, 50 km |
| Cross-border coverage | Blocked by default until a named corridor scenario enables it |

## Expansion Sequence

### Step 1 - GISCO NUTS3 Foundation

Build first because every downstream table needs NUTS3 IDs and centroids.

Status: implemented as a geometry foundation. The current output uses `bbox_midpoint_wgs84_v1` as a transparent representative-point proxy.

Required outputs:
- `raw_gisco_nuts_geometries` for NUTS level 3.
- `raw_gisco_nuts_attributes`.
- `clean_demand_zones` for BE/DE/FR/NL NUTS3 rows.
- Centroid latitude/longitude for every retained NUTS3 row.
- `country_code`, `nuts_version`, `nuts_id`, `zone_name`, `urban_type`, `coast_type`, `mountain_type`.

Validation:
- 100% retained demand zones have `demand_zone_id`.
- 100% have centroid coordinates.
- 100% use `nuts_version=2024`.
- Only BE/DE/FR/NL rows appear in the pilot mart.

Current checkpoint:
- Output path: `data/chargenet/clean/clean_demand_zones_nuts3_pilot.csv`.
- Country counts: BE 44, DE 400, FR 101, NL 40.
- Population fields are joined from Eurostat; missing population count is 0.

### Step 2 - Eurostat Population

Fetch population after NUTS3 IDs are known.

Status: implemented for 2025 total population. The current output keeps `population_as_demand_proxy` labels because population is a demand proxy, not observed charging demand.

Required outputs:
- `raw_eurostat_population`.
- Population joined to every retained NUTS3 demand zone.
- `demand_weight` and `base_demand_weight`.
- `demand_confidence_score`.

Validation:
- 100% retained NUTS3 demand zones have population for the selected year or are quarantined.
- Missing Eurostat values are never converted to zero silently.
- `demand_weight` is labeled as a proxy.

Current checkpoint:
- Output path: `data/chargenet/clean/clean_demand_zones_nuts3_pilot.csv`.
- Populated rows: 585 of 585.
- Missing population rows: 0.
- Country population sums: BE 11,883,495; DE 83,577,140; FR 68,882,600; NL 18,044,027.

### Step 3 - OSM Tiled Extraction

Use tiles instead of whole-country Overpass queries.

Status: tile plan implemented and tested with controlled smoke runs across BE100, DE111, FR101, and NL112. The generated `osm_pilot_tile_plan.csv` has one row per NUTS3 bbox and extract type, with 585 jobs each for `charging_stations`, `candidate_fuel`, and `candidate_services`.

Required extracts:
- `charging_stations`.
- `candidate_fuel`.
- `candidate_services`.

Rules:
- One request at a time per Overpass endpoint.
- Delay between successful requests.
- Dry-run every batch before using `--execute`.
- Exclude previously fetched tile IDs using the cumulative execution log.
- Split overloaded tiles instead of retrying larger requests.
- Mark unresolved tiles as `deferred`, not silently missing.
- Preserve raw tags JSON.
- Store immutable run snapshots.

Validation:
- 0 duplicate `osm:{type}:{id}` per extract.
- 100% retained OSM rows have point or center coordinates.
- 100% retained OSM rows join to pilot country.
- Candidate POIs carry `candidate_proxy_flag=1`.
- Tile plan rows remain `planned_not_run`; smoke execution logs are stored separately so the full plan is not accidentally treated as complete.

### Step 4 - Clean Candidate And Supply Tables

Required outputs:
- `clean_existing_chargers`.
- `clean_candidate_sites`.

Candidate fields required before Phase 4/5:
- `candidate_site_id`.
- `country_code`.
- `nearest_demand_zone_id`.
- `lat`, `lon`.
- `site_type`.
- `candidate_proxy_flag`.
- `candidate_feasibility_note`.
- `estimated_capex_class`.
- `rollout_risk_score`.
- `competition_score`.
- `data_quality_score`.

Validation:
- 100% candidate IDs are deterministic.
- 100% retained candidates have coordinates and country.
- 100% retained candidates have `estimated_capex_class`, `rollout_risk_score`, and `competition_score`, even if assumption/proxy-labeled.
- All feasibility language remains proxy/diligence language.

Current smoke/batch checkpoint:
- Last certified model snapshot: 324 fetched smoke/batch jobs, 0 failed jobs, covering all pilot countries and all three extract types.
- `clean_existing_chargers_tile_smoke.csv`: 1,726 charger rows from controlled BE/DE/FR/NL smoke and batch tiles.
- `clean_candidate_sites_tile_smoke.csv`: 1,973 candidate rows from controlled BE/DE/FR/NL `candidate_fuel` and `candidate_services` smoke/batch tiles (`fuel`: 1,754, `services`: 219).
- `fact_candidate_zone_coverage_tile_smoke.csv`: 3,462,615 rows from 1,973 smoke/batch candidates x 585 demand zones x 3 radii.
- `fact_scenario_inputs_tile_smoke.csv`: 7,674 rows from 1,973 smoke/batch candidates and 585 demand zones across 3 radii.
- `mart_candidate_baseline_scores_tile_smoke.csv`: 5,919 rows from 1,973 smoke/batch candidates x 3 radius scenarios.
- `mart_baseline_sensitivity_tile_smoke.csv`: 29,595 rows from 5,919 baseline rows x 5 weight sets.
- `mart_optimization_results_tile_smoke.csv`: 9 rows comparing baseline top-k, exact shortlisted MCLP, and PuLP/CBC MILP across 3 scenarios.
- `fact_optimization_selected_sites_tile_smoke.csv`: 63 selected-site rows.
- All tile-smoke tables are explicitly labeled as smoke/batch scope, not full pilot coverage.

Current full-gate extraction readiness:
- Last certified `osm-tile-progress` checkpoint reports 1,755 planned jobs, 324 fetched jobs, 0 failed attempts, and 1,431 remaining jobs.
- Current fetch-only progress reports 413 fetched jobs, 0 unresolved failed attempts, and 1,342 remaining jobs. Cumulative `osm-fetch-gate --output-limit 20` passes, while recording 1 historical Overpass HTTP 429 as a rate-limit warning.
- The certified snapshot includes 207 requests capped at `output_limit=20`, so this is still a capped smoke/batch sample rather than a complete OSM extraction.
- `run-osm-tile-batch --max-jobs 9 ...` dry-run selects the next triplet-friendly unfetched jobs without calling Overpass.
- Live full-gate extraction should use `--execute` only after reviewing the dry-run selection, keeping batch size within 25 jobs, and preferring triplet-friendly batch sizes such as 9, 12, 15, or 24.

### Step 5 - Coverage Matrix

Build `fact_candidate_zone_coverage` from the frozen candidate and demand-zone sets.

Required grain:

```text
candidate_site_id + demand_zone_id + coverage_radius_km
```

Required fields:
- `distance_km`.
- `distance_method_version`.
- `a_ij`.
- `same_country_flag`.
- `cross_border_allowed_flag`.
- `pair_eligible_flag`.
- `pair_exclusion_reason`.
- `distance_confidence_flag`.

Validation:
- Coverage radii match `service_radius_scenarios.json`.
- Candidate-zone-radius row count equals `candidate_count * demand_zone_count * radius_count`, unless a sparse matrix mode is explicitly documented.
- Every scenario radius has corresponding `a_ij` rows.
- Demand zones with zero candidate coverage are reported.
- Candidates covering zero demand are reported.

### Step 6 - Scenario Inputs

Build `fact_scenario_inputs` after candidate/demand/coverage marts are stable.

Required completeness:
- Every active scenario has all demand zones with `d_i`.
- Every active scenario has all candidates with `c_j`.
- Every active scenario has budget `b`.
- Every active scenario has site count `k`.
- Risk fields `r_j` and `rho` are either populated or explicitly inactive.

Validation:
- Scenario candidate set equals `clean_candidate_sites`.
- Scenario demand-zone set equals `clean_demand_zones`.
- No Phase 4/5 logic creates new IDs or radii.

### Step 7 - BI Export Layer

Status: implemented for current sample/pilot scope.

Generated files:
- `dim_demand_zone.csv`.
- `dim_candidate_site_sample.csv`.
- `dim_candidate_site_tile_smoke.csv`.
- `dim_scenario.csv`.
- `fact_candidate_zone_coverage_sample.csv`.
- `fact_candidate_zone_coverage_tile_smoke.csv`.
- `fact_scenario_inputs_sample.csv`.
- `fact_scenario_inputs_tile_smoke.csv`.
- `mart_candidate_baseline_scores_tile_smoke.csv`.
- `mart_baseline_sensitivity_tile_smoke.csv`.
- `mart_optimization_results_tile_smoke.csv`.
- `mart_optimization_constraint_diagnostics_tile_smoke.csv`.
- `fact_optimization_selected_sites_tile_smoke.csv`.
- `model_relationships.csv`.
- `export_manifest.json`.

Validation:
- Every export CSV is non-empty.
- Relationship manifest includes candidate, demand-zone, radius/scenario, and scenario-input links.
- Export manifest keeps the caveat that candidate and coverage facts remain capped smoke/batch-scoped until full OSM tiled extraction completes.

## Public Release Rules

- Do not commit full raw OSM extracts.
- Do not commit full derived OSM databases unless ODbL obligations are reviewed.
- Commit code, docs, configs, manifest templates, and small license-safe fixtures only.
- Keep OSM/Eurostat/GISCO attribution visible in generated artifacts.
- Do not claim optimized real-world rollout sites.

## Phase 3 Full Gate

Full Phase 3 can pass only when:

- Pilot NUTS3 demand zones exist for BE/DE/FR/NL.
- Population joins are complete or quarantined.
- OSM candidate and supply extraction is tiled and reproducible.
- Coverage rows exist for every configured radius.
- Scenario inputs include complete `d_i`, `a_ij`, `c_j`, `b`, and `k`.
- Power BI exports are regenerated from the full pilot candidate and coverage facts.
- Quality report fails on radius, FK, missing population, stale raw, and dictionary coverage mismatches.
- Specialist QA reports no open `P0`.
