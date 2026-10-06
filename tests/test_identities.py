"""Two arithmetic identities, checked against the committed pipeline output.

The manuscript's AI-assistance statement says these identities are verified. During
the revision they were checked by hand after each rerun (docs/REVIEW_NOTES.md,
"Constraint checks on the rerun"); here they run with the suite, so a rerun whose
output breaks either one fails.

Identity 1: the full-sample factor intercept tracks the strategy's own mean weekly
return, within the 5e-5 tolerance recorded in docs/REVIEW_NOTES.md. Its blind spot
is documented there: a swap to an adjacent specification (frozen sizing, a gap of
1.8e-5) passes. The tolerance is not tightened here, because choosing it after
seeing which substitution it missed would be a threshold chosen on outcomes.

Identity 2: the returns attributed to low-VIX and high-VIX weeks compound to the
full-sample cumulative return, because the two masks partition the weeks of one run.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "analysis" / "full_pipeline_results.json"
LEDGER = ROOT / "analysis" / "position_ledger.csv"
IDENTITY_1_TOLERANCE = 5e-5


def _identity_gaps(results: dict, mean_weekly_return: float) -> tuple[float, float]:
    intercept = results["factor_attribution"]["full"]["coef"]["const"]["b"]
    low = results["regimes"]["low_vix"]["strategy_return"] / 100
    high = results["regimes"]["high_vix"]["strategy_return"] / 100
    full = results["baseline"]["return"] / 100
    return abs(intercept - mean_weekly_return), abs((1 + low) * (1 + high) - 1 - full)


def _mean_weekly_return() -> float:
    return float(pd.read_csv(LEDGER)["gross_return"].dropna().mean())


def test_factor_intercept_tracks_mean_weekly_return():
    gap, _ = _identity_gaps(json.loads(RESULTS.read_text()), _mean_weekly_return())
    assert gap < IDENTITY_1_TOLERANCE, (
        f"factor intercept and strategy mean weekly return differ by {gap:.2e}; the "
        f"regression may have been run on a different series from the one reported")


def test_vix_regime_returns_compound_to_the_full_sample():
    _, gap = _identity_gaps(json.loads(RESULTS.read_text()), _mean_weekly_return())
    assert gap < 1e-10, (
        f"low- and high-VIX returns compound to a figure {gap:.2e} away from the "
        f"full-sample return; the regime masks no longer partition one run")


def test_the_identities_fail_on_defective_input():
    """Mutation: each identity must reject an input that violates it."""
    results = json.loads(RESULTS.read_text())
    mean = _mean_weekly_return()
    shifted = json.loads(json.dumps(results))
    shifted["factor_attribution"]["full"]["coef"]["const"]["b"] += 1e-4
    assert _identity_gaps(shifted, mean)[0] >= IDENTITY_1_TOLERANCE
    dropped = json.loads(json.dumps(results))
    dropped["regimes"]["high_vix"]["strategy_return"] += 0.5
    assert _identity_gaps(dropped, mean)[1] >= 1e-10
