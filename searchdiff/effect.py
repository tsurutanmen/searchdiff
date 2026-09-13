"""Did the change work?  Before/after on the changed pages against a control.

The number that answers the question is the difference in differences:

    (treated_after - treated_before) - (control_after - control_before)

for CTR (the usual target of a title or description rewrite), for clicks per
day and for impressions per day.  The control's own change is printed next
to it, because a treated group that "improved" by exactly what the control
improved did not improve.
"""

from __future__ import annotations

import datetime as dt
import fnmatch
import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence

from .data import Row, Totals


def matcher(spec: Optional[str]) -> Callable[[str], bool]:
    """A page selector: a regex (prefix 're:'), a glob with * or ?, a substring, or a file of URLs (prefix '@')."""
    if not spec:
        return lambda page: False
    if spec.startswith("@"):
        with open(spec[1:], encoding="utf-8") as f:
            urls = {ln.strip() for ln in f if ln.strip() and not ln.startswith("#")}
        return lambda page: page in urls
    if spec.startswith("re:"):
        rx = re.compile(spec[3:])
        return lambda page: bool(rx.search(page))
    if any(ch in spec for ch in "*?["):
        return lambda page: fnmatch.fnmatch(page, spec)
    return lambda page: spec in page


@dataclass
class Group:
    name: str
    pages: int
    before: Totals
    after: Totals

    def delta(self, key: str) -> float:
        """CTR: difference in points. Position: difference in ranks.
        Clicks and impressions: relative change of the per-day rate, so groups
        of different sizes can be compared."""
        if key == "ctr":
            return self.after.ctr - self.before.ctr
        if key == "position":
            a, b = self.after.position, self.before.position
            return (a - b) if a is not None and b is not None else float("nan")
        b = self.before.per_day(key)
        return (self.after.per_day(key) - b) / b if b else float("nan")


@dataclass
class EffectReport:
    change_date: dt.date
    window: int
    treated: Group
    control: Group
    did: Dict[str, float] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)

    def __str__(self) -> str:
        t, c = self.treated, self.control
        L = [f"change on {self.change_date.isoformat()}, {self.window} days before and after", ""]
        L.append(f"{'':10s} {'pages':>6s} {'clicks/day':>21s} {'impr/day':>21s} {'ctr':>19s} {'position':>15s}")
        for g in (t, c):
            pb, pa = g.before.position, g.after.position
            pos = f"{pb:6.1f} -> {pa:6.1f}" if pb is not None and pa is not None else f"{'':6s}    {'':6s}"
            L.append(f"{g.name:10s} {g.pages:6d} {g.before.per_day('clicks'):9.2f} -> {g.after.per_day('clicks'):9.2f} "
                     f"{g.before.per_day('impressions'):9.1f} -> {g.after.per_day('impressions'):9.1f} "
                     f"{g.before.ctr:8.2%} -> {g.after.ctr:8.2%} {pos:>15s}")
        L.append("")
        L.append("difference in differences (treated change minus control change):")
        L.append(f"  ctr          {self.did['ctr']:+6.2f} points   (treated {t.delta('ctr')*100:+.2f}, control {c.delta('ctr')*100:+.2f})")
        L.append(f"  clicks/day   {self.did['clicks']*100:+6.1f} %        (treated {t.delta('clicks'):+.1%}, control {c.delta('clicks'):+.1%})")
        L.append(f"  impr/day     {self.did['impressions']*100:+6.1f} %        (treated {t.delta('impressions'):+.1%}, control {c.delta('impressions'):+.1%})")
        if "position" in self.did and self.did["position"] == self.did["position"]:
            L.append(f"  position     {self.did['position']:+6.2f} ranks    (treated {t.delta('position'):+.2f}, control {c.delta('position'):+.2f}; negative is better)")
        for n in self.notes:
            L.append(f"note: {n}")
        return "\n".join(L)

    def to_dict(self) -> dict:
        def g(x: Group):
            return {"name": x.name, "pages": x.pages,
                    "before": {"clicks_per_day": x.before.per_day("clicks"), "impressions_per_day": x.before.per_day("impressions"),
                               "ctr": x.before.ctr, "position": x.before.position, "days": x.before.days},
                    "after": {"clicks_per_day": x.after.per_day("clicks"), "impressions_per_day": x.after.per_day("impressions"),
                              "ctr": x.after.ctr, "position": x.after.position, "days": x.after.days}}
        return {"change_date": self.change_date.isoformat(), "window": self.window,
                "treated": g(self.treated), "control": g(self.control), "did": self.did, "notes": self.notes}


def _totals(rows: Sequence[Row], lo: dt.date, hi: dt.date) -> Totals:
    t = Totals()
    days = set()
    for r in rows:
        if r.date is not None and lo <= r.date <= hi:
            t.add(r)
            days.add(r.date)
    t.days = (hi - lo).days + 1
    return t


def effect(rows: List[Row], change_date: dt.date, treated: Callable[[str], bool],
           control: Optional[Callable[[str], bool]] = None, window: int = 28, gap: int = 0) -> EffectReport:
    """``gap`` days after the change are excluded, for changes that take time to be re-indexed."""
    paged = [r for r in rows if r.date is not None and r.page]
    if not paged:
        raise ValueError("the effect view needs rows with both a date and a page")
    tr = [r for r in paged if treated(r.page)]
    ct = [r for r in paged if (control(r.page) if control else not treated(r.page))]
    b_lo, b_hi = change_date - dt.timedelta(days=window), change_date - dt.timedelta(days=1)
    a_lo, a_hi = change_date + dt.timedelta(days=gap), change_date + dt.timedelta(days=gap + window - 1)
    first = min(r.date for r in paged); last = max(r.date for r in paged)

    T = Group("treated", len({r.page for r in tr}), _totals(tr, b_lo, b_hi), _totals(tr, a_lo, a_hi))
    C = Group("control", len({r.page for r in ct}), _totals(ct, b_lo, b_hi), _totals(ct, a_lo, a_hi))
    rep = EffectReport(change_date=change_date, window=window, treated=T, control=C)
    rep.did = {
        "ctr": (T.delta("ctr") - C.delta("ctr")) * 100.0,
        "clicks": T.delta("clicks") - C.delta("clicks"),
        "impressions": T.delta("impressions") - C.delta("impressions"),
        "position": T.delta("position") - C.delta("position"),
    }
    if T.pages == 0:
        rep.notes.append("no treated pages matched")
    if C.pages == 0:
        rep.notes.append("no control pages; the before/after of the treated group alone cannot separate the change from the season")
    if b_lo < first or a_hi > last:
        rep.notes.append(f"data covers {first.isoformat()}..{last.isoformat()}; the window {b_lo.isoformat()}..{a_hi.isoformat()} is cut short")
    if T.before.impressions and T.before.impressions < 200 * 1:
        rep.notes.append("treated group has few impressions before the change; a CTR point is worth less than a click here")
    if T.before.clicks + T.after.clicks < 30:
        rep.notes.append("fewer than 30 treated clicks in total; nothing here is distinguishable from noise")
    if T.pages and C.pages and abs(C.delta("ctr")) > 0 and abs(T.delta("ctr") - C.delta("ctr")) < 0.002:
        rep.notes.append("treated and control moved together: the change did not do anything the control did not also do")
    return rep
