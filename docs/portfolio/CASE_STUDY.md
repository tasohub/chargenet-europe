# ChargeNet Europe Case Study

> DISCLAIMER: This is a decision-support layer for early-stage diligence, not investment advice. All data is public. Outputs are illustrative.

## Business Problem

A charging-network operator, infrastructure investor, or strategy team needs an early screen for where to investigate new EV charging sites across Belgium, Germany, France, and the Netherlands. The challenge is not simply finding places with population. A shortlist has to balance demand coverage, how trustworthy the source data is, how difficult rollout might be, and whether nearby competition could make the site less attractive.

The current project answers a practical question: which public-data candidate-site proxies deserve the next round of diligence? It does not claim that a site should be built. It creates a structured analyst layer before expensive field work, commercial negotiation, engineering review, or financial modeling.

## Approach

The Phase 4 model scores each candidate with four criteria:

- **Coverage:** how much NUTS3 population demand proxy falls within the configured service radius.
- **Data quality:** whether OpenStreetMap tags and coordinates are strong enough to trust for screening.
- **Rollout risk:** a simple proxy for implementation difficulty.
- **Competition:** a proxy for how crowded the nearby charging/supply landscape may be.

The differentiator is sensitivity analysis. Instead of building one polished score and pretending it is stable, the project runs five weight sets: base, coverage-led, risk-aware, competition-aware, and data-quality guardrail. This shows whether a candidate remains attractive when the business priority changes.

## Methodology Highlights

The pipeline uses public sources only: OpenStreetMap via Overpass for candidate and charger proxies, Eurostat population as a demand proxy, and GISCO NUTS boundaries for the regional geography. It converts raw snapshots into clean tables, then into mart outputs for scoring, sensitivity, QA, and Power BI/Streamlit presentation.

The current local snapshot has 585 NUTS3 demand zones, 1,973 candidate-site proxies, 5,919 baseline rows, and 29,595 sensitivity rows. Automated QA currently reports 47 raw checks and 2,068 clean/mart checks with zero failures.

## Results

Top baseline candidates in the base-radius scenario:

| Rank | Candidate | Country | Type | Score | Coverage | Data quality | Risk | Competition |
|---:|---|---|---|---:|---:|---:|---:|---:|
| 1 | `node:25214653` | FR | fuel | 0.810 | 1.000 | 0.675 | 0.500 | 0.500 |
| 2 | `node:309654919` | FR | fuel | 0.810 | 1.000 | 0.675 | 0.500 | 0.500 |
| 3 | `node:320203219` | FR | fuel | 0.810 | 1.000 | 0.675 | 0.500 | 0.500 |
| 4 | `node:255003455` | FR | fuel | 0.785 | 1.000 | 0.550 | 0.500 | 0.500 |
| 5 | `node:259284911` | FR | fuel | 0.785 | 1.000 | 0.550 | 0.500 | 0.500 |

Key insight: the strongest current base-scenario scores cluster in one French smoke/batch area. That is useful as a model test, but it is not a country recommendation. It shows why the project must separate a recruiter-demo snapshot from a full-pilot extraction.

## What I Learned

1. Sensitivity analysis is more honest than a single ranking because it exposes which candidates are robust and which depend on one assumption set.
2. Public geospatial data can support a strong screening layer, but it cannot validate grid capacity, land, permits, utilization, or real CAPEX.
3. The biggest operational surprise was rate limiting: one Overpass HTTP 429 appeared during fetch expansion and forced a slower, gated pipeline design.

## What's Next

Phase 5 adds a formal MILP facility-location model so the project can compare baseline ranking against constrained optimization. Later scope expansion candidates include stronger cost calibration, sparse coverage storage, DuckDB/Parquet, and a broader certified extraction snapshot.
