import numpy as np
import pandas as pd
import pytest

from analysis.strategy import compute_ai, run_asymmetry_strategy, summarize_position_changes


def synthetic(long=None, short=None, returns=None, ai=None):
    n = max(len(x) for x in (long or [], short or [], returns or [], ai or []))
    long = list(long or [False] * n)
    short = list(short or [False] * n)
    returns = list(returns or [0.01] * n)
    ai = list(ai or [1.0] * n)
    idx = pd.date_range("2024-01-05", periods=n, freq="W-FRI")
    return pd.DataFrame(
        {
            "Close": 100 * np.cumprod(1 + np.asarray(returns)),
            "weekly_return": returns,
            "fast_skew_20w": np.where(long, 1.0, 0.0),
            "fast_alpha": 1.0,
            "price_skew_20w": np.where(short, 1.0, 0.0),
            "pricing_alpha": 1.0,
            "pricing_std_20w": 1.0,
            "ai_20w": ai,
        },
        index=idx,
    )


def test_ai_uses_overall_mean_squared_deviations():
    # mean = 4/3; upside MSD = 25/9; downside MSD = (16/9 + 1/9)/2.
    assert compute_ai([0.0, 1.0, 3.0]) == pytest.approx(50 / 17)


def test_ai_edge_cases_are_explicit():
    assert compute_ai([np.nan, 0.0, 1.0, 3.0]) == pytest.approx(50 / 17)
    assert np.isnan(compute_ai([]))
    assert np.isnan(compute_ai([2.0]))
    assert np.isnan(compute_ai([2.0, 2.0, 2.0]))
    # One observation on the upside is valid for a mean-squared deviation.
    assert np.isfinite(compute_ai([0.0, 1.0, 3.0]))


def test_one_and_only_one_execution_lag():
    d = synthetic(long=[True, False, False], returns=[0.0, 0.10, 0.20])
    result = run_asymmetry_strategy(d)
    assert result.position.tolist() == [1.0, 1.0, 1.0]
    assert result.returns.tolist() == pytest.approx([0.0, 0.10, 0.20])


def test_entry_hold_through_no_signal_and_expire_after_four_returns():
    d = synthetic(long=[True, False, False, False, False, False])
    result = run_asymmetry_strategy(d)
    assert result.position.tolist() == [1.0, 1.0, 1.0, 1.0, 0.0, 0.0]
    assert result.applied_position.tolist() == [0.0, 1.0, 1.0, 1.0, 1.0, 0.0]
    assert result.position_ledger.iloc[4]["reason"] == "max_holding_period"
    assert result.trade_ledger.iloc[0]["holding_period"] == 4


def test_opposite_signal_reverses_and_opens_new_episode():
    d = synthetic(
        long=[True, False, False, False, False, False, False],
        short=[False, False, True, False, False, False, False],
    )
    result = run_asymmetry_strategy(d)
    assert result.position.iloc[2] == -1.0
    assert result.position_ledger.iloc[2]["event_type"] == "reversal"
    assert result.metrics["reversals"] == 1
    assert result.metrics["execution_legs"] == 4  # entry + two-leg reversal + final exit
    assert result.metrics["holding_episodes"] == 2
    assert result.trade_ledger["direction"].tolist() == ["long", "short"]


def test_opposite_signal_takes_precedence_on_expiry_date():
    d = synthetic(
        long=[True, False, False, False, False, False],
        short=[False, False, False, False, True, False],
    )
    result = run_asymmetry_strategy(d)
    assert result.position.iloc[4] == -1.0
    assert result.position_ledger.iloc[4]["event_type"] == "reversal"


def test_simultaneous_signals_are_flat():
    flat = run_asymmetry_strategy(synthetic(long=[True], short=[True]))
    assert flat.position.iloc[0] == 0.0
    assert flat.position_ledger.iloc[0]["reason"] == "simultaneous_signals"

    close = run_asymmetry_strategy(
        synthetic(long=[True, True, False], short=[False, True, False])
    )
    assert close.position.tolist() == [1.0, 0.0, 0.0]
    assert close.position_ledger.iloc[1]["event_type"] == "exit"


def test_repeated_same_direction_signal_does_not_resize_or_reset_clock():
    d = synthetic(
        long=[True, True, True, True, True, False],
        ai=[1.0, 2.0, 2.0, 2.0, 2.0, 1.0],
    )
    result = run_asymmetry_strategy(d)
    assert result.position.tolist() == [1.0, 1.0, 1.0, 1.0, 0.0, 0.0]
    assert result.metrics["resizes"] == 0
    assert result.metrics["holding_episodes"] == 1
    assert result.trade_ledger.iloc[0]["holding_period"] == 4


def test_no_signal_without_an_open_position_remains_flat():
    result = run_asymmetry_strategy(synthetic(long=[False] * 5))
    assert (result.position == 0).all()
    assert result.metrics["holding_episodes"] == 0
    assert result.metrics["execution_legs"] == 0


def test_reversal_has_two_legs_but_no_double_counted_episode_cost():
    d = synthetic(
        long=[True, False, False],
        short=[False, True, False],
        returns=[0.0, 0.0, 0.0],
    )
    result = run_asymmetry_strategy(d, round_trip_cost_pips=2.0)
    reversal = result.position_ledger.iloc[1]
    assert reversal["turnover"] == 2.0
    assert reversal["cost"] == pytest.approx(
        reversal["opening_cost"] + reversal["closing_cost"]
    )
    assert result.trade_ledger.iloc[0]["cost"] == pytest.approx(
        result.position_ledger.iloc[0]["opening_cost"] + reversal["closing_cost"]
    )
    assert result.trade_ledger.iloc[1]["cost"] == pytest.approx(reversal["opening_cost"])


def test_resize_is_not_a_new_holding_episode():
    position = pd.Series([0.0, 1.0, 1.5, 1.5, 0.0])
    summary = summarize_position_changes(position)
    assert summary["holding_episodes"] == 1
    assert summary["resizes"] == 1
    assert summary["execution_legs"] == 3  # entry, resize, exit
