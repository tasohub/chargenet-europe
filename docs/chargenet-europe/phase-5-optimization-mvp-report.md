# ChargeNet Europe - Phase 5 Optimization MVP Checkpoint

## Scope

This checkpoint adds an optimization layer on top of the Phase 4 baseline scoring mart. PuLP/CBC is now installed and used as the MILP backend for the smoke candidate set.

This is a smoke-scope MILP checkpoint, not the final full-pilot MILP gate.

## Model Type

The business problem is a maximal covering location problem:

```text
Select candidate sites to maximize unique covered demand weight
subject to:
  selected candidate count <= k
  selected candidate cost <= budget
  candidate-zone coverage is defined by a_ij
```

Current method IDs:

| Method | Meaning |
|---|---|
| `method:baseline-topk` | Benchmark: take top baseline-ranked candidates within `k` and budget. |
| `method:mclp-shortlist-exact` | Exact maximal coverage search over the top baseline shortlist as an audit benchmark. |
| `method:mclp-pulp-cbc` | PuLP/CBC MILP over all current smoke/batch candidates. |

The shortlisted exact search currently uses the top 18 baseline candidates per radius scenario. The PuLP/CBC method uses all 1,973 current smoke/batch candidates.

## Cost Assumptions

Candidate cost `c_j` now uses a proxy model instead of a single flat value:

```text
c_j = site_type_base_cost
      * rollout_risk_contingency
      * data_quality_contingency
```

Current smoke-scope cost range:

| Metric | Value |
|---|---:|
| Minimum candidate cost | 550,000 |
| Maximum candidate cost | 850,000 |
| Unique candidate cost values | 6 |
| Cost model version | `tile_smoke_capex_proxy_v2` |

These are still assumptions. They make the budget constraint more realistic than a single placeholder cost, but they are not observed CAPEX.

## Generated Outputs

| Output | Rows | Grain |
|---|---:|---|
| `mart_optimization_results_tile_smoke.csv` | 9 | One row per scenario and method. |
| `mart_optimization_constraint_diagnostics_tile_smoke.csv` | 36 | One constraint diagnostic per scenario, method, and constraint. |
| `fact_optimization_selected_sites_tile_smoke.csv` | 63 | One selected candidate per scenario and method. |

## Current Results

| Scenario | Method | Selected candidates | Covered demand weight | Note |
|---|---|---:|---:|---|
| `scenario:radius-conservative` | `method:baseline-topk` | 10 | 6,900,499 | Benchmark top-k. |
| `scenario:radius-conservative` | `method:mclp-shortlist-exact` | 1 | 6,900,499 | Same coverage with fewer non-incremental selections. |
| `scenario:radius-conservative` | `method:mclp-pulp-cbc` | 10 | 18,287,940 | MILP improves unique covered demand within constraints. |
| `scenario:radius-base` | `method:baseline-topk` | 10 | 8,197,709 | Benchmark top-k. |
| `scenario:radius-base` | `method:mclp-shortlist-exact` | 1 | 8,197,709 | Same coverage with fewer non-incremental selections. |
| `scenario:radius-base` | `method:mclp-pulp-cbc` | 10 | 27,652,281 | MILP improves unique covered demand within constraints. |
| `scenario:radius-aggressive` | `method:baseline-topk` | 10 | 12,549,288 | Benchmark top-k. |
| `scenario:radius-aggressive` | `method:mclp-shortlist-exact` | 1 | 12,549,288 | Same coverage with fewer non-incremental selections. |
| `scenario:radius-aggressive` | `method:mclp-pulp-cbc` | 10 | 41,225,528 | MILP improves unique covered demand within constraints. |

## Interpretation

The current smoke/batch candidate set is still concentrated in selected tiles. In the French smoke tile, multiple fuel POI candidates cover the same NUTS3 demand zones. The exact MCLP shortlist search therefore finds that one candidate can match the unique coverage delivered by ten baseline-ranked candidates.

The PuLP/CBC MILP uses the full current smoke/batch candidate set instead of only the baseline shortlist. It selects up to `k=10` candidates when additional sites add unique covered demand under the current radius and cross-border rules; in the aggressive radius scenario, the current capped batch set uses the full `k=10` site count.

This is not a recommendation to select one real site. It is a useful diagnostic:

- The optimization layer is using unique covered demand, not summed duplicate coverage.
- The baseline can over-rank redundant nearby candidates.
- The MILP backend can find materially higher unique coverage than baseline top-k on the current smoke set.
- Full pilot extraction is required before interpreting selected-site geography.

## Power BI Readiness

Power BI exports now include:

- `mart_optimization_results_tile_smoke.csv`
- `mart_optimization_constraint_diagnostics_tile_smoke.csv`
- `fact_optimization_selected_sites_tile_smoke.csv`
- Relationship links from optimization outputs to `dim_scenario`, `dim_candidate_site_tile_smoke`, and the `scenario_method_id` summary grain.

Useful BI views:

- Baseline top-k versus MCLP shortlist exact versus PuLP/CBC MILP.
- Covered demand by scenario and method.
- Selected candidate count versus covered demand.
- Constraint status by scenario and method.
- Redundant candidate signal by scenario.

## Gate Status

Phase 5 smoke-scope MILP checkpoint passes as an MVP.

Constraint diagnostics now pass for every current scenario-method output:

| Diagnostic | Scope |
|---|---|
| `budget` | Selected candidate cost stays within scenario budget. |
| `site_count` | Selected candidate count stays within `k`. |
| `solver_status` | Solver or benchmark status is accepted as feasible for this checkpoint. |
| `objective_nonnegative` | Covered-demand objective is nonnegative. |

Full Phase 5 remains open until:

- Full pilot OSM extraction replaces the smoke candidate set.
- Candidate costs are calibrated with stronger external evidence or a finance model.
- Feasibility diagnostics are rerun and reviewed on the full pilot candidate universe.
