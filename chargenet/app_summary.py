from __future__ import annotations

from collections import Counter
from math import isfinite


def build_recruiter_kpis(
    *,
    snapshot_rows: list[dict],
    optimization_rows: list[dict],
    release_gate_rows: list[dict],
    demand_zone_count: int,
) -> list[dict]:
    release = release_gate_headline(release_gate_rows)
    return [
        {
            "key": "scope",
            "label": "Pilot scope",
            "value": "4 countries",
            "caption": "Belgium, Germany, France, Netherlands",
            "status": "neutral",
        },
        {
            "key": "demand_zones",
            "label": "Regions analyzed",
            "value": format_int(demand_zone_count),
            "caption": "Public regional demand areas in the pilot scope",
            "status": "neutral",
        },
        {
            "key": "candidate_proxies",
            "label": "Potential locations screened",
            "value": format_int(metric_value(snapshot_rows, "candidate_site_count")),
            "caption": "Public map-based candidate proxies in the current capped snapshot",
            "status": "neutral",
        },
        {
            "key": "milp_uplift",
            "label": "Coverage improvement",
            "value": format_optional_percent(base_milp_uplift(optimization_rows)),
            "caption": base_milp_caption(optimization_rows),
            "status": "pass" if base_milp_uplift(optimization_rows) is not None else "fail",
        },
        {
            "key": "release_gate",
            "label": "Release gate",
            "value": release["value"],
            "caption": release["caption"],
            "status": release["status"],
        },
    ]


def build_top_candidate_insights(rows: list[dict]) -> list[dict]:
    if not rows:
        return [
            insight_row("top_country", "Top country", "n/a", "No candidates loaded"),
            insight_row("top_site_type", "Top site type", "n/a", "No candidates loaded"),
            insight_row("best_score", "Best baseline score", "0.000", "No candidates loaded"),
            insight_row("largest_demand", "Largest covered demand", "0", "No candidates loaded"),
        ]
    country_counts = Counter(str(row.get("country_code", "")) for row in rows)
    site_type_counts = Counter(str(row.get("site_type", "")) for row in rows)
    top_country, top_country_count = country_counts.most_common(1)[0]
    top_site_type, top_site_type_count = site_type_counts.most_common(1)[0]
    best_score = max(numeric(row.get("baseline_score")) for row in rows)
    largest_demand = max(numeric(row.get("covered_demand_weight")) for row in rows)
    total = len(rows)
    return [
        insight_row("top_country", "Top country", top_country, f"{top_country_count} of {total} visible candidates"),
        insight_row("top_site_type", "Top site type", top_site_type, f"{top_site_type_count} of {total} visible candidates"),
        insight_row("best_score", "Best baseline score", f"{best_score:.3f}", "Highest weighted shortlist score"),
        insight_row("largest_demand", "Largest covered demand", format_int(largest_demand), "Largest single-candidate demand proxy"),
    ]


def build_optimization_takeaways(rows: list[dict], scenario_id: str) -> list[dict]:
    scenario_rows = [row for row in rows if row.get("scenario_id") == scenario_id]
    baseline = method_row(scenario_rows, "method:baseline-topk")
    milp = method_row(scenario_rows, "method:mclp-pulp-cbc")
    min_cost = method_row(scenario_rows, "method:min-cost-coverage-pulp")
    baseline_objective = numeric(baseline.get("objective_covered_demand_weight"))
    baseline_cost = numeric(baseline.get("total_candidate_cost"))
    milp_objective = numeric(milp.get("objective_covered_demand_weight"))
    milp_cost = numeric(milp.get("total_candidate_cost"))
    coverage_uplift = ((milp_objective - baseline_objective) / baseline_objective) if baseline_objective else 0.0
    milp_cost_delta = ((milp_cost - baseline_cost) / baseline_cost) if baseline_cost else 0.0
    return [
        insight_row("coverage_uplift", "Coverage uplift", format_percent(coverage_uplift), "MILP max-coverage vs baseline top-k"),
        insight_row("milp_cost_delta", "Cost delta", format_percent(milp_cost_delta), "Proxy cost movement vs baseline"),
        insight_row("min_cost_sites", "90% floor sites", format_int(numeric(min_cost.get("selected_candidate_count"))), "Sites needed to hit 90% baseline coverage floor"),
        insight_row(
            "zone_expansion",
            "Covered zones",
            f"{format_int(numeric(baseline.get('covered_zone_count')))} -> {format_int(numeric(milp.get('covered_zone_count')))}",
            "Baseline top-k to MILP max-coverage",
        ),
    ]


def build_metric_glossary() -> list[dict]:
    public_proxy_caveat = "Public proxy metric; not investment-grade and not a rollout recommendation."
    return [
        {
            "metric_key": "coverage_uplift",
            "metric_label": "Coverage uplift",
            "plain_english": "How much more demand proxy the MILP shortlist covers compared with the simple baseline top-k shortlist.",
            "why_it_matters": "Shows whether optimization adds business value beyond ranking candidates one by one.",
            "caveat": public_proxy_caveat,
        },
        {
            "metric_key": "min_cost_saving",
            "metric_label": "Min-cost saving",
            "plain_english": "How much lower the proxy cost can be while still meeting a target coverage floor.",
            "why_it_matters": "Frames a cost-control question instead of only asking for maximum coverage.",
            "caveat": public_proxy_caveat,
        },
        {
            "metric_key": "dominant_country_share",
            "metric_label": "Dominant country share",
            "plain_english": "The share of selected sites concentrated in the most represented pilot country.",
            "why_it_matters": "Flags whether a solution is geographically balanced or overly concentrated.",
            "caveat": "Public proxy metric across Belgium, Germany, France, and Netherlands only; not investment-grade.",
        },
        {
            "metric_key": "proxy_cost",
            "metric_label": "Proxy cost",
            "plain_english": "A relative proxy cost built from public assumptions, not vendor quotes or negotiated CAPEX.",
            "why_it_matters": "Allows directional scenario comparison while making the cost limitation explicit.",
            "caveat": "Public proxy cost; excludes grid capacity, permits, land availability, and negotiated supplier pricing.",
        },
        {
            "metric_key": "release_gate",
            "metric_label": "Release gate",
            "plain_english": "A checklist result confirming that expected data files, public claims, and app smoke tests pass.",
            "why_it_matters": "Keeps the portfolio demo reproducible instead of relying on manual screenshots.",
            "caveat": "Quality gate for this demo pipeline; not a guarantee that the public source data is complete.",
        },
    ]


def build_decision_flags(rows: list[dict]) -> list[dict]:
    flags = []
    for row in rows:
        uplift = optional_numeric(row.get("mclp_coverage_uplift_pct"))
        saving = optional_numeric(row.get("min_cost_saving_pct"))
        country_share = optional_numeric(row.get("dominant_coverage_country_share"))
        primary_flag = decision_primary_flag(uplift, saving)
        concentration_note = (
            f" Review country concentration in {row.get('dominant_coverage_country_code') or 'the leading country'}."
            if country_share is not None and country_share >= 0.75
            else " Country concentration does not dominate this checkpoint."
        )
        flags.append(
            {
                "scenario_id": str(row.get("scenario_id") or "n/a"),
                "primary_flag": primary_flag,
                "coverage_uplift": format_optional_percent(uplift),
                "min_cost_saving": format_optional_percent(saving),
                "dominant_country_share": format_optional_percent(country_share),
                "review_prompt": f"{decision_review_prompt(primary_flag)}{concentration_note}",
                "allowed_use_note": "Use as a public-proxy diligence prompt only; not a rollout recommendation.",
            }
        )
    return flags


def build_country_concentration_guardrails(rows: list[dict]) -> list[dict]:
    grouped: dict[tuple[str, str], dict] = {}
    for row in rows:
        key = (str(row.get("scenario_id") or "n/a"), str(row.get("method_id") or "n/a"))
        share = optional_numeric(row.get("covered_demand_share_of_method"))
        if share is None:
            continue
        current = grouped.get(key)
        if current is None or share > current["dominant_share"]:
            grouped[key] = {
                "scenario_id": key[0],
                "method_id": key[1],
                "dominant_country": str(row.get("country_code") or "n/a"),
                "dominant_share": share,
            }
    guardrails = []
    for record in grouped.values():
        status = "Review" if record["dominant_share"] >= 0.75 else "Pass"
        guardrails.append(
            {
                "scenario_id": record["scenario_id"],
                "method_id": record["method_id"],
                "dominant_country": record["dominant_country"],
                "dominant_country_share": format_percent(record["dominant_share"]),
                "concentration_status": status,
                "review_prompt": country_concentration_prompt(status),
            }
        )
    return sorted(guardrails, key=lambda row: (row["scenario_id"], row["method_id"]))


def country_concentration_prompt(status: str) -> str:
    if status == "Review":
        return "High country concentration is a warning-grade review prompt, not a failure or rollout recommendation."
    return "No high concentration warning for this method; still review business-fit before interpreting the shortlist."


def decision_primary_flag(coverage_uplift: float | None, min_cost_saving: float | None) -> str:
    if coverage_uplift is None or min_cost_saving is None:
        return "Metrics unavailable"
    if coverage_uplift >= 0.15:
        return "Coverage upside"
    if min_cost_saving >= 0.15:
        return "Cost-pressure case"
    if coverage_uplift > 0 or min_cost_saving > 0:
        return "Marginal optimization case"
    return "Baseline parity"


def decision_review_prompt(primary_flag: str) -> str:
    if primary_flag == "Metrics unavailable":
        return "Confirm that the method-comparison mart has complete metric fields before interpreting this scenario."
    if primary_flag == "Coverage upside":
        return "Inspect which extra demand zones drive the MILP uplift before narrowing candidates."
    if primary_flag == "Cost-pressure case":
        return "Check whether the coverage floor is acceptable before using the lower-cost shortlist."
    if primary_flag == "Marginal optimization case":
        return "Treat the optimization as a sensitivity check and compare against baseline simplicity."
    return "Keep baseline as the benchmark unless new constraints justify optimization complexity."


def build_scenario_cards(optimization_rows: list[dict], business_rows: list[dict]) -> list[dict]:
    business_by_scenario = {}
    for row in business_rows:
        scenario_id = row.get("scenario_id")
        if scenario_id and scenario_id not in business_by_scenario:
            business_by_scenario[scenario_id] = row

    cards = []
    for scenario_id in sorted({str(row.get("scenario_id", "")) for row in optimization_rows if row.get("scenario_id")}):
        scenario_rows = [row for row in optimization_rows if row.get("scenario_id") == scenario_id]
        best = max(scenario_rows, key=lambda row: numeric(row.get("objective_covered_demand_weight")), default={})
        business = business_by_scenario.get(scenario_id, {})
        cards.append(
            {
                "scenario_id": scenario_id,
                "business_scenario_name": str(business.get("business_scenario_name") or scenario_id.replace("scenario:", "").replace("-", " ").title()),
                "business_question": str(business.get("business_question") or "Compare baseline and optimization outputs for this scenario."),
                "best_method": str(best.get("method_label") or best.get("method_id") or "n/a"),
                "solver_status": str(best.get("solver_status") or "n/a"),
                "covered_demand": format_int(numeric(best.get("objective_covered_demand_weight"))),
                "selected_candidates": format_int(numeric(best.get("selected_candidate_count"))),
                "cost_proxy": format_int(numeric(best.get("total_candidate_cost"))),
                "stability_signal": str(business.get("solution_stability_signal") or "not reported"),
                "decision_readout": str(business.get("decision_readout") or "not reported"),
                "recommended_next_action": str(business.get("recommended_next_action") or "not reported"),
            }
        )
    return cards


def build_candidate_drilldown(candidate_site_id: str, selected_rows: list[dict], trace_rows: list[dict]) -> dict:
    selected = next((row for row in selected_rows if row.get("candidate_site_id") == candidate_site_id), {})
    trace = next((row for row in trace_rows if row.get("candidate_site_id") == candidate_site_id), {})
    zones = str(trace.get("coverage_trace_zone_ids") or "")
    zone_list = [zone for zone in zones.split("|") if zone]
    return {
        "candidate_site_id": candidate_site_id,
        "selection_rank": format_int(numeric(selected.get("selection_rank"))),
        "source_record_id": str(trace.get("source_record_id") or "n/a"),
        "tile_job_id": str(trace.get("tile_job_id") or "n/a"),
        "country_code": str(selected.get("country_code") or trace.get("country_code") or "n/a"),
        "nuts_id": str(selected.get("nuts_id") or trace.get("nuts_id") or "n/a"),
        "site_type": str(selected.get("site_type") or trace.get("site_type") or "n/a"),
        "baseline_rank": format_int(numeric(selected.get("baseline_rank_within_scenario") or trace.get("baseline_rank_within_scenario"))),
        "baseline_score": f"{numeric(selected.get('baseline_score') or trace.get('baseline_score')):.3f}",
        "scenario_candidate_cost": format_int(numeric(selected.get("c_j") or trace.get("scenario_candidate_cost"))),
        "covered_zone_count": format_int(numeric(trace.get("covered_zone_count"))),
        "covered_demand_weight": format_int(numeric(trace.get("covered_demand_weight"))),
        "top_covered_zones": ", ".join(zone_list[:5]) if zone_list else "n/a",
        "raw_tag_keys": str(trace.get("raw_tag_keys") or "n/a"),
    }


def build_weight_set_comparison(rows: list[dict], weight_a: str, weight_b: str, *, limit: int = 25) -> list[dict]:
    paired: dict[str, dict] = {}
    for row in rows:
        weight_name = row.get("weight_set_name")
        if weight_name not in {weight_a, weight_b}:
            continue
        candidate_id = str(row.get("candidate_site_id") or "")
        if not candidate_id:
            continue
        record = paired.setdefault(
            candidate_id,
            {
                "candidate_site_id": candidate_id,
                "country_code": str(row.get("country_code") or ""),
                "nuts_id": str(row.get("nuts_id") or ""),
                "site_type": str(row.get("site_type") or ""),
                "rank_a": None,
                "rank_b": None,
                "weighted_score_a": None,
                "weighted_score_b": None,
            },
        )
        rank = int(numeric(row.get("rank_within_weight_set_scenario"))) or None
        score = numeric(row.get("weighted_score"))
        if weight_name == weight_a:
            record["rank_a"] = rank
            record["weighted_score_a"] = score
        else:
            record["rank_b"] = rank
            record["weighted_score_b"] = score

    comparison = []
    for record in paired.values():
        rank_a = record["rank_a"]
        rank_b = record["rank_b"]
        record["rank_shift_b_vs_a"] = (rank_b - rank_a) if rank_a is not None and rank_b is not None else None
        comparison.append(record)

    return sorted(
        comparison,
        key=lambda row: min([rank for rank in [row["rank_a"], row["rank_b"]] if rank is not None] or [999999]),
    )[:limit]


def release_gate_headline(rows: list[dict]) -> dict:
    total = len(rows)
    passed = sum(1 for row in rows if row.get("gate_status") == "pass")
    blockers = total - passed
    status = "pass" if total and blockers == 0 else "fail"
    if not total:
        return {"value": "0/0", "caption": "Release gate report not available", "status": "fail"}
    caption = "All release gates pass" if blockers == 0 else f"{blockers} blocker(s) need review"
    return {"value": f"{passed}/{total}", "caption": caption, "status": status}


def base_milp_uplift(rows: list[dict]) -> float | None:
    for row in rows:
        if row.get("scenario_id") == "scenario:radius-base" and row.get("method_id") == "method:mclp-pulp-cbc":
            if row.get("solver_status") != "optimal_milp":
                return None
            return numeric(row.get("improvement_vs_baseline_pct"))
    return None


def base_milp_caption(rows: list[dict]) -> str:
    return (
        "Max-coverage result vs simple baseline ranking"
        if base_milp_uplift(rows) is not None
        else "No optimal MILP result available for the base scenario"
    )


def method_row(rows: list[dict], method_id: str) -> dict:
    for row in rows:
        if row.get("method_id") == method_id:
            return row
    return {}


def insight_row(key: str, label: str, value: str, caption: str) -> dict:
    return {"key": key, "label": label, "value": value, "caption": caption}


def metric_value(rows: list[dict], metric_name: str) -> float:
    for row in rows:
        if row.get("metric_name") == metric_name:
            return numeric(row.get("metric_value"))
    return 0.0


def numeric(value: object) -> float:
    try:
        result = float(value or 0)
    except (TypeError, ValueError):
        return 0.0
    return result if isfinite(result) else 0.0


def optional_numeric(value: object) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if isfinite(result) else None


def format_int(value: float | int) -> str:
    return f"{int(round(float(value))):,}"


def format_percent(value: float) -> str:
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.1%}"


def format_optional_percent(value: float | None) -> str:
    if value is None:
        return "n/a"
    return format_percent(value)
