"""searchdiff weeks DATA.csv [--anchor DATE]
   searchdiff effect DATA.csv --change DATE --treated SPEC [--control SPEC] [--window 28] [--gap 0]
   searchdiff fetch --site URL --key sa.json --start DATE --end DATE --out DATA.csv [--coverage]"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys

from .data import load_csv, write_csv
from .weeks import weekly
from .effect import effect, matcher


def _d(s: str) -> dt.date:
    return dt.date.fromisoformat(s)


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser(prog="searchdiff", description="Did the change work? Search Console data as weekly blocks and difference-in-differences.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    w = sub.add_parser("weeks", help="weekly blocks from an anchor date, cliffs, share of peak")
    w.add_argument("data"); w.add_argument("--anchor", type=_d); w.add_argument("--block", type=int, default=7)
    w.add_argument("--json")

    e = sub.add_parser("effect", help="before/after on changed pages against a control")
    e.add_argument("data"); e.add_argument("--change", type=_d, required=True)
    e.add_argument("--treated", required=True, help="substring, glob, re:regex, or @file of URLs")
    e.add_argument("--control", help="same forms; default: every page not treated")
    e.add_argument("--window", type=int, default=28); e.add_argument("--gap", type=int, default=0)
    e.add_argument("--json")

    f = sub.add_parser("fetch", help="pull date x page rows from the API with a service account")
    f.add_argument("--site", required=True, help="property, e.g. https://example.com/ or sc-domain:example.com")
    f.add_argument("--key", required=True, help="service account JSON")
    f.add_argument("--start", type=_d, required=True); f.add_argument("--end", type=_d, required=True)
    f.add_argument("--out", required=True); f.add_argument("--dimensions", default="date,page")
    f.add_argument("--coverage", action="store_true", help="also report how much traffic the query dimension shows")

    a = ap.parse_args(argv)
    if a.cmd == "weeks":
        rep = weekly(load_csv(a.data), anchor=a.anchor, block_days=a.block)
        print(rep)
        if a.json:
            json.dump(rep.to_dict(), open(a.json, "w", encoding="utf-8"), indent=1)
    elif a.cmd == "effect":
        rep = effect(load_csv(a.data), a.change, matcher(a.treated), matcher(a.control) if a.control else None,
                     window=a.window, gap=a.gap)
        print(rep)
        if a.json:
            json.dump(rep.to_dict(), open(a.json, "w", encoding="utf-8"), indent=1)
    else:
        from .api import fetch, coverage
        dims = [d.strip() for d in a.dimensions.split(",") if d.strip()]
        rows = fetch(a.site, a.key, a.start, a.end, dims)
        write_csv(rows, a.out)
        print(f"wrote {len(rows)} rows to {a.out}")
        if a.coverage:
            c = coverage(a.site, a.key, a.start, a.end)
            print(f"total clicks {c['total_clicks']:.0f}; the query dimension shows {c['query_share']:.0%} of them, "
                  f"the page dimension {c['page_share']:.0%}. Analyse by page unless you need the words.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
