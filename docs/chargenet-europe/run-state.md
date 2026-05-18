# ChargeNet Europe - Run State

## 2026-05-16 Autonomous Work Session

**Current objective:** Continue from Phase 2 into Phase 3 without losing quality or filling chat context.

**Active mode:** Subagent-driven development with file-based checkpoints.

**Completed before this session:**
- Phase 0 case brief.
- Phase 1 literature and method review.
- Phase 2 data source audit.
- Phase 2 data contract addendum.
- Phase 0, 1, and 2 QA reports.

**Current task:** Phase 3 data model and quality layer setup.

**Working constraints:**
- V1 primary sources: OSM/Overpass, GISCO NUTS 2024, Eurostat regional population.
- EAFO is deck/context-only until reproducible download is pinned.
- Open Charge Map is optional because API key is required.
- ENTSO-E is excluded from V1 core.
- Hugging Face is optional publishing/demo layer, not authoritative source.

## Active Subagents

| Agent | Role | Status |
|---|---|---|
| Franklin | Phase 3 Data Architecture | Completed; guidance integrated into Phase 3 plan and schema. |
| Ampere | Phase 3 Source Ingestion | Completed; guidance integrated into source snapshot and manifest design. |
| Fermat | Phase 3 Optimization Readiness | Completed; `fact_candidate_zone_coverage`, scenario inputs, and service radii added. |
| Pauli | Phase 3 Portfolio/Overclaim QA | Completed; caveat, proxy, equity, and public-release checks integrated. |

## Next Local Steps

- Use `osm-tile-progress` before every full-gate extraction batch.
- Run only small intentional `run-osm-tile-batch --execute` batches after reviewing the dry-run selection.
- Continue toward full-pilot data expansion or add stronger finance evidence for candidate cost calibration.
- Replace or clearly caveat `bbox_midpoint_wgs84_v1` before final portfolio screenshots.

## Latest Local Verification

Commands run successfully:

```powershell
python -m unittest discover -s tests
python -m chargenet.cli --help
python -m chargenet.cli run-phase3-sample
python -m chargenet.cli build-from-existing-samples
python -m chargenet.cli ingest-gisco-nuts3
python -m chargenet.cli ingest-eurostat-population-pilot
python -m chargenet.cli build-pilot-nuts3
python -m chargenet.cli export-powerbi-sample
python -m chargenet.cli build-osm-tile-plan
python -m chargenet.cli run-osm-tile-smoke --max-jobs 1 --country BE --extract charging_stations --delay-seconds 0 --output-limit 25
python -m chargenet.cli run-osm-tile-smoke --max-jobs 1 --country BE --extract candidate_fuel --delay-seconds 0 --output-limit 25
python -m chargenet.cli run-osm-tile-smoke --max-jobs 1 --country BE --extract candidate_services --delay-seconds 0 --output-limit 25
python -m chargenet.cli run-osm-pilot-smoke --countries DE,FR,NL --extracts charging_stations,candidate_fuel,candidate_services --max-jobs-per-combo 1 --delay-seconds 0 --output-limit 10 --dry-run
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
python -m chargenet.cli write-data-dictionary
python -m chargenet.cli run-osm-tile-batch --max-jobs 9 --countries BE,DE,FR,NL --extracts charging_stations,candidate_fuel,candidate_services --output-limit 20
python -m chargenet.cli osm-tile-progress
python -m chargenet.cli validate
```

Current fetch-only verification:

```powershell
python -m chargenet.cli osm-fetch-gate --output-limit 20
python -m chargenet.cli validate
```

Both commands return `0` after the failed `DE236` request was retried successfully. The cumulative log still records 1 historical Overpass HTTP 429 attempt, but there are 0 unresolved failed attempts.

Latest generated quality report: `reports/chargenet/phase3_sample_quality_report.json`.

Last certified 324-job quality result: raw passed with 47 checks and 0 failures; clean/mart passed with 1,711 checks and 0 failures. Immutable raw run path checks passed for sample and optional pilot raw manifests.

Current fetch-only quality result: raw passed with 47 checks and 0 failures; clean/mart passed with 2,068 checks and 0 failures. The report records 0 unresolved failed attempts and 1 historical Overpass HTTP 429 attempt.

Latest sample run snapshot folder: `data/chargenet/raw/runs/20260516T152454Z`.

Latest GISCO NUTS3 run snapshot folder: `data/chargenet/raw/runs/20260516T152916Z`.

Latest Eurostat pilot population run snapshot folder: `data/chargenet/raw/runs/20260516T153337Z`.

Pilot NUTS3 geometry output: `data/chargenet/clean/clean_demand_zones_nuts3_pilot.csv`.

Pilot NUTS3 row counts: BE 44, DE 400, FR 101, NL 40, total 585.

Pilot NUTS3 population join: 585 populated rows, 0 missing values. Country population sums: BE 11,883,495; DE 83,577,140; FR 68,882,600; NL 18,044,027.

Power BI export folder: `reports/chargenet/powerbi_exports/`.

Power BI export row counts: demand zones 585, candidate sample 20, candidate tile-smoke 1,973, scenarios 3, coverage sample 60, coverage tile-smoke 3,462,615, scenario inputs sample 63, scenario inputs tile-smoke 7,674, baseline scores tile-smoke 5,919, baseline sensitivity tile-smoke 29,595, optimization summary 9, optimization diagnostics 36, optimization selected sites 63, relationships 17.

OSM tile plan: 1,755 planned-not-run jobs, from 585 NUTS3 zones x 3 extract types (`charging_stations`, `candidate_fuel`, `candidate_services`).

Last certified OSM model snapshot:
- Current planned jobs: 1,755.
- Fetched jobs: 324.
- Failed attempts: 0.
- Remaining jobs: 1,431.
- Completion percentage: 0.184615.
- Latest executed batches reached 324 fetched jobs; 207 fetched requests hit `output_limit=20`, so outputs remain capped samples rather than full OSM extraction.

Current fetch-only progress:
- Raw fetch progress reached 413 fetched jobs out of 1,755 planned jobs, with 1,342 remaining and 0 unresolved failed attempts.
- The log includes 1 historical Overpass `HTTP 429` on `osm_tile:candidate_fuel:DE236`; a later retry fetched that tile successfully.
- Cumulative `osm-fetch-gate --output-limit 20` passes, but the 429 is a rate-limit warning. Live fetching should pause or resume with a longer delay/backoff.
- Clean/mart/Power BI/model outputs remain certified only at the 324-job snapshot; do not present 413 as a current decision-model rebuild.

OSM smoke execution:
- `charging_stations` BE100: 25 fetched elements, 25 clean charger rows.
- `candidate_fuel` BE100: 25 fetched elements, 25 clean candidate-site rows.
- `candidate_services` BE100: 2 fetched elements, included in clean candidate-site rows.
- `charging_stations`, `candidate_fuel`, and `candidate_services` smoke jobs for DE111, FR101, and NL112 all fetched successfully through `run-osm-pilot-smoke`.
- Cumulative smoke log: `data/chargenet/marts/osm_tile_execution_log_all.csv`.
- Cumulative smoke log: 324 fetched jobs, 0 failed jobs.
- Tile-smoke clean chargers: 1,726 rows across BE, DE, FR, and NL.
- Tile-smoke clean candidates: 1,973 rows (`fuel`: 1,754, `services`: 219) across BE, DE, FR, and NL.
- Tile-smoke coverage mart: 3,462,615 candidate-zone-radius rows.
- Tile-smoke scenario inputs: 7,674 scenario-entity rows.
- Tile-smoke baseline scores: 5,919 candidate-scenario rows using diligence-shortlist language.
- Tile-smoke baseline sensitivity: 29,595 candidate-scenario-weight rows across 5 weight sets.
- Tile-smoke optimization summary: 9 scenario-method rows, including PuLP/CBC MILP.
- Tile-smoke optimization diagnostics: 36 scenario-method-constraint rows covering budget, site-count, solver status, and non-negative objective.
- Tile-smoke optimization selected sites: 63 selected candidate-method rows.
- Tile-smoke candidate costs: `tile_smoke_capex_proxy_v2`, 6 unique `c_j` values from 550,000 to 850,000.

Human-readable quality checkpoints:
- `docs/chargenet-europe/phase-3-data-quality-report.md`
- `docs/chargenet-europe/phase-4-baseline-scoring-report.md`
- `docs/chargenet-europe/phase-5-optimization-mvp-report.md`

Current status: Phase 3 sample skeleton checkpoint passes, the pilot NUTS3 demand-zone foundation is built with Eurostat population, relationship-ready BI CSV exports exist, OSM tiled extraction is planned, and the last certified model snapshot covers 324 fetched jobs across the pilot-country scope. Fetch-only progress has advanced to 413 fetched jobs with 0 unresolved failed attempts, but the log includes one historical Overpass `HTTP 429`, so live fetching should pause or resume only with a longer delay/backoff. Phase 4 smoke-scope baseline scoring and sensitivity checkpoints exist. Phase 5 smoke-scope PuLP/CBC MILP checkpoint exists with constraint diagnostics. Full pilot-country Phase 3, full Phase 4, and full Phase 5 gates remain open because all 1,755 tiled OSM jobs and the full candidate universe are not complete yet.
