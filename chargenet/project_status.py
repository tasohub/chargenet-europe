from __future__ import annotations

import csv
import json
from pathlib import Path

from .paths import MART_DIR, PROJECT_ROOT, REPORT_DIR, ensure_project_dirs
from .portfolio_release import read_csv_rows


PROJECT_STATUS_FIELDNAMES = [
    "status_key",
    "status_label",
    "status_value",
    "status_state",
    "detail",
]


def build_project_status_rows(
    *,
    snapshot_rows: list[dict] | None = None,
    release_rows: list[dict] | None = None,
    completion_rows: list[dict] | None = None,
    app_manifest: dict | None = None,
) -> list[dict]:
    snapshots = snapshot_rows if snapshot_rows is not None else read_csv_rows(MART_DIR / "mart_pipeline_snapshot_metrics_tile_smoke.csv")
    release = release_rows if release_rows is not None else read_csv_rows(REPORT_DIR / "release_gate_tile_smoke.csv")
    completion = completion_rows if completion_rows is not None else read_csv_rows(REPORT_DIR / "completion_gate.csv")
    manifest = app_manifest if app_manifest is not None else read_app_manifest(PROJECT_ROOT / "app_data" / "manifest.json")

    release_passed = sum(1 for row in release if row.get("gate_status") == "pass")
    completion_passed = sum(1 for row in completion if row.get("gate_status") == "pass")
    app_files = manifest.get("files", {}) if isinstance(manifest.get("files", {}), dict) else {}

    return [
        status_row("phase", "Current phase", "Phase 5 MVP", "pass", "MILP optimization checkpoint and public demo gates are implemented."),
        status_row("pilot_scope", "Pilot scope", "BE, DE, FR, NL", "pass", "Belgium, Germany, France, and the Netherlands only."),
        status_row("candidate_proxies", "Candidate proxies", format_int(metric_value(snapshots, "candidate_site_count")), "pass", "Public OSM candidate proxies in the capped tile-smoke snapshot."),
        status_row("coverage_rows", "Coverage rows", format_int(metric_value(snapshots, "coverage_row_count")), "pass", "Candidate-zone-radius coverage facts in the current snapshot."),
        status_row("release_gates", "Release gates", f"{release_passed}/{len(release)}", gate_state(release_passed, len(release)), "Quality, drift, public claims, app fallback, and manifest gates."),
        status_row("completion_gates", "Completion gates", f"{completion_passed}/{len(completion)}", gate_state(completion_passed, len(completion)), "Portfolio release, private boundary, branch history, and git worktree gates."),
        status_row("app_fallback_files", "App fallback files", format_int(len(app_files)), "pass" if app_files else "fail", "Files listed in app_data/manifest.json for Streamlit Cloud fallback."),
        status_row(
            "known_limits",
            "Known limits",
            "public proxies",
            "info",
            "No grid capacity, permits, land control, traffic flows, negotiated CAPEX, or charger utilization.",
        ),
    ]


def write_project_status_report(
    *,
    rows: list[dict] | None = None,
    output_path: Path | None = None,
) -> Path:
    ensure_project_dirs()
    target = output_path or REPORT_DIR / "project_status.csv"
    report_rows = rows if rows is not None else build_project_status_rows()
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=PROJECT_STATUS_FIELDNAMES)
        writer.writeheader()
        writer.writerows(report_rows)
    return target


def read_project_status_report(path: Path | None = None) -> list[dict]:
    return read_csv_rows(path or REPORT_DIR / "project_status.csv")


def project_status_passed(rows: list[dict]) -> bool:
    return bool(rows) and all(row.get("status_state") in {"pass", "info"} for row in rows)


def status_row(key: str, label: str, value: str, state: str, detail: str) -> dict:
    return {
        "status_key": key,
        "status_label": label,
        "status_value": value,
        "status_state": state,
        "detail": detail,
    }


def metric_value(rows: list[dict], metric_name: str) -> float:
    for row in rows:
        if row.get("metric_name") == metric_name:
            return numeric(row.get("metric_value"))
    return 0.0


def gate_state(passed: int, total: int) -> str:
    return "pass" if total and passed == total else "fail"


def read_app_manifest(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def numeric(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def format_int(value: float | int) -> str:
    return f"{int(round(float(value))):,}"
