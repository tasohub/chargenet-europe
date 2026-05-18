from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = PROJECT_ROOT / "data" / "chargenet"
RAW_DIR = DATA_ROOT / "raw"
CLEAN_DIR = DATA_ROOT / "clean"
MART_DIR = DATA_ROOT / "marts"
REPORT_DIR = PROJECT_ROOT / "reports" / "chargenet"
CONFIG_DIR = PROJECT_ROOT / "config" / "chargenet"


def ensure_project_dirs() -> None:
    for path in [RAW_DIR, CLEAN_DIR, MART_DIR, REPORT_DIR, CONFIG_DIR]:
        path.mkdir(parents=True, exist_ok=True)

