"""The execution-timing contrasts and the weekend-gap test run inside the pipeline.

Until October 2026 the paired bootstrap contrasts, the weekend-gap test and its
power bound were printed in the manuscript from a script that was never
committed. These tests pin the properties the pipeline versions must have.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from analysis.full_pipeline import (
    PRIMARY_EXECUTION_CONTRASTS,
    annualized_return_pct,
    decision_episode_ids,
    episode_ids,
    moving_block_indices,
    paired_execution_contrasts,
)
from analysis.inference import wild_cluster_bootstrap, wild_cluster_bootstrap_vectorized
from analysis.strategy import run_asymmetry_strategy

TIMINGS = ("friday_close", "monday_open", "monday_close", "tuesday_open")


def _series(n=120, seed=3, identical=False):
    rng = np.random.default_rng(seed)
    base = rng.normal(0, 0.01, n)
    data = {}
    for k, name in enumerate(TIMINGS):
        data[name] = base if identical else base + rng.normal(0, 0.002, n) * (k + 1)
    return pd.DataFrame(data)


def test_moving_block_indices_are_contiguous_blocks_without_wrap():
    rng = np.random.default_rng(0)
    n, block = 50, 4
    idx = moving_block_indices(n, block, rng)
    assert len(idx) == n
    assert idx.min() >= 0 and idx.max() <= n - 1
    starts = idx[::block]
    assert (starts <= n - block).all()
    for s0, chunk in zip(starts, np.split(idx, range(block, n, block))):
        assert (chunk == s0 + np.arange(len(chunk))).all()


def test_contrast_estimate_is_the_difference_of_annualized_returns():
    frame = _series()
    out = paired_execution_contrasts(frame, reps=50)
    ann = annualized_return_pct(frame.to_numpy())
    for a, b in PRIMARY_EXECUTION_CONTRASTS:
        want = ann[TIMINGS.index(b)] - ann[TIMINGS.index(a)]
        assert abs(out["estimate"][f"{b}_minus_{a}"] - want) < 1e-12


def test_contrasts_are_paired():
    """One set of indices per replicate for all timings: identical series give zero exactly.

    An unpaired bootstrap would resample each timing separately and produce a
    non-degenerate interval around zero even for identical inputs.
    """
    out = paired_execution_contrasts(_series(identical=True), reps=50)
    for scheme in out["schemes"].values():
        for entry in scheme["contrasts"].values():
            assert entry["percentile_ci"] == [0.0, 0.0]


def test_missing_returns_are_rejected():
    frame = _series()
    frame.iloc[5, 1] = np.nan
    try:
        paired_execution_contrasts(frame, reps=10)
    except AssertionError:
        return
    raise AssertionError("a missing week must not enter the paired contrasts")


def test_vectorized_wild_bootstrap_matches_the_reference_implementation():
    rng = np.random.default_rng(5)
    groups = np.repeat(np.arange(12), 4)
    x = rng.normal(size=len(groups))
    X = np.column_stack([np.ones(len(groups)), x])
    for seed in (1, 2, 3):
        y = 0.3 * x * (seed == 3) + rng.normal(size=len(groups))
        ref = wild_cluster_bootstrap(y, X, groups, 1, reps=499, seed=seed)
        fast = wild_cluster_bootstrap_vectorized(y, X, groups, 1, reps=499, seed=seed)
        assert ref["p"] == fast["p"]
        assert ref["observed_t"] == fast["observed_t"]


def _panel(periods=80):
    idx = pd.date_range("2020-01-03", periods=periods, freq="W-FRI")
    rng = np.random.default_rng(9)
    returns = rng.normal(0, 0.01, periods)
    fires = (np.arange(periods) % 11) < 2
    return pd.DataFrame(
        {
            "Close": 100 * np.cumprod(1 + returns),
            "weekly_return": returns,
            "fast_skew_20w": np.where(fires, 1.5, -1.0),
            "fast_alpha": np.where(fires, 1.0, -1.0),
            "price_skew_20w": np.full(periods, -1.0),
            "pricing_alpha": np.zeros(periods),
            "pricing_std_20w": np.ones(periods),
            "ai_20w": np.full(periods, 1.5),
        },
        index=idx,
    )


def test_decision_labels_are_applied_labels_shifted_back_one_week():
    """Invariant B.2: a decision-week sample needs the applied-week labels shifted by -1."""
    ledger = run_asymmetry_strategy(_panel(), 0.75).position_ledger
    decision = decision_episode_ids(ledger)
    applied = episode_ids(ledger)
    assert (decision.iloc[:-1].to_numpy() == applied.shift(-1).iloc[:-1].to_numpy()).all()
    assert (decision != 0).sum() == (ledger["new_position"] != 0).sum()
    assert decision.max() >= 2
