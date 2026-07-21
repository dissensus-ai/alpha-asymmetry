#!/usr/bin/env python3
"""Regenerate paper/backtest_results.png from the corrected pipeline.

The previous figure (Dec 2025) plotted momentum/mean-reversion equity curves
from the retired dataset that matched no committed code. This one shows the
four Table 3 strategies -- asymmetry (0.75 threshold), 20-week time-series
momentum, 2.0-sigma mean reversion, buy & hold -- on the same weekly plumbing
as analysis/full_pipeline.py (definitions identical to its Table 11 universe).
"""
import warnings

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yfinance as yf
from scipy import stats

warnings.filterwarnings("ignore")


def dl(ticker):
    d = yf.download(ticker, start="2014-06-01", end="2025-08-31",
                    interval="1d", progress=False)
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = d.columns.get_level_values(0)
    return d


daily = dl("EURJPY=X")
df = daily[["Close"]].copy()
df["returns"] = df["Close"].pct_change()
q95 = df["returns"].abs().rolling(252, min_periods=60).quantile(0.95)
df["tail_alpha"] = np.where(df["returns"].abs() > q95,
                            np.sign(df["returns"]) * df["returns"].abs(), 0.0)
df["ret_5d"] = df["Close"].pct_change(5)
df["vol_20d"] = df["returns"].rolling(20).std()
df["fast_alpha"] = df["ret_5d"] / (df["vol_20d"] * np.sqrt(5))
df["ma_60d"] = df["Close"].rolling(60).mean()
df["std_60d"] = df["Close"].rolling(60).std()
df["pricing_alpha"] = (df["Close"] - df["ma_60d"]) / df["std_60d"]

weekly = df.resample("W-FRI").last()
weekly["weekly_return"] = weekly["Close"].pct_change()
weekly = weekly.loc["2015-11-01":"2025-08-31"]
weekly["fast_skew_20w"] = weekly["fast_alpha"].rolling(20, min_periods=10).apply(
    lambda x: stats.skew(x, nan_policy="omit"), raw=False)
weekly["price_skew_20w"] = weekly["pricing_alpha"].rolling(20, min_periods=10).apply(
    lambda x: stats.skew(x, nan_policy="omit"), raw=False)
weekly["pricing_std_20w"] = weekly["pricing_alpha"].rolling(20, min_periods=10).std()


def compute_ai(x):
    x = x.dropna()
    if len(x) < 5:
        return 1.0
    mean_x = x.mean()
    pos = x[x > mean_x] - mean_x
    neg = x[x < mean_x] - mean_x
    if len(neg) == 0 or neg.var() == 0:
        return 1.0
    return pos.var() / neg.var() if len(pos) > 0 else 1.0


weekly["ai_20w"] = weekly["fast_alpha"].rolling(20, min_periods=10).apply(compute_ai, raw=False)
weekly = weekly.dropna(subset=["fast_skew_20w", "price_skew_20w", "ai_20w"])


def run_asymmetry_strategy(data, threshold=0.75):
    d = data.copy()
    long_signal = (d["fast_skew_20w"] > threshold) & (d["fast_alpha"] > 0)
    short_signal = (d["price_skew_20w"] > threshold) & (d["pricing_alpha"] > 0.5 * d["pricing_std_20w"])
    position = pd.Series(0.0, index=d.index)
    hold_counter = pd.Series(0, index=d.index)
    for i in range(1, len(d)):
        prev_pos = position.iloc[i - 1]
        prev_hold = hold_counter.iloc[i - 1]
        if prev_hold >= 4:
            position.iloc[i] = 0.0
            hold_counter.iloc[i] = 0
            continue
        if i >= 2:
            sig_long = long_signal.iloc[i - 1]
            sig_short = short_signal.iloc[i - 1]
        else:
            sig_long = sig_short = False
        ai_val = d["ai_20w"].iloc[i - 1]
        ps = max(0.5, min(2.0, 1.0 + abs(ai_val - 1.0)))
        if sig_long and not sig_short:
            new_pos = ps
        elif sig_short and not sig_long:
            new_pos = -ps
        elif sig_long and sig_short:
            new_pos = 0.0
        else:
            if prev_pos > 0 and not long_signal.iloc[i - 1]:
                new_pos = 0.0
            elif prev_pos < 0 and not short_signal.iloc[i - 1]:
                new_pos = 0.0
            else:
                new_pos = prev_pos
        position.iloc[i] = new_pos
        if new_pos != 0 and np.sign(new_pos) == np.sign(prev_pos):
            hold_counter.iloc[i] = prev_hold + 1
        elif new_pos != 0:
            hold_counter.iloc[i] = 1
        else:
            hold_counter.iloc[i] = 0
    return (position.shift(1) * d["weekly_return"]).fillna(0)


def simple_strategy(pos):
    return (pos.shift(1) * weekly["weekly_return"]).fillna(0)


asym = run_asymmetry_strategy(weekly, 0.75)
mom = simple_strategy(np.sign(weekly["Close"].pct_change(20)))
ma20 = weekly["Close"].rolling(20).mean()
sd20 = weekly["Close"].rolling(20).std()
zsc = (weekly["Close"] - ma20) / sd20
pos_mr = pd.Series(0.0, index=weekly.index)
pos_mr[zsc > 2.0] = -1.0
pos_mr[zsc < -2.0] = 1.0
mr = simple_strategy(pos_mr)
bh = simple_strategy(pd.Series(1.0, index=weekly.index))

BURGUNDY = "#6e0e1e"
SERIES = [("Asymmetry (0.75)", asym, BURGUNDY, 1.8),
          ("Momentum (20w)", mom, "#888888", 1.1),
          ("Mean reversion (2.0$\\sigma$)", mr, "#4a6a8a", 1.1),
          ("Buy & hold", bh, "#b0892d", 1.1)]

fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True,
                         gridspec_kw={"height_ratios": [2.2, 1]})
for label, rets, color, lw in SERIES:
    cum = (1 + rets).cumprod()
    axes[0].plot(cum.index, (cum - 1) * 100, label=label, color=color, lw=lw)
    dd = (cum / cum.cummax() - 1) * 100
    axes[1].plot(dd.index, dd, color=color, lw=lw)
axes[0].axhline(0, color="black", lw=0.7)
axes[0].set_ylabel("Cumulative return (%)", fontsize=10)
axes[0].legend(fontsize=9, loc="upper left", frameon=False)
axes[0].tick_params(labelsize=9)
axes[1].set_ylabel("Drawdown (%)", fontsize=10)
axes[1].tick_params(labelsize=9)
fig.suptitle("Strategy equity curves and drawdowns, EUR/JPY weekly 2015–2025 (n = 504)",
             fontsize=12)
fig.tight_layout(rect=(0, 0, 1, 0.96))
out = "/home/purrpower/Resurrexi/projects/papers/papers-official/alpha-asymmetry/paper/backtest_results.png"
fig.savefig(out, dpi=200)
print("saved", out)
for label, rets, _, _ in SERIES:
    print(f"  {label:<28} cum={((1 + rets).prod() - 1) * 100:7.2f}%")
