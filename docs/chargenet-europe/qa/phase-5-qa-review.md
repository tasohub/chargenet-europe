# Phase 5 QA Review

## Reviewed Artifacts

- `chargenet/optimization.py`
- `chargenet/cli.py`
- `chargenet/dq.py`
- `chargenet/exports.py`
- `chargenet/dictionary.py`
- `tests/test_chargenet_core.py`
- `data/chargenet/marts/mart_optimization_results_tile_smoke.csv`
- `data/chargenet/marts/mart_optimization_constraint_diagnostics_tile_smoke.csv`
- `data/chargenet/marts/fact_optimization_selected_sites_tile_smoke.csv`
- `reports/chargenet/powerbi_exports/`
- `docs/chargenet-europe/phase-5-optimization-mvp-report.md`

## Specialist Reviewers

- Operations Research QA.
- Experiment Design QA.
- Data Engineering QA.
- Strategy Case QA.
- Overclaim And Ethics QA.

## Gate Decision

Implementation checkpoint pass for the Phase 5 smoke-scope MILP MVP.

Full Phase 5 gate is not yet passed because the candidate set is still smoke-scoped and candidate costs are proxy assumptions.

## Findings

| Severity | Reviewer | Finding | Evidence | Required action | Status |
|---|---|---|---|---|---|
| `P1` | Operations Research QA | The environment initially had no external MILP solver. | `scipy`, `pulp`, and `ortools` imports were unavailable. | Install a solver and keep fallback/audit methods explicit. | Fixed for checkpoint: PuLP/CBC installed and `method:mclp-pulp-cbc` added; shortlisted exact search remains as audit benchmark. |
| `P1` | Operations Research QA | Baseline ranking can double-count redundant nearby candidates. | Baseline top-k selects 10 candidates while MCLP shortlist exact matches unique covered demand with 1 candidate in each current radius scenario. | Report unique coverage and selected candidate count side by side. | Fixed in optimization summary mart. |
| `P1` | Data Engineering QA | Optimization outputs needed reproducible marts and BI exports. | No optimization result table existed before Phase 5. | Add summary and selected-site marts, dictionary coverage, DQ checks, and Power BI exports. | Fixed. |
| `P1` | Operations Research QA | Constraint satisfaction needed row-level diagnostics. | Summary checks existed, but no scenario-method diagnostic mart was available for BI or QA drilldown. | Add diagnostics for budget, site-count, solver status, and non-negative objective. | Fixed for checkpoint with 36 diagnostic rows and DQ value-parity checks. |
| `P1` | Experiment Design QA | Optimization must use the same candidate, demand-zone, and radius IDs as baseline. | Phase 3 contract requires shared IDs. | Build from `fact_candidate_zone_coverage_tile_smoke`, `fact_scenario_inputs_tile_smoke`, and `mart_candidate_baseline_scores_tile_smoke`. | Fixed for smoke scope. |
| `P1` | Finance / Assumption QA | Candidate costs were a single flat placeholder. | Earlier `c_j` values were fixed at one value across candidate rows. | Add a transparent proxy cost model and validate positive, variable, versioned costs. | Fixed for checkpoint: `tile_smoke_capex_proxy_v2` produces 6 unique `c_j` values from 550,000 to 850,000. |
| `P1` | Overclaim And Ethics QA | MCLP selected sites could be mistaken for real recommendations. | Current OSM candidate set is a capped 324-job smoke/batch subset, not full pilot coverage. | Preserve smoke-scope and diligence-only caveats. | Fixed in marts and report. |
| `P2` | Strategy Case QA | Current MILP result is still smoke-scoped. | PuLP/CBC improves covered demand versus baseline on current smoke data, but the candidate universe is not full pilot coverage. | Re-run after full pilot extraction where candidate geography is broader. | Carry forward. |

## Gate Checklist

- [x] No smoke-scope `P0` findings remain.
- [x] Method limitation is explicit: PuLP/CBC MILP on smoke scope, not full pilot scope.
- [x] Budget and site-count constraints are checked.
- [x] Constraint diagnostics exist for every scenario-method output.
- [x] Candidate IDs in selected-site output join to the smoke candidate dimension.
- [x] Candidate costs are positive, variable, and version-labeled.
- [x] Optimization results are exported for BI.
- [x] Diligence-only language is preserved.
- [ ] Full Phase 5 gate is not passed yet.

## Required Carry-Forward

- Run optimization after full pilot OSM extraction.
- Calibrate candidate costs with stronger external evidence or the later finance model.
- Re-run constraint diagnostics after full pilot extraction.
- Compare baseline, shortlisted exact MCLP, and full MILP once full data exists.
