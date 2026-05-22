from __future__ import annotations

import csv
from pathlib import Path

from .paths import PROJECT_ROOT, REPORT_DIR, ensure_project_dirs


PUBLIC_CLAIM_FIELDNAMES = [
    "file_path",
    "line_number",
    "claim_phrase",
    "claim_status",
    "line_text",
    "review_note",
]

OVERCLAIM_PATTERNS = {
    "complete OSM coverage": "Avoid implying the current capped smoke/batch OSM extract is complete.",
    "guaranteed": "Avoid certainty language; ChargeNet is an early-stage decision-support layer.",
    "investment advice": "Keep investment-advice wording only inside explicit disclaimers.",
    "investment-grade": "Keep investment-grade wording only inside explicit limitations.",
    "optimal sites": "Prefer candidate or shortlist language unless describing a formal model objective.",
}

SAFE_NEGATION_PREFIXES = ("not ", "not an ", "not a ", "no ")
SAFE_GUARDRAIL_MARKERS = ("must not drift into", "drift from", "rather than", "avoid implying", "do not describe", "flags", "such as")


def default_public_claim_paths() -> list[Path]:
    return [
        PROJECT_ROOT / "app.py",
        PROJECT_ROOT / "docs" / "chargenet-europe" / "pipeline-drift-monitoring.md",
        PROJECT_ROOT / "docs" / "chargenet-europe" / "pipeline-v2-operating-model.md",
        PROJECT_ROOT / "docs" / "chargenet-europe" / "autonomous-runbook.md",
        PROJECT_ROOT / "docs" / "chargenet-europe" / "qa-governance-framework.md",
        PROJECT_ROOT / "docs" / "chargenet-europe" / "candidate-lineage-walkthrough.md",
        PROJECT_ROOT / "docs" / "chargenet-europe" / "completion-gate.md",
        PROJECT_ROOT / "docs" / "chargenet-europe" / "project-status.md",
    ]


def scan_public_claims(paths: list[Path], *, root: Path = PROJECT_ROOT) -> list[dict]:
    findings = []
    for path in paths:
        if not path.exists():
            continue
        for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            line = raw_line.strip()
            lower_line = line.lower()
            for phrase, review_note in OVERCLAIM_PATTERNS.items():
                if phrase.lower() not in lower_line:
                    continue
                if is_safe_disclaimer(lower_line, phrase.lower()):
                    continue
                findings.append(
                    {
                        "file_path": str(path.relative_to(root)) if path.is_relative_to(root) else str(path),
                        "line_number": line_number,
                        "claim_phrase": phrase,
                        "claim_status": "needs_review",
                        "line_text": line,
                        "review_note": review_note,
                    }
                )
    return sorted(findings, key=lambda row: (row["file_path"], int(row["line_number"]), row["claim_phrase"]))


def write_public_claim_gate(
    paths: list[Path] | None = None,
    *,
    output_path: Path | None = None,
    root: Path = PROJECT_ROOT,
) -> Path:
    ensure_project_dirs()
    target = output_path or REPORT_DIR / "public_claim_gate.csv"
    findings = scan_public_claims(paths or default_public_claim_paths(), root=root)
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=PUBLIC_CLAIM_FIELDNAMES)
        writer.writeheader()
        writer.writerows(findings)
    return target


def is_safe_disclaimer(line: str, phrase: str) -> bool:
    position = line.find(phrase)
    if position < 0:
        return False
    prefix_window = line[max(0, position - 12) : position]
    guardrail_window = line[:position]
    return any(prefix_window.endswith(prefix) for prefix in SAFE_NEGATION_PREFIXES) or any(
        marker in guardrail_window for marker in SAFE_GUARDRAIL_MARKERS
    )
