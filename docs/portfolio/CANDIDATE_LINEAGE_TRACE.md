# Candidate Lineage Trace

This trace follows one real top-50 baseline candidate end to end: `candidate:osm:node:25214653`, a public OpenStreetMap fuel-station proxy in Paris. It is a strong baseline candidate, but it is still only a proxy record. Nothing below validates land control, grid capacity, permits, traffic, utilization, or commercial feasibility.

## 1. Raw OSM Record

| Field | Value |
|---|---|
| Source record | `osm:node:25214653` |
| Tile job | `osm_tile:candidate_fuel:FR101` |
| Name | Relais des Chaufourniers |
| Brand / operator | TotalEnergies / Total |
| Coordinates | 48.8801814, 2.3707442 |

Selected raw tags copied from the cleaned OSM payload:

| OSM tag | Value |
|---|---|
| `amenity` | `fuel` |
| `brand` | `TotalEnergies` |
| `operator` | `Total` |
| `opening_hours` | `24/7` |
| `shop` | `convenience;gas` |
| `compressed_air` | `yes` |
| `toilets` | `yes` |
| `wheelchair` | `yes` |
| `check_date` | `2023-05-17` |
| `source` | `stations.gpl.online.fr` |

What the data supports: this is an observed OSM fuel POI with useful amenities and a recognizable brand/operator. What is inferred: using it as an EV charging candidate assumes a fuel-site proxy could be relevant for expansion diligence.

## 2. Cleaning Layer

| Clean field | Value |
|---|---|
| Candidate ID | `candidate:osm:node:25214653` |
| Country / NUTS3 | FR / FR101 |
| Nearest demand zone | `dz:nuts2024:FR101` |
| Site type | `fuel` |
| Data quality score | 0.675 |
| Rollout risk score | 0.500 |
| Competition score | 0.500 |

The cleaning layer standardized the OSM node into a deterministic candidate ID, normalized the site type to `fuel`, retained source lineage, assigned the nearest NUTS3 demand zone, and kept a feasibility caveat: "land, permit, grid, and commercial feasibility not validated."

## 3. Coverage Layer

Under `scenario:radius-base`, the service radius is 30 km. Coverage is straight-line distance from candidate coordinates to NUTS3 centroid proxies, not road travel time.

| Covered demand zone | Zone name | Distance km | Demand proxy |
|---|---:|---:|---:|
| `dz:nuts2024:FR101` | Paris | 3.147 | 2,065,560 |
| `dz:nuts2024:FR106` | Seine-Saint-Denis | 6.071 | 1,731,789 |
| `dz:nuts2024:FR105` | Hauts-de-Seine | 9.749 | 1,668,275 |
| `dz:nuts2024:FR107` | Val-de-Marne | 13.704 | 1,434,875 |
| `dz:nuts2024:FR108` | Val-d'Oise | 28.966 | 1,297,210 |

Total covered demand proxy is 8,197,709 across 5 NUTS3 zones. This supports a dense central-Paris coverage signal; it does not prove charger demand or available capacity.

## 4. Baseline Score

| Component | Value |
|---|---:|
| Coverage component | 1.000 |
| Data quality component | 0.675 |
| Rollout risk component | 0.500 |
| Competition component | 0.500 |
| Baseline score | 0.810 |
| Baseline rank | 1 |
| Action bucket | Priority diligence shortlist |

The high score is driven mainly by coverage. Data quality is moderate, while risk and competition are neutral proxy values.

## 5. Sensitivity Behavior

| Weight set | Weighted score | Rank | Change vs base |
|---|---:|---:|---:|
| Base balanced | 0.81000 | 1 | 0 |
| Coverage led | 0.86750 | 1 | 0 |
| Risk aware | 0.75125 | 1 | 0 |
| Competition aware | 0.75125 | 1 | 0 |
| Data quality guardrail | 0.78625 | 1 | 0 |

Its rank did not move across the five tested weight sets. That is a robustness signal for screening, not a build recommendation.

## 6. MILP Result

The baseline top-k benchmark selected this candidate. The full max-coverage mixed-integer linear programming run for `scenario:radius-base` did not. Instead, the first selected MILP site was `candidate:osm:way:901643395`, a French `services` proxy in FR101 with baseline rank 13 and cost proxy 850,000.

That is the main lesson: a single strong baseline site can be locally excellent but redundant for system coverage. The MILP selected a set of 10 candidates covering 67 zones and 27,652,281 demand proxy, versus the baseline top-k's 5 zones and 8,197,709 demand proxy.
