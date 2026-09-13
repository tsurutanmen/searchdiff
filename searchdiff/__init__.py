"""searchdiff: did the change work?

Search Console data as weekly blocks (where was the cliff, how far back is
it) and as a difference in differences (the pages you changed against the
pages you did not, before and after).  Reads the UI's CSV exports or pulls
from the API with a service account.
"""

from .data import Row, Totals, load_csv, write_csv
from .weeks import weekly, WeeksReport
from .effect import effect, matcher, EffectReport

__version__ = "0.1.0"
__all__ = ["Row", "Totals", "load_csv", "write_csv", "weekly", "WeeksReport", "effect", "matcher", "EffectReport"]
