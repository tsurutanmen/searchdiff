import datetime as dt
import os
import subprocess
import sys

import pytest

import searchdiff as sd
from searchdiff.api import to_rows

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")


@pytest.fixture(scope="module", autouse=True)
def data():
    if not os.path.exists(os.path.join(DATA, "pages.csv")):
        subprocess.check_call([sys.executable, os.path.join(HERE, "make_data.py")])


def test_load_ui_export_shape():
    rows = sd.load_csv(os.path.join(DATA, "daily.csv"))
    assert len(rows) == 90 and rows[0].page is None and rows[0].date == dt.date(2026, 6, 3)
    assert rows[0].position is not None


def test_weeks_find_the_cliff():
    rep = sd.weekly(sd.load_csv(os.path.join(DATA, "daily.csv")), anchor=dt.date(2026, 7, 18))
    flags = {w.start: w.flag for w in rep.weeks}
    assert flags[dt.date(2026, 8, 8)] == "CLIFF"
    assert any("cliff in the block starting 2026-08-08" in n for n in rep.notes)
    assert any(w.flag == "peak" for w in rep.weeks)
    assert all(0 < w.of_peak <= 1.0 for w in rep.weeks)
    # blocks line up on the anchor
    assert dt.date(2026, 7, 18) in flags


def test_weeks_anchor_defaults_to_first_day():
    rep = sd.weekly(sd.load_csv(os.path.join(DATA, "daily.csv")))
    assert rep.weeks[0].start == dt.date(2026, 6, 3)
    assert rep.weeks[-1].days <= 7


def test_effect_null_change_is_null():
    rows = sd.load_csv(os.path.join(DATA, "pages.csv"))
    rep = sd.effect(rows, dt.date(2026, 8, 4), sd.matcher("re:/p/0[0-4]$"), window=28)
    assert rep.treated.pages == 5 and rep.control.pages == 35
    assert abs(rep.did["ctr"]) < 1.0            # within a CTR point of zero
    # the cliff hit both groups: treated alone looks like a loss, the control explains it
    assert rep.treated.delta("impressions") < 0 and rep.control.delta("impressions") < 0


def test_effect_real_lift_is_seen():
    rows = sd.load_csv(os.path.join(DATA, "pages.csv"))
    rep = sd.effect(rows, dt.date(2026, 8, 4), sd.matcher("re:/p/1[0-4]$"), control=sd.matcher("re:/p/[23][0-9]$"), window=28)
    assert rep.did["ctr"] > 2.0
    assert rep.did["clicks"] > 0.2                 # more than +20% relative to the control's change


def test_matchers(tmp_path):
    assert sd.matcher("/p/01")("https://example.com/p/01")
    assert sd.matcher("*/p/0?")("https://example.com/p/07")
    assert not sd.matcher("re:/p/1")("https://example.com/p/07")
    f = tmp_path / "urls.txt"; f.write_text("https://example.com/p/03\n# c\n")
    assert sd.matcher("@" + str(f))("https://example.com/p/03")
    assert not sd.matcher(None)("anything")


def test_effect_notes_when_window_exceeds_data():
    rows = sd.load_csv(os.path.join(DATA, "pages.csv"))
    rep = sd.effect(rows, dt.date(2026, 8, 25), sd.matcher("/p/00"), window=28)
    assert any("cut short" in n for n in rep.notes)


def test_api_rows_conversion():
    api_rows = [{"keys": ["2026-08-01", "https://e.com/a"], "clicks": 3, "impressions": 50, "ctr": 0.06, "position": 4.2}]
    rows = to_rows(api_rows, ("date", "page"))
    assert rows[0].date == dt.date(2026, 8, 1) and rows[0].page == "https://e.com/a" and rows[0].clicks == 3


def test_api_query_pages_with_mock():
    from searchdiff.api import query, ROW_LIMIT

    class Resp:
        def __init__(self, rows): self._rows = rows
        def raise_for_status(self): pass
        def json(self): return {"rows": self._rows}

    class Sess:
        def __init__(self): self.calls = []
        def post(self, url, json, timeout):
            self.calls.append(json["startRow"])
            n = ROW_LIMIT if json["startRow"] == 0 else 3
            return Resp([{"keys": ["2026-08-01", "x"], "clicks": 1, "impressions": 1} for _ in range(n)])

    s = Sess()
    rows = query("https://e.com/", "unused", dt.date(2026, 8, 1), dt.date(2026, 8, 2), session=s)
    assert len(rows) == ROW_LIMIT + 3 and s.calls == [0, ROW_LIMIT]


def test_cli(tmp_path, capsys):
    from searchdiff.cli import main
    out = tmp_path / "w.json"
    assert main(["weeks", os.path.join(DATA, "daily.csv"), "--anchor", "2026-07-18", "--json", str(out)]) == 0
    assert "CLIFF" in capsys.readouterr().out and out.exists()
    assert main(["effect", os.path.join(DATA, "pages.csv"), "--change", "2026-08-04", "--treated", "re:/p/0[0-4]$"]) == 0
    assert "difference in differences" in capsys.readouterr().out
