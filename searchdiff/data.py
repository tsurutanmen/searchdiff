"""Rows of Search Console data and how to read them from a CSV.

A row is (date, page, clicks, impressions, position).  CTR is always
recomputed from clicks and impressions, never read from the file, because
exported CTRs are rounded and averaged CTRs are wrong.

Accepted CSV shapes (header names are matched case-insensitively, a few
synonyms are understood):

    date,clicks,impressions[,ctr][,position]                   the UI "Dates" export
    date,page,clicks,impressions[,ctr][,position]              per page per day (API)
    page,clicks,impressions[,ctr][,position]                   the UI "Pages" export (no dates)
"""

from __future__ import annotations

import csv
import datetime as dt
from dataclasses import dataclass
from typing import Iterable, List, Optional

SYNONYMS = {
    "date": {"date", "day", "日付"},
    "page": {"page", "url", "top pages", "pages", "ページ", "上位ページ"},
    "clicks": {"clicks", "click", "クリック数", "クリック"},
    "impressions": {"impressions", "impr", "表示回数", "表示"},
    "position": {"position", "avg position", "average position", "掲載順位", "平均掲載順位"},
}


@dataclass(frozen=True)
class Row:
    date: Optional[dt.date]
    page: Optional[str]
    clicks: float
    impressions: float
    position: Optional[float]      # impression-weighted when aggregated


def _col(header: List[str], key: str) -> Optional[int]:
    names = {h.strip().lower(): i for i, h in enumerate(header)}
    for syn in SYNONYMS[key]:
        if syn in names:
            return names[syn]
    return None


def _num(s: str) -> float:
    s = (s or "").strip().replace(",", "").replace("%", "")
    if s in ("", "-"):
        return 0.0
    return float(s)


def _date(s: str) -> dt.date:
    s = s.strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%m/%d/%Y", "%Y%m%d"):
        try:
            return dt.datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return dt.date.fromisoformat(s[:10])


def load_csv(path: str, delimiter: str = ",") -> List[Row]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f, delimiter=delimiter)
        header = next(reader)
        ci = {k: _col(header, k) for k in SYNONYMS}
        if ci["clicks"] is None or ci["impressions"] is None:
            raise ValueError(f"need clicks and impressions columns; got {header}")
        rows = []
        for r in reader:
            if not r or all(not c.strip() for c in r):
                continue
            rows.append(Row(
                date=_date(r[ci["date"]]) if ci["date"] is not None else None,
                page=r[ci["page"]].strip() if ci["page"] is not None else None,
                clicks=_num(r[ci["clicks"]]),
                impressions=_num(r[ci["impressions"]]),
                position=_num(r[ci["position"]]) if ci["position"] is not None and r[ci["position"]].strip() else None,
            ))
    return rows


def write_csv(rows: Iterable[Row], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "page", "clicks", "impressions", "ctr", "position"])
        for r in rows:
            ctr = r.clicks / r.impressions if r.impressions else 0.0
            w.writerow([r.date.isoformat() if r.date else "", r.page or "", int(r.clicks), int(r.impressions),
                        f"{ctr:.4f}", "" if r.position is None else f"{r.position:.2f}"])


@dataclass
class Totals:
    clicks: float = 0.0
    impressions: float = 0.0
    pos_weighted: float = 0.0
    days: int = 0

    def add(self, r: Row) -> None:
        self.clicks += r.clicks
        self.impressions += r.impressions
        if r.position is not None:
            self.pos_weighted += r.position * r.impressions

    @property
    def ctr(self) -> float:
        return self.clicks / self.impressions if self.impressions else 0.0

    @property
    def position(self) -> Optional[float]:
        return self.pos_weighted / self.impressions if self.impressions and self.pos_weighted else None

    def per_day(self, key: str) -> float:
        v = getattr(self, key)
        return v / self.days if self.days else 0.0
