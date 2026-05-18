# Phase 4 QA Review

## Reviewed Artifacts

- `chargenet/baseline.py`
- `chargenet/cli.py`
- `chargenet/dq.py`
- `chargenet/exports.py`
- `chargenet/dictionary.py`
- `tests/test_chargenet_core.py`
- `data/chargenet/marts/mart_candidate_baseline_scores_tile_smoke.csv`
- `data/chargenet/marts/mart_baseline_sensitivity_tile_smoke.csv`
- `reports/chargenet/powerbi_exports/`
- `docs/chargenet-europe/phase-4-baseline-scoring-report.md`

## Specialist Reviewers

- Baseline And Scoring QA.
- Strategy Case QA.
- Data Engineering QA.
- Power BI QA.
- Overclaim And Ethics QA.

## Gate Decision

Implementation checkpoint pass for the Phase 4 smoke-scope baseline layer.

Full Phase 4 gate is not yet passed because the candidate set is still smoke-scoped, not full pilot-country OSM coverage.

## Findings

| Severity | Reviewer | Finding | Evidence | Required action | Status |
|---|---|---|---|---|---|
| `P1` | Baseline And Scoring QA | Baseline scores needed sensitivity testing before being presented as a business ranking. | `mart_candidate_baseline_scores_tile_smoke.csv` had one weighted score per candidate-scenario only. | Add multiple explainable weight sets and rank-delta outputs. | Fixed: `mart_baseline_sensitivity_tile_smoke.csv` has 29,595 rows from 5,919 baseline rows x 5 weight sets. |
| `P1` | Baseline And Scoring QA | Weight sets needed explicit validation. | Weight choices could be mistyped or fail to sum to 1.0. | Validate weight sums and score bounds. | Fixed: tests validate weight sets; DQ checks weight sums and score range. |
| `P1` | Data Engineering QA | Sensitivity output needed to be reusable by BI, not only a Python-side calculation. | No export or relationship link existed for sensitivity ranking. | Add Power BI export and relationship manifest entries. | Fixed: sensitivity mart exports to Power BI folder and model relationships include candidate and scenario links. |
| `P1` | Power BI QA | Dashboard users need rank movement fields, not only recomputed scores. | A weighted score alone does not show stability. | Add rank, base-rank, rank-delta, stable-top-10, and rank-band fields. | Fixed. |
| `P1` | Overclaim And Ethics QA | Rank outputs could be overread as real site recommendations. | Current candidate set is only controlled smoke scope. | Keep diligence-only language and explicit smoke-scope caveat. | Fixed for checkpoint; carry forward until full pilot extraction. |
| `P2` | Strategy Case QA | Top current candidates are useful for demo, but not yet geographically meaningful. | Base rank-1 rows come from current smoke/batch candidates. | Re-review top and bottom sites after full pilot candidate extraction. | Carry forward. |

## Gate Checklist

- [x] No smoke-scope `P0` findings remain.
- [x] Every smoke-scope `P1` finding has a fix or carry-forward owner.
- [x] Baseline score components and weights are documented.
- [x] Sensitivity weight sets are documented and machine-validated.
- [x] Sensitivity output is exported for BI consumption.
- [x] Diligence-only language is preserved.
- [ ] Full Phase 4 gate is not passed yet.

## Required Carry-Forward

- Rerun baseline and sensitivity after full pilot OSM extraction.
- Add geographic reasonableness review for top and bottom ranked candidates.
- Compare this baseline against the Phase 5 MILP output using the same candidate and demand-zone IDs.
- Keep public materials clear that these are decision-support rankings, not investment-grade recommendations.
