from __future__ import annotations

import csv
import json
from pathlib import Path

from .paths import CLEAN_DIR, CONFIG_DIR, MART_DIR, ensure_project_dirs


DEFAULT_SNAPSHOT_ID = "tile_smoke_current"
DEFAULT_REFERENCE_SNAPSHOT_ID = "tile_smoke_reference_candidate"
DEFAULT_WARNING_PCT = 0.10
DEFAULT_FAIL_PCT = 0.25


def build_pipeline_snapshot_metrics_tile_smoke(
    *,
    candidate_path: Path | None = None,
    coverage_path: Path | None = None,
    baseline_path: Path | None = None,
    optimization_path: Path | None = None,
    output_path: Path | None = None,
    snapshot_id: str = DEFAULT_SNAPSHOT_ID,
) -> Path:
    ensure_project_dirs()
    candidates = read_csv_rows(candidate_path or CLEAN_DIR / "clean_candidate_sites_tile_smoke.csv")
    coverage = read_csv_rows(coverage_path or MART_DIR / "fact_candidate_zone_coverage_tile_smoke.csv")
    baseline = read_csv_rows(baseline_path or MART_DIR / "mart_candidate_baseline_scores_tile_smoke.csv")
    optimization = read_csv_rows(optimization_path or MART_DIR / "mart_optimization_results_tile_smoke.csv")
    target = output_path or MART_DIR / "mart_pipeline_snapshot_metrics_tile_smoke.csv"

    rows = [
        metric_row(snapshot_id, "candidate_site_count", len(candidates), "count", "clean_candidate_sites_tile_smoke"),
        metric_row(snapshot_id, "coverage_row_count", len(coverage), "count", "fact_candidate_zone_coverage_tile_smoke"),
        metric_row(
            snapshot_id,
            "eligible_coverage_pair_count",
            sum(1 for row in coverage if int(float(row.get("pair_eligible_flag") or 0)) == 1),
            "count",
            "fact_candidate_zone_coverage_tile_smoke",
        ),
        metric_row(snapshot_id, "baseline_score_row_count", len(baseline), "count", "mart_candidate_baseline_scores_tile_smoke"),
        metric_row(snapshot_id, "optimization_summary_row_count", len(optimization), "count", "mart_optimization_results_tile_smoke"),
    ]
    base_mclp = next(
        (
            row
            for row in optimization
            if row.get("scenario_id") in {"scenario:radius-base", "scenario:base"}
            and row.get("method_id") == "method:mclp-pulp-cbc"
        ),
        {},
    )
    if base_mclp:
        rows.append(
            metric_row(
                snapshot_id,
                "optimization_objective_mclp_base",
                numeric(base_mclp.get("objective_covered_demand_weight")),
                "demand_weight",
                "mart_optimization_results_tile_smoke",
            )
        )
        rows.append(
            metric_row(
                snapshot_id,
                "optimization_cost_mclp_base",
                numeric(base_mclp.get("total_candidate_cost")),
                "cost_proxy",
                "mart_optimization_results_tile_smoke",
            )
        )

    return write_csv(target, rows, SNAPSHOT_METRIC_FIELDNAMES)


def compare_snapshot_metrics(
    *,
    current_path: Path | None = None,
    reference_path: Path | None = None,
    output_path: Path | None = None,
    warning_pct: float = DEFAULT_WARNING_PCT,
    fail_pct: float = DEFAULT_FAIL_PCT,
    thresholds: dict | None = None,
) -> Path:
    ensure_project_dirs()
    current = read_csv_rows(current_path or MART_DIR / "mart_pipeline_snapshot_metrics_tile_smoke.csv")
    reference = read_csv_rows(reference_path or MART_DIR / "mart_pipeline_snapshot_metrics_reference_tile_smoke.csv")
    threshold_config = thresholds if thresholds is not None else load_threshold_config(warning_pct, fail_pct)
    target = output_path or MART_DIR / "mart_pipeline_snapshot_drift_tile_smoke.csv"
    reference_by_metric = {row["metric_name"]: row for row in reference}
    rows = []
    for current_row in current:
        metric_name = current_row["metric_name"]
        reference_row = reference_by_metric.get(metric_name, {})
        current_value = numeric(current_row.get("metric_value"))
        reference_value = numeric(reference_row.get("metric_value"))
        metric_warning_pct, metric_fail_pct = threshold_for_metric(metric_name, threshold_config)
        absolute_delta = current_value - reference_value
        relative_delta = absolute_delta / reference_value if reference_value else 0.0
        rows.append(
            {
                "metric_name": metric_name,
                "current_snapshot_id": current_row.get("snapshot_id", ""),
                "reference_snapshot_id": reference_row.get("snapshot_id", ""),
                "current_metric_value": round(current_value, 6),
                "reference_metric_value": round(reference_value, 6),
                "absolute_delta": round(absolute_delta, 6),
                "relative_delta_pct": round(relative_delta, 6),
                "warning_threshold_pct": metric_warning_pct,
                "fail_threshold_pct": metric_fail_pct,
                "drift_status": drift_status(current_value, reference_value, warning_pct=metric_warning_pct, fail_pct=metric_fail_pct),
                "source_table": current_row.get("source_table", reference_row.get("source_table", "")),
                "allowed_use_note": "Snapshot drift is an alert for review, not a source-data error by itself.",
                "proxy_assumption_label": "tile_smoke_snapshot_drift_not_investment_grade",
            }
        )
    return write_csv(target, rows, SNAPSHOT_DRIFT_FIELDNAMES)


def stage_reference_snapshot_metrics_tile_smoke(
    *,
    current_path: Path | None = None,
    reference_output_path: Path | None = None,
    certification_log_path: Path | None = None,
    reference_snapshot_id: str = DEFAULT_REFERENCE_SNAPSHOT_ID,
    reviewer: str = "codex-local",
    certification_note: str = "Staged reference snapshot candidate; human review required before public certification.",
) -> list[Path]:
    ensure_project_dirs()
    current = read_csv_rows(current_path or MART_DIR / "mart_pipeline_snapshot_metrics_tile_smoke.csv")
    reference_target = reference_output_path or MART_DIR / "mart_pipeline_snapshot_metrics_reference_tile_smoke.csv"
    log_target = certification_log_path or MART_DIR / "mart_pipeline_snapshot_certifications_tile_smoke.csv"
    reference_rows = []
    for row in current:
        reference_rows.append(
            {
                **row,
                "snapshot_id": reference_snapshot_id,
                "allowed_use_note": "Reference snapshot candidate for drift comparison; staged for review, not a certification.",
                "proxy_assumption_label": "tile_smoke_reference_snapshot_candidate",
            }
        )
    write_csv(reference_target, reference_rows, SNAPSHOT_METRIC_FIELDNAMES)
    log_rows = [
        {
            "reference_snapshot_id": reference_snapshot_id,
            "source_snapshot_id": current[0].get("snapshot_id", "") if current else "",
            "certification_status": "staged_for_review",
            "reviewer": reviewer,
            "certification_note": certification_note,
            "metric_count": len(reference_rows),
            "allowed_use_note": "Staged snapshot reference for drift checks; this is not a certification until reviewed.",
            "proxy_assumption_label": "tile_smoke_snapshot_certification_log",
        }
    ]
    write_csv(log_target, log_rows, SNAPSHOT_CERTIFICATION_FIELDNAMES)
    return [reference_target, log_target]


def promote_reference_snapshot_metrics_tile_smoke(
    *,
    certification_log_path: Path | None = None,
    drift_path: Path | None = None,
    output_path: Path | None = None,
    reviewer: str = "codex-local-qa-gate",
) -> Path:
    ensure_project_dirs()
    log_target = certification_log_path or MART_DIR / "mart_pipeline_snapshot_certifications_tile_smoke.csv"
    drift_target = drift_path or MART_DIR / "mart_pipeline_snapshot_drift_tile_smoke.csv"
    output_target = output_path or log_target
    log_rows = read_csv_rows(log_target)
    drift_rows = read_csv_rows(drift_target)
    non_pass_rows = [row for row in drift_rows if row.get("drift_status") != "pass"]
    next_status = "certified" if drift_rows and not non_pass_rows else "rejected"
    if next_status == "certified":
        note = f"Certified by explicit promotion gate: all drift checks passed across {len(drift_rows)} metrics."
        allowed_use_note = "Certified reference snapshot for tile-smoke drift checks; still not investment advice."
    else:
        note = f"Promotion blocked by {len(non_pass_rows)} drift row(s) needing review."
        allowed_use_note = "Reference snapshot not certified; review drift warnings or failures before public use."

    promoted_rows = []
    for row in log_rows:
        promoted_rows.append(
            {
                **row,
                "certification_status": next_status,
                "reviewer": reviewer,
                "certification_note": note,
                "allowed_use_note": allowed_use_note,
                "proxy_assumption_label": "tile_smoke_snapshot_promotion_gate",
            }
        )
    return write_csv(output_target, promoted_rows, SNAPSHOT_CERTIFICATION_FIELDNAMES)


def load_threshold_config(warning_pct: float = DEFAULT_WARNING_PCT, fail_pct: float = DEFAULT_FAIL_PCT) -> dict:
    path = CONFIG_DIR / "drift_thresholds.json"
    if not path.exists():
        return {"default": {"warning_pct": warning_pct, "fail_pct": fail_pct}, "metrics": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"default": {"warning_pct": warning_pct, "fail_pct": fail_pct}, "metrics": {}}
    payload.setdefault("default", {"warning_pct": warning_pct, "fail_pct": fail_pct})
    payload.setdefault("metrics", {})
    return payload


def threshold_for_metric(metric_name: str, thresholds: dict) -> tuple[float, float]:
    default = thresholds.get("default", {})
    metric = thresholds.get("metrics", {}).get(metric_name, {})
    return (
        float(metric.get("warning_pct", default.get("warning_pct", DEFAULT_WARNING_PCT))),
        float(metric.get("fail_pct", default.get("fail_pct", DEFAULT_FAIL_PCT))),
    )


def drift_status(current_value: float, reference_value: float, *, warning_pct: float, fail_pct: float) -> str:
    if reference_value == 0:
        return "pass" if current_value == 0 else "warning"
    relative_delta = abs((current_value - reference_value) / reference_value)
    if relative_delta >= fail_pct:
        return "fail"
    if relative_delta >= warning_pct:
        return "warning"
    return "pass"


def metric_row(snapshot_id: str, metric_name: str, metric_value: float, metric_unit: str, source_table: str) -> dict:
    return {
        "snapshot_id": snapshot_id,
        "metric_name": metric_name,
        "metric_value": round(float(metric_value), 6),
        "metric_unit": metric_unit,
        "source_table": source_table,
        "allowed_use_note": "Pipeline snapshot metric for drift monitoring; not investment advice.",
        "proxy_assumption_label": "tile_smoke_pipeline_snapshot_metric",
    }


def numeric(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


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


SNAPSHOT_METRIC_FIELDNAMES = [
    "snapshot_id",
    "metric_name",
    "metric_value",
    "metric_unit",
    "source_table",
    "allowed_use_note",
    "proxy_assumption_label",
]

SNAPSHOT_DRIFT_FIELDNAMES = [
    "metric_name",
    "current_snapshot_id",
    "reference_snapshot_id",
    "current_metric_value",
    "reference_metric_value",
    "absolute_delta",
    "relative_delta_pct",
    "warning_threshold_pct",
    "fail_threshold_pct",
    "drift_status",
    "source_table",
    "allowed_use_note",
    "proxy_assumption_label",
]

SNAPSHOT_CERTIFICATION_FIELDNAMES = [
    "reference_snapshot_id",
    "source_snapshot_id",
    "certification_status",
    "reviewer",
    "certification_note",
    "metric_count",
    "allowed_use_note",
    "proxy_assumption_label",
]
