"""Pull rows from the Search Console API with a service account.

Needs the ``api`` extra: pip install "searchdiff[api]".
The service account's e-mail must be added as a user of the property.
"""

from __future__ import annotations

import datetime as dt
from typing import Dict, List, Optional, Sequence

from .data import Row

SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"
ROW_LIMIT = 25000


def _session(key_path: str):
    try:
        from google.oauth2 import service_account
        from google.auth.transport.requests import AuthorizedSession
    except ImportError as exc:  # pragma: no cover
        raise ImportError("pip install 'searchdiff[api]' for the Search Console API") from exc
    creds = service_account.Credentials.from_service_account_file(key_path, scopes=[SCOPE])
    return AuthorizedSession(creds)


def query(site: str, key_path: str, start: dt.date, end: dt.date, dimensions: Sequence[str] = ("date", "page"),
          session=None, search_type: str = "web", data_state: str = "final") -> List[Dict]:
    """All rows for the dimensions, following ``startRow`` until the API runs dry."""
    import urllib.parse
    sess = session or _session(key_path)
    url = f"https://www.googleapis.com/webmasters/v3/sites/{urllib.parse.quote(site, safe='')}/searchAnalytics/query"
    out: List[Dict] = []
    start_row = 0
    while True:
        body = {"startDate": start.isoformat(), "endDate": end.isoformat(), "dimensions": list(dimensions),
                "rowLimit": ROW_LIMIT, "startRow": start_row, "type": search_type, "dataState": data_state}
        r = sess.post(url, json=body, timeout=120)
        r.raise_for_status()
        rows = r.json().get("rows", [])
        out.extend(rows)
        if len(rows) < ROW_LIMIT:
            break
        start_row += ROW_LIMIT
    return out


def to_rows(api_rows: Sequence[Dict], dimensions: Sequence[str]) -> List[Row]:
    di = {d: i for i, d in enumerate(dimensions)}
    out = []
    for r in api_rows:
        keys = r.get("keys", [])
        out.append(Row(
            date=dt.date.fromisoformat(keys[di["date"]]) if "date" in di else None,
            page=keys[di["page"]] if "page" in di else None,
            clicks=float(r.get("clicks", 0)), impressions=float(r.get("impressions", 0)),
            position=float(r["position"]) if "position" in r else None,
        ))
    return out


def fetch(site: str, key_path: str, start: dt.date, end: dt.date, dimensions: Sequence[str] = ("date", "page")) -> List[Row]:
    return to_rows(query(site, key_path, start, end, dimensions), dimensions)


def coverage(site: str, key_path: str, start: dt.date, end: dt.date, session=None) -> Dict[str, float]:
    """How much of the traffic the query dimension shows.  Search Console hides
    rare queries, so the sum over queries is usually well below the total; the
    sum over pages is not.  Analyse by page unless you need the words."""
    total = query(site, key_path, start, end, dimensions=(), session=session)
    q = query(site, key_path, start, end, dimensions=("query",), session=session)
    p = query(site, key_path, start, end, dimensions=("page",), session=session)
    tc = sum(r.get("clicks", 0) for r in total)
    return {"total_clicks": tc,
            "query_share": (sum(r.get("clicks", 0) for r in q) / tc) if tc else 0.0,
            "page_share": (sum(r.get("clicks", 0) for r in p) / tc) if tc else 0.0}
