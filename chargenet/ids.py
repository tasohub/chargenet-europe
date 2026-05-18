from __future__ import annotations


def osm_object_id(osm_type: str, osm_id: int | str) -> str:
    return f"osm:{osm_type}:{osm_id}"


def nuts_region_id(nuts_id: str, version: str = "2024") -> str:
    return f"nuts{version}:{nuts_id}"


def demand_zone_id(nuts_id: str, version: str = "2024") -> str:
    return f"dz:nuts{version}:{nuts_id}"


def candidate_site_id(osm_type: str, osm_id: int | str) -> str:
    return f"candidate:osm:{osm_type}:{osm_id}"


def scenario_id(slug: str) -> str:
    cleaned = slug.strip().lower().replace(" ", "-").replace("_", "-")
    return f"scenario:{cleaned}"
