from __future__ import annotations

import csv
import itertools
import warnings
from pathlib import Path

from .paths import MART_DIR, ensure_project_dirs


DEFAULT_SHORTLIST_SIZE = 18
DEFAULT_SENSITIVITY_SHORTLIST_SIZE = 80
DEFAULT_COVERAGE_FLOOR_PCT = 0.9
BASELINE_METHOD_ID = "method:baseline-topk"
MCLP_METHOD_ID = "method:mclp-shortlist-exact"
PULP_METHOD_ID = "method:mclp-pulp-cbc"
MIN_COST_METHOD_ID = "method:min-cost-coverage-pulp"
SENSITIVITY_MCLP_METHOD_ID = "method:mclp-weighted-shortlist-pulp-cbc"
ACCEPTED_SOLVER_STATUSES = {"benchmark_feasible", "optimal_shortlist", "optimal_milp", "optimal_min_cost"}


def build_optimization_results_tile_smoke(
    baseline_path: Path | None = None,
    coverage_path: Path | None = None,
    scenario_path: Path | None = None,
    summary_output_path: Path | None = None,
    selected_output_path: Path | None = None,
    diagnostics_output_path: Path | None = None,
    shortlist_size: int = DEFAULT_SHORTLIST_SIZE,
) -> list[Path]:
    ensure_project_dirs()
    baseline_rows = read_csv_rows(baseline_path or MART_DIR / "mart_candidate_baseline_scores_tile_smoke.csv")
    coverage_rows = read_csv_rows(coverage_path or MART_DIR / "fact_candidate_zone_coverage_tile_smoke.csv")
    scenario_rows = read_csv_rows(scenario_path or MART_DIR / "fact_scenario_inputs_tile_smoke.csv")
    summary_target = summary_output_path or MART_DIR / "mart_optimization_results_tile_smoke.csv"
    selected_target = selected_output_path or MART_DIR / "fact_optimization_selected_sites_tile_smoke.csv"

    baseline_by_scenario = group_rows(baseline_rows, "scenario_id")
    coverage_by_scenario = build_coverage_maps(coverage_rows, baseline_rows)
    scenario_config = build_scenario_config(scenario_rows)
    summary_rows = []
    selected_rows = []
    diagnostics_target = diagnostics_output_path or MART_DIR / "mart_optimization_constraint_diagnostics_tile_smoke.csv"

    for scenario_id, scenario_baseline_rows in sorted(baseline_by_scenario.items()):
        ranked_rows = sorted(scenario_baseline_rows, key=lambda row: int(row["rank_within_scenario"]))
        config = scenario_config[scenario_id]
        k = min(int(float(config["k"])), len(ranked_rows))
        budget = float(config["b"])
        costs = config["costs"]
        coverage_by_candidate = coverage_by_scenario.get(scenario_id, {})

        baseline_selected = select_baseline_topk(ranked_rows, costs, budget, k)
        baseline_objective = coverage_objective(baseline_selected, coverage_by_candidate)
        baseline_total_cost = sum(costs.get(candidate_id, 0.0) for candidate_id in baseline_selected)
        baseline_summary = result_summary_row(
            scenario_id=scenario_id,
            method_id=BASELINE_METHOD_ID,
            solver_status="benchmark_feasible",
            selected_candidate_ids=baseline_selected,
            objective=baseline_objective,
            coverage_by_candidate=coverage_by_candidate,
            costs=costs,
            budget=budget,
            k=k,
            candidate_pool_count=len(ranked_rows),
            baseline_objective=baseline_objective,
            baseline_total_cost=baseline_total_cost,
            coverage_floor=0.0,
            objective_type="benchmark_baseline_score",
            solver_note="Baseline benchmark selects highest baseline-score candidates within k and budget.",
        )
        summary_rows.append(baseline_summary)
        selected_rows.extend(selected_site_rows(scenario_id, BASELINE_METHOD_ID, baseline_selected, ranked_rows, costs))

        shortlisted_ids = [row["candidate_site_id"] for row in ranked_rows[:shortlist_size]]
        result = solve_mclp_exact(shortlisted_ids, coverage_by_candidate, k=k, costs=costs, budget=budget)
        mclp_summary = result_summary_row(
            scenario_id=scenario_id,
            method_id=MCLP_METHOD_ID,
            solver_status=result["solver_status"],
            selected_candidate_ids=result["selected_candidate_ids"],
            objective=float(result["objective_covered_demand_weight"]),
            coverage_by_candidate=coverage_by_candidate,
            costs=costs,
            budget=budget,
            k=k,
            candidate_pool_count=len(shortlisted_ids),
            baseline_objective=baseline_objective,
            baseline_total_cost=baseline_total_cost,
            coverage_floor=0.0,
            objective_type="maximize_unique_covered_demand",
            solver_note="Exact maximal coverage search over a baseline shortlist used as a transparent audit benchmark.",
        )
        summary_rows.append(mclp_summary)
        selected_rows.extend(selected_site_rows(scenario_id, MCLP_METHOD_ID, result["selected_candidate_ids"], ranked_rows, costs))

        pulp_result = solve_mclp_pulp([row["candidate_site_id"] for row in ranked_rows], coverage_by_candidate, k=k, costs=costs, budget=budget)
        pulp_summary = result_summary_row(
            scenario_id=scenario_id,
            method_id=PULP_METHOD_ID,
            solver_status=pulp_result["solver_status"],
            selected_candidate_ids=pulp_result["selected_candidate_ids"],
            objective=float(pulp_result["objective_covered_demand_weight"]),
            coverage_by_candidate=coverage_by_candidate,
            costs=costs,
            budget=budget,
            k=k,
            candidate_pool_count=len(ranked_rows),
            baseline_objective=baseline_objective,
            baseline_total_cost=baseline_total_cost,
            coverage_floor=0.0,
            objective_type="maximize_unique_covered_demand",
            solver_note="MILP maximal coverage model solved with PuLP/CBC over the current smoke candidate set.",
        )
        summary_rows.append(pulp_summary)
        selected_rows.extend(selected_site_rows(scenario_id, PULP_METHOD_ID, pulp_result["selected_candidate_ids"], ranked_rows, costs))

        coverage_floor = round(baseline_objective * DEFAULT_COVERAGE_FLOOR_PCT, 3)
        min_cost_result = solve_min_cost_coverage_pulp(
            [row["candidate_site_id"] for row in ranked_rows],
            coverage_by_candidate,
            k=k,
            costs=costs,
            budget=budget,
            coverage_floor=coverage_floor,
        )
        min_cost_summary = result_summary_row(
            scenario_id=scenario_id,
            method_id=MIN_COST_METHOD_ID,
            solver_status=min_cost_result["solver_status"],
            selected_candidate_ids=min_cost_result["selected_candidate_ids"],
            objective=float(min_cost_result["objective_covered_demand_weight"]),
            coverage_by_candidate=coverage_by_candidate,
            costs=costs,
            budget=budget,
            k=k,
            candidate_pool_count=len(ranked_rows),
            baseline_objective=baseline_objective,
            baseline_total_cost=baseline_total_cost,
            coverage_floor=coverage_floor,
            objective_type="minimize_cost_at_coverage_floor",
            solver_note=f"PuLP/CBC min-cost coverage model; floor is {DEFAULT_COVERAGE_FLOOR_PCT:.0%} of baseline top-k covered demand.",
        )
        summary_rows.append(min_cost_summary)
        selected_rows.extend(selected_site_rows(scenario_id, MIN_COST_METHOD_ID, min_cost_result["selected_candidate_ids"], ranked_rows, costs))

    write_csv(summary_target, summary_rows, SUMMARY_FIELDNAMES)
    write_csv(selected_target, selected_rows, SELECTED_FIELDNAMES)
    write_csv(diagnostics_target, constraint_diagnostics_rows(summary_rows), DIAGNOSTIC_FIELDNAMES)
    return [summary_target, selected_target, diagnostics_target]


def build_optimization_constraint_diagnostics_tile_smoke(
    summary_path: Path | None = None,
    output_path: Path | None = None,
) -> Path:
    ensure_project_dirs()
    source = summary_path or MART_DIR / "mart_optimization_results_tile_smoke.csv"
    target = output_path or MART_DIR / "mart_optimization_constraint_diagnostics_tile_smoke.csv"
    summary_rows = read_csv_rows(source)
    return write_csv(target, constraint_diagnostics_rows(summary_rows), DIAGNOSTIC_FIELDNAMES)


def build_optimization_sensitivity_tile_smoke(
    sensitivity_path: Path | None = None,
    coverage_path: Path | None = None,
    scenario_path: Path | None = None,
    output_path: Path | None = None,
    shortlist_size: int = DEFAULT_SENSITIVITY_SHORTLIST_SIZE,
) -> Path:
    ensure_project_dirs()
    sensitivity_rows = read_csv_rows(sensitivity_path or MART_DIR / "mart_baseline_sensitivity_tile_smoke.csv")
    coverage_rows = read_csv_rows(coverage_path or MART_DIR / "fact_candidate_zone_coverage_tile_smoke.csv")
    scenario_rows = read_csv_rows(scenario_path or MART_DIR / "fact_scenario_inputs_tile_smoke.csv")
    target = output_path or MART_DIR / "mart_optimization_sensitivity_tile_smoke.csv"

    coverage_by_scenario = build_coverage_maps(coverage_rows, sensitivity_rows)
    scenario_config = build_scenario_config(scenario_rows)
    grouped = group_by_fields(sensitivity_rows, ["scenario_id", "weight_set_id"])
    result_rows = []

    for (scenario_id, weight_set_id), rows in sorted(grouped.items()):
        config = scenario_config[scenario_id]
        ranked_rows = sorted(rows, key=lambda row: (int(row["rank_within_weight_set_scenario"]), row["candidate_site_id"]))
        candidate_ids = [row["candidate_site_id"] for row in ranked_rows[:shortlist_size]]
        k = min(int(float(config["k"])), len(candidate_ids))
        budget = float(config["b"])
        costs = config["costs"]
        coverage_by_candidate = coverage_by_scenario.get(scenario_id, {})
        result = solve_mclp_pulp(candidate_ids, coverage_by_candidate, k=k, costs=costs, budget=budget)
        result_rows.append(
            sensitivity_summary_row(
                scenario_id=scenario_id,
                weight_set_id=weight_set_id,
                weight_set_name=rows[0].get("weight_set_name", ""),
                selected_candidate_ids=result["selected_candidate_ids"],
                objective=float(result["objective_covered_demand_weight"]),
                solver_status=result["solver_status"],
                coverage_by_candidate=coverage_by_candidate,
                costs=costs,
                budget=budget,
                k=k,
                shortlist_size=shortlist_size,
                candidate_pool_count=len(candidate_ids),
                base_objective=0.0,
                base_selected_candidate_ids=[],
            )
        )

    base_by_scenario = {row["scenario_id"]: row for row in result_rows if row["weight_set_id"] == "weights:base"}
    final_rows = []
    for row in result_rows:
        base = base_by_scenario.get(row["scenario_id"], {})
        final_rows.append(
            {
                **row,
                **optimization_sensitivity_comparison_fields(
                    row,
                    float(base.get("objective_covered_demand_weight") or 0),
                    split_candidate_ids(base.get("selected_candidate_ids", "")),
                ),
            }
        )

    return write_csv(target, final_rows, OPTIMIZATION_SENSITIVITY_FIELDNAMES)


def solve_mclp_exact(
    candidate_ids: list[str],
    coverage_by_candidate: dict[str, dict[str, float]],
    *,
    k: int,
    costs: dict[str, float],
    budget: float,
) -> dict:
    feasible_candidates = [candidate_id for candidate_id in candidate_ids if costs.get(candidate_id, 0.0) <= budget]
    max_size = min(k, len(feasible_candidates))
    best_selection: tuple[str, ...] = ()
    best_objective = -1.0
    best_cost = 0.0
    for size in range(1, max_size + 1):
        for combo in itertools.combinations(feasible_candidates, size):
            total_cost = sum(costs.get(candidate_id, 0.0) for candidate_id in combo)
            if total_cost > budget:
                continue
            objective = coverage_objective(combo, coverage_by_candidate)
            if objective > best_objective or (objective == best_objective and (total_cost < best_cost or combo < best_selection)):
                best_selection = combo
                best_objective = objective
                best_cost = total_cost
    return {
        "solver_status": "optimal_shortlist" if best_selection else "infeasible_or_no_coverage",
        "selected_candidate_ids": list(best_selection),
        "objective_covered_demand_weight": round(max(best_objective, 0.0), 3),
        "selected_candidate_count": len(best_selection),
        "total_candidate_cost": round(best_cost, 2),
    }


def solve_mclp_pulp(
    candidate_ids: list[str],
    coverage_by_candidate: dict[str, dict[str, float]],
    *,
    k: int,
    costs: dict[str, float],
    budget: float,
) -> dict:
    try:
        import pulp
    except ImportError as exc:
        raise RuntimeError("PuLP is required for solve_mclp_pulp; install with `python -m pip install pulp`.") from exc

    zone_weights = zone_weight_map(candidate_ids, coverage_by_candidate)
    if not candidate_ids or not zone_weights:
        return {
            "solver_status": "infeasible_or_no_coverage",
            "selected_candidate_ids": [],
            "objective_covered_demand_weight": 0.0,
            "selected_candidate_count": 0,
            "total_candidate_cost": 0.0,
        }

    model = pulp.LpProblem("chargenet_mclp", pulp.LpMaximize)
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Constructing LpVariable.*", category=DeprecationWarning)
        x = {candidate_id: pulp.LpVariable(f"x_{safe_var_name(candidate_id)}", cat="Binary") for candidate_id in candidate_ids}
        y = {zone_id: pulp.LpVariable(f"y_{safe_var_name(zone_id)}", cat="Binary") for zone_id in zone_weights}

    model += pulp.lpSum(zone_weights[zone_id] * y[zone_id] for zone_id in zone_weights)
    model += pulp.lpSum(x[candidate_id] for candidate_id in candidate_ids) <= k
    model += pulp.lpSum(costs.get(candidate_id, 0.0) * x[candidate_id] for candidate_id in candidate_ids) <= budget
    for zone_id in zone_weights:
        covering_candidates = [candidate_id for candidate_id in candidate_ids if zone_id in coverage_by_candidate.get(candidate_id, {})]
        model += y[zone_id] <= pulp.lpSum(x[candidate_id] for candidate_id in covering_candidates)

    status_code = model.solve(pulp.PULP_CBC_CMD(msg=False))
    status = pulp.LpStatus.get(status_code, str(status_code))
    selected = [candidate_id for candidate_id in candidate_ids if pulp.value(x[candidate_id]) and pulp.value(x[candidate_id]) > 0.5]
    selected.sort(key=lambda candidate_id: candidate_ids.index(candidate_id))
    objective = coverage_objective(selected, coverage_by_candidate)
    return {
        "solver_status": "optimal_milp" if status == "Optimal" else f"milp_{status.lower()}",
        "selected_candidate_ids": selected,
        "objective_covered_demand_weight": round(objective, 3),
        "selected_candidate_count": len(selected),
        "total_candidate_cost": round(sum(costs.get(candidate_id, 0.0) for candidate_id in selected), 2),
    }


def solve_min_cost_coverage_pulp(
    candidate_ids: list[str],
    coverage_by_candidate: dict[str, dict[str, float]],
    *,
    k: int,
    costs: dict[str, float],
    budget: float,
    coverage_floor: float,
) -> dict:
    try:
        import pulp
    except ImportError as exc:
        raise RuntimeError("PuLP is required for solve_min_cost_coverage_pulp; install with `python -m pip install pulp`.") from exc

    zone_weights = zone_weight_map(candidate_ids, coverage_by_candidate)
    if not candidate_ids or not zone_weights or coverage_floor <= 0:
        return {
            "solver_status": "infeasible_or_no_coverage",
            "selected_candidate_ids": [],
            "objective_covered_demand_weight": 0.0,
            "selected_candidate_count": 0,
            "total_candidate_cost": 0.0,
            "coverage_floor_demand_weight": round(max(coverage_floor, 0.0), 3),
        }

    model = pulp.LpProblem("chargenet_min_cost_coverage", pulp.LpMinimize)
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Constructing LpVariable.*", category=DeprecationWarning)
        x = {candidate_id: pulp.LpVariable(f"x_{safe_var_name(candidate_id)}", cat="Binary") for candidate_id in candidate_ids}
        y = {zone_id: pulp.LpVariable(f"y_{safe_var_name(zone_id)}", cat="Binary") for zone_id in zone_weights}

    model += pulp.lpSum(costs.get(candidate_id, 0.0) * x[candidate_id] for candidate_id in candidate_ids)
    model += pulp.lpSum(x[candidate_id] for candidate_id in candidate_ids) <= k
    model += pulp.lpSum(costs.get(candidate_id, 0.0) * x[candidate_id] for candidate_id in candidate_ids) <= budget
    model += pulp.lpSum(zone_weights[zone_id] * y[zone_id] for zone_id in zone_weights) >= coverage_floor
    for zone_id in zone_weights:
        covering_candidates = [candidate_id for candidate_id in candidate_ids if zone_id in coverage_by_candidate.get(candidate_id, {})]
        model += y[zone_id] <= pulp.lpSum(x[candidate_id] for candidate_id in covering_candidates)

    status_code = model.solve(pulp.PULP_CBC_CMD(msg=False))
    status = pulp.LpStatus.get(status_code, str(status_code))
    if status != "Optimal":
        return {
            "solver_status": f"milp_{status.lower()}",
            "selected_candidate_ids": [],
            "objective_covered_demand_weight": 0.0,
            "selected_candidate_count": 0,
            "total_candidate_cost": 0.0,
            "coverage_floor_demand_weight": round(coverage_floor, 3),
        }

    selected = [candidate_id for candidate_id in candidate_ids if pulp.value(x[candidate_id]) and pulp.value(x[candidate_id]) > 0.5]
    selected.sort(key=lambda candidate_id: candidate_ids.index(candidate_id))
    objective = coverage_objective(selected, coverage_by_candidate)
    return {
        "solver_status": "optimal_min_cost",
        "selected_candidate_ids": selected,
        "objective_covered_demand_weight": round(objective, 3),
        "selected_candidate_count": len(selected),
        "total_candidate_cost": round(sum(costs.get(candidate_id, 0.0) for candidate_id in selected), 2),
        "coverage_floor_demand_weight": round(coverage_floor, 3),
    }


def zone_weight_map(candidate_ids: list[str], coverage_by_candidate: dict[str, dict[str, float]]) -> dict[str, float]:
    weights: dict[str, float] = {}
    for candidate_id in candidate_ids:
        for zone_id, demand_weight in coverage_by_candidate.get(candidate_id, {}).items():
            weights[zone_id] = max(weights.get(zone_id, 0.0), float(demand_weight))
    return weights


def safe_var_name(value: str) -> str:
    return "".join(character if character.isalnum() else "_" for character in value)


def coverage_objective(candidate_ids: list[str] | tuple[str, ...], coverage_by_candidate: dict[str, dict[str, float]]) -> float:
    covered_by_zone: dict[str, float] = {}
    for candidate_id in candidate_ids:
        for demand_zone_id, demand_weight in coverage_by_candidate.get(candidate_id, {}).items():
            covered_by_zone[demand_zone_id] = max(covered_by_zone.get(demand_zone_id, 0.0), float(demand_weight))
    return round(sum(covered_by_zone.values()), 3)


def build_coverage_maps(coverage_rows: list[dict], baseline_rows: list[dict]) -> dict[str, dict[str, dict[str, float]]]:
    scenario_by_radius = {row["coverage_radius_km"]: row["scenario_id"] for row in baseline_rows}
    maps: dict[str, dict[str, dict[str, float]]] = {}
    for row in coverage_rows:
        scenario_id = scenario_by_radius.get(row["coverage_radius_km"])
        if not scenario_id or int(row.get("pair_eligible_flag") or 0) != 1:
            continue
        maps.setdefault(scenario_id, {}).setdefault(row["candidate_site_id"], {})[row["demand_zone_id"]] = float(row.get("demand_weight_contribution") or 0)
    return maps


def build_scenario_config(rows: list[dict]) -> dict[str, dict]:
    configs: dict[str, dict] = {}
    for row in rows:
        scenario_id = row["scenario_id"]
        config = configs.setdefault(scenario_id, {"b": row.get("b", "0"), "k": row.get("k", "0"), "costs": {}})
        if row["entity_type"] == "candidate_site":
            config["costs"][row["entity_id"]] = float(row.get("c_j") or 0)
    return configs


def select_baseline_topk(rows: list[dict], costs: dict[str, float], budget: float, k: int) -> list[str]:
    selected = []
    total_cost = 0.0
    for row in rows:
        candidate_id = row["candidate_site_id"]
        cost = costs.get(candidate_id, 0.0)
        if len(selected) >= k:
            break
        if total_cost + cost > budget:
            continue
        selected.append(candidate_id)
        total_cost += cost
    return selected


def result_summary_row(
    *,
    scenario_id: str,
    method_id: str,
    solver_status: str,
    selected_candidate_ids: list[str],
    objective: float,
    coverage_by_candidate: dict[str, dict[str, float]],
    costs: dict[str, float],
    budget: float,
    k: int,
    candidate_pool_count: int,
    baseline_objective: float,
    baseline_total_cost: float,
    coverage_floor: float,
    objective_type: str,
    solver_note: str,
) -> dict:
    covered_zone_count = len({zone_id for candidate_id in selected_candidate_ids for zone_id in coverage_by_candidate.get(candidate_id, {})})
    improvement = objective - baseline_objective
    improvement_pct = improvement / baseline_objective if baseline_objective else 0.0
    total_cost = sum(costs.get(candidate_id, 0.0) for candidate_id in selected_candidate_ids)
    cost_saving = baseline_total_cost - total_cost
    cost_saving_pct = cost_saving / baseline_total_cost if baseline_total_cost else 0.0
    return {
        "scenario_method_id": scenario_method_id(scenario_id, method_id),
        "scenario_id": scenario_id,
        "method_id": method_id,
        "objective_type": objective_type,
        "solver_status": solver_status,
        "selected_candidate_count": len(selected_candidate_ids),
        "selected_candidate_ids": "|".join(selected_candidate_ids),
        "objective_covered_demand_weight": round(objective, 3),
        "coverage_floor_demand_weight": round(coverage_floor, 3),
        "coverage_floor_pct_of_baseline": round(coverage_floor / baseline_objective, 6) if baseline_objective else 0.0,
        "covered_zone_count": covered_zone_count,
        "total_candidate_cost": round(total_cost, 2),
        "budget": round(budget, 2),
        "k": k,
        "candidate_pool_count": candidate_pool_count,
        "improvement_vs_baseline_demand_weight": round(improvement, 3),
        "improvement_vs_baseline_pct": round(improvement_pct, 6),
        "cost_saving_vs_baseline": round(cost_saving, 2),
        "cost_saving_vs_baseline_pct": round(cost_saving_pct, 6),
        "solver_note": solver_note,
        "allowed_use_note": "Optimization checkpoint for diligence prioritization only; smoke scope is not a full pilot rollout recommendation.",
        "proxy_assumption_label": "tile_smoke_optimization_not_investment_grade",
    }


def constraint_diagnostics_rows(summary_rows: list[dict]) -> list[dict]:
    rows = []
    for summary in summary_rows:
        scenario_id = summary["scenario_id"]
        method_id = summary["method_id"]
        summary_scenario_method_id = summary.get("scenario_method_id") or scenario_method_id(scenario_id, method_id)
        budget = float(summary.get("budget") or 0)
        total_cost = float(summary.get("total_candidate_cost") or 0)
        k = float(summary.get("k") or 0)
        selected_count = float(summary.get("selected_candidate_count") or 0)
        objective = float(summary.get("objective_covered_demand_weight") or 0)
        coverage_floor = float(summary.get("coverage_floor_demand_weight") or 0)
        solver_status = summary.get("solver_status", "")

        rows.append(
            numeric_constraint_row(
                scenario_id=scenario_id,
                method_id=method_id,
                scenario_method_id=summary_scenario_method_id,
                constraint_name="budget",
                lhs=total_cost,
                operator="<=",
                rhs=budget,
                slack=budget - total_cost,
                pass_note="Selected candidate cost is within the scenario budget.",
                fail_note="Selected candidate cost exceeds the scenario budget.",
            )
        )
        rows.append(
            numeric_constraint_row(
                scenario_id=scenario_id,
                method_id=method_id,
                scenario_method_id=summary_scenario_method_id,
                constraint_name="site_count",
                lhs=selected_count,
                operator="<=",
                rhs=k,
                slack=k - selected_count,
                pass_note="Selected candidate count is within the scenario k limit.",
                fail_note="Selected candidate count exceeds the scenario k limit.",
            )
        )
        rows.append(
            {
                "scenario_method_id": summary_scenario_method_id,
                "scenario_id": scenario_id,
                "method_id": method_id,
                "constraint_name": "solver_status",
                "constraint_status": "pass" if solver_status in ACCEPTED_SOLVER_STATUSES else "fail",
                "lhs_value": solver_status,
                "operator": "in",
                "rhs_value": "|".join(sorted(ACCEPTED_SOLVER_STATUSES)),
                "slack_value": "",
                "diagnostic_note": (
                    f"{solver_status} is an accepted feasible status."
                    if solver_status in ACCEPTED_SOLVER_STATUSES
                    else f"{solver_status} is not an accepted feasible status."
                ),
                "allowed_use_note": diagnostic_allowed_use_note(),
                "proxy_assumption_label": diagnostic_proxy_assumption_label(),
            }
        )
        rows.append(
            numeric_constraint_row(
                scenario_id=scenario_id,
                method_id=method_id,
                scenario_method_id=summary_scenario_method_id,
                constraint_name="objective_nonnegative",
                lhs=objective,
                operator=">=",
                rhs=0.0,
                slack=objective,
                pass_note="Objective value is nonnegative.",
                fail_note="Objective value is negative and should be investigated.",
            )
        )
        rows.append(
            numeric_constraint_row(
                scenario_id=scenario_id,
                method_id=method_id,
                scenario_method_id=summary_scenario_method_id,
                constraint_name="coverage_floor",
                lhs=objective,
                operator=">=",
                rhs=coverage_floor,
                slack=objective - coverage_floor,
                pass_note="Covered demand meets the method coverage floor.",
                fail_note="Covered demand is below the method coverage floor.",
            )
        )
    return rows


def numeric_constraint_row(
    *,
    scenario_method_id: str,
    scenario_id: str,
    method_id: str,
    constraint_name: str,
    lhs: float,
    operator: str,
    rhs: float,
    slack: float,
    pass_note: str,
    fail_note: str,
) -> dict:
    passed = slack >= -0.000001
    return {
        "scenario_method_id": scenario_method_id,
        "scenario_id": scenario_id,
        "method_id": method_id,
        "constraint_name": constraint_name,
        "constraint_status": "pass" if passed else "fail",
        "lhs_value": format_numeric(lhs),
        "operator": operator,
        "rhs_value": format_numeric(rhs),
        "slack_value": format_numeric(slack),
        "diagnostic_note": pass_note if passed else fail_note,
        "allowed_use_note": diagnostic_allowed_use_note(),
        "proxy_assumption_label": diagnostic_proxy_assumption_label(),
    }


def format_numeric(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")


def diagnostic_allowed_use_note() -> str:
    return "Constraint diagnostics for optimization QA only; smoke scope is not a full pilot rollout recommendation."


def diagnostic_proxy_assumption_label() -> str:
    return "tile_smoke_optimization_constraint_diagnostics_not_investment_grade"


def scenario_method_id(scenario_id: str, method_id: str) -> str:
    return f"{scenario_id}|{method_id}"


def selected_site_rows(
    scenario_id: str,
    method_id: str,
    selected_candidate_ids: list[str],
    ranked_rows: list[dict],
    costs: dict[str, float],
) -> list[dict]:
    baseline_by_candidate = {row["candidate_site_id"]: row for row in ranked_rows}
    rows = []
    ordered_ids = sorted(selected_candidate_ids, key=lambda candidate_id: int(baseline_by_candidate.get(candidate_id, {}).get("rank_within_scenario") or 999999))
    for selection_rank, candidate_id in enumerate(ordered_ids, start=1):
        baseline = baseline_by_candidate.get(candidate_id, {})
        rows.append(
            {
                "scenario_method_id": scenario_method_id(scenario_id, method_id),
                "scenario_id": scenario_id,
                "method_id": method_id,
                "selection_rank": selection_rank,
                "candidate_site_id": candidate_id,
                "country_code": baseline.get("country_code", ""),
                "nuts_id": baseline.get("nuts_id", ""),
                "site_type": baseline.get("site_type", ""),
                "baseline_rank_within_scenario": baseline.get("rank_within_scenario", ""),
                "baseline_score": baseline.get("baseline_score", ""),
                "c_j": costs.get(candidate_id, ""),
                "allowed_use_note": "Selected by optimization checkpoint for diligence prioritization only.",
                "proxy_assumption_label": "tile_smoke_optimization_selected_site_not_investment_grade",
            }
        )
    return rows


def sensitivity_summary_row(
    *,
    scenario_id: str,
    weight_set_id: str,
    weight_set_name: str,
    selected_candidate_ids: list[str],
    objective: float,
    solver_status: str,
    coverage_by_candidate: dict[str, dict[str, float]],
    costs: dict[str, float],
    budget: float,
    k: int,
    shortlist_size: int,
    candidate_pool_count: int,
    base_objective: float,
    base_selected_candidate_ids: list[str],
) -> dict:
    row = {
        "sensitivity_run_id": sensitivity_run_id(scenario_id, weight_set_id),
        "scenario_id": scenario_id,
        "weight_set_id": weight_set_id,
        "weight_set_name": weight_set_name,
        "method_id": SENSITIVITY_MCLP_METHOD_ID,
        "solver_status": solver_status,
        "shortlist_size": shortlist_size,
        "candidate_pool_count": candidate_pool_count,
        "selected_candidate_count": len(selected_candidate_ids),
        "selected_candidate_ids": "|".join(selected_candidate_ids),
        "objective_covered_demand_weight": round(objective, 3),
        "covered_zone_count": len({zone_id for candidate_id in selected_candidate_ids for zone_id in coverage_by_candidate.get(candidate_id, {})}),
        "total_candidate_cost": round(sum(costs.get(candidate_id, 0.0) for candidate_id in selected_candidate_ids), 2),
        "budget": round(budget, 2),
        "k": k,
        "allowed_use_note": "Optimization sensitivity over weight-set shortlists for diligence prioritization only.",
        "proxy_assumption_label": "tile_smoke_optimization_sensitivity_not_investment_grade",
    }
    row.update(optimization_sensitivity_comparison_fields(row, base_objective, base_selected_candidate_ids))
    return row


def optimization_sensitivity_comparison_fields(row: dict, base_objective: float, base_selected_candidate_ids: list[str]) -> dict:
    objective = float(row.get("objective_covered_demand_weight") or 0)
    selected_ids = split_candidate_ids(row.get("selected_candidate_ids", ""))
    selected_set = set(selected_ids)
    base_selected_set = set(base_selected_candidate_ids)
    overlap = len(selected_set & base_selected_set)
    return {
        "base_weight_set_objective": round(base_objective, 3),
        "objective_delta_vs_base_weight_set": round(objective - base_objective, 3),
        "objective_delta_vs_base_weight_set_pct": round((objective - base_objective) / base_objective, 6) if base_objective else 0.0,
        "overlap_with_base_solution_count": overlap,
        "overlap_with_base_solution_pct": round(overlap / len(base_selected_set), 6) if base_selected_set else 0.0,
    }


def split_candidate_ids(value: str) -> list[str]:
    if not value:
        return []
    return [candidate_id for candidate_id in value.split("|") if candidate_id]


def sensitivity_run_id(scenario_id: str, weight_set_id: str) -> str:
    return f"{scenario_id}|{weight_set_id}|{SENSITIVITY_MCLP_METHOD_ID}"


def group_rows(rows: list[dict], field: str) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row[field], []).append(row)
    return grouped


def group_by_fields(rows: list[dict], fields: list[str]) -> dict[tuple[str, ...], list[dict]]:
    grouped: dict[tuple[str, ...], list[dict]] = {}
    for row in rows:
        grouped.setdefault(tuple(row[field] for field in fields), []).append(row)
    return grouped


def read_csv_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> Path:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


SUMMARY_FIELDNAMES = [
    "scenario_method_id",
    "scenario_id",
    "method_id",
    "objective_type",
    "solver_status",
    "selected_candidate_count",
    "selected_candidate_ids",
    "objective_covered_demand_weight",
    "coverage_floor_demand_weight",
    "coverage_floor_pct_of_baseline",
    "covered_zone_count",
    "total_candidate_cost",
    "budget",
    "k",
    "candidate_pool_count",
    "improvement_vs_baseline_demand_weight",
    "improvement_vs_baseline_pct",
    "cost_saving_vs_baseline",
    "cost_saving_vs_baseline_pct",
    "solver_note",
    "allowed_use_note",
    "proxy_assumption_label",
]

SELECTED_FIELDNAMES = [
    "scenario_method_id",
    "scenario_id",
    "method_id",
    "selection_rank",
    "candidate_site_id",
    "country_code",
    "nuts_id",
    "site_type",
    "baseline_rank_within_scenario",
    "baseline_score",
    "c_j",
    "allowed_use_note",
    "proxy_assumption_label",
]

DIAGNOSTIC_FIELDNAMES = [
    "scenario_method_id",
    "scenario_id",
    "method_id",
    "constraint_name",
    "constraint_status",
    "lhs_value",
    "operator",
    "rhs_value",
    "slack_value",
    "diagnostic_note",
    "allowed_use_note",
    "proxy_assumption_label",
]

OPTIMIZATION_SENSITIVITY_FIELDNAMES = [
    "sensitivity_run_id",
    "scenario_id",
    "weight_set_id",
    "weight_set_name",
    "method_id",
    "solver_status",
    "shortlist_size",
    "candidate_pool_count",
    "selected_candidate_count",
    "selected_candidate_ids",
    "objective_covered_demand_weight",
    "base_weight_set_objective",
    "objective_delta_vs_base_weight_set",
    "objective_delta_vs_base_weight_set_pct",
    "overlap_with_base_solution_count",
    "overlap_with_base_solution_pct",
    "covered_zone_count",
    "total_candidate_cost",
    "budget",
    "k",
    "allowed_use_note",
    "proxy_assumption_label",
]
