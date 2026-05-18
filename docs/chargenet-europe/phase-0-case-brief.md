# ChargeNet Europe - Phase 0 Case Brief

## Decision Case

**Working title:** ChargeNet Europe: EV Charging Expansion Decision Support

**Case question:** Given a fixed expansion budget, where should a European EV charging operator prioritize its next charging-site diligence shortlist over 24 months to maximize coverage, expected utilization, and payback while managing competition, rollout, and grid-proxy constraints?

**Business decision supported:** Select and sequence a portfolio of candidate EV charging sites for a constrained 24-month expansion plan.

## Pilot Geography

**Default V1 geography:** Germany, France, Netherlands, and Belgium.

This is a controlled pilot region, not a full Europe-wide optimization. It gives the project enough cross-border complexity for a market-entry and corridor story while keeping data collection, geocoding, and optimization tractable.

**Why this geography is a good first scope:**
- It covers high-relevance Western European EV markets and cross-border travel patterns.
- It can support both urban-node and corridor-style expansion scenarios.
- It keeps the first optimization small enough to run and explain.
- It avoids pretending the first version can solve all European charging infrastructure planning.

## Hypothetical Client

**Client persona:** A mid-sized European charging point operator planning its next wave of fast-charging expansion.

**Primary decision-maker:** Head of Network Development, with Strategy and Finance supporting the investment committee recommendation.

**Client situation:**
- The operator wants to expand beyond its current footprint.
- Capital is limited, so every site must be justified.
- Leadership needs a defensible shortlist, not only a map of existing chargers.
- The decision must balance coverage, expected demand, competition, cost, and rollout feasibility.

## Strategic Framing

This is a capital allocation and market-entry problem with an operations research decision engine.

The project should read like a consulting and analytics case:
- Where should the operator expand first?
- Which areas are attractive but already saturated?
- Which areas have demand potential but weak public charging coverage?
- How sensitive is the recommendation to budget and utilization assumptions?
- What KPIs should leadership monitor after rollout?

## Decision Output Taxonomy

Every recommended candidate site or site cluster should resolve to one of these management actions:

| Action | Meaning |
|---|---|
| Prioritize for diligence | Strong public-data shortlist candidate under the base scenario; requires land, permit, grid, utilization, and commercial validation before any build decision. |
| Keep in future shortlist | Attractive but dependent on higher demand, lower CAPEX, or later rollout capacity. |
| Investigate / partner | Attractive location logic, but execution depends on a partner such as a supermarket, parking operator, fleet hub, or local network. |
| Monitor | Potential future opportunity; not enough current demand or confidence for capital allocation. |
| Do not prioritize under current assumptions | Weak current public-data case or unreliable data; not proof that the location is objectively bad. |

## V1 Site Concept

**Candidate site unit:** A fast-charging hub candidate, represented by a city, NUTS3 zone, motorway/service-area proxy, or road-accessible candidate point depending on available data.

**Charging hub assumption for modeling:** A candidate site represents a small public fast-charging rollout option, not an exact engineered site design. Charger count, charger power class, CAPEX, OPEX, and utilization are handled as assumptions in the Excel model.

## Success Metrics

The first version must report these metrics for every scenario:

- **Demand covered:** weighted demand covered within the chosen service radius.
- **Coverage gap reduced:** underserved demand zones improved versus the current supply baseline.
- **CAPEX used:** estimated expansion investment under the scenario budget.
- **Expected utilization proxy:** demand captured relative to installed capacity.
- **Payback or NPV proxy:** assumption-driven financial attractiveness from the Excel model.
- **Average access distance proxy:** weighted distance from demand zones to selected sites or nearest covered candidate.
- **Competition exposure:** selected sites in already saturated versus underserved areas.
- **Access equity tradeoff:** whether the recommendation favors dense high-utilization markets over underserved access-improvement areas.

## Assumption And Proxy Register

This register starts in Phase 0 and must be carried forward into later artifacts.

| Item | Type | Current treatment | Risk | Downstream artifact |
|---|---|---|---|---|
| Charger utilization | Assumption | Modeled through scenario inputs. | Public data may not show actual utilization. | Excel model, scenario analysis. |
| Site CAPEX | Assumption | CAPEX class used until better data appears. | Exact land/grid/site cost is unavailable. | Excel model, MILP budget constraint. |
| Demand | Proxy | Population, road/corridor, EV market, and macro indicators. | Proxy may not represent true charging demand. | Baseline score, MILP demand weights. |
| Grid capacity | Proxy / optional | Treated as high-level risk only. | Site-level grid capacity is not public. | Scenario penalty or caveat. |
| Geographic fairness | Metric / tradeoff | Reported as access gap and underserved-area coverage. | Pure utilization logic may ignore lower-density access needs. | Dashboard, deck, model appendix. |

## V1 Scenarios

The first build will compare a small set of controlled scenarios:

| Scenario | Purpose | Initial setting |
|---|---|---|
| Conservative budget | Test capital discipline | Lower site count and tighter CAPEX |
| Base budget | Main recommendation | Balanced coverage and economics |
| Aggressive budget | Growth case | Larger network expansion |
| Urban-first | Dense demand focus | Prioritize population and city demand |
| Corridor-first | Travel coverage focus | Prioritize motorway/service-area proxies |
| Balanced | Executive recommendation candidate | Blend urban demand, corridor value, and gap closure |

## Method Boundaries

**In scope for V1:**
- Public EV charging supply data.
- Public demand and market proxies.
- Weighted scoring baseline.
- MILP maximal-coverage or facility-location model.
- Scenario and sensitivity analysis.
- Excel financial model.
- Power BI executive dashboard.
- Executive deck, investment memo, and technical appendix.

**Out of scope for V1:**
- Real-time charger availability.
- Real utilization data unless a reliable public source appears during Phase 2.
- Detailed land acquisition cost.
- Detailed grid-connection capacity.
- Electrical network simulation.
- Real-time traffic routing.
- Dynamic pricing.
- Charging queue simulation.
- Full Europe-wide optimization.
- Claims that outputs are investment-grade recommendations.

## Required Outputs

Phase 0 is accepted when the project has:
- A one-sentence business decision question.
- A named pilot geography.
- A named target user/client persona.
- A fixed list of success metrics.
- A list of explicit non-goals.
- A clear statement that V1 is a decision-support prototype based on public data and assumptions.

## Phase 0 Gate Status

**Status:** QA-reviewed conditional pass.

**QA report:** `docs/chargenet-europe/qa/phase-0-qa-review.md`

**Locked defaults for Phase 1:**
- Pilot geography: Germany, France, Netherlands, Belgium.
- Main model family: maximal coverage / facility location.
- Baseline: weighted scoring / greedy ranking.
- V1 optimization core: MILP.
- NSGA-II: hold for V1.5 unless Phase 5 is stable.
