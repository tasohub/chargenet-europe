# ChargeNet Europe - Phase 4 Baseline Scoring Checkpoint

## Scope

This checkpoint turns the tile-smoke candidate set into an explainable baseline ranking and weight-sensitivity layer. It is a business-analytics benchmark for diligence prioritization, not a final site rollout or investment decision.

The current baseline uses the controlled smoke/batch scope: 324 fetched OSM jobs across selected BE/DE/FR/NL tiles plus all 585 pilot NUTS3 demand zones. Full Phase 4 remains open until full pilot OSM extraction is complete.

## Inputs

| Input | Rows | Role |
|---|---:|---|
| `clean_candidate_sites_tile_smoke.csv` | 1,973 | Candidate POI proxies. |
| `fact_candidate_zone_coverage_tile_smoke.csv` | 3,462,615 | Candidate-zone-radius coverage matrix. |
| `fact_scenario_inputs_tile_smoke.csv` | 7,674 | Scenario `d_i`, `c_j`, `b`, and `k` inputs. |
| `mart_candidate_baseline_scores_tile_smoke.csv` | 5,919 | Base weighted score by candidate and radius scenario. |

## Baseline Formula

The baseline score is a weighted sum of four bounded components:

| Component | Base weight | Meaning |
|---|---:|---|
| Coverage | 0.55 | Normalized covered demand weight. |
| Data quality | 0.20 | OSM tag and coordinate quality proxy. |
| Risk | 0.15 | Inverse rollout-risk proxy. |
| Competition | 0.10 | Inverse competition proxy. |

Formula:

```text
baseline_score =
  0.55 * coverage_component
  + 0.20 * data_quality_component
  + 0.15 * risk_component
  + 0.10 * competition_component
```

Scores are bounded between 0 and 1. Action labels use diligence language only: priority diligence shortlist, secondary diligence shortlist, monitor as data improves, or no current coverage signal.

## Sensitivity Design

The sensitivity mart tests five weight sets:

| Weight set | Coverage | Data quality | Risk | Competition | Purpose |
|---|---:|---:|---:|---:|---|
| `weights:base` | 0.55 | 0.20 | 0.15 | 0.10 | Balanced benchmark. |
| `weights:coverage-led` | 0.70 | 0.10 | 0.10 | 0.10 | Demand coverage emphasis. |
| `weights:risk-aware` | 0.45 | 0.15 | 0.30 | 0.10 | Rollout-risk caution. |
| `weights:competition-aware` | 0.45 | 0.15 | 0.15 | 0.25 | Competition-pressure caution. |
| `weights:data-quality-guardrail` | 0.45 | 0.35 | 0.10 | 0.10 | Data-quality caution. |

Generated sensitivity output:

| Output | Rows | Notes |
|---|---:|---|
| `mart_baseline_sensitivity_tile_smoke.csv` | 29,595 | 5,919 baseline rows x 5 weight sets. |
| Weight sets | 5 | Every weight set sums to 1.0. |
| Top-10 rows across all scenarios and weight sets | 150 | 3 radius scenarios x 5 weight sets x 10 ranks. |
| Maximum absolute rank movement | 836 | Useful for discussing sensitivity and assumption risk. |

## Current Smoke-Scope Observation

Under the base weights, the current rank-1 candidates by radius scenario are:

| Scenario | Candidate | Country | Weighted score |
|---|---|---|---:|
| `scenario:radius-conservative` | `candidate:osm:node:25213823` | FR | 0.81 |
| `scenario:radius-base` | `candidate:osm:node:25214653` | FR | 0.81 |
| `scenario:radius-aggressive` | `candidate:osm:node:25213823` | FR | 0.81 |

This observation is not a country recommendation. It reflects the current capped smoke/batch candidate set and should be used only to explain how the ranking machinery works.

## Power BI Readiness

The Power BI export folder now includes:

- `mart_candidate_baseline_scores_tile_smoke.csv`
- `mart_baseline_sensitivity_tile_smoke.csv`
- `model_relationships.csv` with candidate and scenario links for both marts.

This supports dashboard views such as:

- Top candidates by radius scenario.
- Score decomposition by component.
- Rank movement by weight set.
- Stable top-10 candidates under sensitivity tests.

## Gate Status

Phase 4 smoke-scope checkpoint passes as an explainable benchmark layer.

Full Phase 4 remains open until:

- Full pilot OSM candidate extraction replaces the smoke candidate set.
- Top and bottom ranked sites are reviewed geographically.
- Sensitivity is rerun on the full pilot candidate universe.
- Baseline And Scoring QA reports no open `P0` findings for the full scope.
