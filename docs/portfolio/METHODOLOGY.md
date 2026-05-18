# Methodology

## Scope

ChargeNet Europe is a public-data decision-support project for four pilot countries: Belgium, Germany, France, and the Netherlands. The current recruiter-facing layer is Phase 4: baseline scoring and sensitivity analysis. Phase 5 MILP facility-location modeling is in progress and should be treated as the next analytical layer, not as a completed recommendation engine.

## Data Sources

| Source | URL | Refresh cadence | Current use | Schema sample |
|---|---|---|---|---|
| OpenStreetMap / Overpass | https://www.openstreetmap.org and https://overpass-api.de | Continuously edited by the OSM community; fetched snapshots are pinned locally. | Existing charger proxies and candidate POIs such as fuel and motorway service sites. | `osm_object_id`, `lat`, `lon`, `tags`, `extract_slug` |
| Eurostat regional population | https://ec.europa.eu/eurostat | Annual or periodic statistical updates by dataset. | Population as a demand proxy for NUTS3 zones. | `geo`, `time`, `unit`, `value` |
| GISCO NUTS | https://gisco-services.ec.europa.eu | NUTS versions are periodic; this project uses NUTS 2024. | Pilot-country demand-zone boundaries and representative coordinates. | `nuts_id`, `country_code`, `geometry`, `bbox` |

OpenStreetMap is treated as a public POI source, not as proof that a site is feasible. Eurostat population is treated as a demand proxy, not observed charging demand. GISCO representative points currently use a transparent bounding-box midpoint method, which is acceptable for a demo but not final network design.

## Data Model

The pipeline follows a raw to clean to mart structure.

**Raw layer:** stores source snapshots and manifests. Example field: `content_sha256` in a manifest verifies that a raw JSON or CSV file has not changed after capture.

**Clean layer:** normalizes IDs and screening fields. Example field: `candidate_site_id` converts OSM objects into deterministic IDs such as `candidate:osm:node:25214653`.

**Mart layer:** creates analyst-ready facts for scoring and dashboarding. Example field: `coverage_component` is a bounded score used by the baseline model after coverage calculations are complete.

This separation matters because raw source shape, cleaned business entities, and final decision-support metrics should not be mixed. It also makes QA easier: a manifest check belongs in raw, coordinate and country checks belong in clean, and scoring bounds belong in marts.

The current mart layer is intentionally dashboard-friendly. Candidate IDs, demand-zone IDs, scenario IDs, and radius assumptions are shared across baseline scoring and sensitivity outputs. That means a recruiter or analyst can trace a displayed rank back to the candidate proxy, the scenario radius, and the component scores that produced it. It also prevents a common analytics failure: creating one set of IDs for the dashboard and another set for the model.

Large coverage facts are treated carefully. The local workspace can generate dense candidate-zone-radius rows, but the public portfolio package avoids shipping large raw extracts or oversized coverage matrices. For deployment, the Streamlit app uses compact summary CSVs under `docs/portfolio/data/` and falls back to the fuller local marts when they exist.

## Baseline Scoring Formula

For candidate site `j`, the baseline score is:

```text
score_j =
  0.55 * coverage_j
  + 0.20 * data_quality_j
  + 0.15 * risk_j
  + 0.10 * competition_j
```

Each component is bounded between 0 and 1. Higher values are better. `coverage_j` rewards candidates that cover more population-weighted demand zones within the selected radius. `data_quality_j` rewards stronger OSM tag and coordinate confidence. `risk_j` is an inverse rollout-risk proxy. `competition_j` is an inverse competition-pressure proxy.

The score is not a build recommendation. It is a diligence-prioritization score designed to focus analyst attention.

## Sensitivity Analysis

The project tests five weight sets:

| Weight set | Coverage | Data quality | Risk | Competition | What it tests |
|---|---:|---:|---:|---:|---|
| Base balanced | 0.55 | 0.20 | 0.15 | 0.10 | A balanced analyst default. |
| Coverage led | 0.70 | 0.10 | 0.10 | 0.10 | Whether demand coverage dominates the ranking. |
| Risk aware | 0.45 | 0.15 | 0.30 | 0.10 | Whether risk caution changes priorities. |
| Competition aware | 0.45 | 0.15 | 0.15 | 0.25 | Whether crowded markets fall in the ranking. |
| Data quality guardrail | 0.45 | 0.35 | 0.10 | 0.10 | Whether weak source quality should suppress candidates. |

This is the main analytical differentiator versus a naive single-score dashboard. If a candidate stays near the top across weight sets, it is more robust. If it moves sharply, it becomes a discussion point rather than a hidden model artifact.

The sensitivity output stores both the new rank and the rank delta versus the base case. That design is deliberate. A score change can look small while a rank change is operationally meaningful, especially when many candidates have similar coverage values. The Streamlit demo therefore emphasizes rank movement, not only score movement. In the current snapshot, some top baseline candidates remain stable, while other candidates move sharply when data quality receives more weight. That is exactly the kind of caveat an analyst should surface before recommending follow-up work.

The five weight sets are not presented as statistically estimated preferences. They are scenario assumptions. Their value is that they make assumptions visible and testable. A hiring manager can see that the project does not hide behind one apparently precise number.

## QA Approach

The local quality report currently passes 47 raw checks and 2,068 clean/mart checks.

Raw checks validate items such as file existence, manifest presence, content hash parity, license mapping, immutable snapshot paths, and basic OSM JSON shape. Example: if a raw file is changed after capture, its manifest hash check fails.

Clean and mart checks validate required fields, referential integrity, country coverage, radius parity, candidate and demand completeness, dictionary coverage, Power BI export presence, score bounds, sensitivity weight sums, and fetch-log integrity. Example: the sensitivity layer must prove that each weight set sums to 1.0 and that generated scores remain within the 0 to 1 range.

The project also records operational fetch safety. One historical Overpass HTTP 429 was observed and then resolved by a successful retry. That is why the pipeline distinguishes historical failures from unresolved failed attempts.

QA is also used as a communication guardrail. Several generated fields contain `allowed_use_note` and `proxy_assumption_label` values, and public docs repeat the same scope caveat. This is not cosmetic. The portfolio is meant to show business judgment: the pipeline can support early diligence, but it should not imply that public POI data is enough for a build decision.

## Limitations And Assumptions

- The current snapshot is capped smoke/batch scope, not full pilot-country coverage.
- Candidate sites are OSM POI proxies, not confirmed buildable parcels.
- Population is a demand proxy, not observed EV charging utilization.
- Distances use haversine distance to representative NUTS3 points, not road-network travel time.
- Costs are not investment-grade. Real CAPEX, grid upgrades, land, permitting, and commercial terms are outside the current scope.
- Phase 5 MILP is in progress; current public artifacts should be read as Phase 4 baseline and sensitivity outputs.

## Reproducibility Notes

The pipeline is designed to be rebuilt locally without re-fetching OpenStreetMap during portfolio review. The Streamlit app does not call Overpass. It reads existing local data when available and otherwise uses the lightweight derived summaries generated by `scripts/build_portfolio_assets.py`. This keeps the demo fast, avoids external API dependency during interviews, and respects the fact that OSM extraction should be rate-limited and logged.

For a production-grade version, I would move the large marts from CSV into DuckDB or Parquet, replace dense coverage facts with sparse eligible pairs, use stronger representative points or road-network travel time, and calibrate candidate costs with external evidence before treating Phase 5 optimization as a serious business recommendation.
