# Phase 2 QA Review

## Reviewed Artifacts

- `docs/chargenet-europe/phase-2-data-source-audit.md`
- `docs/chargenet-europe/phase-2-data-contract-addendum.md`
- `docs/chargenet-europe/qa-governance-framework.md`
- `docs/chargenet-europe/phase-0-case-brief.md`
- `docs/chargenet-europe/phase-1-literature-method-review.md`
- `docs/superpowers/plans/2026-05-16-chargenet-europe-master-plan.md`

## Specialist Reviewers

- Data Source QA.
- Data Engineering QA.
- Overclaim And Ethics QA.

## Gate Decision

Conditional Pass.

No `P0` findings were reported. Phase 2 can pass because the project has enough public data support for a conservative V1 coverage and demand-proxy model. Phase 3 must treat the data-contract addendum as a required entry contract.

## Findings

| Severity | Reviewer | Finding | Evidence | Required action | Status |
|---|---|---|---|---|---|
| `P1` | Data Source QA / Data Engineering QA | Live probe evidence was too narrative for Phase 3 handoff. | Phase 2 summarized samples without exact query URLs, parameters, row counts, or sample rows. | Add reproducible probe evidence: endpoint, query, timestamp, scope, sample fields, row count, and failure evidence. | Applied in `phase-2-data-contract-addendum.md`. |
| `P1` | Data Source QA / Overclaim And Ethics QA | Licensing and redistribution handling was acknowledged but not operationalized. | OSM ODbL, Eurostat/GISCO, EAFO, OCM, ENTSO-E, and Hugging Face were noted but not translated into public-release rules. | Create a source-level licensing matrix covering attribution, raw storage, public artifacts, and redistribution status. | Applied in `phase-2-data-contract-addendum.md`; Phase 3 must create a machine-readable license manifest. |
| `P1` | Data Source QA | Required fields did not clearly separate source data, derived proxies, assumptions, and caveat-only fields. | Candidate fields included `competition_score`, `estimated_capex_class`, and `rollout_risk_score`, while Phase 0 and Phase 1 mark these as proxy/assumption areas. | Add field-level contract with source/derivation, classification, null handling, quality flag, and allowed use. | Applied in `phase-2-data-contract-addendum.md`. |
| `P1` | Data Engineering QA | Stable ID strategy was named but not defined. | Phase 2 listed `source_record_id`, `demand_zone_id`, and `candidate_site_id`, but did not define deterministic ID generation. | Define ID rules for OSM objects, NUTS regions, demand zones, candidate sites, clusters, and scenarios. | Applied in `phase-2-data-contract-addendum.md`. |
| `P1` | Data Engineering QA | Data contract was a field list, not a typed raw/clean/mart contract. | Phase 3 requires raw, cleaned, and mart datasets plus a data dictionary and quality report. | Add table grain, keys, metadata, and raw-to-clean-to-mart expectations. | Applied in `phase-2-data-contract-addendum.md`. |
| `P1` | Data Engineering QA | Optimization compatibility needs an explicit candidate-zone coverage mart. | The MILP requires demand zones `i`, candidate sites `j`, distance/coverage relation `a_ij`, and scenario-independent coverage inputs. | Add `fact_candidate_zone_coverage` with candidate-zone distance, radius flag, and demand contribution. | Applied in `phase-2-data-contract-addendum.md` and referenced from Phase 2 audit. |
| `P1` | Data Engineering QA | Data quality dimensions were risks but not concrete checks. | Accuracy, completeness, consistency, timeliness, validity, and uniqueness were not converted into Phase 3 thresholds. | Define minimum DQ checks for coordinates, duplicates, clustering, missing socket/power, NUTS joins, source versioning, schema, license metadata, and proxy labels. | Applied in `phase-2-data-contract-addendum.md`. |
| `P1` | Overclaim And Ethics QA | Decision labels can read like rollout instructions unless qualified. | Rollout-style labels and financial certainty language can drift into investment-grade wording. | Treat labels as shortlisting/prioritization and require due-diligence caveat. | Applied in `phase-2-data-contract-addendum.md`; must be carried into Phase 4/7/9/10 outputs. |
| `P1` | Overclaim And Ethics QA | Access equity was named but not yet measurable. | Phase 0 and Phase 1 require access equity, but Phase 2 did not define required derived fields. | Define underserved-zone, baseline access gap, density segment, and coverage-split metrics. | Applied in `phase-2-data-contract-addendum.md`. |
| `P2` | Data Source QA / Data Engineering QA | EAFO path is acceptable as non-core context, but reproducible graph download must be pinned before it enters marts. | EAFO has downloadable graphs but no stable API was identified in Phase 2. | Keep EAFO deck-only unless exact download workflow and fields are pinned. | Assigned as Phase 3 entry criterion. |
| `P2` | Data Engineering QA | Power BI geometry/export handling needs a convention. | Phase 8 requires maps and marts, while geometry can create many-to-many ambiguity. | Define centroid fields, GeoJSON/WKT sidecar, CSV/Parquet export, and relationship keys. | Applied in `phase-2-data-contract-addendum.md`. |
| `P2` | Overclaim And Ethics QA | Caveats should become machine-readable so dashboards and decks cannot drop them. | Caveats are written in prose but need fields. | Carry `proxy/assumption`, confidence, missingness, and allowed-use fields into the data dictionary. | Assigned to Phase 3 data dictionary. |

## Gate Checklist

- [x] No `P0` findings remain.
- [x] Every `P1` finding has a fix or Phase 3 entry action.
- [x] Phase acceptance criteria are explicitly checked.
- [x] Data, model, financial, and business claims are supported at a conservative V1 level.

## Phase 3 Required Carry-Forward

- Treat `phase-2-data-contract-addendum.md` as binding.
- Build the first ingest only for OSM, GISCO, and Eurostat.
- Keep EAFO deck-only until an exact reproducible download is pinned.
- Keep Open Charge Map optional unless an API key and public reproduction path are available.
- Exclude ENTSO-E from V1 core.
- Label utilization, CAPEX, payback, rollout, and grid fields as assumptions or caveat-only unless a stronger source is added.
