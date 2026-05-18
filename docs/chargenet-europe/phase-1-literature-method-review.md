# ChargeNet Europe - Phase 1 Literature And Method Review

## Purpose

This review chooses the operations research method for the ChargeNet Europe case. The goal is not to collect impressive algorithms. The goal is to justify a practical decision engine for selecting EV charging expansion sites under budget and coverage constraints.

## Method Conclusion

V1 should use a **maximal coverage / facility-location MILP** as the analytical core.

The project should use three method layers:

1. **Weighted scoring / greedy baseline** as the explainable business benchmark.
2. **MILP maximal coverage or facility-location model** as the formal V1 optimization model.
3. **NSGA-II multi-objective optimization** only as V1.5, after the MILP model, data marts, and financial model are stable.

This structure keeps the project credible and portfolio-friendly: the baseline is easy to understand, the MILP gives rigor, and NSGA-II can later show Pareto tradeoffs without making the first version too complex.

## Decision-Maker And Action Mapping

**Primary decision-maker:** Head of Network Development, with Strategy and Finance supporting the investment committee recommendation.

The model output must map candidate sites or site clusters to management actions:

| Action | Trigger logic |
|---|---|
| Prioritize for diligence | Selected by MILP in the base scenario and passes assumption-driven finance screens; still requires land, permit, grid, utilization, and commercial validation. |
| Keep in future shortlist | Selected only in aggressive budget or demand scenarios, or financially sensitive to utilization. |
| Investigate / partner | Attractive coverage and demand logic, but high rollout, grid-proxy, or execution risk. |
| Monitor | Not selected now, but improves under future demand or lower cost assumptions. |
| Do not prioritize under current assumptions | Not selected across scenarios, weak public-data case, high saturation, or poor data confidence. |

## Literature And Source Matrix

| Source | Type | What It Supports | Relevance To This Project |
|---|---|---|---|
| Hakimi, 1965, "Optimum Distribution of Switching Centers..." | Academic OR classic | p-median and graph-based facility-location foundations | Useful background for minimizing weighted distance and explaining why location decisions can be formulated on networks. |
| Church and ReVelle, 1974, "The Maximal Covering Location Problem" | Academic OR classic | Maximal coverage under limited facilities | Direct foundation for selecting charging sites when budget or site count prevents covering every demand zone. |
| Deb et al., 2002, "A fast and elitist multi-objective genetic algorithm: NSGA-II" | Academic algorithm classic | Pareto optimization for conflicting objectives | Useful for V1.5 when comparing coverage, CAPEX, payback, and regional balance. |
| Lamontagne et al., "Optimising Electric Vehicle Charging Station Placement using Advanced Discrete Choice Models" | EV charging optimization paper | EV charging placement, integer programming, maximum covering, greedy heuristics | Confirms that EV charging placement can be cast as a maximum-covering problem and compared with greedy methods. |
| MDPI Applied Sciences, 2022, "Planning of High-Power Charging Stations for Electric Vehicles: A Review" | EV charging planning review | Planning, allocation, sizing, charging infrastructure, grid and transport considerations | Helps define what V1 excludes: detailed load profiles, grid models, and full transport simulation. |
| Regulation (EU) 2023/1804, AFIR | Official policy source | TEN-T and alternative fuels infrastructure policy context | Provides strategic policy framing for corridor charging without turning V1 into a legal compliance model. |
| EAFO FAQ | Official data/methodology source | European charging-point data context and data reliability caveats | Supports using EAFO as macro validation, while recognizing that detailed location work needs additional public sources. |
| OpenStreetMap charging station tagging | Official community data documentation | Location-level charger attributes such as station tags, sockets, operator, access, power | Supports OSM/Overpass as a location-level supply source with explicit quality controls. |
| Open Charge Map developer/source documentation | Open data source documentation | API-based charging location data | Candidate source for station coordinates, status, connection type, and operator fields; must be treated as imperfect public data. |
| Eurostat/GISCO | Official geospatial data source | European administrative boundaries and population grid data | Supports NUTS/geospatial demand zones and Power BI map structure. |

## Source Credibility Tiers

| Tier | Sources | Valid use | Caveat |
|---|---|---|---|
| Peer-reviewed OR classics | Hakimi; Church and ReVelle; Deb et al. | Method foundations and algorithm justification. | They justify model families, not EV-specific assumptions. |
| EV-specific research | Lamontagne et al.; high-power charging planning review. | EV charging placement framing and scope boundaries. | Some sources may be preprint or review-level rather than direct implementation templates. |
| Official policy | Regulation (EU) 2023/1804 / AFIR. | Strategic corridor and infrastructure policy framing. | Do not claim legal compliance unless corridor geometry and regulatory details are modeled. |
| Official statistical/geospatial | EAFO; Eurostat/GISCO. | Macro validation, country context, NUTS/geospatial demand structures. | Country-level data may not support exact site-level conclusions. |
| Community/open operational data | OpenStreetMap; Open Charge Map. | Location-level charger supply and candidate-source enrichment. | Must include confidence, duplicate, missing-field, and freshness checks. |

## Model Family Review

### Weighted Scoring / Greedy Baseline

**Role:** Business-friendly benchmark.

This method ranks candidate sites by a weighted attractiveness score. Example factors:
- Demand proxy.
- Current charger gap.
- Road or corridor proximity.
- Competition saturation.
- Estimated CAPEX class.
- Grid/load proxy.
- Strategic market priority.

**Why include it:**
- It mirrors how a non-OR analyst might shortlist markets.
- It is transparent enough for a strategy deck.
- It gives the MILP model a benchmark to beat.

**Risk:** It can hide arbitrary weights. Mitigation: document weights and run sensitivity checks.

### MILP Maximal Coverage / Facility Location

**Role:** V1 optimization core.

This model selects a portfolio of candidate sites under constraints. It is the right first formal model because the business question is constrained site selection.

**Sets:**
- `I`: demand zones.
- `J`: candidate charging sites.
- `S`: scenarios.

**Parameters:**
- `d_i`: weighted demand in zone `i`.
- `a_ij`: 1 if candidate site `j` can cover demand zone `i` within the chosen service radius; otherwise 0.
- `c_j`: estimated CAPEX class for site `j`.
- `b`: scenario budget.
- `k`: maximum number of sites in a scenario.
- `r_j`: normalized risk score for competition, rollout difficulty, or grid proxy, used only in risk-penalty scenarios.
- `rho`: risk penalty weight used only when the risk-penalty objective is active.

**Decision variables:**
- `x_j`: 1 if site `j` is selected.
- `y_ij`: 1 if demand zone `i` is assigned to selected site `j`.
- `z_i`: 1 if demand zone `i` is covered by at least one selected site.

**Variable domains:**

```text
x_j in {0,1} for all j
y_ij in {0,1} for all i,j
z_i in {0,1} for all i
```

**Core objective:**

Maximize weighted covered demand:

```text
maximize sum_i d_i * z_i
```

**Risk-penalty scenario objective:**

Use only when `d_i` and `r_j` are normalized and `rho` is explicitly documented:

```text
maximize sum_i d_i * z_i - rho * sum_j r_j * x_j
```

**Core constraints:**

```text
sum_j c_j * x_j <= b
sum_j x_j <= k
y_ij <= x_j for all i,j
y_ij <= a_ij for all i,j
sum_j y_ij <= 1 for all i
z_i <= sum_j y_ij for all i
sum_j y_ij <= |J| * z_i for all i
```

Optional constraints can add minimum country/corridor coverage, capacity class, or maximum saturation exposure. These should only be added when the data supports them.

**Why use it:**
- It is formal enough for an OR portfolio project.
- It maps directly to the business decision.
- It can be solved and explained before any advanced heuristic is added.

**Risk:** If candidate sites or demand zones are too numerous, the model can become slow. Mitigation: start with a small pilot geography and aggregate demand zones.

### NSGA-II Multi-Objective Optimization

**Role:** V1.5 advanced layer, not MVP.

NSGA-II is useful if the project later needs a Pareto frontier rather than one weighted objective. Example objectives:
- Maximize demand coverage.
- Minimize CAPEX.
- Maximize payback or NPV proxy.
- Minimize competition exposure.
- Improve regional balance.

**Why not first:**
- It is harder to explain than MILP.
- It can look like algorithm decoration if the business decision is not already strong.
- It requires careful parameter tuning and validation.

**When to add it:**
- After the MILP model is stable.
- After Power BI can show scenario outputs.
- After Excel can translate selected site portfolios into financial metrics.

## V1 Formulation Choice

Use **MILP maximal coverage with budget and site-count constraints**.

This is the best first model because:
- Public data can support coverage and demand proxies more reliably than exact utilization.
- The result is easy to explain: selected sites cover more weighted demand under budget.
- It produces clear outputs for Power BI and Excel.
- It can be compared fairly against a greedy baseline.

## Experimental Design

The first experiment set should be small and controlled.

| Experiment | Purpose | Output |
|---|---|---|
| Greedy baseline vs MILP | Show value of optimization | Coverage, CAPEX, selected sites, gap reduction |
| Budget sensitivity | Test capital constraint | Conservative/base/aggressive budgets |
| Strategy sensitivity | Compare business priorities | Urban-first, corridor-first, balanced |
| Demand sensitivity | Test market uncertainty | Conservative/base/aggressive demand proxies |
| Competition penalty on/off | Test saturation logic | Change in selected sites and coverage |
| Access equity sensitivity | Test underserved-area tradeoff | Change in dense-market versus access-gap coverage |

**Input freeze rules:**
- Greedy baseline and MILP must use the same candidate-site table.
- Greedy baseline and MILP must use the same demand-zone table.
- Service radius must be identical within each scenario.
- Budget and site-count limits must be identical within each scenario.
- Feature weights can change only in named sensitivity runs.
- No algorithm may use output from another algorithm as an input feature.

## Validation Metrics

Every algorithm run should report:
- Weighted demand covered.
- Share of demand zones covered within the service radius.
- Average weighted distance proxy.
- Number of selected sites.
- Total estimated CAPEX.
- Uncovered demand.
- Coverage gap reduction versus existing supply.
- Overlap with saturated areas.
- Access equity tradeoff: dense-market coverage versus underserved-area coverage.
- Solver status.
- Optimality gap when available.
- Runtime.
- Infeasible-constraint notes when a scenario cannot solve.
- Constraint violation checks.
- Payback or NPV proxy after Excel integration.

## Data Caveats To Carry Into Later Phases

The method must not depend on data that is unlikely to be publicly reliable:
- Exact utilization by charger.
- Exact land and connection cost per site.
- Site-level electrical grid capacity.
- Real-time charger status.
- Live route-level travel demand.

These should be handled as assumptions, proxies, or sensitivity inputs.

## Assumption And Proxy Register

| Item | Type | Current treatment | Risk | Downstream artifact |
|---|---|---|---|---|
| Demand weight `d_i` | Proxy | Built from public demand and market indicators. | Proxy may not represent true charging sessions. | Baseline score, MILP objective. |
| Risk score `r_j` | Proxy | Used only in named risk-penalty scenarios after normalization. | Risk components can distort objective if not scaled. | Scenario results, technical appendix. |
| CAPEX `c_j` | Assumption | CAPEX class or scenario estimate. | Exact site cost is not public. | MILP budget, Excel model. |
| Service radius | Assumption | Fixed per scenario. | Real driver behavior and corridor geometry are simplified. | MILP coverage matrix, dashboard. |
| Geographic fairness | Metric / scenario | Report dense-market versus underserved-area coverage. | Utilization-focused optimization may deprioritize lower-density access. | Scenario comparison, deck caveats. |

## Phase 1 Gate Status

**Status:** QA-reviewed conditional pass with P1 remediations applied.

**QA report:** `docs/chargenet-europe/qa/phase-1-qa-review.md`

**Method decisions locked for Phase 2:**
- V1 optimization model: MILP maximal coverage / facility location.
- Baseline: weighted scoring / greedy ranking.
- V1.5 candidate: NSGA-II Pareto frontier.
- Data audit must prioritize sources that can produce demand zones, existing charger supply, and candidate sites.

## Source Links

- Hakimi, 1965: https://pubsonline.informs.org/doi/10.1287/opre.13.3.462
- Church and ReVelle, 1974: https://cir.nii.ac.jp/crid/1362262946026100736
- Deb et al., 2002 NSGA-II: https://research.birmingham.ac.uk/en/publications/a-fast-and-elitist-multi-objective-genetic-algorithm-nsga-ii/
- Lamontagne et al., EV charging placement: https://arxiv.org/abs/2206.11165
- Planning of High-Power Charging Stations review: https://www.mdpi.com/2076-3417/12/7/3214
- Regulation (EU) 2023/1804: https://eur-lex.europa.eu/eli/reg/2023/1804/oj
- EAFO FAQ: https://alternative-fuels-observatory.ec.europa.eu/general-information/frequently-asked-questions
- OSM charging station tags: https://wiki.openstreetmap.org/wiki/Tag%3Aamenity%3Dcharging_station
- Open Charge Map developer page: https://openchargemap.org/develop
- Eurostat/GISCO: https://ec.europa.eu/eurostat/web/gisco
