# Phase 3 QA Review

## Reviewed Artifacts

- `chargenet/*.py`
- `tests/test_chargenet_core.py`
- `docs/chargenet-europe/phase-3-data-model-quality-plan.md`
- `docs/chargenet-europe/phase-2-data-contract-addendum.md`
- `config/chargenet/license_manifest.json`
- `config/chargenet/service_radius_scenarios.json`
- `config/chargenet/pilot_scope.json`
- `reports/chargenet/phase3_sample_quality_report.json`
- `data/chargenet/clean/clean_demand_zones_nuts3_pilot.csv`
- `reports/chargenet/powerbi_exports/`
- `data/chargenet/marts/osm_pilot_tile_plan.csv`
- `data/chargenet/.gitignore`
- `reports/chargenet/.gitignore`
- `.gitignore`

## Specialist Reviewers

- Data Engineering QA.
- Optimization Readiness QA.
- Public Release / Overclaim QA.
- Code Quality QA.

## Gate Decision

Implementation checkpoint pass for the Phase 3 sample skeleton.

Full Phase 3 gate is not yet passed because the pipeline still needs full pilot-country tiled OSM ingestion and full candidate-zone coverage marts.

## Findings

| Severity | Reviewer | Finding | Evidence | Required action | Status |
|---|---|---|---|---|---|
| `P0` | Optimization Readiness QA | Coverage radii were inconsistent: scenarios had 15/30/50 km but coverage mart had only 50 km. | `service_radius_scenarios.json`; `fact_candidate_zone_coverage_sample.csv`. | Build coverage rows for every configured radius and validate parity. | Fixed for sample skeleton; DQ now checks radius parity. |
| `P0` | Optimization Readiness QA | `c_j` was incomplete for the candidate set. | Scenario input sample had one candidate while clean candidates had 20. | Generate scenario candidate rows for every clean candidate per scenario. | Fixed for sample skeleton; DQ now checks scenario candidate completeness. |
| `P0` | Optimization Readiness QA | Coverage was Brussels-only and not the full NUTS3 pilot-country contract. | Sample transforms use BE100. | Do not claim final Phase 3 pass; implement full pilot-country NUTS3 pipeline next. | Reclassified as full Phase 3 carry-forward; sample skeleton clearly labeled. |
| `P1` | Data Engineering QA | Reproducibility was not locked because live fetches overwrite fixed sample paths. | Sample ingest writes current snapshots and manifests. | Add immutable run folders or fixture mode before full pilot ingestion. | Fixed for sample skeleton: immutable run folders and build-from-existing command added; full pilot still needs run-id expansion. |
| `P1` | Code Quality QA | Country scaling was hard-coded to Brussels/BE100. | Sample transform constants. | Parameterize pilot countries, NUTS3 centroids, and Eurostat population joins. | Assigned to full pilot expansion; sample labels and pilot config added. |
| `P1` | Code Quality QA | Validation was too shallow for radius, FK, stale, and scenario mismatches. | Initial DQ checks passed despite mismatches. | Add radius parity, candidate/demand completeness, FK integrity, stale raw, manifest hash, and dictionary coverage checks. | Fixed for sample skeleton. |
| `P1` | Public Release QA | Report `.gitignore` ignored itself. | `reports/chargenet/.gitignore`. | Unignore `.gitignore` and add root ignore policy. | Fixed. |
| `P1` | Public Release QA | Older docs used action labels that could read as rollout instructions. | Phase 0 and Phase 1 action tables. | Replace with diligence/shortlist language. | Fixed in Phase 0, Phase 1, and master plan wording. |
| `P1` | Public Release QA | License manifest missed ENTSO-E and Hugging Face statuses. | Generated manifest. | Add optional/excluded source statuses to machine-readable manifest. | Fixed. |
| `P1` | Public Release QA | Data dictionary covered only five fields. | `data_dictionary_sample.csv`. | Generate dictionary rows for all clean and mart sample columns. | Fixed for sample skeleton, pilot NUTS3 table, OSM smoke clean tables, tile-smoke marts, sensitivity mart, and optimization marts; 261 rows generated. |
| `P1` | Data Engineering QA | Pilot demand-zone geography was not implemented beyond hard-coded BE100. | `clean_demand_zones_sample.csv`; `pilot_scope.json`. | Ingest GISCO NUTS3 level-3 geometry and build BE/DE/FR/NL NUTS3 demand-zone rows. | Fixed for demand-zone foundation: 585 pilot NUTS3 rows generated and 585 Eurostat population values joined. |
| `P1` | Power BI QA | BI consumption layer was not yet relationship-ready. | No export folder or relationship manifest. | Generate CSV exports with dimensions, facts, and model relationships. | Fixed for current sample/pilot scope: 14 CSV exports plus manifest generated and DQ checks export presence/non-empty relationships. |
| `P1` | Data Source QA | Full-country OSM extraction could overload Overpass if run as one broad query. | Expansion plan called for tiling but no executable tile matrix existed. | Generate a planned-not-run tile job matrix from pilot NUTS3 bboxes before any broad extraction. | Fixed as planning layer: 1,755 tile jobs generated with rate-limit/retry fields and `planned_not_run` status. |
| `P1` | Data Engineering QA | Tiled OSM extraction was planned but not tested end to end. | Tile plan existed, but no raw tile run or clean smoke table existed. | Run a tiny smoke subset and normalize both charger supply and candidate POI outputs. | Fixed for smoke/batch scope: 324 fetched tile jobs across controlled BE/DE/FR/NL smoke and batch tiles generated clean scoped tables. |
| `P1` | Data Engineering QA | OSM smoke jobs were manual one-off commands and could be repeated accidentally. | Only `run-osm-tile-smoke` existed, which selects the first matching tile unless manually filtered. | Add an orchestration command that can dry-run selected jobs and skip previously fetched tiles. | Fixed: `run-osm-pilot-smoke` added with `--dry-run`, country/extract lists, per-combo cap, delay, and fetched-tile exclusion. |
| `P1` | Data Engineering QA | Smoke log validation did not prove country and extract coverage. | Validation only checked non-empty log, safe batch size, terminal status, and manifest existence. | Add explicit checks for pilot-country coverage and extract-type coverage. | Fixed: DQ now checks BE/DE/FR/NL coverage and `charging_stations`, `candidate_fuel`, `candidate_services` coverage. |
| `P1` | Optimization Readiness QA | Smoke candidates did not yet produce a candidate-zone-radius matrix or scenario inputs. | Clean candidate smoke table existed without `a_ij`, `d_i`, `c_j`, `b`, and `k` for the pilot demand set. | Build tile-smoke coverage and scenario input marts against all pilot NUTS3 demand zones. | Fixed for smoke/batch scope: 3,462,615 coverage rows and 7,674 scenario input rows generated. |
| `P1` | Business Analytics QA | There was no recruiter-readable baseline score layer on top of the optimization inputs. | Coverage and scenario inputs existed, but no ranked candidate shortlist mart existed. | Add a weighted baseline scoring mart using diligence language and bounded score checks. | Fixed for smoke/batch scope: 5,919 candidate-scenario score rows generated and validated. |
| `P1` | Data Engineering QA | Fetch-only progress advanced beyond the certified model snapshot and hit an Overpass rate-limit warning. | Cumulative fetch log reached 413 fetched jobs with 0 unresolved failed attempts and 1 historical HTTP 429 on `osm_tile:candidate_fuel:DE236`; `osm-fetch-gate --output-limit 20` returns zero after retry resolution. | Keep downstream claims tied to the 324-job certified model snapshot and resume live fetching only with longer delay/backoff. | Carry forward. |
| `P2` | Code Quality QA | Open Charge Map no-key probe could mask unrelated failures. | `probe_open_charge_map_without_key`. | Distinguish 403 expected key failures from network/schema errors. | Fixed for sample skeleton; non-403/non-key errors are labeled `unexpected_probe_failure`. |

## Gate Checklist

- [x] No unresolved sample-skeleton `P0` findings remain.
- [x] Every sample-skeleton `P1` finding has a fix or next-step owner.
- [x] Phase acceptance criteria are checked for the sample skeleton.
- [x] Pilot-country NUTS3 geometry foundation exists for BE/DE/FR/NL.
- [x] Pilot-country NUTS3 population join has 0 missing values.
- [x] Power BI relationship-ready sample/pilot exports exist.
- [x] OSM tiled extraction plan exists, with only named smoke jobs executed separately.
- [x] OSM smoke/batch extraction and clean normalization work for the current 324 fetched jobs.
- [x] Fetch-only unresolved failure resolved; cumulative fetch gate passes again.
- [x] Tile-smoke coverage and scenario input marts exist for optimization-readiness testing.
- [x] Tile-smoke baseline diligence scores exist for business-analytics demo readiness.
- [ ] Full pilot-country Phase 3 gate is not passed yet.

## Required Carry-Forward

- Extend immutable run IDs and build-from-run behavior from sample/GISCO snapshots to full pilot OSM and Eurostat extracts.
- Expand OSM ingest from Brussels sample to tiled pilot-country extraction.
- Resume future live Overpass batches only with longer delay/backoff because one HTTP 429 has already occurred.
- Replace bbox-midpoint geography proxy with a stronger centroid or representative-point method before final portfolio screenshots, or keep the proxy caveat visible.
- Expand Power BI exports from sample candidate/coverage facts to full pilot candidate/coverage facts after OSM tiling is complete.
- Run full Phase 3 QA again after pilot-country data expands.
