# ChargeNet Europe

Public-data decision support for early EV charging expansion diligence across Belgium, Germany, France, and the Netherlands.

## What it does

- Scores candidate charging-site proxies using coverage, data quality, rollout risk, and competition.
- Shows whether rankings survive five different business-priority weight sets.
- Packages the results into Streamlit, Power BI-ready exports, screenshots, and recruiter-readable documentation.

## Why it matters

Expansion decisions are expensive, but early screening is often too informal: a map view, a single score, or a spreadsheet that hides assumptions. ChargeNet Europe makes the first diligence layer more transparent. It shows what public data can support, where the current evidence is weak, and which candidates deserve more investigation before field work or financial modeling.

The project is designed for analyst-internship storytelling. It demonstrates data cleaning, quality checks, business scoring, sensitivity analysis, dashboard packaging, and clear communication of limitations. The strongest signal is not that the model claims to know the best site. The signal is that the workflow makes tradeoffs visible and prevents overclaiming.

Current scope is a capped four-country pilot snapshot, not a full European rollout model. Candidate locations are OpenStreetMap proxies, and population is a demand proxy, so the outputs are diligence shortlists rather than site-selection decisions.

## Next

Phase 5 adds a MILP facility-location model to compare the baseline shortlist with constrained optimization.

## Tech Tags

`Python` `Streamlit` `pandas` `matplotlib` `seaborn` `OpenStreetMap` `Overpass` `Eurostat` `GISCO NUTS` `Power BI CSV` `QA automation` `MILP in progress`
