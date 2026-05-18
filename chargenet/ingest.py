from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from .http_client import fetch_text
from .paths import RAW_DIR, ensure_project_dirs


PILOT_COUNTRIES = ["BE", "DE", "FR", "NL"]

OVERPASS_ENDPOINT = "https://overpass-api.de/api/interpreter"
GISCO_NUTS_LEVEL0_URL = "https://gisco-services.ec.europa.eu/distribution/v2/nuts/geojson/NUTS_RG_20M_2024_4326_LEVL_0.geojson"
GISCO_NUTS_LEVEL3_URL = "https://gisco-services.ec.europa.eu/distribution/v2/nuts/geojson/NUTS_RG_20M_2024_4326_LEVL_3.geojson"
GISCO_NUTS_ATTR_URL = "https://gisco-services.ec.europa.eu/distribution/v2/nuts/csv/NUTS_AT_2024.csv"
EUROSTAT_POPULATION_SAMPLE_URL = (
    "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
    "demo_r_pjanaggr3?geo=BE100&sex=T&age=TOTAL&unit=NR&time=2025&lang=en"
)
EUROSTAT_POPULATION_PILOT_URL = (
    "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
    "demo_r_pjanaggr3?sex=T&age=TOTAL&unit=NR&time=2025&lang=en"
)
OPEN_CHARGE_MAP_SAMPLE_URL = "https://api.openchargemap.io/v3/poi/?output=json&countrycode=DE&maxresults=3&compact=true&verbose=false"

OSM_CHARGERS_QUERY = """
[out:json][timeout:25];
(
  node["amenity"="charging_station"](50.83,4.30,50.88,4.40);
  way["amenity"="charging_station"](50.83,4.30,50.88,4.40);
  relation["amenity"="charging_station"](50.83,4.30,50.88,4.40);
);
out body 20;
""".strip()

OSM_CANDIDATES_QUERY = """
[out:json][timeout:25];
(
  node["highway"="services"](50.83,4.30,50.95,4.55);
  way["highway"="services"](50.83,4.30,50.95,4.55);
  node["amenity"="fuel"](50.83,4.30,50.95,4.55);
);
out body center 20;
""".strip()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def write_snapshot(name: str, source_id: str, url: str, content: str, *, query: str | None = None, run_id: str | None = None) -> Path:
    ensure_project_dirs()
    run_id = run_id or make_run_id()
    snapshot_path = RAW_DIR / f"{name}.json" if name.endswith("_json") else RAW_DIR / name
    snapshot_path.write_text(content, encoding="utf-8")

    run_dir = RAW_DIR / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    run_snapshot_path = run_dir / snapshot_path.name
    run_snapshot_path.write_text(content, encoding="utf-8")

    manifest = {
        "manifest_schema_version": "phase3_sample_v1",
        "run_id": run_id,
        "snapshot_name": name,
        "source_id": source_id,
        "url": url,
        "query": query,
        "retrieved_at_utc": utc_now(),
        "content_sha256": hashlib.sha256(snapshot_path.read_bytes()).hexdigest(),
        "query_hash": stable_hash(query) if query else None,
        "path": str(snapshot_path.as_posix()),
        "immutable_run_path": str(run_snapshot_path.as_posix()),
    }
    manifest_path = RAW_DIR / f"{snapshot_path.stem}.manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (run_dir / manifest_path.name).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return snapshot_path


def overpass_url(query: str) -> str:
    return f"{OVERPASS_ENDPOINT}?data={quote(query)}"


def make_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def ingest_osm_chargers_sample(run_id: str | None = None) -> Path:
    url = overpass_url(OSM_CHARGERS_QUERY)
    content = fetch_text(url)
    return write_snapshot("osm_chargers_brussels_sample.json", "osm_overpass", url, content, query=OSM_CHARGERS_QUERY, run_id=run_id)


def ingest_osm_candidates_sample(run_id: str | None = None) -> Path:
    url = overpass_url(OSM_CANDIDATES_QUERY)
    content = fetch_text(url)
    return write_snapshot("osm_candidate_pois_brussels_sample.json", "osm_overpass", url, content, query=OSM_CANDIDATES_QUERY, run_id=run_id)


def ingest_gisco_nuts_level0(run_id: str | None = None) -> Path:
    content = fetch_text(GISCO_NUTS_LEVEL0_URL)
    return write_snapshot("gisco_nuts_2024_level0.geojson", "gisco_nuts", GISCO_NUTS_LEVEL0_URL, content, run_id=run_id)


def ingest_gisco_nuts_level3(run_id: str | None = None) -> Path:
    content = fetch_text(GISCO_NUTS_LEVEL3_URL)
    return write_snapshot("gisco_nuts_2024_level3.geojson", "gisco_nuts", GISCO_NUTS_LEVEL3_URL, content, run_id=run_id)


def ingest_gisco_nuts_attributes(run_id: str | None = None) -> Path:
    run_id = run_id or make_run_id()
    content = fetch_text(GISCO_NUTS_ATTR_URL)
    target = RAW_DIR / "gisco_nuts_2024_attributes.csv"
    ensure_project_dirs()
    target.write_text(content, encoding="utf-8")
    run_dir = RAW_DIR / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    run_target = run_dir / target.name
    run_target.write_text(content, encoding="utf-8")
    manifest = {
        "manifest_schema_version": "phase3_sample_v1",
        "run_id": run_id,
        "snapshot_name": target.name,
        "source_id": "gisco_nuts",
        "url": GISCO_NUTS_ATTR_URL,
        "query": None,
        "retrieved_at_utc": utc_now(),
        "content_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        "path": str(target.as_posix()),
        "immutable_run_path": str(run_target.as_posix()),
    }
    (RAW_DIR / "gisco_nuts_2024_attributes.manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (run_dir / "gisco_nuts_2024_attributes.manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return target


def ingest_eurostat_population_sample(run_id: str | None = None) -> Path:
    content = fetch_text(EUROSTAT_POPULATION_SAMPLE_URL)
    return write_snapshot("eurostat_population_be100_2025_sample.json", "eurostat_population", EUROSTAT_POPULATION_SAMPLE_URL, content, run_id=run_id)


def ingest_eurostat_population_pilot(run_id: str | None = None) -> Path:
    content = fetch_text(EUROSTAT_POPULATION_PILOT_URL)
    return write_snapshot(
        "eurostat_population_nuts3_2025_pilot.json",
        "eurostat_population",
        EUROSTAT_POPULATION_PILOT_URL,
        content,
        run_id=run_id,
    )


def probe_open_charge_map_without_key(run_id: str | None = None) -> Path:
    try:
        content = fetch_text(OPEN_CHARGE_MAP_SAMPLE_URL, retries=0)
        status = {"status": "unexpected_success", "body": content[:1000]}
    except Exception as exc:  # Intentional: capture API-key failure evidence as raw probe metadata.
        error_text = str(exc)
        status_name = "expected_failure_without_api_key" if "HTTP 403" in error_text and "API key" in error_text else "unexpected_probe_failure"
        status = {"status": status_name, "error": error_text}
    return write_snapshot(
        "open_charge_map_no_key_probe.json",
        "open_charge_map",
        OPEN_CHARGE_MAP_SAMPLE_URL,
        json.dumps(status, indent=2) + "\n",
        run_id=run_id,
    )


def ingest_all_samples() -> list[Path]:
    run_id = make_run_id()
    steps = [
        ingest_osm_chargers_sample,
        ingest_osm_candidates_sample,
        ingest_gisco_nuts_level0,
        ingest_gisco_nuts_attributes,
        ingest_eurostat_population_sample,
        probe_open_charge_map_without_key,
    ]
    paths: list[Path] = []
    errors: list[str] = []
    for step in steps:
        try:
            paths.append(step(run_id))
        except Exception as exc:
            errors.append(f"{step.__name__}: {exc}")
    if errors:
        raise RuntimeError("Sample ingest failed: " + " | ".join(errors))
    return paths
