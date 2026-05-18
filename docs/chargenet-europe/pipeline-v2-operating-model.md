# ChargeNet Europe - Pipeline V2 Operating Model

## Decision

Do not make all 1,755 planned OSM jobs the capped MVP finish line. The current certified snapshot already demonstrates the portfolio-critical capabilities: public-data ingestion, governed raw manifests, pilot demand zones, candidate cleaning, coverage modeling, baseline scoring, sensitivity, PuLP/CBC optimization, diagnostics, and Power BI exports.

The project now uses two tracks:

| Track | Purpose | Frequency | Output status |
|---|---|---|---|
| Fetch-only | Expand raw OSM evidence safely. | Small batches, usually 9 triplet-aligned jobs. | Raw/log progress only, not a new decision model. |
| Certified model | Rebuild clean/marts/BI/QA from raw evidence. | Milestones only. | Recruiter/demo-ready snapshot. |

The full Phase 3/4/5 gates remain separate from this capped MVP snapshot. They stay open until full pilot OSM extraction and full-scope rebuilds are complete.

## Why This Changes

The dense coverage mart grows as:

```text
candidate_count x 585 demand zones x 3 radius scenarios
```

At the current scale it already produces millions of rows and hundreds of MB of CSV. Rebuilding coverage, baseline, sensitivity, optimization, Power BI exports, docs, and QA after every 9-job fetch window wastes time and creates unnecessary stale-doc churn.

## Per-Batch Gate

Run after every live fetch-only batch:

```powershell
python -m chargenet.cli osm-fetch-gate --latest-only --output-limit 20
python -m chargenet.cli osm-fetch-gate --output-limit 20
```

The batch passes only if:

- unresolved `failed_attempts` is `0`; historical failures may remain in the log only if a later retry fetched the same tile successfully.
- Every fetched row has existing raw and manifest paths.
- Manifest hashes match raw files.
- Immutable manifest paths exist.
- No fetched tile ID is duplicated.
- No log row has an unknown tile ID or nonterminal status.
- Output-limit hits are counted and kept as a scope caveat.

## Milestone Gate

Run full rebuild and QA only at milestones:

- Every 90-180 newly fetched jobs.
- Country or country-cluster completion.
- 25/50/75/100% planned-job progress.
- Scenario, cost, distance, centroid, or cross-border assumption changes.
- Before public screenshots, deck, README, CV claims, or portfolio publishing.

Milestone output must include:

- Unit tests.
- Full `validate`.
- Clean charger and candidate tables.
- Coverage, scenario inputs, baseline, sensitivity, optimization, diagnostics.
- Power BI exports and data dictionary.
- Stale-value scan and overclaim scan.
- Read-only specialist QA.

## Model Validity Rules

- Coverage can be made incremental only if demand zones, radii, candidate IDs, coordinates, distance method, and cross-border rules are unchanged.
- Baseline, sensitivity, and MILP are global snapshot outputs. They must not be treated as current after fetch-only progress.
- Power BI decision pages should show the last certified snapshot, not raw fetch-only progress.
- Preview pages may show fetch progress and new candidate counts, but must be labeled non-certified.

## Warehouse Direction

The next performance upgrade is DuckDB/Parquet:

- Use DuckDB as the compute engine.
- Persist large marts as Parquet.
- Keep CSV for small dimensions, manifests, docs, and final Power BI/reviewer exports.
- Replace dense coverage as the operating fact with candidate-zone distance plus sparse eligible coverage rows.

This keeps the public portfolio story simple while preventing CSV size from dominating the work.
