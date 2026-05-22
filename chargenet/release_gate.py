from __future__ import annotations

import csv
import json
from pathlib import Path

from .paths import MART_DIR, PROJECT_ROOT, REPORT_DIR, ensure_project_dirs


RELEASE_GATE_FIELDNAMES = [
    "gate_name",
    "gate_status",
    "evidence_path",
    "blocker_count",
    "detail",
]

PUBLIC_PROXY_LABEL_MARKERS = (
    "not_investment_grade",
    "proxy",
    "tile_smoke",
    "snapshot",
)

ALLOWED_USE_NOTE_MARKERS = (
    "not investment",
    "not a recommendation",
    "not a feasibility",
    "not a rollout",
    "not a full pilot",
    "public proxy",
    "public-proxy",
    "diligence",
    "qa only",
    "review",
)

SCENARIO_METHOD_CHILD_FILES = (
    "optimization_selected_sites_tile_smoke.csv",
    "optimization_zone_trace_tile_smoke.csv",
    "optimization_country_diagnostics_tile_smoke.csv",
)


def evaluate_release_gate(
    *,
    quality_report_path: Path | None = None,
    drift_path: Path | None = None,
    certification_path: Path | None = None,
    public_claim_gate_path: Path | None = None,
    app_certification_path: Path | None = None,
    app_manifest_path: Path | None = None,
) -> list[dict]:
    quality_target = quality_report_path or REPORT_DIR / "phase3_sample_quality_report.json"
    drift_target = drift_path or MART_DIR / "mart_pipeline_snapshot_drift_tile_smoke.csv"
    certification_target = certification_path or MART_DIR / "mart_pipeline_snapshot_certifications_tile_smoke.csv"
    public_claim_target = public_claim_gate_path or REPORT_DIR / "public_claim_gate.csv"
    app_certification_target = app_certification_path or PROJECT_ROOT / "app_data" / "pipeline_snapshot_certifications_tile_smoke.csv"
    app_manifest_target = app_manifest_path or PROJECT_ROOT / "app_data" / "manifest.json"

    quality_passed = quality_report_passed(quality_target)
    drift_rows = read_csv_rows(drift_target)
    drift_blockers = [row for row in drift_rows if row.get("drift_status") != "pass"]
    certification_rows = read_csv_rows(certification_target)
    latest_certification = certification_rows[0] if certification_rows else {}
    claim_rows = read_csv_rows(public_claim_target)
    app_rows = read_csv_rows(app_certification_target)
    app_certification = app_rows[0] if app_rows else {}
    manifest_summary = app_data_manifest_summary(app_manifest_target)

    return [
        gate_row(
            "quality_report",
            quality_passed,
            quality_target,
            0 if quality_passed else 1,
            "Raw and clean/mart quality report passed." if quality_passed else "Quality report failed or is missing.",
        ),
        gate_row(
            "snapshot_drift",
            bool(drift_rows) and not drift_blockers,
            drift_target,
            len(drift_blockers) if drift_rows else 1,
            f"{len(drift_rows)} drift metrics passed." if drift_rows and not drift_blockers else "Drift warnings or failures block release.",
        ),
        gate_row(
            "snapshot_certification",
            latest_certification.get("certification_status") == "certified",
            certification_target,
            0 if latest_certification.get("certification_status") == "certified" else 1,
            f"Demo drift reference is {latest_certification.get('certification_status', 'missing')}.",
        ),
        gate_row(
            "public_claims",
            len(claim_rows) == 0,
            public_claim_target,
            len(claim_rows),
            "No public overclaim findings." if not claim_rows else "Public wording findings need review.",
        ),
        gate_row(
            "app_fallback_sync",
            certifications_match(latest_certification, app_certification),
            app_certification_target,
            0 if certifications_match(latest_certification, app_certification) else 1,
            "App fallback certification matches mart certification."
            if certifications_match(latest_certification, app_certification)
            else "App fallback certification is missing or stale.",
        ),
        gate_row(
            "app_data_manifest",
            bool(manifest_summary["passed"]),
            app_manifest_target,
            int(manifest_summary["blocker_count"]),
            str(manifest_summary["detail"]),
        ),
    ]


def write_release_gate_report(
    *,
    rows: list[dict] | None = None,
    output_path: Path | None = None,
) -> Path:
    ensure_project_dirs()
    target = output_path or REPORT_DIR / "release_gate_tile_smoke.csv"
    report_rows = rows if rows is not None else evaluate_release_gate()
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=RELEASE_GATE_FIELDNAMES)
        writer.writeheader()
        writer.writerows(report_rows)
    return target


def release_gate_passed(rows: list[dict]) -> bool:
    return bool(rows) and all(row.get("gate_status") == "pass" for row in rows)


def quality_report_passed(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return bool(report.get("raw", {}).get("passed")) and bool(report.get("clean", {}).get("passed"))


def certifications_match(mart_row: dict, app_row: dict) -> bool:
    if not mart_row or not app_row:
        return False
    return (
        mart_row.get("reference_snapshot_id") == app_row.get("reference_snapshot_id")
        and mart_row.get("certification_status") == app_row.get("certification_status")
        and str(mart_row.get("metric_count")) == str(app_row.get("metric_count"))
    )


def app_data_manifest_summary(path: Path) -> dict:
    if not path.exists():
        return {
            "passed": False,
            "expected_files": 0,
            "valid_files": 0,
            "blocker_count": 1,
            "detail": "app_data manifest is missing.",
        }
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {
            "passed": False,
            "expected_files": 0,
            "valid_files": 0,
            "blocker_count": 1,
            "detail": "app_data manifest is not valid JSON.",
        }
    files = manifest.get("files", {})
    schemas = manifest.get("schemas", {})
    if not isinstance(files, dict) or not files:
        return {
            "passed": False,
            "expected_files": 0,
            "valid_files": 0,
            "blocker_count": 1,
            "detail": "app_data manifest has no files mapping.",
        }
    blockers = []
    valid_files = 0
    if manifest.get("not_investment_grade") is not True:
        blockers.append("manifest not_investment_grade must be true")
    for file_name, expected_count in sorted(files.items()):
        file_path = path.parent / str(file_name)
        if not file_path.exists():
            blockers.append(f"{file_name} missing")
            continue
        actual_count = csv_row_count(file_path)
        try:
            expected_rows = int(expected_count)
        except (TypeError, ValueError):
            blockers.append(f"{file_name} has invalid expected row count")
            continue
        if actual_count != expected_rows:
            blockers.append(f"{file_name} expected {expected_rows} rows, found {actual_count}")
            continue
        expected_columns = schemas.get(str(file_name), []) if isinstance(schemas, dict) else []
        if expected_columns:
            actual_columns = csv_header(file_path)
            missing_columns = [column for column in expected_columns if column not in actual_columns]
            if missing_columns:
                blockers.append(f"{file_name} missing columns: {', '.join(missing_columns)}")
                continue
        blockers.extend(app_data_file_semantic_blockers(str(file_name), file_path))
        valid_files += 1
    blockers.extend(app_data_scenario_method_fk_blockers(path.parent, files))
    return {
        "passed": not blockers,
        "expected_files": len(files),
        "valid_files": valid_files,
        "blocker_count": len(blockers),
        "detail": f"{valid_files}/{len(files)} app_data files match manifest row counts and required columns." if not blockers else "; ".join(blockers),
    }


def app_data_file_semantic_blockers(file_name: str, path: Path) -> list[str]:
    header = csv_header(path)
    if not header:
        return []
    blockers = []
    rows = read_csv_rows(path)
    if "proxy_assumption_label" in header:
        for row_number, row in enumerate(rows, start=1):
            label = str(row.get("proxy_assumption_label") or "").strip().lower()
            if not label or not any(marker in label for marker in PUBLIC_PROXY_LABEL_MARKERS):
                blockers.append(f"{file_name} row {row_number} missing public proxy label")
    if "allowed_use_note" in header:
        for row_number, row in enumerate(rows, start=1):
            note = str(row.get("allowed_use_note") or "").strip().lower()
            if not note or not any(marker in note for marker in ALLOWED_USE_NOTE_MARKERS):
                blockers.append(f"{file_name} row {row_number} missing allowed_use_note")
    return blockers


def app_data_scenario_method_fk_blockers(app_dir: Path, files: dict) -> list[str]:
    summary_name = "optimization_results_tile_smoke.csv"
    if summary_name not in files:
        return []
    summary_path = app_dir / summary_name
    if not summary_path.exists() or "scenario_method_id" not in csv_header(summary_path):
        return []
    blockers = []
    summary_ids = []
    for row_number, row in enumerate(read_csv_rows(summary_path), start=1):
        scenario_method_key = row.get("scenario_method_id")
        if not scenario_method_key:
            blockers.append(f"{summary_name} row {row_number} missing scenario_method_id")
            continue
        summary_ids.append(scenario_method_key)
    known_ids = set(summary_ids)
    if len(known_ids) != len(summary_ids):
        blockers.append(f"{summary_name} has duplicate scenario_method_id")
    for file_name in SCENARIO_METHOD_CHILD_FILES:
        if file_name not in files:
            continue
        child_path = app_dir / file_name
        if not child_path.exists() or "scenario_method_id" not in csv_header(child_path):
            continue
        for row_number, row in enumerate(read_csv_rows(child_path), start=1):
            scenario_method_key = row.get("scenario_method_id")
            if not scenario_method_key:
                blockers.append(f"{file_name} row {row_number} missing scenario_method_id")
            elif scenario_method_key not in known_ids:
                blockers.append(f"{file_name} row {row_number} has unknown scenario_method_id {scenario_method_key}")
    return blockers


def csv_row_count(path: Path) -> int:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        rows = list(reader)
    return max(0, len(rows) - 1)


def csv_header(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        try:
            return next(reader)
        except StopIteration:
            return []


def gate_row(gate_name: str, passed: bool, evidence_path: Path, blocker_count: int, detail: str) -> dict:
    return {
        "gate_name": gate_name,
        "gate_status": "pass" if passed else "fail",
        "evidence_path": display_path(evidence_path),
        "blocker_count": blocker_count,
        "detail": detail,
    }


def display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return path.name


def read_csv_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))
