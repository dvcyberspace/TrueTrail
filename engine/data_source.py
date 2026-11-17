"""Data source loader for the network correlation engine.

Loads TrueTrail canonical records (transactions, calls, ip_sessions) from:

1. The FastAPI backend at http://localhost:8000 (preferred).
2. The frozen JSON copies in data/canonical/*.json (fallback).

The backend is *not* required for the demo — if it is not running, the
canonical JSON files are used transparently.
"""
import json
import os
from typing import Any, Dict, List

try:
    import requests
except ImportError:  # requests not installed -> fallback only
    requests = None


API_BASE = os.environ.get("TRUETRAIL_API", "http://localhost:8000")

_CANONICAL_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "canonical",
)

_AVAILABILITY_TIMEOUT = 2       # seconds for the /ingestion/summary probe
_FETCH_TIMEOUT = 15             # seconds for actual record fetches
_MAX_LIMIT = 50000              # backend max per the handoff doc


def _api_available() -> bool:
    if requests is None:
        return False
    try:
        response = requests.get(
            f"{API_BASE}/ingestion/summary",
            timeout=_AVAILABILITY_TIMEOUT,
        )
        return response.status_code == 200
    except Exception:
        return False


def _fetch_from_api(record_type: str) -> List[Dict[str, Any]]:
    response = requests.get(
        f"{API_BASE}/records/{record_type}",
        params={"limit": _MAX_LIMIT},
        timeout=_FETCH_TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()
    if isinstance(payload, dict):
        return payload.get("items", [])
    return payload or []


def _load_from_canonical(record_type: str) -> List[Dict[str, Any]]:
    path = os.path.join(_CANONICAL_DIR, f"{record_type}.json")
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        if "items" in data:
            return data["items"]
        for value in data.values():
            if isinstance(value, list):
                return value
        return []
    return data or []


def load_records(record_type: str) -> List[Dict[str, Any]]:
    """Load one record type. API first, canonical JSON as fallback."""
    if _api_available():
        try:
            records = _fetch_from_api(record_type)
            if records:
                return records
        except Exception as error:
            print(f"[data_source] API fetch failed for {record_type}: {error}")
    return _load_from_canonical(record_type)


def load_transactions() -> List[Dict[str, Any]]:
    return load_records("transactions")


def load_calls() -> List[Dict[str, Any]]:
    return load_records("calls")


def load_ip_sessions() -> List[Dict[str, Any]]:
    return load_records("ip_sessions")


def load_all() -> Dict[str, List[Dict[str, Any]]]:
    return {
        "transactions": load_transactions(),
        "calls": load_calls(),
        "ip_sessions": load_ip_sessions(),
    }


def data_source_description() -> str:
    if _api_available():
        return f"FastAPI backend ({API_BASE})"
    return f"canonical JSON fallback ({_CANONICAL_DIR})"