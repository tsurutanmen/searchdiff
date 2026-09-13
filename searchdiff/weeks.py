"""Weekly blocks from an anchor date, with cliffs and recovery."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import List, Optional

from .data import Row, Totals

CLIFF = -0.30      # week-over-week change that counts as a cliff


@dataclass
class Week:
    start: dt.date
    end: dt.date
    days: int
    totals: Totals
    change: Optional[float] = None       # clicks/day vs previous block
    of_peak: float = 0.0
    flag: str = ""


@dataclass
class WeeksReport:
    anchor: dt.date
    weeks: List[Week] = field(default_factory=list)
    partial_last: bool = False
    notes: List[str] = field(default_factory=list)

    def __str__(self) -> str:
        L = [f"weekly blocks from {self.anchor.isoformat()}", ""]
        L.append(f"{'week':23s} {'days':>4s} {'clicks':>7s} {'/day':>6s} {'impr':>8s} {'ctr':>6s} {'pos':>5s} {'vs prev':>8s} {'of peak':>8s}  ")
        for w in self.weeks:
            t = w.totals
            ch = "" if w.change is None else f"{w.change:+.0%}"
            pos = "" if t.position is None else f"{t.position:.1f}"
            L.append(f"{w.start.isoformat()}..{w.end.strftime('%m-%d'):6s} {w.days:4d} {t.clicks:7.0f} {t.per_day('clicks'):6.1f} "
                     f"{t.impressions:8.0f} {t.ctr:6.1%} {pos:>5s} {ch:>8s} {w.of_peak:8.0%}  {w.flag}")
        if self.partial_last:
            L.append("last block is partial; its /day figure is comparable, its totals are not")
        for n in self.notes:
            L.append(f"note: {n}")
        return "\n".join(L)

    def to_dict(self) -> dict:
        return {"anchor": self.anchor.isoformat(), "partial_last": self.partial_last, "notes": self.notes,
                "weeks": [{"start": w.start.isoformat(), "end": w.end.isoformat(), "days": w.days,
                           "clicks": w.totals.clicks, "impressions": w.totals.impressions, "ctr": w.totals.ctr,
                           "position": w.totals.position, "clicks_per_day": w.totals.per_day("clicks"),
                           "change": w.change, "of_peak": w.of_peak, "flag": w.flag} for w in self.weeks]}


def weekly(rows: List[Row], anchor: Optional[dt.date] = None, block_days: int = 7) -> WeeksReport:
    dated = [r for r in rows if r.date is not None]
    if not dated:
        raise ValueError("no dated rows; the weeks view needs a date column")
    days = sorted({r.date for r in dated})
    first, last = days[0], days[-1]
    if anchor is None:
        anchor = first
    # walk backwards from the anchor so blocks before it also line up
    start = anchor
    while start - dt.timedelta(days=block_days) >= first:
        start -= dt.timedelta(days=block_days)
    while start > first:
        start -= dt.timedelta(days=block_days)

    by_day = {}
    for r in dated:
        t = by_day.setdefault(r.date, Totals())
        t.add(r)
    rep = WeeksReport(anchor=anchor)
    cur = start
    prev_rate = None
    while cur <= last:
        end = cur + dt.timedelta(days=block_days - 1)
        tot = Totals()
        n = 0
        for d in days:
            if cur <= d <= end:
                t = by_day[d]
                tot.clicks += t.clicks; tot.impressions += t.impressions; tot.pos_weighted += t.pos_weighted
                n += 1
        tot.days = n
        if n:
            w = Week(start=cur, end=min(end, last), days=n, totals=tot)
            rate = tot.per_day("clicks")
            if prev_rate:
                w.change = (rate - prev_rate) / prev_rate
            prev_rate = rate if rate else prev_rate
            rep.weeks.append(w)
        cur = end + dt.timedelta(days=1)
    if rep.weeks:
        peak = max(w.totals.per_day("clicks") for w in rep.weeks) or 1.0
        for w in rep.weeks:
            w.of_peak = w.totals.per_day("clicks") / peak
            if w.change is not None and w.change <= CLIFF:
                w.flag = "CLIFF"
            elif w.of_peak >= 0.999:
                w.flag = "peak"
        rep.partial_last = rep.weeks[-1].days < block_days
        cliffs = [w for w in rep.weeks if w.flag == "CLIFF"]
        if cliffs:
            c = cliffs[-1]
            after = [w for w in rep.weeks if w.start > c.start]
            if after:
                rep.notes.append(f"cliff in the block starting {c.start.isoformat()} ({c.change:+.0%}); "
                                 f"latest block is at {rep.weeks[-1].of_peak:.0%} of peak")
        span = (last - first).days + 1
        if span < 28:
            rep.notes.append(f"only {span} days of data; week-over-week changes are noisy below four weeks")
        if last >= dt.date.today() - dt.timedelta(days=3):
            rep.notes.append("Search Console lags two to three days; the last block will grow")
    return rep
