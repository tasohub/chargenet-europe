# ChargeNet Europe - Phase 2 Data Source Audit

## Purpose

This phase checks whether ChargeNet Europe can be built from public data without pretending that public data can answer private investment questions exactly.

The audit separates four source roles:

| Role | Meaning | V1 treatment |
|---|---|---|
| Model input | Required by the optimization and Power BI marts. | Must be inspectable and reproducible. |
| Demand proxy | Supports demand-zone weights. | Must have stable geography keys. |
| Strategic context | Supports the deck and market-entry story. | Useful but not allowed to drive exact site selection alone. |
| Optional enrichment | Can improve the story later. | Excluded from V1 if it adds access, licensing, or complexity risk. |

## Source Inventory

| Source | Intended use | Access path | License / reuse note | Key fields needed | Probe status | V1 decision |
|---|---|---|---|---|---|---|
| OpenStreetMap / Overpass | Existing charger supply and candidate points. | Overpass API queries for `amenity=charging_station`, `amenity=fuel`, and service-area proxies. | OSM data is ODbL; attribution and derived-database obligations must be respected. | `osm_id`, `lat`, `lon`, `operator`, `brand`, `capacity`, `access`, `socket:*`, `socket:*:output`, `opening_hours`, candidate proxy tags. | Live sample succeeded for charging stations and fuel/service-area proxies. | Primary V1 source for location-level public charger supply and candidate generation. |
| Eurostat / GISCO NUTS boundaries | Demand-zone geography and Power BI maps. | GISCO NUTS 2024 GeoJSON and CSV distribution API. | EU / Eurostat reuse generally requires attribution; check dataset-level notes. | `CNTR_CODE`, `NUTS_ID`, `NAME_LATN`, geometry, `URBN_TYPE`, `COAST_TYPE`, `MOUNT_TYPE`. | Live GeoJSON and CSV samples succeeded. | Primary V1 geography source. |
| Eurostat regional population API | Demand-zone weights. | Eurostat dissemination statistics API, dataset `demo_r_pjanaggr3`. | EU / Eurostat reuse generally requires attribution; check dataset-level notes. | `geo`, `time`, `unit`, `sex`, `age`, population value. | Live NUTS population sample succeeded. | Primary V1 demand proxy. |
| EAFO | Country-level charging market context and macro validation. | EAFO graphs and downloadable CSV/XLS where available. | Site says most graphs can be downloaded as CSV or XLS; source caveats apply. | Country, time, recharging points, charger type, public accessibility definitions. | Documentation confirms downloadable graph data, but no stable public API was identified in this audit. | Strategic context and validation, not a core model dependency. |
| Open Charge Map | Optional charger supply cross-check. | `api.openchargemap.io/v3/poi/` endpoint. | Requires Open Charge Map API key; source quality must be checked separately. | POI ID, address, coordinates, operator, connection type, status, power, usage. | Live unauthenticated request returned 403 and API-key requirement. | Optional enrichment only unless an API key is available. |
| ENTSO-E Transparency Platform | Optional country or zone-level load/grid proxy. | Platform UI, downloads, and registered-user API. | Requires registration for API/download workflows; use only with attribution and caveats. | Country/zone, time, load or market data, bidding zone. | Official documentation indicates registration is needed for download/API access. | V1.5 optional; exclude from V1 core to avoid grid-overclaiming. |
| Hugging Face datasets | Optional packaging, demo distribution, or secondary comparison. | Hugging Face Hub datasets. | Dataset-level licenses vary. | Dataset card, schema, license, provenance. | Search found relevant community EV datasets, including a global EV infrastructure dataset, but these are secondary to official/primary sources. | Publishing/demo layer only; not a V1 authoritative source. |

## Live Probe Evidence

The live probes were run on 2026-05-16 from the project workspace.

| Probe | Result | Evidence |
|---|---|---|
| OSM charging stations through Overpass | Succeeded. | Sample returned Brussels-area charging-station records with `id`, `lat`, `lon`, `capacity`, `operator`, `access`, and socket tags. |
| OSM candidate proxies through Overpass | Succeeded. | Sample returned `amenity=fuel` records with coordinates, brand, operator, and opening-hour style tags. |
| GISCO NUTS 2024 GeoJSON | Succeeded. | Sample returned BE, DE, FR, and NL country features with `CNTR_CODE`, `NUTS_ID`, `NAME_LATN`, and `MultiPolygon` geometry. |
| GISCO NUTS 2024 CSV | Succeeded with `curl.exe`. | Sample returned NUTS attributes including `CNTR_CODE`, `NUTS_ID`, `NAME_LATN`, `NUTS_NAME`, `MOUNT_TYPE`, `URBN_TYPE`, and `COAST_TYPE`. |
| Eurostat regional population API | Succeeded. | Query for `demo_r_pjanaggr3` returned population for Germany and a NUTS3 example (`DE212`). |
| Open Charge Map API | Failed without key, as expected. | Endpoint returned 403 with the message that an API key must be specified through `key` or `x-api-key`. |
| EAFO | Documentation verified, but no stable public API confirmed. | EAFO FAQ says most graphs can be downloaded in CSV or XLS and describes public recharging-point definitions. |
| ENTSO-E | Documentation verified; no unauthenticated API dependency accepted. | ENTSO-E Manual of Procedures says registration is necessary to download data or query via REST API / repository. |

## Required V1 Fields

### Existing Charger Supply

Required fields:
- `charger_source`
- `source_record_id`
- `country_code`
- `lat`
- `lon`
- `operator`
- `brand`
- `access`
- `capacity`
- `socket_count_type2`
- `socket_count_ccs`
- `socket_count_chademo`
- `max_power_kw`
- `data_quality_score`

OSM can support the core coordinate and tag fields, but socket and power tags may be incomplete. Missing socket or power fields must be flagged rather than filled silently.

### Demand Zones

Required fields:
- `demand_zone_id`
- `country_code`
- `nuts_id`
- `zone_name`
- `geometry`
- `population`
- `urban_type`
- `coast_type`
- `mountain_type`
- `demand_weight`

GISCO and Eurostat can support these fields. `demand_weight` must be documented as a proxy, not observed charging demand.

### Candidate Sites

Required fields:
- `candidate_site_id`
- `candidate_source`
- `country_code`
- `lat`
- `lon`
- `site_type`
- `road_or_service_proxy`
- `nearest_demand_zone_id`
- `existing_charger_gap_score`
- `competition_score`
- `estimated_capex_class`
- `rollout_risk_score`

OSM can support initial candidate points from fuel stations, motorway service proxies, and existing POI structures. Exact land availability and grid connection feasibility are not publicly observable and must remain assumptions or risk scores.

### Macro Context

Required fields:
- `country_code`
- `year_or_month`
- `public_recharging_points`
- `charger_type_or_power_class`
- `source_definition`

EAFO can support this layer for market context and country-level validation. It should not be used to claim exact utilization or site-level economics.

## Data Quality Risk Register

| Risk | Severity | Why it matters | Treatment |
|---|---|---|---|
| OSM completeness varies by country and city. | High | Apparent charger gaps may reflect mapping gaps. | Add source confidence, compare country totals with EAFO/Open Charge Map where possible, and avoid exact market-size claims from OSM alone. |
| Socket and power tags are incomplete. | High | Fast-charging strategy depends on power class. | Parse available `socket:*:output` tags, otherwise classify as unknown. Do not impute exact kW values unless an assumption is explicitly stated. |
| Open Charge Map requires an API key. | Medium | It may not be available for reproducible portfolio review. | Keep OCM optional; build V1 from OSM and Eurostat/GISCO. |
| EAFO is strong for macro context but not direct site records. | Medium | Country totals cannot select exact candidate sites. | Use EAFO for validation and deck context only. |
| Population is a demand proxy, not charging-session demand. | High | The model can over-prioritize dense areas. | Add urban/corridor/fairness scenarios and label `demand_weight` as a proxy. |
| Grid capacity is not site-level public data. | High | A selected site may be unrealistic without grid feasibility checks. | Treat grid as a caveat or optional V1.5 risk proxy, not a hard V1 constraint. |
| ODbL obligations affect redistribution. | Medium | Published derived datasets may need ODbL-compatible handling. | Provide OSM attribution, keep raw OSM extracts out of public repo if needed, and publish scripts/configs rather than large derived OSM databases. |
| Coordinate duplicates and clustered charge points can overcount supply. | Medium | Many charge points may represent one station or hub. | Deduplicate by source ID and spatial clustering; report station-level and connector-level counts separately. |
| NUTS revisions can break joins. | Medium | Eurostat and GISCO versions must match. | Lock NUTS 2024 for V1 and store source version in metadata. |

## Fit-For-Use Decision

V1 is feasible from public sources if the project uses a conservative data contract:

- Use OSM/Overpass as the primary location-level public infrastructure source.
- Use GISCO NUTS 2024 as the geography backbone.
- Use Eurostat regional population as the first demand proxy.
- Use EAFO as macro validation and market-context evidence.
- Keep Open Charge Map as optional enrichment because the live endpoint requires an API key.
- Keep ENTSO-E outside the V1 core because it adds registration and grid-overclaiming risk.
- Use Hugging Face only as an optional publishing/demo layer or secondary comparison, not as the authority for the decision model.

## Phase 3 Data Contract

Detailed Phase 3 handoff rules are defined in `docs/chargenet-europe/phase-2-data-contract-addendum.md`. That addendum is part of the Phase 2 gate and covers:

- Exact probe queries and sample evidence.
- Source licensing and public-release rules.
- Deterministic ID rules.
- Field-level observed/proxy/assumption classification.
- Raw, clean, and mart table contracts.
- Required data quality checks and thresholds.
- Access-equity metrics.
- Due-diligence wording guardrails.
- Power BI export conventions.

The next phase should build only these first raw extracts:

| Raw extract | Source | Minimum acceptance |
|---|---|---|
| `raw_osm_charging_stations` | OSM/Overpass | Charger records for DE, FR, NL, BE with coordinates and raw tag JSON. |
| `raw_osm_candidate_pois` | OSM/Overpass | Fuel/service-area/candidate POIs with coordinates and raw tag JSON. |
| `raw_gisco_nuts_geometries` | GISCO | NUTS 2024 geometries for DE, FR, NL, BE. |
| `raw_gisco_nuts_attributes` | GISCO | NUTS attributes including urban/coastal/mountain typology where available. |
| `raw_eurostat_population` | Eurostat API | Population values keyed by NUTS region and year. |
| `raw_eafo_country_context` | EAFO manual/API-like download | Country-level charging context if the graph download is reproducible. |
| `fact_candidate_zone_coverage` | Derived mart | Candidate-zone distance, within-radius flag, and demand contribution for the MILP coverage matrix. |

Phase 3 must not start by downloading every possible dataset. It should first create these extracts, write a data dictionary, then generate a data quality report.

## Phase 2 Gate Status

**Status:** QA-reviewed conditional pass with P1 remediations applied or assigned to Phase 3 entry criteria.

**QA report:** `docs/chargenet-europe/qa/phase-2-qa-review.md`

**Gate condition:** Phase 3 implementation can start only if the addendum rules are treated as entry criteria, not optional notes.

## Source Links

- OpenStreetMap copyright and ODbL: https://www.openstreetmap.org/copyright/en
- OSM charging-station tagging: https://wiki.openstreetmap.org/wiki/Tag%3Aamenity%3Dcharging_station
- Overpass API: https://wiki.openstreetmap.org/wiki/Overpass_API
- GISCO NUTS 2024 distribution API: https://gisco-services.ec.europa.eu/distribution/v1/nuts-2024.html
- Eurostat population grids: https://ec.europa.eu/eurostat/web/gisco/geodata/population-distribution/population-grids
- Eurostat API getting started: https://ec.europa.eu/eurostat/web/user-guides/data-browser/api-data-access/api-getting-started
- Eurostat copyright notice: https://ec.europa.eu/eurostat/help/copyright-notice
- EAFO FAQ: https://alternative-fuels-observatory.ec.europa.eu/general-information/frequently-asked-questions
- EAFO about page: https://alternative-fuels-observatory.ec.europa.eu/general-information/about-european-alternative-fuels-observatory
- Open Charge Map developer page: https://openchargemap.org/develop
- ENTSO-E Transparency Platform Manual of Procedures: https://www.entsoe.eu/Documents/MC%20documents/Transparency%20Platform/MOP/00_ENTSO-E%20Manual%20of%20Procedures_V2R1.pdf
- Hugging Face global EV infrastructure dataset: https://huggingface.co/datasets/tarekmasryo/global-ev-infra-dataset
