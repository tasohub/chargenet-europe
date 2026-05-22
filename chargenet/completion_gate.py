from __future__ import annotations

import csv
import subprocess
from pathlib import Path

from .paths import PROJECT_ROOT, REPORT_DIR, ensure_project_dirs
from .portfolio_release import (
    portfolio_release_check_passed,
    read_csv_rows,
    run_portfolio_release_check,
    write_portfolio_release_check,
)
from .public_claims import default_public_claim_paths
from .release_gate import display_path


COMPLETION_GATE_FIELDNAMES = [
    "gate_name",
    "gate_status",
    "evidence_path",
    "blocker_count",
    "detail",
]

PRIVATE_PREP_PUBLIC_PATHS = {
    "docs/chargenet-europe/interview-pack.md",
    "docs/chargenet-europe/three-month-roadmap.md",
}


def evaluate_completion_gate(
    *,
    portfolio_rows: list[dict] | None = None,
    public_claim_paths: list[Path] | None = None,
    private_dir_ignored: bool | None = None,
    git_status_lines: list[str] | None = None,
    private_history_hits: list[str] | None = None,
) -> list[dict]:
    release_rows = portfolio_rows if portfolio_rows is not None else run_portfolio_release_check()
    public_paths = public_claim_paths if public_claim_paths is not None else default_public_claim_paths()
    private_ignored = private_dir_ignored if private_dir_ignored is not None else git_path_is_ignored(PROJECT_ROOT / ".private")
    status_lines = git_status_lines if git_status_lines is not None else current_git_status_lines()
    history_hits = private_history_hits if private_history_hits is not None else private_prep_history_hits()

    return [
        completion_row(
            "portfolio_release",
            portfolio_release_check_passed(release_rows),
            REPORT_DIR / "portfolio_release_check.csv",
            0 if portfolio_release_check_passed(release_rows) else count_failed_portfolio_steps(release_rows),
            "Portfolio release check passed." if portfolio_release_check_passed(release_rows) else "Portfolio release blockers remain.",
        ),
        private_boundary_row(public_paths, private_ignored),
        private_history_row(history_hits),
        completion_row(
            "git_worktree",
            len(status_lines) == 0,
            PROJECT_ROOT,
            len(status_lines),
            "Git worktree is clean." if not status_lines else f"{len(status_lines)} uncommitted git status line(s).",
        ),
    ]


def write_completion_gate(
    *,
    rows: list[dict] | None = None,
    output_path: Path | None = None,
) -> Path:
    ensure_project_dirs()
    release_path = REPORT_DIR / "portfolio_release_check.csv"
    if rows is None:
        release_rows = run_portfolio_release_check()
        write_portfolio_release_check(rows=release_rows, output_path=release_path)
        gate_rows = evaluate_completion_gate(portfolio_rows=release_rows)
    else:
        gate_rows = rows
    target = output_path or REPORT_DIR / "completion_gate.csv"
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COMPLETION_GATE_FIELDNAMES)
        writer.writeheader()
        writer.writerows(gate_rows)
    return target


def completion_gate_passed(rows: list[dict]) -> bool:
    return bool(rows) and all(row.get("gate_status") == "pass" for row in rows)


def private_boundary_row(public_claim_paths: list[Path], private_dir_ignored: bool) -> dict:
    public_relative_paths = {relative_to_project(path) for path in public_claim_paths}
    leaked_paths = sorted(public_relative_paths & PRIVATE_PREP_PUBLIC_PATHS)
    blockers = len(leaked_paths) + (0 if private_dir_ignored else 1)
    if blockers:
        detail_parts = []
        if leaked_paths:
            detail_parts.append(f"private prep path(s) in public claim scan: {', '.join(leaked_paths)}")
        if not private_dir_ignored:
            detail_parts.append(".private is not ignored")
        detail = "; ".join(detail_parts)
    else:
        detail = "Private prep docs are outside public claim paths and .private is ignored."
    return completion_row(
        "private_boundary",
        blockers == 0,
        PROJECT_ROOT / ".gitignore",
        blockers,
        detail,
    )


def private_history_row(history_hits: list[str]) -> dict:
    blockers = len(history_hits)
    if blockers:
        preview = "; ".join(history_hits[:3])
        detail = f"private prep path(s) in branch history: {preview}"
    else:
        detail = "No private prep paths found in branch history."
    return completion_row(
        "private_history",
        blockers == 0,
        PROJECT_ROOT,
        blockers,
        detail,
    )


def completion_row(gate_name: str, passed: bool, evidence_path: Path, blocker_count: int, detail: str) -> dict:
    return {
        "gate_name": gate_name,
        "gate_status": "pass" if passed else "fail",
        "evidence_path": display_path(evidence_path),
        "blocker_count": blocker_count,
        "detail": detail,
    }


def count_failed_portfolio_steps(rows: list[dict]) -> int:
    return sum(1 for row in rows if row.get("step_status") != "pass")


def relative_to_project(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def current_git_status_lines() -> list[str]:
    result = subprocess.run(
        ["git", "status", "--short"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return ["git status failed"]
    return [line for line in result.stdout.splitlines() if line.strip()]


def git_path_is_ignored(path: Path) -> bool:
    result = subprocess.run(
        ["git", "check-ignore", "-q", str(path)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def private_prep_history_hits() -> list[str]:
    hits: list[str] = []
    for private_path in sorted(PRIVATE_PREP_PUBLIC_PATHS):
        result = subprocess.run(
            ["git", "log", "HEAD", "--format=%h", "--", private_path],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            hits.append(f"git log failed for {private_path}")
            continue
        for commit_sha in [line.strip() for line in result.stdout.splitlines() if line.strip()]:
            hits.append(f"{commit_sha} {private_path}")
    return hits


def read_completion_gate(path: Path | None = None) -> list[dict]:
    target = path or REPORT_DIR / "completion_gate.csv"
    return read_csv_rows(target) if target.exists() else []
