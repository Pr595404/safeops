"""Load synthetic incident data from the local JSON catalog."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any


def resolve_catalog_path() -> Path:
    env_override = os.environ.get("SAFEOPS_DATA_PATH") or os.environ.get("SAFEOPS_INCIDENTS_PATH")
    if env_override:
        return Path(env_override).resolve()
    repo_path = Path(__file__).resolve().parents[2] / "data" / "incidents.json"
    if repo_path.exists():
        return repo_path
    package_path = Path(__file__).resolve().parent / "data" / "incidents.json"
    if package_path.exists():
        return package_path
    return repo_path


CATALOG_PATH = resolve_catalog_path()


class CatalogError(KeyError):
    """Requested synthetic record is missing."""


@lru_cache(maxsize=1)
def load_catalog() -> dict[str, Any]:
    path = resolve_catalog_path()
    with path.open(encoding="utf-8") as handle:
        payload: dict[str, Any] = json.load(handle)
    return payload


def incidents() -> list[dict[str, Any]]:
    return list(load_catalog()["incidents"])


def get_incident(incident_id: str) -> dict[str, Any]:
    for row in incidents():
        if row["incident_id"] == incident_id:
            return row
    raise CatalogError(f"unknown incident_id: {incident_id}")


def get_resource(name_or_id: str) -> dict[str, Any]:
    resources: dict[str, Any] = load_catalog()["resources"]
    if name_or_id in resources:
        return resources[name_or_id]
    for row in resources.values():
        if row["resource_id"] == name_or_id or row["name"] == name_or_id:
            return row
    raise CatalogError(f"unknown resource: {name_or_id}")
