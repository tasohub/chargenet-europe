# ChargeNet Europe - Candidate Lineage Walkthrough

## Purpose

This appendix is a recruiter and interview aid. It traces one selected candidate through the local ChargeNet Europe demo pipeline so the project can be explained as auditable decision support, not as a black-box recommendation engine.

Scope is deliberately narrow: this uses the capped `tile_smoke` batch and public proxy fields already present in local marts. It is not investment advice, not a site feasibility claim, and it does not model grid capacity, permits, traffic, land availability, or commercial due diligence.

## Candidate Traced

Source mart:

```text
data/chargenet/marts/mart_candidate_lineage_trace_tile_smoke.csv
```

Selected row:

| Field | Value |
|---|---|
| `trace_id` | `scenario:radius-base|method:mclp-pulp-cbc|candidate:osm:node:302017504` |
| `candidate_site_id` | `candidate:osm:node:302017504` |
| `source_record_id` | `osm:node:302017504` |
| `tile_run_id` | `20260517T134748Z` |
| `tile_job_id` | `osm_tile:candidate_fuel:BE32C` |
| `candidate_source` | `osm_overpass` |
| `country_code` | `BE` |
| `nuts_id` | `BE32C` |
| `lat`, `lon` | `50.621021`, `4.141594` |
| `site_type` | `fuel` |
| `brand`, `operator`, `name` | `Shell`, `Shell`, `Shell Express` |
| `raw_tag_keys` | `amenity|brand|brand:wikidata|brand:wikipedia|fuel:diesel|fuel:octane_95|fuel:octane_98|name|operator` |

## Pipeline Read

1. Raw public proxy: the candidate begins as an OpenStreetMap Overpass record, represented by `source_record_id = osm:node:302017504`.
2. Tile lineage: `tile_job_id = osm_tile:candidate_fuel:BE32C` and `tile_run_id = 20260517T134748Z` show which capped tile-smoke job produced the candidate proxy.
3. Clean candidate attributes: the clean layer standardizes the public POI into a candidate id, location, NUTS area, site type, brand/operator/name fields, and exported tag keys.
4. Baseline screen: in `scenario:radius-base`, this candidate has `baseline_rank_within_scenario = 27`, `baseline_score = 0.484544`, and `action_bucket = Secondary diligence shortlist`.
5. Optimization selection: the same candidate is selected by `method:mclp-pulp-cbc` with `selection_rank = 2`.
6. Coverage explanation: at `coverage_radius_km = 30`, the trace reports `covered_zone_count = 9`, `covered_demand_weight = 3719438.0`, and top covered demand zones `dz:nuts2024:BE100|dz:nuts2024:BE241|dz:nuts2024:BE310|dz:nuts2024:BE32B|dz:nuts2024:BE231`.
7. Scenario proxy economics: the scenario row contributes `scenario_candidate_cost = 560000`, with `scenario_budget = 10000000` and `scenario_k = 10`.

The useful interview point is not that this is a build-ready location. The point is that a selected candidate can be traced from public source id to tile job, standardized attributes, scoring context, optimization rank, covered proxy zones, and explicit caveats.

## Caveats To Say Out Loud

- Public proxy data only; this is not a proprietary site database.
- Capped smoke/batch output; it proves pipeline behavior, not exhaustive European coverage.
- Scenario costs, demand weights, and coverage are portfolio proxies.
- No grid interconnection, permits, traffic, land parcel, lease, or construction constraints are modeled.
- The mart itself labels the row: `Candidate lineage trace for audit and portfolio explanation only; not investment advice or a site feasibility claim.`
- The proxy assumption label is `tile_smoke_candidate_lineage_trace_not_investment_grade`.

## Regeneration Commands

Run from the project root:

```powershell
python -m chargenet.cli build-candidate-lineage-trace-tile-smoke
python -m chargenet.cli run-portfolio-release-check
```

The first command regenerates the lineage mart and refreshes the data dictionary plus quality report. The second command runs the local recruiter-demo release check and writes `reports/chargenet/portfolio_release_check.csv`.

For a broader local check before demo use:

```powershell
python -m unittest discover -s tests
python -m chargenet.cli run-portfolio-release-check
```
