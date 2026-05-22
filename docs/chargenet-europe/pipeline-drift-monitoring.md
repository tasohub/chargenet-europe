# ChargeNet Europe - Pipeline Drift Monitoring

## Purpose

Pipeline drift monitoring checks whether a certified ChargeNet run has changed materially versus a reference run. It is not a data-source truth test by itself. It is an early warning layer for review when candidate counts, coverage matrix size, or optimization outcomes move unexpectedly.

This matters because ChargeNet uses public, changing sources. OpenStreetMap tags can be edited, Overpass batches can be incomplete, and model outputs can shift after new raw tiles are fetched. A recruiter or hiring manager should be able to see that the pipeline does not blindly trust every refresh.

## Current Snapshot Metrics

The current tile-smoke snapshot produces these monitoring metrics:

| Metric | Value | Source |
|---|---:|---|
| `candidate_site_count` | 1,973 | `clean_candidate_sites_tile_smoke` |
| `coverage_row_count` | 3,462,615 | `fact_candidate_zone_coverage_tile_smoke` |
| `eligible_coverage_pair_count` | 28,252 | `fact_candidate_zone_coverage_tile_smoke` |
| `baseline_score_row_count` | 5,919 | `mart_candidate_baseline_scores_tile_smoke` |
| `optimization_summary_row_count` | 12 | `mart_optimization_results_tile_smoke` |
| `optimization_objective_mclp_base` | 27,652,281 | `mart_optimization_results_tile_smoke` |
| `optimization_cost_mclp_base` | 5,920,000 | `mart_optimization_results_tile_smoke` |

These values are generated from local marts, not hand-entered. The lightweight copy in `app_data/` is for Streamlit demo fallback only.

## Commands

Build the current metrics:

```powershell
python -m chargenet.cli build-pipeline-snapshot-metrics-tile-smoke
```

Stage the current metrics as a reference candidate:

```powershell
python -m chargenet.cli stage-reference-snapshot-metrics-tile-smoke
```

Compare current metrics to a reference metrics file:

```powershell
python -m chargenet.cli compare-pipeline-snapshot-drift-tile-smoke
```

Promote the staged reference only after all drift rows pass:

```powershell
python -m chargenet.cli promote-reference-snapshot-metrics-tile-smoke
```

Scan selected public-facing ChargeNet text for overclaim language:

```powershell
python -m chargenet.cli build-public-claim-gate
```

Evaluate the release gate before refreshing public demo assets:

```powershell
python -m chargenet.cli run-release-gate-tile-smoke
```

The comparison expects `data/chargenet/marts/mart_pipeline_snapshot_metrics_reference_tile_smoke.csv`. The staging command creates that file plus `mart_pipeline_snapshot_certifications_tile_smoke.csv`.

Important: the staging command writes `certification_status=staged_for_review`. It is deliberately not an automatic certification. A human or explicit review gate should decide whether the staged reference becomes the certified baseline for public claims.

The promotion command rewrites the certification log to `certified` only when every row in `mart_pipeline_snapshot_drift_tile_smoke.csv` is `pass`. If any drift row is `warning` or `fail`, the reference is marked `rejected` until reviewed. This certification is narrow: it covers the tile-smoke drift reference, not investment readiness.

The public-claim gate writes `reports/chargenet/public_claim_gate.csv`. It flags certainty and overclaim phrases such as `guaranteed`, `optimal sites`, and `complete OSM coverage`, while allowing explicit limitations such as `not investment advice` and guardrail wording.

The release gate writes `reports/chargenet/release_gate_tile_smoke.csv` and checks five release blockers together:

| Gate | Evidence | Blocks when |
|---|---|---|
| Quality report | `reports/chargenet/phase3_sample_quality_report.json` | Raw or clean/mart checks fail. |
| Snapshot drift | `mart_pipeline_snapshot_drift_tile_smoke.csv` | Any drift row is not `pass`. |
| Snapshot certification | `mart_pipeline_snapshot_certifications_tile_smoke.csv` | Latest reference is not `certified`. |
| Public claims | `reports/chargenet/public_claim_gate.csv` | Any overclaim finding remains. |
| App fallback sync | `app_data/pipeline_snapshot_certifications_tile_smoke.csv` | Streamlit fallback status is stale versus the mart certification. |

## Status Rules

| Status | Meaning |
|---|---|
| `pass` | Relative movement is below the warning threshold. |
| `warning` | Movement is large enough to review before updating public claims. |
| `fail` | Movement is large enough to block certification until investigated. |

The current staged reference compares current metrics against themselves, so every drift row is expected to pass. That is useful as a pipeline smoke check, not as evidence that future refreshes are stable.

The default thresholds are 10% for warning and 25% for fail. Metric-specific overrides live in `config/chargenet/drift_thresholds.json`.

Current metric-specific examples:

| Metric | Warning | Fail | Why |
|---|---:|---:|---|
| `candidate_site_count` | 15% | 35% | OSM batch progress can legitimately change candidate volume. |
| `coverage_row_count` | 15% | 35% | Coverage facts scale with candidate volume and radius coverage. |
| `eligible_coverage_pair_count` | 20% | 40% | Eligible pairs are sparse and can move more sharply after new tiles. |
| `optimization_objective_mclp_base` | 5% | 15% | Objective movement is closer to the decision-support story and should be reviewed earlier. |
| `optimization_cost_mclp_base` | 5% | 15% | Cost movement affects scenario interpretation and should be reviewed earlier. |

These thresholds are intentionally conservative for a portfolio demo. In a production setting they would be calibrated from historical runs and split by source freshness, country, and extract type.

## Interpretation

A drift alert is not automatically bad. More fetched OSM tiles should increase candidates and coverage rows. A lower optimization objective could be valid if the candidate universe changed or if data quality filters became stricter. The point is to force an explicit review before updating docs, app fallback data, or public claims.

Known limitations:

- Current metrics monitor high-level shape and selected Phase 5 outputs, not every row-level change.
- There is no long historical baseline yet.
- The system does not currently classify source-side OSM edits versus local pipeline changes.
- The model still uses public POI proxies, straight-line coverage, population demand weights, and cost assumptions.

## Next Improvement

The next useful step is to add a small Streamlit methodology badge backed by the release gate report, so demo viewers can see the same gate status without opening the CSV.
