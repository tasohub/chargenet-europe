from __future__ import annotations

import csv
import hashlib
import json
import re
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .http_client import FetchError, fetch_text
from .ingest import make_run_id, overpass_url, stable_hash
from .paths import MART_DIR, RAW_DIR, ensure_project_dirs


SAFE_DEFAULT_MAX_JOBS = 1
SAFE_BATCH_MAX_JOBS = 25
DEFAULT_PILOT_COUNTRIES = ("BE", "DE", "FR", "NL")
DEFAULT_EXTRACTS = ("charging_stations", "candidate_fuel", "candidate_services")
LATEST_LOG = MART_DIR / "osm_tile_execution_log_latest.csv"
ALL_LOG = MART_DIR / "osm_tile_execution_log_all.csv"
LOG_FIELDNAMES = [
    "run_id",
    "tile_job_id",
    "extract_slug",
    "country_code",
    "nuts_id",
    "demand_zone_id",
    "status",
    "element_count",
    "raw_path",
    "manifest_path",
    "query_hash",
    "started_at_utc",
    "finished_at_utc",
    "error",
]


def run_osm_tile_smoke(
    *,
    max_jobs: int = SAFE_DEFAULT_MAX_JOBS,
    country_code: str | None = "BE",
    extract_slug: str | None = "charging_stations",
    delay_seconds: float = 2.0,
    output_limit: int = 25,
    timeout_seconds: int = 60,
    exclude_tile_job_ids: set[str] | None = None,
) -> dict:
    ensure_project_dirs()
    tile_plan = MART_DIR / "osm_pilot_tile_plan.csv"
    planned_jobs = select_jobs(
        read_csv_rows(tile_plan),
        max_jobs=max_jobs,
        country_code=country_code,
        extract_slug=extract_slug,
        exclude_tile_job_ids=exclude_tile_job_ids,
    )
    run_id = make_run_id()
    run_dir = RAW_DIR / "osm_tile_runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    log_rows = []
    for index, job in enumerate(planned_jobs):
        if index:
            time.sleep(delay_seconds)
        query = build_overpass_query(job, output_limit=output_limit)
        url = overpass_url(query)
        started_at = utc_now()
        safe_name = safe_tile_filename(job["tile_job_id"])
        raw_path = run_dir / f"{safe_name}.json"
        manifest_path = run_dir / f"{safe_name}.manifest.json"
        try:
            content = fetch_text(url, timeout=timeout_seconds, retries=int(job.get("max_retries") or 0), delay_seconds=delay_seconds)
            raw_path.write_text(content, encoding="utf-8")
            payload = json.loads(content)
            element_count = len(payload.get("elements", []))
            status = "fetched"
            error = ""
            write_manifest(manifest_path, run_id, job, url, query, raw_path)
        except (FetchError, json.JSONDecodeError, OSError) as exc:
            element_count = 0
            status = "fetch_failed"
            error = str(exc)
        log_rows.append(
            {
                "run_id": run_id,
                "tile_job_id": job["tile_job_id"],
                "extract_slug": job["extract_slug"],
                "country_code": job["country_code"],
                "nuts_id": job["nuts_id"],
                "demand_zone_id": job.get("demand_zone_id", ""),
                "status": status,
                "element_count": element_count,
                "raw_path": str(raw_path.as_posix()) if raw_path.exists() else "",
                "manifest_path": str(manifest_path.as_posix()) if manifest_path.exists() else "",
                "query_hash": stable_hash(query),
                "started_at_utc": started_at,
                "finished_at_utc": utc_now(),
                "error": error[:500],
            }
        )

    log_path = run_dir / "tile_execution_log.csv"
    write_log(log_path, log_rows)
    write_log(LATEST_LOG, log_rows)
    all_log = rebuild_osm_tile_execution_log_all()
    return {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "latest_log": str(LATEST_LOG),
        "all_log": str(all_log),
        "selected_jobs": len(planned_jobs),
        "tile_job_ids": [job["tile_job_id"] for job in planned_jobs],
        "fetched_jobs": sum(1 for row in log_rows if row["status"] == "fetched"),
        "failed_jobs": sum(1 for row in log_rows if row["status"] == "fetch_failed"),
    }


def run_osm_pilot_smoke(
    *,
    countries: list[str] | tuple[str, ...] = DEFAULT_PILOT_COUNTRIES,
    extracts: list[str] | tuple[str, ...] = DEFAULT_EXTRACTS,
    max_jobs_per_combo: int = SAFE_DEFAULT_MAX_JOBS,
    delay_seconds: float = 2.0,
    output_limit: int = 25,
    timeout_seconds: int = 60,
    dry_run: bool = False,
) -> dict:
    ensure_project_dirs()
    tile_plan = MART_DIR / "osm_pilot_tile_plan.csv"
    rows = read_csv_rows(tile_plan)
    rebuild_osm_tile_execution_log_all()
    completed = read_fetched_tile_job_ids(ALL_LOG)
    combo_results = []
    attempted = 0
    for country in countries:
        for extract in extracts:
            try:
                selected = select_jobs(
                    rows,
                    max_jobs=max_jobs_per_combo,
                    country_code=country,
                    extract_slug=extract,
                    exclude_tile_job_ids=completed,
                )
            except ValueError as exc:
                combo_results.append(
                    {
                        "country_code": country,
                        "extract_slug": extract,
                        "status": "skipped",
                        "reason": str(exc),
                    }
                )
                continue

            if dry_run:
                combo_results.append(
                    {
                        "country_code": country,
                        "extract_slug": extract,
                        "status": "planned",
                        "selected_jobs": len(selected),
                        "tile_job_ids": [job["tile_job_id"] for job in selected],
                    }
                )
                completed.update(job["tile_job_id"] for job in selected)
                continue

            if attempted and delay_seconds > 0:
                time.sleep(delay_seconds)
            result = run_osm_tile_smoke(
                max_jobs=max_jobs_per_combo,
                country_code=country,
                extract_slug=extract,
                delay_seconds=delay_seconds,
                output_limit=output_limit,
                timeout_seconds=timeout_seconds,
                exclude_tile_job_ids=completed,
            )
            attempted += 1
            completed = read_fetched_tile_job_ids(ALL_LOG)
            combo_results.append(
                {
                    "country_code": country,
                    "extract_slug": extract,
                    "status": "completed",
                    **result,
                }
            )

    fetched_jobs = sum(int(row.get("fetched_jobs") or 0) for row in combo_results if row.get("status") == "completed")
    failed_jobs = sum(int(row.get("failed_jobs") or 0) for row in combo_results if row.get("status") == "completed")
    return {
        "dry_run": dry_run,
        "countries": list(countries),
        "extracts": list(extracts),
        "max_jobs_per_combo": max_jobs_per_combo,
        "combo_count": len(combo_results),
        "runs_attempted": attempted,
        "fetched_jobs": fetched_jobs,
        "failed_jobs": failed_jobs,
        "skipped_combos": sum(1 for row in combo_results if row.get("status") == "skipped"),
        "all_log": str(ALL_LOG),
        "results": combo_results,
    }


def run_osm_tile_batch(
    *,
    max_jobs: int = 9,
    countries: list[str] | tuple[str, ...] | None = None,
    extracts: list[str] | tuple[str, ...] | None = None,
    delay_seconds: float = 2.0,
    output_limit: int = 25,
    timeout_seconds: int = 60,
    dry_run: bool = True,
) -> dict:
    ensure_project_dirs()
    tile_plan = MART_DIR / "osm_pilot_tile_plan.csv"
    plan_rows = read_csv_rows(tile_plan)
    rebuild_osm_tile_execution_log_all()
    completed = read_fetched_tile_job_ids(ALL_LOG)
    selected_jobs = select_batch_jobs(
        plan_rows,
        max_jobs=max_jobs,
        countries=countries,
        extracts=extracts,
        exclude_tile_job_ids=completed,
    )
    before_progress = osm_tile_progress_summary(plan_rows, read_csv_rows(ALL_LOG))

    if dry_run:
        return {
            "dry_run": True,
            "selected_jobs": len(selected_jobs),
            "tile_job_ids": [job["tile_job_id"] for job in selected_jobs],
            "countries": sorted({job["country_code"] for job in selected_jobs}),
            "extracts": sorted({job["extract_slug"] for job in selected_jobs}),
            "progress_before": before_progress,
            "all_log": str(ALL_LOG),
        }

    run_id = make_run_id()
    run_dir = RAW_DIR / "osm_tile_runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    log_rows = []
    for index, job in enumerate(selected_jobs):
        if index:
            time.sleep(delay_seconds)
        query = build_overpass_query(job, output_limit=output_limit)
        url = overpass_url(query)
        started_at = utc_now()
        safe_name = safe_tile_filename(job["tile_job_id"])
        raw_path = run_dir / f"{safe_name}.json"
        manifest_path = run_dir / f"{safe_name}.manifest.json"
        try:
            content = fetch_text(url, timeout=timeout_seconds, retries=int(job.get("max_retries") or 0), delay_seconds=delay_seconds)
            raw_path.write_text(content, encoding="utf-8")
            payload = json.loads(content)
            element_count = len(payload.get("elements", []))
            status = "fetched"
            error = ""
            write_manifest(manifest_path, run_id, job, url, query, raw_path, schema_version="phase3_osm_tile_batch_v1")
        except (FetchError, json.JSONDecodeError, OSError) as exc:
            element_count = 0
            status = "fetch_failed"
            error = str(exc)
        log_rows.append(
            {
                "run_id": run_id,
                "tile_job_id": job["tile_job_id"],
                "extract_slug": job["extract_slug"],
                "country_code": job["country_code"],
                "nuts_id": job["nuts_id"],
                "demand_zone_id": job.get("demand_zone_id", ""),
                "status": status,
                "element_count": element_count,
                "raw_path": str(raw_path.as_posix()) if raw_path.exists() else "",
                "manifest_path": str(manifest_path.as_posix()) if manifest_path.exists() else "",
                "query_hash": stable_hash(query),
                "started_at_utc": started_at,
                "finished_at_utc": utc_now(),
                "error": error[:500],
            }
        )

    log_path = run_dir / "tile_execution_log.csv"
    write_log(log_path, log_rows)
    write_log(LATEST_LOG, log_rows)
    all_log = rebuild_osm_tile_execution_log_all()
    return {
        "dry_run": False,
        "run_id": run_id,
        "run_dir": str(run_dir),
        "latest_log": str(LATEST_LOG),
        "all_log": str(all_log),
        "selected_jobs": len(selected_jobs),
        "tile_job_ids": [job["tile_job_id"] for job in selected_jobs],
        "fetched_jobs": sum(1 for row in log_rows if row["status"] == "fetched"),
        "failed_jobs": sum(1 for row in log_rows if row["status"] == "fetch_failed"),
        "progress_after": osm_tile_progress_summary(plan_rows, read_csv_rows(ALL_LOG)),
    }


def select_batch_jobs(
    rows: list[dict],
    *,
    max_jobs: int,
    countries: list[str] | tuple[str, ...] | None = None,
    extracts: list[str] | tuple[str, ...] | None = None,
    exclude_tile_job_ids: set[str] | None = None,
) -> list[dict]:
    if max_jobs < 1 or max_jobs > SAFE_BATCH_MAX_JOBS:
        raise ValueError(f"run-osm-tile-batch requires max_jobs between 1 and {SAFE_BATCH_MAX_JOBS}")
    country_filter = {country.strip() for country in countries or [] if country.strip()}
    extract_filter = {extract.strip() for extract in extracts or [] if extract.strip()}
    excluded = exclude_tile_job_ids or set()
    selected = []
    for row in rows:
        if row.get("tile_job_id") in excluded:
            continue
        if country_filter and row.get("country_code") not in country_filter:
            continue
        if extract_filter and row.get("extract_slug") not in extract_filter:
            continue
        selected.append(row)
        if len(selected) >= max_jobs:
            break
    if not selected:
        raise ValueError("No OSM tile jobs matched the requested batch filters")
    return selected


def osm_tile_progress_summary(plan_rows: list[dict], log_rows: list[dict]) -> dict:
    planned_ids = {row["tile_job_id"] for row in plan_rows if row.get("tile_job_id")}
    fetched_ids = {row["tile_job_id"] for row in log_rows if row.get("tile_job_id") in planned_ids and row.get("status") == "fetched"}
    failed_attempts = sum(
        1
        for row in log_rows
        if row.get("tile_job_id") in planned_ids
        and row.get("status") == "fetch_failed"
        and row.get("tile_job_id") not in fetched_ids
    )
    planned_jobs = len(planned_ids)
    fetched_jobs = len(fetched_ids)
    remaining_jobs = max(planned_jobs - fetched_jobs, 0)
    return {
        "planned_jobs": planned_jobs,
        "fetched_jobs": fetched_jobs,
        "failed_attempts": failed_attempts,
        "remaining_jobs": remaining_jobs,
        "completion_pct": round(fetched_jobs / planned_jobs, 6) if planned_jobs else 0.0,
    }


def current_osm_tile_progress() -> dict:
    tile_plan = MART_DIR / "osm_pilot_tile_plan.csv"
    rebuild_osm_tile_execution_log_all()
    return osm_tile_progress_summary(read_csv_rows(tile_plan), read_csv_rows(ALL_LOG))


def current_osm_fetch_gate(*, latest_only: bool = False, output_limit: int = 20) -> dict:
    tile_plan = MART_DIR / "osm_pilot_tile_plan.csv"
    rebuild_osm_tile_execution_log_all()
    log_path = LATEST_LOG if latest_only else ALL_LOG
    gate = osm_fetch_gate_summary(read_csv_rows(tile_plan), read_csv_rows(log_path), output_limit=output_limit)
    gate["log_scope"] = "latest" if latest_only else "all"
    gate["log_path"] = str(log_path)
    return gate


def osm_fetch_gate_summary(
    plan_rows: list[dict],
    log_rows: list[dict],
    *,
    output_limit: int = 20,
    base_dir: Path | None = None,
) -> dict:
    planned_ids = {row["tile_job_id"] for row in plan_rows if row.get("tile_job_id")}
    known_rows = [row for row in log_rows if row.get("tile_job_id") in planned_ids]
    fetched_rows = [row for row in known_rows if row.get("status") == "fetched"]
    fetched_counts = Counter(row.get("tile_job_id", "") for row in fetched_rows if row.get("tile_job_id"))
    unknown_tile_ids = sorted({row.get("tile_job_id", "") for row in log_rows if row.get("tile_job_id") and row.get("tile_job_id") not in planned_ids})
    duplicate_ids = sorted(tile_job_id for tile_job_id, count in fetched_counts.items() if count > 1)
    nonterminal_rows = [row for row in log_rows if row.get("status") not in {"fetched", "fetch_failed"}]

    missing_raw = 0
    missing_manifest = 0
    manifest_hash_mismatches = 0
    manifest_immutable_missing = 0
    for row in fetched_rows:
        raw_path = resolve_logged_path(row.get("raw_path", ""), base_dir=base_dir)
        manifest_path = resolve_logged_path(row.get("manifest_path", ""), base_dir=base_dir)
        raw_exists = raw_path is not None and raw_path.exists()
        manifest_exists = manifest_path is not None and manifest_path.exists()
        if not raw_exists:
            missing_raw += 1
        if not manifest_exists:
            missing_manifest += 1
        if not raw_exists or not manifest_exists:
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            manifest_hash_mismatches += 1
            continue
        expected_hash = manifest.get("content_sha256", "")
        actual_hash = hashlib.sha256(raw_path.read_bytes()).hexdigest()
        if expected_hash != actual_hash:
            manifest_hash_mismatches += 1
        immutable_path = resolve_logged_path(manifest.get("immutable_run_path", ""), base_dir=base_dir)
        if immutable_path is None or not immutable_path.exists():
            manifest_immutable_missing += 1

    output_limit_hits = sum(1 for row in fetched_rows if str(row.get("element_count", "")) == str(output_limit))
    historical_failed_attempts = sum(1 for row in known_rows if row.get("status") == "fetch_failed")
    progress = osm_tile_progress_summary(plan_rows, log_rows)
    passed = (
        progress["failed_attempts"] == 0
        and not duplicate_ids
        and missing_raw == 0
        and missing_manifest == 0
        and manifest_hash_mismatches == 0
        and manifest_immutable_missing == 0
        and not unknown_tile_ids
        and not nonterminal_rows
    )
    return {
        "passed": passed,
        "progress": progress,
        "failed_attempts": progress["failed_attempts"],
        "historical_failed_attempts": historical_failed_attempts,
        "fetched_row_count": len(fetched_rows),
        "duplicate_fetched_tile_ids": duplicate_ids,
        "missing_raw_count": missing_raw,
        "missing_manifest_count": missing_manifest,
        "manifest_hash_mismatch_count": manifest_hash_mismatches,
        "manifest_immutable_missing_count": manifest_immutable_missing,
        "unknown_tile_ids": unknown_tile_ids,
        "nonterminal_status_count": len(nonterminal_rows),
        "output_limit": output_limit,
        "output_limit_hit_count": output_limit_hits,
    }


def resolve_logged_path(value: str, *, base_dir: Path | None = None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    if path.is_absolute():
        return path
    return (base_dir or Path.cwd()) / path


def select_jobs(
    rows: list[dict],
    *,
    max_jobs: int,
    country_code: str | None,
    extract_slug: str | None,
    exclude_tile_job_ids: set[str] | None = None,
) -> list[dict]:
    if max_jobs < 1 or max_jobs > 5:
        raise ValueError("run-osm-tile-smoke requires max_jobs between 1 and 5")
    selected = []
    excluded = exclude_tile_job_ids or set()
    for row in rows:
        if row.get("tile_job_id") in excluded:
            continue
        if country_code and row.get("country_code") != country_code:
            continue
        if extract_slug and row.get("extract_slug") != extract_slug:
            continue
        selected.append(row)
        if len(selected) >= max_jobs:
            break
    if not selected:
        raise ValueError("No OSM tile jobs matched the requested smoke-run filters")
    return selected


def build_overpass_query(job: dict, *, output_limit: int = 25, timeout_seconds: int = 25) -> str:
    key, value = parse_osm_filter(job["osm_filter"])
    south = format_coordinate(job["bbox_south"])
    west = format_coordinate(job["bbox_west"])
    north = format_coordinate(job["bbox_north"])
    east = format_coordinate(job["bbox_east"])
    bbox = f"({south},{west},{north},{east})"
    return "\n".join(
        [
            f"[out:json][timeout:{timeout_seconds}];",
            "(",
            f'  node["{key}"="{value}"]{bbox};',
            f'  way["{key}"="{value}"]{bbox};',
            f'  relation["{key}"="{value}"]{bbox};',
            ");",
            f"out body center {output_limit};",
        ]
    )


def parse_osm_filter(value: str) -> tuple[str, str]:
    match = re.fullmatch(r'([A-Za-z0-9:_-]+)="([^"]+)"', value.strip())
    if not match:
        raise ValueError(f"Unsupported OSM filter expression: {value}")
    return match.group(1), match.group(2)


def format_coordinate(value: str | float) -> str:
    return f"{float(value):.6f}".rstrip("0").rstrip(".")


def write_manifest(path: Path, run_id: str, job: dict, url: str, query: str, raw_path: Path, *, schema_version: str = "phase3_osm_tile_smoke_v1") -> None:
    manifest = {
        "manifest_schema_version": schema_version,
        "run_id": run_id,
        "tile_job_id": job["tile_job_id"],
        "source_id": "osm_overpass",
        "url": url,
        "query": query,
        "retrieved_at_utc": utc_now(),
        "content_sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest(),
        "query_hash": stable_hash(query),
        "path": str(raw_path.as_posix()),
        "immutable_run_path": str(raw_path.as_posix()),
    }
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def write_log(path: Path, rows: list[dict]) -> Path:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=LOG_FIELDNAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in LOG_FIELDNAMES})
    return path


def rebuild_osm_tile_execution_log_all() -> Path:
    ensure_project_dirs()
    run_root = RAW_DIR / "osm_tile_runs"
    rows = []
    if run_root.exists():
        for log_path in sorted(run_root.glob("*/tile_execution_log.csv")):
            rows.extend(read_csv_rows(log_path))
    rows.sort(key=lambda row: (row.get("started_at_utc", ""), row.get("tile_job_id", "")))
    return write_log(ALL_LOG, rows)


def read_fetched_tile_job_ids(path: Path = ALL_LOG) -> set[str]:
    return {row["tile_job_id"] for row in read_csv_rows(path) if row.get("status") == "fetched" and row.get("tile_job_id")}


def read_csv_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def safe_tile_filename(tile_job_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", tile_job_id)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
