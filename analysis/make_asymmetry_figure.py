#!/usr/bin/env python3
"""Regenerate paper/alpha_asymmetry_analysis.png from the corrected pipeline.

The previous figure displayed the pre-correction Table 1 statistics (unsigned
tail magnitudes etc.). This one shows the signed weekly series (n=504) with
skewness point estimates and 95% circular-block-bootstrap CIs.
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

daily = yf.download("EURJPY=X", start="2014-06-01", end="2025-08-31",
                    interval="1d", progress=False)
if isinstance(daily.columns, pd.MultiIndex):
    daily.columns = daily.columns.get_level_values(0)
dxy = yf.download("DX-Y.NYB", start="2014-06-01", end="2025-08-31",
                  interval="1d", progress=False)
if isinstance(dxy.columns, pd.MultiIndex):
    dxy.columns = dxy.columns.get_level_values(0)

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
df["coverage_alpha"] = df["vol_20d"] / df["vol_20d"].shift(5) - 1
rc = pd.DataFrame({"e": df["returns"], "d": dxy["Close"].pct_change()}).dropna()
df["hedge_alpha"] = rc["e"].rolling(100).corr(rc["d"]).reindex(df.index) * -0.02

weekly = df.resample("W-FRI").last().loc["2015-11-01":"2025-08-31"]
weekly["fast_skew_20w"] = weekly["fast_alpha"].rolling(20, min_periods=10).apply(
    lambda x: stats.skew(x, nan_policy="omit"), raw=False)
weekly["price_skew_20w"] = weekly["pricing_alpha"].rolling(20, min_periods=10).apply(
    lambda x: stats.skew(x, nan_policy="omit"), raw=False)
weekly = weekly.dropna(subset=["fast_skew_20w", "price_skew_20w"])

ALPHAS = [("tail_alpha", "Tail"), ("fast_alpha", "Fast"),
          ("pricing_alpha", "Pricing"), ("coverage_alpha", "Coverage"),
          ("hedge_alpha", "Hedge")]


def block_ci(x, B=2000, block=13, seed=42):
    r = np.random.default_rng(seed)
    x = np.asarray(x)
    n = len(x)
    nb = int(np.ceil(n / block))
    out = np.empty(B)
    for b in range(B):
        starts = r.integers(0, n, nb)
        idx = (starts[:, None] + np.arange(block)[None, :]).ravel() % n
        out[b] = stats.skew(x[idx[:n]])
    return np.percentile(out, [2.5, 97.5])


fig, axes = plt.subplots(2, 3, figsize=(13, 7.5))
BURGUNDY = "#6e0e1e"
GREY = "#555555"

skews, cis, labels = [], [], []
for ax, (col, label) in zip(axes.ravel()[:5], ALPHAS):
    x = weekly[col].dropna()
    g1 = stats.skew(x)
    lo, hi = block_ci(x)
    skews.append(g1)
    cis.append((lo, hi))
    labels.append(label)
    ax.hist(x, bins=48, color=BURGUNDY, alpha=0.75, edgecolor="white",
            linewidth=0.3, density=True)
    ax.axvline(x.mean(), color=GREY, lw=0.9, ls="--")
    ax.set_title(f"{label} alpha", fontsize=11)
    ax.text(0.97, 0.95,
            f"$\\hat{{\\gamma}}_1$ = {g1:.2f}\nCI [{lo:.2f}, {hi:.2f}]",
            transform=ax.transAxes, ha="right", va="top", fontsize=9,
            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=GREY, alpha=0.85))
    ax.tick_params(labelsize=8)

ax = axes.ravel()[5]
ypos = np.arange(len(labels))[::-1]
for y, g1, (lo, hi) in zip(ypos, skews, cis):
    color = BURGUNDY if lo > 0 or hi < 0 else GREY
    ax.plot([lo, hi], [y, y], color=color, lw=2)
    ax.plot(g1, y, "o", color=color, ms=6)
ax.axvline(0, color="black", lw=0.8)
ax.set_yticks(ypos)
ax.set_yticklabels(labels, fontsize=9)
ax.set_xlabel("Skewness (95% block-bootstrap CI)", fontsize=9)
ax.set_title("Dependence-robust skewness", fontsize=11)
ax.tick_params(labelsize=8)

fig.suptitle("Distributional properties of the five signed weekly alpha signals, EUR/JPY 2015–2025 (n = 504)",
             fontsize=12)
fig.tight_layout(rect=(0, 0, 1, 0.96))
out = "/home/purrpower/Resurrexi/projects/papers/papers-official/alpha-asymmetry/paper/alpha_asymmetry_analysis.png"
fig.savefig(out, dpi=200)
print("saved", out)
