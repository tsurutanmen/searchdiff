# searchdiff

Did the change work?

Search Console answers two questions badly on its own. "When did traffic drop, and how far back is
it?" gets a daily chart with the weekday wobble in it. "We rewrote the titles, did it help?" gets a
before/after on the changed pages, which contains the season, the algorithm update, and the change,
all mixed together. `searchdiff` gives the first question weekly blocks from a fixed anchor, and the
second a control group and a difference in differences.

```
pip install git+https://github.com/tsurutanmen/searchdiff                 # CSV only, no dependencies
pip install "git+https://github.com/tsurutanmen/searchdiff#egg=searchdiff[api]"   # plus the API
```

## Weekly blocks

```
$ searchdiff weeks daily.csv --anchor 2026-07-18

week                    days  clicks   /day     impr    ctr   pos  vs prev  of peak
2026-07-18..07-24     7    1486  212.3    28420   5.2%   6.6      +2%      95%
2026-07-25..07-31     7    1487  212.4    28605   5.2%   7.0      +0%      95%
2026-08-01..08-07     7    1562  223.1    28365   5.5%   6.1      +5%     100%  peak
2026-08-08..08-14     7    1000  142.9    17816   5.6%   6.1     -36%      64%  CLIFF
2026-08-15..08-21     7    1031  147.3    18516   5.6%   5.9      +3%      66%
2026-08-22..08-28     7    1197  171.0    20313   5.9%   6.2     +16%      77%
2026-08-29..08-31     3     483  161.0     8482   5.7%   7.6      -6%      72%
last block is partial; its /day figure is comparable, its totals are not
note: cliff in the block starting 2026-08-08 (-36%); latest block is at 72% of peak
```

`daily.csv` here is the `Dates` export from the Performance report, unchanged. Any CSV with
`date,clicks,impressions[,position]` works, with or without a `page` column. Blocks are counted
from the anchor in both directions, so the same anchor gives the same blocks next month.

## Did the change work

```
$ searchdiff effect pages.csv --change 2026-08-04 --treated "re:/p/0[0-4]$" --window 28

change on 2026-08-04, 28 days before and after

            pages            clicks/day              impr/day                 ctr        position
treated         5     30.25 ->     21.50     564.4 ->     409.5    5.36% ->    5.25%    7.2 ->    8.0
control        35    182.57 ->    143.82    3487.6 ->    2512.7    5.23% ->    5.72%    7.7 ->    7.4

difference in differences (treated change minus control change):
  ctr           -0.60 points   (treated -0.11, control +0.49)
  clicks/day     -7.7 %        (treated -28.9%, control -21.2%)
  impr/day       +0.5 %        (treated -27.4%, control -28.0%)
  position      +0.95 ranks    (treated +0.72, control -0.23; negative is better)
```

The treated pages lost 29% of their clicks after the change. So did everything else: a traffic cliff
hit the whole site four days later. The difference in differences is within a CTR point of zero. The
rewrite did nothing, and a before/after on the five pages alone would have called it a disaster.

The same data with pages that really did get a lift:

```
  ctr           +3.41 points   (treated +3.33, control -0.09)
  clicks/day    +49.0 %        (treated +20.4%, control -28.6%)
```

`pages.csv` needs `date,page,clicks,impressions[,position]` rows, which the API gives and the UI does
not. `--treated` and `--control` take a substring, a glob, `re:` a regex, or `@file` with one URL per
line. The control defaults to every page not treated; a control of the same kind as the treated pages
is better. `--gap N` skips the first N days after the change for edits that take time to be re-indexed.

The report adds notes when the window runs past the data, when the treated group has too few clicks
for anything to be distinguishable from noise, and when treated and control moved together.

## Fetching from the API

```
searchdiff fetch --site https://example.com/ --key service-account.json \
    --start 2026-06-01 --end 2026-08-31 --out pages.csv --coverage
```

The service account's e-mail has to be added as a user of the property. `--coverage` prints how much
of the clicks the query dimension shows. Search Console hides rare queries; on a site of ours the
query-level sum was 39% of the total while the page-level sum matched it. Analyse by page unless the
words are the point. Paging past 25,000 rows is handled.

## Python

```python
import datetime as dt, searchdiff as sd

rows = sd.load_csv("pages.csv")
print(sd.weekly(rows, anchor=dt.date(2026, 7, 18)))
rep = sd.effect(rows, dt.date(2026, 8, 4), sd.matcher("re:/blog/"), window=28)
rep.did          # {'ctr': points, 'clicks': relative, 'impressions': relative, 'position': ranks}
rep.to_dict()
```

## Where this came from

A title rewrite on a set of comparison pages, measured before/after, looked like nothing: 3.38% to
3.37%. A second rewrite on another set, the same. Both times the tempting reading was "wait longer".
With the untouched pages as control the answer was the same and available on day 28, and the
proposal to rewrite 475 more titles was dropped. The weekly-block view is how a 40% cliff and its
slow return were tracked without re-reading a daily chart every session. The tool packages those
two habits.

## Claude Code skill

`skill/searchdiff/SKILL.md` teaches Claude Code to reach for the control group instead of the
before/after, and how to read the two tables. Install by copying the folder:

```
cp -r skill/searchdiff ~/.claude/skills/searchdiff
```

## License

MIT.
