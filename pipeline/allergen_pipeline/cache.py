"""Versioned, dated caches. Failed requests never replace useful observations."""
from __future__ import annotations
import json
from datetime import date
from pathlib import Path

CACHE_VERSION = 2
POSITIVE_TTL_DAYS = 14
NEGATIVE_TTL_DAYS = 1

def observation_date(value: object) -> date | None:
    try:
        return date.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        return None

def is_fresh(record: dict | None, now: date | None = None) -> bool:
    if not record or record.get('_cache_version') != CACHE_VERSION:
        return False
    checked = observation_date(record.get('_checked_on'))
    if checked is None:
        return False
    age = ((now or date.today()) - checked).days
    ttl = NEGATIVE_TTL_DAYS if record.get('_not_found') else POSITIVE_TTL_DAYS
    return 0 <= age < ttl

def observed_record(payload: dict | None, previous: dict | None = None) -> dict:
    today = date.today().isoformat()
    positive_fields = ('contains', 'may_contain', 'allergen_ids', 'trace_ids')
    previous_positive = previous and any(previous.get(key) for key in positive_fields)
    silent = payload is not None and not any(payload.get(key) for key in positive_fields)
    if previous and not previous.get('_not_found') and (payload is None or (previous_positive and silent)):
        # A missing product must not clear an earlier positive observation.
        result = dict(previous)
        result['_stale'] = True
    else:
        result = dict(payload) if payload is not None else {'_not_found': True}
        result['observed_on'] = today
    result.update(_cache_version=CACHE_VERSION, _checked_on=today)
    return result

def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    staging = path.with_suffix(path.suffix + '.tmp')
    staging.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
    staging.replace(path)
