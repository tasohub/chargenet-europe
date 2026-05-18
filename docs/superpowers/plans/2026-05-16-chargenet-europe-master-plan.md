# ChargeNet Europe Master Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a portfolio-grade EV charging expansion decision-support case that uses public European infrastructure data, operations research, Excel financial modeling, and Power BI to shortlist where a charging operator should prioritize diligence for its next sites.

**Architecture:** The project is organized as gated phases. Each phase produces a concrete artifact and must pass an acceptance gate before the next phase starts. The analytical core is a reproducible data pipeline feeding both the optimization models and Power BI/Excel deliverables.

**Tech Stack:** Public EV/infrastructure datasets, Python, SQL/DuckDB or SQLite, OR-Tools or PuLP, Power BI Desktop, Excel, PowerPoint, optional CLI wrapper for repeatable ingest/validate/export commands.

---

## Project Thesis

**Working title:** ChargeNet Europe: EV Charging Expansion Decision Support

**Case question:** Given a fixed expansion budget, where should a European EV charging operator prioritize diligence for its next charging sites over 24 months to maximize coverage, expected utilization proxy, and payback proxy while managing competition, rollout, and grid-proxy constraints?

**Target audience:** Strategy consulting, business analytics, operations, market entry, value creation, and infrastructure investment reviewers.

**Portfolio promise:** This is not a generic dashboard. It is a board-style decision case with public data, a formal optimization model, scenario economics, and executive communication.

## V1 Scope

V1 focuses on **site prioritization and scenario planning**, not precise real-world investment forecasting.

**In scope:**
- Pilot geography limited to one European corridor family or 3-5 countries.
- Public charger supply mapping from Open Charge Map and/or OpenStreetMap.
- Demand and market proxies from EAFO, Eurostat/GISCO, NUTS regions, population, road proximity, and optional macro indicators.
- Baseline weighted scoring.
- MILP facility-location or maximal-coverage model.
- Excel assumption-driven financial model.
- Power BI dashboard using exported CSV or Parquet marts.
- Executive deck, investment memo, technical appendix, and portfolio README.

**Out of scope for V1:**
- Real-time traffic simulation.
- Charging-session simulation and queueing theory.
- Dynamic pricing.
- Battery degradation.
- Detailed electrical grid capacity modeling.
- Deep learning demand forecasting.
- Claiming exact investment-grade site economics.
- Europe-wide optimization in the first build.

## Decision Model

The optimization layer must answer a business decision, not merely display technical output.

**Core decision:** Select candidate charging sites under budget and rollout constraints.

**Minimum formal model:**
- Demand zones `i`: city, NUTS3 region, motorway/service-area zone, or grid cell depending on available data.
- Candidate sites `j`: candidate charging locations generated from road/service-area/city nodes and filtered by data quality.
- Binary site variable `x_j = 1` if candidate site `j` is selected.
- Assignment variable `y_ij = 1` if demand zone `i` is served by candidate site `j`.
- Objective: maximize weighted demand covered within service radius, with optional penalties for cost, competition, and grid-proxy risk.
- Constraints: total budget, maximum number of sites, service radius, site capacity class, minimum market coverage, and optional country/corridor balance.

**Algorithm ladder:**
1. Weighted scoring / greedy baseline for business explainability.
2. MILP maximal-coverage or facility-location model as the V1 academic core.
3. NSGA-II as V1.5 only after the MILP model and financial model are stable.

## QA Governance Layer

Every phase must pass a specialist QA review before the next phase starts. The QA framework is defined in `docs/chargenet-europe/qa-governance-framework.md`.

**QA rules:**
- QA reviewers do not implement changes directly; they produce a review report.
- Each finding receives severity `P0`, `P1`, or `P2`.
- `P0` findings block the phase.
- `P1` findings require either a fix or an explicit carry-forward action.
- `P2` findings are improvement suggestions and do not block the phase.
- QA reports are saved under `docs/chargenet-europe/qa/phase-X-qa-review.md`.

**Specialist reviewer pool:**
- Strategy Case QA.
- Operations Research QA.
- Data Source QA.
- Data Engineering QA.
- Baseline And Scoring QA.
- Experiment Design QA.
- Finance QA.
- Power BI QA.
- Communication And Portfolio QA.
- Overclaim And Ethics QA.

**Universal phase gate:** A phase is not considered complete until the required QA report exists, no `P0` findings remain, and all `P1` findings have a fix or next-phase owner.

## Phase Gates

### Phase 0: Case Thesis And Scope

**Purpose:** Lock the exact business question and prevent scope drift.

**Outputs:**
- One-page case brief.
- Pilot geography choice.
- Target operator persona.
- Success metrics and non-goals.

**Acceptance gate:**
- The case question is written in one sentence.
- Pilot geography is limited and named.
- Success metrics include coverage, CAPEX, payback or NPV proxy, and gap reduction.
- Every excluded topic is explicitly recorded so it does not return mid-project.
- Strategy Case QA and Overclaim And Ethics QA complete the Phase 0 review with no open `P0` findings.

### Phase 1: Literature And Method Review

**Purpose:** Make the OR layer defensible and choose algorithms for a reason.

**Outputs:**
- Literature matrix covering facility location, maximal covering, p-median/p-center, capacitated facility location, EV charging planning, GIS suitability, and multi-objective optimization.
- Algorithm selection memo.
- Initial mathematical formulation.

**Acceptance gate:**
- At least 8 credible academic or official sources are summarized.
- The chosen V1 model is justified against the business decision.
- The baseline, MILP, and possible NSGA-II roles are clearly separated.
- The mathematical formulation includes sets, parameters, variables, objective, and constraints.
- Operations Research QA, Strategy Case QA, and Overclaim And Ethics QA complete the Phase 1 review with no open `P0` findings.

### Phase 2: Data Source Audit

**Purpose:** Confirm the project can be built from public data without overclaiming.

**Primary source candidates:**
- EAFO for country-level EV charging and market context.
- Open Charge Map and/or OpenStreetMap for location-level charger supply.
- Eurostat/GISCO population grids and NUTS boundaries for demand zones.
- OSM road and service-area features for candidate site generation.
- ENTSO-E only as a high-level grid/load proxy if it adds useful signal without overcomplication.

**Outputs:**
- Data inventory with URLs, licenses, fields, update cadence, and caveats.
- Sample extracts.
- Data quality risk register.
- Data contract addendum covering reproducible probes, licensing, ID rules, field classification, quality checks, and Phase 3 entry criteria.

**Acceptance gate:**
- Sample rows are loaded for each required source.
- Charger coordinates, country/region identifiers, and demand-zone fields are available.
- Known limitations are documented, especially utilization, land cost, and grid capacity gaps.
- The final source list can support both Power BI and optimization inputs.
- Data Source QA, Data Engineering QA, and Overclaim And Ethics QA complete the Phase 2 review with no open `P0` findings.

### Phase 3: Data Model And Quality Layer

**Purpose:** Create one clean data foundation for algorithms, Excel, and Power BI.

**Target marts:**
- `dim_country`
- `dim_nuts_region`
- `dim_site_type`
- `dim_operator`
- `dim_connector`
- `dim_scenario`
- `fact_existing_chargers`
- `fact_demand_zones`
- `fact_candidate_sites`
- `fact_candidate_zone_coverage`
- `fact_scenario_results`

**Outputs:**
- Raw, cleaned, and mart-level datasets.
- Data dictionary.
- Quality report for duplicates, missing coordinates, missing power values, invalid countries, and source confidence.

**Acceptance gate:**
- Power BI can load the marts without messy many-to-many relationships.
- Algorithms and BI use the same candidate-site and demand-zone IDs.
- Every generated field has a documented definition.
- Data quality issues are either fixed or flagged with a clear confidence score.
- Every proxy or assumption field is labeled with its allowed use.
- Data Engineering QA, Data Source QA, and Power BI QA complete the Phase 3 review with no open `P0` findings.

### Phase 4: Baseline Scoring Model

**Purpose:** Build an explainable benchmark before optimization.

**Outputs:**
- Weighted site/zone attractiveness score.
- Weight rationale.
- Top/bottom ranked candidate sites.
- Sensitivity check for weight changes.

**Current smoke checkpoint:**
- `mart_candidate_baseline_scores_tile_smoke.csv` generates 5,919 candidate-scenario baseline rows.
- `mart_baseline_sensitivity_tile_smoke.csv` generates 29,595 sensitivity rows from 5 weight sets.
- This is an implementation checkpoint only; full Phase 4 still waits on full pilot OSM extraction.

**Acceptance gate:**
- Scores are explainable in business language.
- Top-ranked sites make geographic and market sense.
- The baseline can be compared against MILP using the same metrics.
- No baseline feature secretly uses future MILP output.
- Baseline And Scoring QA, Strategy Case QA, and Overclaim And Ethics QA complete the Phase 4 review with no open `P0` findings.

### Phase 5: OR MVP

**Purpose:** Build the formal optimization model that improves on the baseline.

**Outputs:**
- MILP model implementation.
- Scenario configuration for low/base/high budget.
- Solver result table.
- Constraint satisfaction report.
- Comparison against greedy baseline.

**Current smoke checkpoint:**
- PuLP/CBC is installed and used for a smoke-scope MILP backend.
- `mart_optimization_results_tile_smoke.csv` produces 9 rows comparing baseline top-k, exact shortlisted maximal coverage, and PuLP/CBC MILP.
- `fact_optimization_selected_sites_tile_smoke.csv` produces 63 selected-site rows.
- This is a smoke-scope OR MVP only; full Phase 5 still requires full pilot candidate extraction and stronger external evidence for cost calibration.

**Acceptance gate:**
- Model runs in minutes on the pilot geography.
- Objective value, selected sites, total CAPEX, covered demand, and uncovered demand are reported.
- Constraints are shown as satisfied or explicitly infeasible.
- MILP beats or meaningfully challenges the baseline on at least one core metric.
- If the model is infeasible, the reason is documented and the scenario is adjusted transparently.
- Operations Research QA, Experiment Design QA, and Overclaim And Ethics QA complete the Phase 5 review with no open `P0` findings.

### Phase 6: Scenario And Sensitivity Design

**Purpose:** Show the recommendation is not dependent on one fragile assumption set.

**Scenario set:**
- Budget: conservative, base, aggressive.
- Demand growth: conservative, base, aggressive.
- Strategy: urban-first, corridor-first, balanced.
- Grid-proxy penalty: low, high.
- Competition penalty: ignored, included.

**Outputs:**
- Scenario result matrix.
- Sensitivity summary.
- Stable vs unstable site recommendations.

**Acceptance gate:**
- Each scenario uses the same data foundation.
- The project can explain why selected sites change across scenarios.
- At least one robust recommendation remains stable across multiple assumptions.
- Experiment Design QA, Strategy Case QA, and Finance QA complete the Phase 6 review with no open `P0` findings.

### Phase 7: Excel Financial Model

**Purpose:** Translate site selection into business economics.

**Outputs:**
- Assumptions sheet.
- CAPEX/OPEX model.
- Revenue/utilization proxy.
- Payback and NPV proxy.
- Sensitivity table for utilization, price per kWh, margin, and CAPEX.

**Acceptance gate:**
- No hidden hardcoded results disconnected from scenario outputs.
- Selected site/scenario IDs tie back to optimization results.
- The model is clearly labeled as assumption-driven, not investment-grade forecasting.
- A reviewer can change key assumptions and see outputs update.
- Finance QA, Strategy Case QA, and Overclaim And Ethics QA complete the Phase 7 review with no open `P0` findings.

### Phase 8: Power BI Dashboard

**Purpose:** Create the executive decision interface.

**Pages:**
- Executive overview.
- Market gap map.
- Candidate site ranking.
- Scenario comparison.
- Financial summary.
- Data quality and assumptions.

**Outputs:**
- Power BI `.pbix` report.
- Exported screenshots.
- DAX measure list.
- Refresh instructions.

**Acceptance gate:**
- Dashboard answers the case question directly.
- Maps and rankings use the exported marts.
- Scenario filters update visible outputs coherently.
- Data limitations are visible and not hidden.
- Power BI QA, Data Engineering QA, and Strategy Case QA complete the Phase 8 review with no open `P0` findings.

### Phase 9: Strategy Deck And Investment Memo

**Purpose:** Convert analysis into consulting-style communication.

**Outputs:**
- 10-12 slide executive deck.
- 2-page investment memo.
- Technical appendix.

**Acceptance gate:**
- Recommendation appears in the first two slides/pages.
- Each analytical result maps to a business action: build, partner, acquire, wait, monitor, or reject.
- Risks and limitations are stated without weakening the main recommendation.
- The deck reads as a decision document, not a school report.
- Strategy Case QA, Communication And Portfolio QA, and Finance QA complete the Phase 9 review with no open `P0` findings.

### Phase 10: Portfolio Packaging

**Purpose:** Make the project easy for recruiters and analysts to understand.

**Outputs:**
- GitHub-ready README.
- Portfolio case page copy.
- Short CV bullet.
- Linked artifact list: PBIX, Excel model, deck, memo, appendix, screenshots, data dictionary.
- Optional Hugging Face dataset card or Space-style demo package if it helps make the project easier to inspect publicly.

**Acceptance gate:**
- A recruiter can understand the project in 90 seconds.
- A technical reviewer can reproduce the pipeline from documented steps.
- Public-facing materials avoid overclaiming and clearly distinguish real data from assumptions.
- Communication And Portfolio QA, Overclaim And Ethics QA, and Strategy Case QA complete the Phase 10 review with no open `P0` findings.

## Future CLI Shape

The CLI stays as a later implementation convenience, not the first deliverable.

Possible command contract:

```powershell
chargenet ingest ocm --countries DE FR NL BE
chargenet ingest osm --tag amenity=charging_station --countries DE FR NL BE
chargenet ingest eurostat --population-grid --nuts
chargenet validate --rules dq/chargers.yml
chargenet build-marts --target duckdb --export powerbi
chargenet score-baseline --weights config/base.yml
chargenet optimize --method max-coverage --budget 10000000
chargenet export-excel --scenario base
chargenet export-powerbi --format parquet
chargenet publish-hf --artifact dataset-card
```

## Success Evidence

The project is considered portfolio-ready only when it has:
- Real public data sources with citations and caveats.
- A formal OR formulation.
- Greedy baseline and MILP comparison.
- Scenario and sensitivity analysis.
- Excel model linked to optimization outputs.
- Power BI report built from clean marts.
- Executive deck and investment memo.
- Technical appendix explaining data, assumptions, and limits.
- Public-facing summary that is ambitious but not exaggerated.
- QA review reports for every completed phase, with no unresolved `P0` findings.

## Immediate Next Step

Start with **Phase 0: Case Thesis And Scope** and **Phase 1: Literature And Method Review**. Do not build the data pipeline, dashboard, or Excel model until those two gates pass.
