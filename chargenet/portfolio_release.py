from __future__ import annotations

import csv
import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from .country_diagnostics import build_optimization_country_diagnostics_tile_smoke
from .dq import write_quality_report
from .exports import write_powerbi_exports
from .lineage import build_optimization_zone_trace_tile_smoke
from .method_comparison import build_method_comparison_narrative_tile_smoke
from .paths import PROJECT_ROOT, REPORT_DIR, ensure_project_dirs
from .public_claims import write_public_claim_gate
from .release_gate import display_path, evaluate_release_gate, release_gate_passed, write_release_gate_report


PortfolioStep = Callable[[], dict]
APP_FALLBACK_GATE_NAMES = {"app_fallback_sync", "app_data_manifest"}

PORTFOLIO_RELEASE_FIELDNAMES = [
    "step_order",
    "step_name",
    "step_status",
    "evidence_path",
    "detail",
]


def run_portfolio_release_check(
    *,
    steps: list[tuple[str, PortfolioStep]] | None = None,
) -> list[dict]:
    rows = []
    blocked = False
    for index, (step_name, step_fn) in enumerate(steps or default_portfolio_release_steps(), start=1):
        if blocked:
            rows.append(
                release_check_row(
                    index,
                    step_name,
                    "skipped",
                    "",
                    "Skipped because an earlier release check failed.",
                )
            )
            continue
        try:
            result = step_fn()
            status = "pass" if bool(result.get("passed")) else "fail"
            rows.append(
                release_check_row(
                    index,
                    step_name,
                    status,
                    display_path(Path(str(result.get("evidence_path", "")))) if result.get("evidence_path") else "",
                    str(result.get("detail", "")),
                )
            )
        except Exception as exc:  # pragma: no cover - defensive reporting path
            status = "fail"
            rows.append(release_check_row(index, step_name, status, "", f"{type(exc).__name__}: {exc}"))
        if status != "pass":
            blocked = True
    return rows


def write_portfolio_release_check(
    *,
    rows: list[dict] | None = None,
    output_path: Path | None = None,
) -> Path:
    ensure_project_dirs()
    target = output_path or REPORT_DIR / "portfolio_release_check.csv"
    report_rows = rows if rows is not None else run_portfolio_release_check()
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=PORTFOLIO_RELEASE_FIELDNAMES)
        writer.writeheader()
        writer.writerows(report_rows)
    return target


def portfolio_release_check_passed(rows: list[dict]) -> bool:
    return bool(rows) and all(row.get("step_status") == "pass" for row in rows)


def default_portfolio_release_steps() -> list[tuple[str, PortfolioStep]]:
    return [
        ("phase5_derived_marts", phase5_derived_marts_step),
        ("quality_report", quality_report_step),
        ("public_claims", public_claims_step),
        ("release_gate_pre_sync", release_gate_pre_sync_step),
        ("app_data_build", app_data_build_step),
        ("release_gate_final", release_gate_final_step),
        ("streamlit_smoke", streamlit_smoke_step),
    ]


def phase5_derived_marts_step() -> dict:
    zone_trace = build_optimization_zone_trace_tile_smoke()
    country_diagnostics = build_optimization_country_diagnostics_tile_smoke()
    method_comparison = build_method_comparison_narrative_tile_smoke()
    powerbi_exports = write_powerbi_exports()
    return {
        "passed": zone_trace.exists() and country_diagnostics.exists() and method_comparison.exists() and bool(powerbi_exports),
        "evidence_path": method_comparison,
        "detail": f"zone trace, country diagnostics, method comparison, and {len(powerbi_exports)} Power BI export files refreshed",
    }


def quality_report_step() -> dict:
    path = write_quality_report()
    report = json.loads(path.read_text(encoding="utf-8"))
    passed = bool(report.get("raw", {}).get("passed")) and bool(report.get("clean", {}).get("passed"))
    raw_count = report.get("raw", {}).get("check_count", 0)
    clean_count = report.get("clean", {}).get("check_count", 0)
    return {
        "passed": passed,
        "evidence_path": path,
        "detail": f"raw checks={raw_count}; clean/mart checks={clean_count}",
    }


def public_claims_step() -> dict:
    path = write_public_claim_gate()
    findings = read_csv_rows(path)
    return {
        "passed": len(findings) == 0,
        "evidence_path": path,
        "detail": "no public claim findings" if not findings else f"{len(findings)} public claim finding(s)",
    }


def release_gate_pre_sync_step() -> dict:
    rows = evaluate_release_gate()
    path = write_release_gate_report(rows=rows)
    non_app_rows = [row for row in rows if row.get("gate_name") not in APP_FALLBACK_GATE_NAMES]
    passed = release_gate_pre_sync_passed(rows)
    blockers = [row for row in non_app_rows if row.get("gate_status") != "pass"]
    return {
        "passed": passed,
        "evidence_path": path,
        "detail": "non-app release gates passed" if passed else f"{len(blockers)} non-app release blocker(s)",
    }


def release_gate_pre_sync_passed(rows: list[dict]) -> bool:
    non_app_rows = [row for row in rows if row.get("gate_name") not in APP_FALLBACK_GATE_NAMES]
    return bool(non_app_rows) and all(row.get("gate_status") == "pass" for row in non_app_rows)


def app_data_build_step() -> dict:
    script = PROJECT_ROOT / "scripts" / "build_app_phase5_data.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    manifest = PROJECT_ROOT / "app_data" / "manifest.json"
    passed = result.returncode == 0 and manifest.exists()
    detail = "app_data manifest refreshed" if passed else stderr_tail(result.stderr)
    return {"passed": passed, "evidence_path": manifest if manifest.exists() else script, "detail": detail}


def release_gate_final_step() -> dict:
    rows = evaluate_release_gate()
    path = write_release_gate_report(rows=rows)
    passed = release_gate_passed(rows)
    blockers = [row for row in rows if row.get("gate_status") != "pass"]
    return {
        "passed": passed,
        "evidence_path": path,
        "detail": "all release gates passed" if passed else f"{len(blockers)} release gate blocker(s)",
    }


def streamlit_smoke_step() -> dict:
    from streamlit.testing.v1 import AppTest

    app_path = PROJECT_ROOT / "app.py"
    app = AppTest.from_file(str(app_path))
    app.run(timeout=30)
    exceptions = len(app.exception)
    tab_count = len(app.tabs)
    return {
        "passed": exceptions == 0 and tab_count >= 5,
        "evidence_path": app_path,
        "detail": f"exceptions={exceptions}; tabs={tab_count}",
    }


def release_check_row(order: int, name: str, status: str, evidence_path: str, detail: str) -> dict:
    return {
        "step_order": order,
        "step_name": name,
        "step_status": status,
        "evidence_path": evidence_path,
        "detail": detail,
    }


def read_csv_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def stderr_tail(stderr: str) -> str:
    lines = [line for line in stderr.splitlines() if line.strip()]
    return lines[-1] if lines else "command failed without stderr"
