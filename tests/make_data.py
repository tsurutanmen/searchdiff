"""Synthetic Search Console data with a known cliff and a known null effect.

    python tests/make_data.py

daily.csv        90 days, site totals, a 40% cliff on 2026-08-08 and slow recovery
pages.csv        date x page for 40 pages; 5 "treated" pages get a title rewrite on
                 2026-08-04 that does nothing; 5 "lifted" pages get +3 CTR points
"""
import csv
import datetime as dt
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "data")
START = dt.date(2026, 6, 3)
DAYS = 90
CLIFF = dt.date(2026, 8, 8)
CHANGE = dt.date(2026, 8, 4)


def main():
    os.makedirs(OUT, exist_ok=True)
    rng = random.Random(1)
    pages = [f"https://example.com/p/{i:02d}" for i in range(40)]
    base_impr = {p: rng.uniform(20, 200) for p in pages}
    base_ctr = {p: rng.uniform(0.02, 0.08) for p in pages}
    with open(os.path.join(OUT, "pages.csv"), "w", newline="") as f, \
         open(os.path.join(OUT, "daily.csv"), "w", newline="") as g:
        wp = csv.writer(f); wd = csv.writer(g)
        wp.writerow(["date", "page", "clicks", "impressions", "ctr", "position"])
        wd.writerow(["Date", "Clicks", "Impressions", "CTR", "Position"])
        for k in range(DAYS):
            d = START + dt.timedelta(days=k)
            season = 1.0 + 0.1 * ((k // 7) % 2)
            cliff = 0.6 if d >= CLIFF else 1.0
            recover = 1.0 + 0.01 * max(0, (d - CLIFF).days) if d >= CLIFF else 1.0
            tc = ti = 0
            for i, p in enumerate(pages):
                impr = max(0, int(rng.gauss(base_impr[p] * season * cliff * recover, base_impr[p] * 0.15)))
                ctr = base_ctr[p]
                if 10 <= i < 15 and d >= CHANGE:
                    ctr += 0.03                      # lifted pages
                if 0 <= i < 5:
                    ctr = ctr                        # treated pages: no effect
                clicks = sum(1 for _ in range(impr) if rng.random() < ctr)
                pos = rng.uniform(3, 12)
                wp.writerow([d.isoformat(), p, clicks, impr, f"{clicks / impr if impr else 0:.4f}", f"{pos:.2f}"])
                tc += clicks; ti += impr
            wd.writerow([d.isoformat(), tc, ti, f"{100 * tc / ti if ti else 0:.2f}%", f"{rng.uniform(5, 8):.2f}"])
    print("wrote", OUT)


if __name__ == "__main__":
    main()
