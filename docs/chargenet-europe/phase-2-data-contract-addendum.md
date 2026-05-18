# ChargeNet Europe - Phase 2 Data Contract Addendum

## Purpose

This addendum closes the Phase 2 QA findings before Phase 3 starts. It turns the data-source audit into a reproducible handoff for ingestion, data modeling, Power BI exports, and optimization inputs.

## Source Probe Manifest

All probes below were run on 2026-05-16 from `C:\Users\USER\OneDrive\Belgeler\New project`.

### Probe 1 - OSM Charging Stations

**Role:** Existing charger supply sample.

**Endpoint:** `https://overpass-api.de/api/interpreter`

**Query:**

```text
[out:json][timeout:25];
node["amenity"="charging_station"](50.83,4.30,50.88,4.40);
out body 20;
```

**Scope:** Brussels-area bounding box used only to validate source shape and fields.

**Sample result count:** 20 returned records.

**Observed fields:** `type`, `id`, `lat`, `lon`, `tags.amenity`, `tags.capacity`, `tags.operator`, `tags.access`, `tags.socket:*`, `tags.socket:*:output`.

**Sample rows:**

| type | id | lat | lon | observed tags |
|---|---:|---:|---:|---|
| node | 1409850613 | 50.8391959 | 4.3720102 | `amenity=charging_station`, `capacity=2`, `operator=Elektromotive` |
| node | 4696334505 | 50.8613760 | 4.3541716 | `operator=Allego`, `capacity=3`, `socket:type2`, `socket:type2_combo`, `socket:chademo` |
| node | 4957016623 | 50.8641848 | 4.3492416 | `amenity=charging_station`, `capacity=2`, `motorcar=yes` |

**Phase 3 requirement:** Store raw tag JSON. Do not discard tags that are not yet modeled.

### Probe 2 - OSM Candidate POI Proxies

**Role:** Candidate-site proxy sample.

**Endpoint:** `https://overpass-api.de/api/interpreter`

**Query:**

```text
[out:json][timeout:25];
(
  node["highway"="services"](50.83,4.30,50.95,4.55);
  way["highway"="services"](50.83,4.30,50.95,4.55);
  node["amenity"="fuel"](50.83,4.30,50.95,4.55);
);
out body center 20;
```

**Scope:** Brussels/Zaventem-area bounding box used only to validate candidate-source shape and fields.

**Sample result count:** 20 returned records.

**Observed fields:** `type`, `id`, `lat`, `lon`, `center`, `tags.amenity`, `tags.highway`, `tags.brand`, `tags.operator`, `tags.name`, `tags.opening_hours`.

**Sample rows:**

| type | id | lat | lon | observed tags |
|---|---:|---:|---:|---|
| node | 89229494 | 50.8787490 | 4.5105242 | `amenity=fuel`, `brand=DATS 24`, `operator=Colruyt`, `opening_hours=24/7` |
| node | 144865475 | 50.8656024 | 4.5135988 | `amenity=fuel`, `brand=Q8`, `wheelchair=yes` |
| node | 144913415 | 50.8734613 | 4.4864018 | `amenity=fuel`, `brand=Q8`, `website=*` |

**Phase 3 requirement:** Candidate POIs are proxies, not guaranteed feasible charging sites.

### Probe 3 - GISCO NUTS 2024 GeoJSON

**Role:** Geography backbone for maps and demand zones.

**Endpoint:**

```text
https://gisco-services.ec.europa.eu/distribution/v2/nuts/geojson/NUTS_RG_20M_2024_4326_LEVL_0.geojson
```

**Sample result count:** 39 total country-level features; 4 pilot-country features selected.

**Observed fields:** `CNTR_CODE`, `NUTS_ID`, `NAME_LATN`, `LEVL_CODE`, `geometry.type`.

**Sample rows:**

| CNTR_CODE | NUTS_ID | NAME_LATN | geometry |
|---|---|---|---|
| BE | BE | Belgique/Belgique | MultiPolygon |
| DE | DE | Deutschland | MultiPolygon |
| FR | FR | France | MultiPolygon |
| NL | NL | Nederland | MultiPolygon |

**Phase 3 requirement:** Use NUTS 2024 consistently across geometry, attributes, and population tables.

### Probe 4 - GISCO NUTS 2024 CSV Attributes

**Role:** NUTS attributes for typology and joins.

**Endpoint:**

```text
https://gisco-services.ec.europa.eu/distribution/v2/nuts/csv/NUTS_AT_2024.csv
```

**Observed fields:** `CNTR_CODE`, `NUTS_ID`, `NAME_LATN`, `NUTS_NAME`, `MOUNT_TYPE`, `URBN_TYPE`, `COAST_TYPE`.

**Phase 3 requirement:** Store all NUTS levels but filter reporting marts to the chosen modeling grain.

### Probe 5 - Eurostat Regional Population

**Role:** First demand-zone proxy.

**Endpoint:**

```text
https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/demo_r_pjanaggr3?geo=BE100&sex=T&age=TOTAL&unit=NR&time=2025&lang=en
```

**Sample result:** `geo=BE100`, Brussels-Capital NUTS region, `time=2025`, `value=1271709`.

**Observed dimensions:** `freq`, `unit`, `sex`, `age`, `geo`, `time`.

**Phase 3 requirement:** Use `geo` as the NUTS join key and store `time`, `unit`, `age`, and `sex` as explicit dimensions.

### Probe 6 - Open Charge Map

**Role:** Optional charger cross-check.

**Endpoint:**

```text
https://api.openchargemap.io/v3/poi/?output=json&countrycode=DE&maxresults=3&compact=true&verbose=false
```

**Probe result:** HTTP 403.

**Returned message:** `You must specify an API key using the key query parameter or x-api-key header.`

**Phase 3 requirement:** Do not make Open Charge Map a required source unless an API key is available and public reproduction instructions are documented.

## Licensing And Public Release Matrix

| Source | License / terms handling | Attribution text | Raw data public repo policy | Derived artifact policy |
|---|---|---|---|---|
| OpenStreetMap / Overpass | OSM data is under ODbL. Derived database obligations may apply. | `Contains information from OpenStreetMap, which is made available under the Open Database License.` | Do not publish large raw OSM extracts in V1. Publish scripts, query configs, and small illustrative samples only. | Public screenshots and aggregate outputs must credit OSM. If derived data tables are published, review ODbL share-alike obligations first. |
| Eurostat / GISCO | Use EU/Eurostat attribution; check dataset-level copyright notice. | `Source: Eurostat/GISCO, accessed 2026-05-16.` | Public use allowed only with attribution and source/version metadata. | Public geometry screenshots and tables must include Eurostat/GISCO source note. |
| Eurostat statistics API | Use EU/Eurostat attribution; record dataset code and query dimensions. | `Source: Eurostat dataset demo_r_pjanaggr3, accessed 2026-05-16.` | Public sample outputs allowed with attribution. | Aggregated demand-zone marts can be published if source and transformation are documented. |
| EAFO | Graph downloads are usable only after exact graph/file workflow is pinned. | `Source: European Alternative Fuels Observatory, accessed [date].` | Do not publish EAFO-derived raw extracts until the exact download and terms are recorded. | Deck context is allowed with citation; model dependency is blocked until reproducible. |
| Open Charge Map | API key required; terms and attribution must be checked before use. | `Source: Open Charge Map, accessed [date].` | Do not publish key-dependent raw extracts unless terms allow it and no key is exposed. | Optional cross-check only. |
| ENTSO-E | Registration required for API/download workflows. | `Source: ENTSO-E Transparency Platform, accessed [date].` | Excluded from V1 raw repo. | V1.5 context only unless registration, terms, and exact data path are documented. |
| Hugging Face datasets | Dataset-level license varies. | Use exact dataset card attribution. | Do not treat community datasets as authoritative source of the decision model. | Optional demo/publishing comparison only. |

## Deterministic ID Rules

| Entity | ID rule | Rationale |
|---|---|---|
| Raw OSM object | `osm:{type}:{id}` | Prevents collisions between node, way, and relation IDs. |
| Existing charger station cluster | `charger_cluster:{country}:{geohash_or_grid}:{cluster_sequence}` | Allows nearby charge points to be grouped without losing original source IDs. |
| NUTS region | `nuts2024:{NUTS_ID}` | Prevents NUTS revision drift. |
| Demand zone | `dz:nuts2024:{NUTS_ID}` for NUTS-based V1 | Keeps optimization and Power BI aligned. |
| Candidate POI | `candidate:osm:{type}:{id}` for raw OSM-derived candidates | Keeps candidate lineage inspectable. |
| Candidate cluster | `candidate_cluster:{country}:{geohash_or_grid}:{cluster_sequence}` | Supports clustering and deduplication. |
| Scenario | `scenario:{slug}` | Stable joins between optimization, Excel, and Power BI. |

Rules:
- Do not use raw coordinates as primary keys.
- Store original source IDs and generated IDs together.
- Store NUTS version in every geography-derived table.
- If clustering rules change, create a new cluster-method version rather than rewriting IDs silently.

## Field-Level Contract

| Target field | Source / derivation | Classification | Allowed use |
|---|---|---|---|
| `lat`, `lon` | OSM coordinates or GISCO centroid derivation. | Observed / derived geometry. | BI maps, distance matrix, coverage model. |
| `operator`, `brand` | OSM tags where available. | Observed but incomplete. | Supply analysis, competition proxy with missingness flag. |
| `capacity` | OSM `capacity` tag. | Observed but incomplete. | Supply intensity proxy only. |
| `socket_count_*` | Parsed from OSM `socket:*` tags. | Observed but incomplete. | Charger-type summary with unknown category. |
| `max_power_kw` | Parsed from `socket:*:output` tags where present. | Observed but incomplete. | Power-class proxy only; no exact site capability claims. |
| `population` | Eurostat `demo_r_pjanaggr3`. | Observed statistical data. | Demand proxy input. |
| `demand_weight` | Population plus scenario weights. | Derived proxy. | Baseline score and MILP objective, labeled as proxy. |
| `existing_charger_gap_score` | Demand-zone demand minus nearby observed public-supply proxy. | Derived proxy. | Baseline, scenario reporting, coverage-gap metric. |
| `competition_score` | Nearby existing chargers/operators within defined radius. | Derived proxy. | Baseline/scenario penalty only; not a market-share claim. |
| `estimated_capex_class` | Scenario assumption by site type/country class. | Assumption. | Finance model and budget constraint if labeled as assumption. |
| `rollout_risk_score` | Proxy from candidate type, unknown power, and optional manual risk flags. | Derived proxy / assumption. | Scenario penalty and caveat reporting only. |
| `grid_risk_score` | Not available in V1. | Caveat-only unless reproducible source is added. | Exclude from V1 MILP core. |
| `utilization_proxy` | Scenario assumption, not public observed utilization. | Assumption. | Excel sensitivity only. |
| `payback_proxy` | Excel calculation from assumptions. | Assumption-driven output. | Finance sensitivity; never investment-grade claim. |

## Phase 3 Raw/Clean/Mart Contract

| Layer | Table | Grain | Primary key | Required notes |
|---|---|---|---|---|
| Raw | `raw_osm_charging_stations` | One OSM object per row. | `raw_osm_object_id` | Store raw tags JSON, retrieval timestamp, query hash, source URL. |
| Raw | `raw_osm_candidate_pois` | One OSM object per row. | `raw_osm_object_id` | Store raw tags JSON and candidate-source query name. |
| Raw | `raw_gisco_nuts_geometries` | One NUTS feature per row. | `nuts_version`, `nuts_id` | Store geometry sidecar path or geometry column. |
| Raw | `raw_gisco_nuts_attributes` | One NUTS attribute row. | `nuts_version`, `nuts_id` | Store all typology fields. |
| Raw | `raw_eurostat_population` | One dimension combination per row. | `dataset`, `geo`, `time`, `unit`, `sex`, `age` | Store query dimensions and value. |
| Clean | `clean_existing_chargers` | One cleaned charger object per row. | `charger_source_id` | Preserve original source ID and missingness flags. |
| Clean | `clean_candidate_sites` | One cleaned candidate or candidate cluster per row. | `candidate_site_id` | Candidate feasibility remains a proxy. |
| Clean | `clean_demand_zones` | One demand zone per row. | `demand_zone_id` | Include NUTS version, population, centroid, typology. |
| Mart | `fact_candidate_zone_coverage` | One candidate-zone pair per row. | `candidate_site_id`, `demand_zone_id`, `scenario_independent_radius_km` | Required for MILP `a_ij`, distance, and coverage matrix. |
| Mart | `fact_scenario_inputs` | One scenario-candidate or scenario-zone row. | `scenario_id`, entity ID | Stores scenario-specific assumptions and weights. |
| Mart | `fact_scenario_results` | One scenario-candidate output row. | `scenario_id`, `candidate_site_id` | Stores baseline/MILP selection and metrics. |

## Minimum Data Quality Checks

| Check | Applies to | Acceptance threshold for Phase 3 |
|---|---|---|
| Coordinate validity | OSM chargers/candidates | 100% of retained rows must have valid lat/lon inside pilot countries or be quarantined. |
| Duplicate source keys | Raw OSM extracts | 0 duplicate `osm:{type}:{id}` keys per extract. |
| Spatial clustering audit | Chargers/candidates | Report cluster count and average records per cluster; do not silently merge. |
| Missing socket/power rate | OSM chargers | Report missing rate; unknowns must be explicit. |
| Country/NUTS join success | Chargers/candidates/demand zones | Report join success rate; failed joins go to quarantine table. |
| Population value presence | Demand zones | 100% for zones retained in the V1 optimization set. |
| Source timestamp/version | All raw tables | 100% of raw rows must carry source/retrieval metadata. |
| Schema consistency | All tables | Required columns present before marts build. |
| License metadata | All raw tables | 100% of raw extracts must map to the license manifest. |
| Proxy labeling | Derived fields | 100% of proxy/assumption fields must carry allowed-use note. |

## Access Equity Metrics

Phase 3 must create enough fields for equity to be measurable, not only narrated.

Required fields:
- `baseline_nearest_charger_distance_km`
- `baseline_charger_count_within_radius`
- `underserved_zone_flag`
- `urban_density_segment`
- `coverage_after_selection_flag`
- `dense_market_coverage_share`
- `underserved_coverage_share`
- `access_gap_reduction`

The executive dashboard may call this an access-equity tradeoff, but it must not claim social-impact optimization unless a stronger socioeconomic dataset is added.

## Action Label And Due-Diligence Guardrails

Downstream outputs must treat decision labels as prioritization language:

| Former shorthand | Public-facing interpretation |
|---|---|
| Immediate shortlist | Prioritize for diligence. |
| Build later | Keep in future expansion shortlist. |
| Investigate / partner | Explore partner-led or site-owner validation. |
| Monitor | Track as market conditions change. |
| Reject | Do not prioritize under current assumptions. |

Mandatory caveat for deck, dashboard, README, and memo:

```text
Outputs are public-data decision-support shortlists. They are not investment-grade site recommendations and require land, permit, grid-connection, utilization, and commercial due diligence before site rollout.
```

## Power BI Export Convention

Power BI-facing exports should avoid ambiguous many-to-many relationships.

Required conventions:
- Export dimension tables separately from fact tables.
- Use `country_code`, `nuts_version`, `nuts_id`, `demand_zone_id`, `candidate_site_id`, and `scenario_id` as relationship keys.
- Include centroid `lat` and `lon` for map points.
- Store complex geometry as GeoJSON/WKT sidecar files rather than forcing it into every CSV.
- Export CSV for reviewer simplicity and Parquet only as an optional advanced format.
- Include a visible `source_note` or `data_limitation_note` table for report pages.

## Phase 3 Entry Criteria

Phase 3 can start only when:
- Raw extract scripts/configs are created for OSM, GISCO, and Eurostat.
- The license manifest exists.
- The data dictionary includes field classification: observed, derived proxy, assumption, or caveat-only.
- `fact_candidate_zone_coverage` is included in the target mart list.
- The first data quality report covers the checks listed above.
- EAFO is either pinned to an exact reproducible download workflow or kept deck-only for V1.
