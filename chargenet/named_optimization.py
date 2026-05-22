from __future__ import annotations

import csv
import json
from pathlib import Path

from .optimization import build_scenario_config, solve_mclp_pulp
from .paths import CLEAN_DIR, CONFIG_DIR, MART_DIR, ensure_project_dirs


NAMED_MCLP_METHOD_ID = "method:named-scenario-mclp-pulp-cbc"
DEFAULT_CONFIG_PATH = CONFIG_DIR / "named_optimization_scenarios.json"
DEFAULT_SUMMARY_OUTPUT = MART_DIR / "mart_named_optimization_scenarios_tile_smoke.csv"
DEFAULT_SELECTED_OUTPUT = MART_DIR / "fact_named_optimization_selected_sites_tile_smoke.csv"


SUMMARY_FIELDNAMES = [
    "named_scenario_id",
    "named_scenario_slug",
    "scenario_name",
    "business_framing",
    "base_scenario_id",
    "method_id",
    "solver_status",
    "selected_candidate_count",
    "selected_candidate_ids",
    "objective_covered_demand_weight",
    "covered_zone_count",
    "total_candidate_cost",
    "budget",
    "k",
    "candidate_pool_count",
    "candidate_pool_rule",
    "bias_summary",
    "allowed_use_note",
    "proxy_assumption_label",
]

SELECTED_FIELDNAMES = [
    "named_scenario_id",
    "named_scenario_slug",
    "method_id",
    "selection_rank",
    "candidate_site_id",
    "country_code",
    "nuts_id",
    "site_type",
    "baseline_rank_within_scenario",
    "baseline_score",
    "scenario_priority_score",
    "candidate_pool_rank",
    "c_j",
    "allowed_use_note",
    "proxy_assumption_label",
]


def build_named_optimization_scenario(
    scenario_slug: str,
    *,
    config_path: Path | None = None,
    baseline_path: Path | None = None,
    coverage_path: Path | None = None,
    scenario_path: Path | None = None,
    clean_candidate_path: Path | None = None,
    demand_zone_path: Path | None = None,
    existing_charger_path: Path | None = None,
    summary_output_path: Path | None = None,
    selected_output_path: Path | None = None,
) -> list[Path]:
    ensure_project_dirs()
    configs = load_named_scenario_configs(config_path)
    if scenario_slug not in configs:
        known = ", ".join(sorted(configs))
        raise ValueError(f"Unknown named optimization scenario '{scenario_slug}'. Known scenarios: {known}")

    config = configs[scenario_slug]
    base_scenario_id = config["base_scenario_id"]
    baseline_rows = [
        row for row in read_csv_rows(baseline_path or MART_DIR / "mart_candidate_baseline_scores_tile_smoke.csv")
        if row.get("scenario_id") == base_scenario_id
    ]
    if not baseline_rows:
        raise ValueError(f"No baseline rows found for {base_scenario_id}")

    scenario_rows = read_csv_rows(scenario_path or MART_DIR / "fact_scenario_inputs_tile_smoke.csv")
    scenario_config = build_scenario_config(scenario_rows).get(base_scenario_id)
    if not scenario_config:
        raise ValueError(f"No scenario input rows found for {base_scenario_id}")

    clean_rows = read_csv_rows(clean_candidate_path or CLEAN_DIR / "clean_candidate_sites_tile_smoke.csv")
    demand_rows = read_csv_rows(demand_zone_path or CLEAN_DIR / "clean_demand_zones_nuts3_pilot.csv")
    charger_rows = read_csv_rows(existing_charger_path or CLEAN_DIR / "clean_existing_chargers_tile_smoke.csv")
    scored_rows = build_scored_candidate_rows(baseline_rows, clean_rows, demand_rows, charger_rows, config)
    pool_size = int(config.get("candidate_pool_size") or len(scored_rows))
    pool_rows = sorted(
        scored_rows,
        key=lambda row: (-float(row["scenario_priority_score"]), int(float(row.get("rank_within_scenario") or 999999)), row["candidate_site_id"]),
    )[:pool_size]
    candidate_ids = [row["candidate_site_id"] for row in pool_rows]
    coverage_radius_km = scenario_radius_km(scenario_rows, base_scenario_id)
    coverage_by_candidate = build_coverage_map_for_candidates(
        coverage_path or MART_DIR / "fact_candidate_zone_coverage_tile_smoke.csv",
        candidate_ids,
        coverage_radius_km,
    )
    budget = float(config.get("budget") or scenario_config["b"])
    k = min(int(config.get("k") or float(scenario_config["k"])), len(candidate_ids))
    costs = scenario_config["costs"]

    result = solve_mclp_pulp(candidate_ids, coverage_by_candidate, k=k, costs=costs, budget=budget)
    selected_ids = result["selected_candidate_ids"]
    summary_row = named_summary_row(config, result, coverage_by_candidate, costs, budget, k, len(candidate_ids))
    selected_rows = named_selected_rows(config, selected_ids, pool_rows, costs)

    summary_target = summary_output_path or DEFAULT_SUMMARY_OUTPUT
    selected_target = selected_output_path or DEFAULT_SELECTED_OUTPUT
    upsert_rows(summary_target, [summary_row], SUMMARY_FIELDNAMES, "named_scenario_id", config["named_scenario_id"])
    upsert_rows(selected_target, selected_rows, SELECTED_FIELDNAMES, "named_scenario_id", config["named_scenario_id"])
    return [summary_target, selected_target]


def load_named_scenario_configs(path: Path | None = None) -> dict[str, dict]:
    source = path or DEFAULT_CONFIG_PATH
    payload = json.loads(source.read_text(encoding="utf-8"))
    configs = {row["scenario_slug"]: row for row in payload}
    for slug, config in configs.items():
        if not config.get("named_scenario_id") or not config.get("base_scenario_id"):
            raise ValueError(f"Named optimization scenario '{slug}' is missing required identifiers")
        if not config.get("priority_weights"):
            raise ValueError(f"Named optimization scenario '{slug}' has no priority weights")
    return configs


def build_scored_candidate_rows(
    baseline_rows: list[dict],
    clean_rows: list[dict],
    demand_rows: list[dict],
    charger_rows: list[dict],
    config: dict,
) -> list[dict]:
    clean_by_id = {row["candidate_site_id"]: row for row in clean_rows}
    low_population_by_nuts, high_population_by_nuts = population_scores_by_nuts(demand_rows)
    charger_gap_by_nuts = charger_gap_scores_by_nuts(demand_rows, charger_rows)
    scored_rows = []
    for baseline in baseline_rows:
        clean = clean_by_id.get(baseline["candidate_site_id"], {})
        nuts_id = clean.get("nearest_demand_zone_id") or clean.get("nuts_id") or baseline.get("nuts_id", "")
        nuts_id = nuts_id.replace("dz:nuts2024:", "")
        row = {**baseline, **clean}
        row["low_population_proxy"] = low_population_by_nuts.get(nuts_id, 0.0)
        row["nearest_zone_population_score"] = row["low_population_proxy"]
        row["high_population_proxy"] = high_population_by_nuts.get(nuts_id, 0.0)
        row["charger_gap_proxy"] = charger_gap_by_nuts.get(nuts_id, 0.0)
        row["high_demand_gap_proxy"] = row["high_population_proxy"] * row["charger_gap_proxy"]
        row["scenario_priority_score"] = scenario_priority_score(row, config)
        scored_rows.append(row)
    return scored_rows


def scenario_priority_score(row: dict, config: dict) -> float:
    return round(
        sum(float(weight) * metric_value(row, metric) for metric, weight in config.get("priority_weights", {}).items()),
        6,
    )


def metric_value(row: dict, metric: str) -> float:
    if metric == "highway_corridor_proxy":
        return highway_corridor_proxy(row)
    if metric == "low_population_proxy":
        return float_or_default(row.get("low_population_proxy", row.get("nearest_zone_population_score")), 0.0)
    if metric == "charger_gap_proxy":
        return float_or_default(row.get("charger_gap_proxy"), 0.0)
    if metric in {"high_demand_gap_proxy", "competitor_gap_proxy"}:
        return float_or_default(row.get("high_demand_gap_proxy", row.get("competitor_gap_proxy")), 0.0)
    return float_or_default(row.get(metric), 0.0)


def highway_corridor_proxy(row: dict) -> float:
    tags = parse_tags(row.get("raw_tags_json"))
    site_type = str(row.get("site_type", "")).strip().lower()
    if site_type == "services":
        return 1.0
    if str(tags.get("highway", "")).lower() in {"services", "motorway_junction", "rest_area"}:
        return 1.0
    if "atmotorway" in tags:
        return 1.0
    return 0.0


def population_scores_by_nuts(demand_rows: list[dict]) -> tuple[dict[str, float], dict[str, float]]:
    populations = {
        row["nuts_id"]: float_or_default(row.get("population") or row.get("demand_weight"), 0.0)
        for row in demand_rows
        if row.get("nuts_id")
    }
    return inverse_normalized(populations), normalized(populations)


def charger_gap_scores_by_nuts(demand_rows: list[dict], charger_rows: list[dict]) -> dict[str, float]:
    populations = {
        row["nuts_id"]: max(float_or_default(row.get("population") or row.get("demand_weight"), 0.0), 1.0)
        for row in demand_rows
        if row.get("nuts_id")
    }
    charger_counts = {nuts_id: 0 for nuts_id in populations}
    for row in charger_rows:
        nuts_id = row.get("nuts_id", "")
        if nuts_id in charger_counts:
            charger_counts[nuts_id] += 1
    density_by_nuts = {
        nuts_id: (charger_counts.get(nuts_id, 0) / population) * 100000
        for nuts_id, population in populations.items()
    }
    return inverse_normalized(density_by_nuts)


def normalized(values: dict[str, float]) -> dict[str, float]:
    if not values:
        return {}
    min_value = min(values.values())
    max_value = max(values.values())
    if max_value == min_value:
        return {key: 1.0 for key in values}
    return {key: round((value - min_value) / (max_value - min_value), 6) for key, value in values.items()}


def inverse_normalized(values: dict[str, float]) -> dict[str, float]:
    return {key: round(1.0 - value, 6) for key, value in normalized(values).items()}


def scenario_radius_km(scenario_rows: list[dict], scenario_id: str) -> int:
    for row in scenario_rows:
        if row.get("scenario_id") == scenario_id and row.get("service_radius_km"):
            return int(float(row["service_radius_km"]))
    raise ValueError(f"No service radius found for {scenario_id}")


def build_coverage_map_for_candidates(path: Path, candidate_ids: list[str], coverage_radius_km: int) -> dict[str, dict[str, float]]:
    candidate_id_set = set(candidate_ids)
    coverage: dict[str, dict[str, float]] = {candidate_id: {} for candidate_id in candidate_ids}
    if not path.exists():
        return coverage
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            candidate_id = row.get("candidate_site_id", "")
            if candidate_id not in candidate_id_set:
                continue
            if int(float(row.get("coverage_radius_km") or 0)) != coverage_radius_km:
                continue
            if int(float(row.get("pair_eligible_flag") or 0)) != 1:
                continue
            demand_zone_id = row["demand_zone_id"]
            demand_weight = float_or_default(row.get("demand_weight_contribution"), 0.0)
            coverage[candidate_id][demand_zone_id] = max(coverage[candidate_id].get(demand_zone_id, 0.0), demand_weight)
    return coverage


def named_summary_row(
    config: dict,
    result: dict,
    coverage_by_candidate: dict[str, dict[str, float]],
    costs: dict[str, float],
    budget: float,
    k: int,
    candidate_pool_count: int,
) -> dict:
    selected_ids = result["selected_candidate_ids"]
    return {
        "named_scenario_id": config["named_scenario_id"],
        "named_scenario_slug": config["scenario_slug"],
        "scenario_name": config["scenario_name"],
        "business_framing": config["business_framing"],
        "base_scenario_id": config["base_scenario_id"],
        "method_id": NAMED_MCLP_METHOD_ID,
        "solver_status": result["solver_status"],
        "selected_candidate_count": len(selected_ids),
        "selected_candidate_ids": "|".join(selected_ids),
        "objective_covered_demand_weight": result["objective_covered_demand_weight"],
        "covered_zone_count": len({zone_id for candidate_id in selected_ids for zone_id in coverage_by_candidate.get(candidate_id, {})}),
        "total_candidate_cost": round(sum(costs.get(candidate_id, 0.0) for candidate_id in selected_ids), 2),
        "budget": round(budget, 2),
        "k": k,
        "candidate_pool_count": candidate_pool_count,
        "candidate_pool_rule": f"top {candidate_pool_count} candidates by named scenario priority score, then PuLP/CBC max coverage",
        "bias_summary": bias_summary(config),
        "allowed_use_note": "Named optimization scenario for portfolio diligence only; public proxies are not investment advice.",
        "proxy_assumption_label": "named_scenario_public_proxy_not_investment_grade",
    }


def named_selected_rows(config: dict, selected_candidate_ids: list[str], pool_rows: list[dict], costs: dict[str, float]) -> list[dict]:
    by_id = {row["candidate_site_id"]: row for row in pool_rows}
    pool_rank_by_id = {row["candidate_site_id"]: index for index, row in enumerate(pool_rows, start=1)}
    rows = []
    for selection_rank, candidate_id in enumerate(selected_candidate_ids, start=1):
        row = by_id[candidate_id]
        rows.append(
            {
                "named_scenario_id": config["named_scenario_id"],
                "named_scenario_slug": config["scenario_slug"],
                "method_id": NAMED_MCLP_METHOD_ID,
                "selection_rank": selection_rank,
                "candidate_site_id": candidate_id,
                "country_code": row.get("country_code", ""),
                "nuts_id": row.get("nuts_id", ""),
                "site_type": row.get("site_type", ""),
                "baseline_rank_within_scenario": row.get("rank_within_scenario", ""),
                "baseline_score": row.get("baseline_score", ""),
                "scenario_priority_score": row.get("scenario_priority_score", ""),
                "candidate_pool_rank": pool_rank_by_id[candidate_id],
                "c_j": costs.get(candidate_id, ""),
                "allowed_use_note": "Selected by named optimization scenario for diligence comparison only.",
                "proxy_assumption_label": "named_scenario_selected_site_not_investment_grade",
            }
        )
    return rows


def bias_summary(config: dict) -> str:
    weights = config.get("priority_weights", {})
    return "; ".join(f"{key}={value}" for key, value in weights.items())


def upsert_rows(path: Path, new_rows: list[dict], fieldnames: list[str], key_field: str, key_value: str) -> None:
    existing_rows = [row for row in read_csv_rows(path) if row.get(key_field) != key_value]
    final_rows = existing_rows + new_rows
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(final_rows)


def parse_tags(value: object) -> dict:
    if not value:
        return {}
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def float_or_default(value: object, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def read_csv_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))
