**ChargeNet Europe turns public EV, population, and geography data into an early diligence shortlist for charging-network expansion.**

> DISCLAIMER: This is a decision-support layer for early-stage diligence, not investment advice. All data is public. Outputs are illustrative.

## The Problem

EV charging operators cannot expand by looking only at a map of existing chargers. A useful first screen needs to compare demand potential, data quality, rollout risk, and competitive pressure across many candidate locations. Without that structure, a team can easily over-focus on visually obvious cities or on one attractive score that hides fragile assumptions.

This project frames that problem for four pilot countries: Belgium, Germany, France, and the Netherlands. It asks which public-data candidate sites should be prioritized for diligence, while staying honest that public data cannot confirm land availability, grid capacity, permitting, utilization, or investment-grade economics.

## What This Tool Does

- Builds a reproducible public-data pipeline from OpenStreetMap, Eurostat population, and GISCO NUTS boundaries.
- Scores candidate charging-site proxies with four criteria: coverage, data quality, rollout risk, and competition.
- Tests whether rankings are stable across five weight sets instead of trusting one single score.

## Methodology

The current public demo centers on Phase 4: baseline scoring and sensitivity analysis. The pipeline creates raw snapshots, clean candidate and demand-zone tables, mart-level scoring outputs, QA reports, and Power BI-ready exports. See [docs/portfolio/METHODOLOGY.md](docs/portfolio/METHODOLOGY.md) for the technical deep dive.

## Status

Phase 4 is complete for the current capped pilot snapshot: 585 NUTS3 demand zones, 1,973 candidate-site proxies, 5,919 baseline scoring rows, 29,595 sensitivity rows, and automated QA with 47 raw plus 2,068 clean/mart checks passing locally. Phase 5 MILP facility-location optimization is in progress and should not be read as a final recommendation.

Not in scope: investment advice, final site selection, traffic forecasting, land availability, grid-capacity validation, permitting, or real CAPEX forecasting.

## Live Demo

**[chargenet-europe.streamlit.app](https://chargenet-europe.streamlit.app/)** — interactive tabs for top candidates, sensitivity across 5 weight sets, methodology, coverage map, and the Phase 5 MILP optimization (max-coverage and min-cost formulations).

## Tech Stack

Python, Streamlit, pandas, matplotlib, seaborn, OpenStreetMap Overpass, Eurostat, GISCO NUTS, Power BI CSV exports, PuLP/CBC for the Phase 5 MILP optimization layer.

## Run Locally

```powershell
python -m pip install -r requirements.txt
python -m chargenet.cli validate
python -m streamlit run app.py
```
