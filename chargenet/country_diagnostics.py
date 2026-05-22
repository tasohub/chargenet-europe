from __future__ import annotations

import csv
from pathlib import Path

from .paths import MART_DIR, ensure_project_dirs


CONCENTRATION_WARNING_THRESHOLD = 0.75


def build_optimization_country_diagnostics_tile_smoke(
    *,
    selected_path: Path | None = None,
    zone_trace_path: Path | None = None,
    output_path: Path | None = None,
) -> Path:
    ensure_project_dirs()
    selected_rows = read_csv_rows(selected_path or MART_DIR / "fact_optimization_selected_sites_tile_smoke.csv")
    zone_rows = read_csv_rows(zone_trace_path or MART_DIR / "fact_optimization_zone_trace_tile_smoke.csv")
    target = output_path or MART_DIR / "mart_optimization_country_diagnostics_tile_smoke.csv"

    selected_groups = group_selected_by_method_country(selected_rows)
    coverage_groups = group_unique_zone_coverage_by_method_country(zone_rows)
    method_totals = method_total_coverage(coverage_groups)
    cost_totals = method_total_cost(selected_groups)
    output_rows = []

    method_country_keys = sorted(set(selected_groups) | set(coverage_groups))
    for scenario_id, method_id, country_code in method_country_keys:
        scenario_method_id = scenario_method_key(scenario_id, method_id)
        selected = selected_groups.get((scenario_id, method_id, country_code), {"selected_candidate_count": 0, "total_candidate_cost": 0.0})
        coverage = coverage_groups.get((scenario_id, method_id, country_code), {"covered_zone_count": 0, "covered_demand_weight": 0.0})
        total_coverage = method_totals.get((scenario_id, method_id), 0.0)
        total_cost = cost_totals.get((scenario_id, method_id), 0.0)
        coverage_share = coverage["covered_demand_weight"] / total_coverage if total_coverage else 0.0
        output_rows.append(
            {
                "scenario_method_country_id": f"{scenario_method_id}|{country_code}",
                "scenario_method_id": scenario_method_id,
                "scenario_id": scenario_id,
                "method_id": method_id,
                "country_code": country_code,
                "selected_candidate_count": selected["selected_candidate_count"],
                "covered_zone_count": coverage["covered_zone_count"],
                "covered_demand_weight": format_numeric(coverage["covered_demand_weight"]),
                "covered_demand_share_of_method": format_numeric(coverage_share),
                "total_candidate_cost": format_numeric(selected["total_candidate_cost"]),
                "candidate_cost_share_of_method": format_numeric(selected["total_candidate_cost"] / total_cost if total_cost else 0.0),
                "concentration_status": concentration_status(coverage_share),
                "concentration_warning_threshold": format_numeric(CONCENTRATION_WARNING_THRESHOLD),
                "concentration_review_note": concentration_review_note(coverage_share),
                "diagnostic_note": country_diagnostic_note(coverage["covered_demand_weight"], total_coverage),
                "allowed_use_note": "Country diagnostic for portfolio-balance review only; not a fairness, demand, or rollout recommendation.",
                "proxy_assumption_label": "tile_smoke_optimization_country_diagnostics_not_investment_grade",
            }
        )

    return write_csv(target, output_rows, COUNTRY_DIAGNOSTIC_FIELDNAMES)


def group_selected_by_method_country(rows: list[dict]) -> dict[tuple[str, str, str], dict]:
    grouped: dict[tuple[str, str, str], dict] = {}
    for row in rows:
        key = (row.get("scenario_id", ""), row.get("method_id", ""), row.get("country_code", ""))
        record = grouped.setdefault(key, {"selected_candidate_count": 0, "total_candidate_cost": 0.0})
        record["selected_candidate_count"] += 1
        record["total_candidate_cost"] += numeric(row.get("c_j"))
    return grouped


def group_unique_zone_coverage_by_method_country(rows: list[dict]) -> dict[tuple[str, str, str], dict]:
    zone_by_key: dict[tuple[str, str, str, str], float] = {}
    for row in rows:
        country_code = country_from_demand_zone_id(row.get("demand_zone_id", ""))
        key = (row.get("scenario_id", ""), row.get("method_id", ""), country_code, row.get("demand_zone_id", ""))
        zone_by_key[key] = max(zone_by_key.get(key, 0.0), numeric(row.get("zone_demand_weight")))

    grouped: dict[tuple[str, str, str], dict] = {}
    for (scenario_id, method_id, country_code, _zone_id), demand_weight in zone_by_key.items():
        key = (scenario_id, method_id, country_code)
        record = grouped.setdefault(key, {"covered_zone_count": 0, "covered_demand_weight": 0.0})
        record["covered_zone_count"] += 1
        record["covered_demand_weight"] += demand_weight
    return grouped


def method_total_coverage(groups: dict[tuple[str, str, str], dict]) -> dict[tuple[str, str], float]:
    totals: dict[tuple[str, str], float] = {}
    for (scenario_id, method_id, _country_code), record in groups.items():
        key = (scenario_id, method_id)
        totals[key] = totals.get(key, 0.0) + float(record["covered_demand_weight"])
    return totals


def method_total_cost(groups: dict[tuple[str, str, str], dict]) -> dict[tuple[str, str], float]:
    totals: dict[tuple[str, str], float] = {}
    for (scenario_id, method_id, _country_code), record in groups.items():
        key = (scenario_id, method_id)
        totals[key] = totals.get(key, 0.0) + float(record["total_candidate_cost"])
    return totals


def country_from_demand_zone_id(value: str) -> str:
    prefix = "dz:nuts2024:"
    if value.startswith(prefix) and len(value) >= len(prefix) + 2:
        return value[len(prefix) : len(prefix) + 2]
    return ""


def scenario_method_key(scenario_id: str, method_id: str) -> str:
    return f"{scenario_id}|{method_id}"


def concentration_status(share: float) -> str:
    return "warning" if share >= CONCENTRATION_WARNING_THRESHOLD else "pass"


def concentration_review_note(share: float) -> str:
    if share >= CONCENTRATION_WARNING_THRESHOLD:
        return "Warning-grade concentration review: this is analytically important but not a mathematical failure."
    if share >= 0.5:
        return "Material concentration review: inspect whether the business question needs a balance constraint."
    return "No country concentration warning under the current public-proxy threshold."


def country_diagnostic_note(country_demand: float, method_demand: float) -> str:
    share = country_demand / method_demand if method_demand else 0.0
    if share >= 0.8:
        return "Covered demand is highly concentrated in this country under the current public-proxy solution."
    if share >= 0.5:
        return "Covered demand is materially concentrated in this country under the current public-proxy solution."
    return "Covered demand is not dominant in this country under the current public-proxy solution."


def numeric(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def format_numeric(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")


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


COUNTRY_DIAGNOSTIC_FIELDNAMES = [
    "scenario_method_country_id",
    "scenario_method_id",
    "scenario_id",
    "method_id",
    "country_code",
    "selected_candidate_count",
    "covered_zone_count",
    "covered_demand_weight",
    "covered_demand_share_of_method",
    "total_candidate_cost",
    "candidate_cost_share_of_method",
    "concentration_status",
    "concentration_warning_threshold",
    "concentration_review_note",
    "diagnostic_note",
    "allowed_use_note",
    "proxy_assumption_label",
]
