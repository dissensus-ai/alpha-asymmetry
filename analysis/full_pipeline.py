#!/usr/bin/env python3
"""Run the complete alpha-asymmetry replication and specification audit.

The pipeline has one shared implementation for the headline strategy, all
downstream analysis, ledgers, costs, and figures. Raw data are cached locally
and identified by SHA-256 hashes; the cache is not committed.
"""

from __future__ import annotations

import argparse
import json
import os
import warnings
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(REPO_ROOT / ".matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats
from statsmodels.stats.diagnostic import acorr_ljungbox

try:
    from analysis.data_access import load_datasets, write_manifest
    from analysis.strategy import compute_ai, run_asymmetry_strategy, simple_strategy, summarize_position_changes
except ModuleNotFoundError:  # direct execution from analysis/
    from data_access import load_datasets, write_manifest
    from strategy import compute_ai, run_asymmetry_strategy, simple_strategy, summarize_position_changes


ANALYSIS_DIR = REPO_ROOT / "analysis"
PAPER_DIR = REPO_ROOT / "paper"
ALPHA_COLS = ["tail_alpha", "fast_alpha", "pricing_alpha", "coverage_alpha", "hedge_alpha"]
GRID = [0.50, 0.75, 1.00, 1.25]
SEED = 42
warnings.filterwarnings("default")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=ANALYSIS_DIR / "cache")
    parser.add_argument("--output-dir", type=Path, default=ANALYSIS_DIR)
    parser.add_argument("--paper-dir", type=Path, default=PAPER_DIR)
    parser.add_argument("--offline", action="store_true", help="require local cached CSV inputs")
    parser.add_argument("--refresh", action="store_true", help="redownload and replace cached CSV inputs")
    return parser.parse_args()


def build_weekly_alphas(daily_px: pd.DataFrame, dxy: pd.DataFrame | None = None) -> pd.DataFrame:
    d = daily_px[["Close"]].copy()
    d["returns"] = d["Close"].pct_change(fill_method=None)
    q95 = d["returns"].abs().rolling(252, min_periods=60).quantile(0.95)
    d["tail_alpha"] = np.where(
        d["returns"].abs() > q95,
        np.sign(d["returns"]) * d["returns"].abs(),
        0.0,
    )
    d["ret_5d"] = d["Close"].pct_change(5, fill_method=None)
    d["vol_20d"] = d["returns"].rolling(20).std()
    d["fast_alpha"] = d["ret_5d"] / (d["vol_20d"] * np.sqrt(5))
    d["ma_60d"] = d["Close"].rolling(60).mean()
    d["std_60d"] = d["Close"].rolling(60).std()
    d["pricing_alpha"] = (d["Close"] - d["ma_60d"]) / d["std_60d"]
    d["coverage_alpha"] = d["vol_20d"] / d["vol_20d"].shift(5) - 1
    if dxy is not None:
        corr_data = pd.DataFrame(
            {"eurjpy": d["returns"], "dxy": dxy["Close"].pct_change(fill_method=None)}
        ).dropna()
        corr = corr_data["eurjpy"].rolling(100).corr(corr_data["dxy"])
        d["hedge_alpha"] = corr.reindex(d.index) * -0.02

    w = d.resample("W-FRI").last()
    w["weekly_return"] = w["Close"].pct_change(fill_method=None)
    w = w.loc["2015-11-01":"2025-08-31"]
    w["fast_skew_20w"] = w["fast_alpha"].rolling(20, min_periods=10).apply(
        lambda x: stats.skew(x, nan_policy="omit", bias=False), raw=False
    )
    w["price_skew_20w"] = w["pricing_alpha"].rolling(20, min_periods=10).apply(
        lambda x: stats.skew(x, nan_policy="omit", bias=False), raw=False
    )
    w["pricing_std_20w"] = w["pricing_alpha"].rolling(20, min_periods=10).std()
    w["ai_20w"] = w["fast_alpha"].rolling(20, min_periods=10).apply(compute_ai, raw=False)
    return w.dropna(subset=["fast_skew_20w", "price_skew_20w", "ai_20w"])


def block_bootstrap_skew_ci(x, b=2000, block=13, seed=SEED):
    values = np.asarray(x, dtype=float)
    rng = np.random.default_rng(seed)
    n = len(values)
    nblocks = int(np.ceil(n / block))
    boot = np.empty(b)
    for i in range(b):
        starts = rng.integers(0, n, nblocks)
        idx = (starts[:, None] + np.arange(block)[None, :]).ravel() % n
        boot[i] = stats.skew(values[idx[:n]], bias=False)
    return np.percentile(boot, [2.5, 97.5]), float(boot.std(ddof=1))


def stationary_bootstrap_indices(n, expected_block=4.0, size=None, rng=None):
    rng = rng or np.random.default_rng()
    size = size or n
    idx = np.empty(size, dtype=int)
    idx[0] = rng.integers(0, n)
    for i in range(1, size):
        idx[i] = rng.integers(0, n) if rng.random() < 1 / expected_block else (idx[i - 1] + 1) % n
    return idx


def performance(rets: pd.Series, position: pd.Series) -> dict:
    rets = rets.fillna(0.0)
    cum = float((1 + rets).prod() - 1)
    sd = float(rets.std())
    neg = rets[rets < 0]
    downside = float(neg.std()) if len(neg) > 1 else 0.0
    curve = (1 + rets).cumprod()
    return {
        "ret": cum * 100,
        "vol": sd * np.sqrt(52) * 100,
        "sharpe": float(rets.mean() / sd * np.sqrt(52)) if sd > 0 else 0.0,
        "sortino": float(rets.mean() / downside * np.sqrt(52)) if downside > 0 else 0.0,
        "mdd": float((curve / curve.cummax() - 1).min() * 100),
        **summarize_position_changes(position),
    }


def hac_reg(frame: pd.DataFrame) -> dict | None:
    dat = frame.dropna()
    if len(dat) <= 10:
        return None
    model = sm.OLS(dat["strat"], sm.add_constant(dat[["carry", "mom", "dollar"]])).fit(
        cov_type="HAC", cov_kwds={"maxlags": 4}
    )
    return {
        "n": int(model.nobs), "r2": float(model.rsquared), "adj_r2": float(model.rsquared_adj),
        "f": float(model.fvalue),
        "coef": {name: {"b": float(model.params[name]), "t": float(model.tvalues[name]), "p": float(model.pvalues[name])}
                 for name in ["const", "carry", "mom", "dollar"]},
    }


def ferro_segers_theta(exc_idx):
    gaps = np.diff(exc_idx)
    if len(gaps) < 2:
        return np.nan
    if gaps.max() <= 2:
        numerator = 2 * gaps.sum() ** 2
        denominator = len(gaps) * np.square(gaps).sum()
    else:
        numerator = 2 * np.square((gaps - 1).sum())
        denominator = len(gaps) * ((gaps - 1) * (gaps - 2)).sum()
    return min(1.0, numerator / denominator) if denominator > 0 else np.nan


def json_safe(value):
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [json_safe(v) for v in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def portable_path(path: Path) -> str:
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(resolved)


def make_figures(weekly, table_stats, strategy_returns, benchmarks, paper_dir):
    paper_dir.mkdir(parents=True, exist_ok=True)
    labels = ["Tail", "Fast", "Pricing", "Coverage", "Hedge"]
    fig, axes = plt.subplots(2, 3, figsize=(13, 7.5))
    for ax, col, label in zip(axes.ravel()[:5], ALPHA_COLS, labels):
        x = weekly[col].dropna()
        row = table_stats[col]
        ax.hist(x, bins=48, color="#6e0e1e", alpha=0.75, edgecolor="white", linewidth=0.3, density=True)
        ax.axvline(x.mean(), color="#555555", lw=0.9, ls="--")
        ax.set_title(f"{label} alpha", fontsize=11)
        lo, hi = row["skew_ci"]
        ax.text(0.97, 0.95, f"skew = {row['skew']:.2f}\nCI [{lo:.2f}, {hi:.2f}]", transform=ax.transAxes,
                ha="right", va="top", fontsize=9, bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#555555"))
    ax = axes.ravel()[5]
    ypos = np.arange(5)[::-1]
    for y, col in zip(ypos, ALPHA_COLS):
        row = table_stats[col]
        lo, hi = row["skew_ci"]
        color = "#6e0e1e" if lo > 0 or hi < 0 else "#555555"
        ax.plot([lo, hi], [y, y], color=color, lw=2)
        ax.plot(row["skew"], y, "o", color=color)
    ax.axvline(0, color="black", lw=0.8)
    ax.set_yticks(ypos, labels)
    ax.set_xlabel("Skewness (95% block-bootstrap CI)")
    ax.set_title("Dependence-robust skewness")
    fig.suptitle(f"Signed weekly alpha signals, EUR/JPY ({weekly.index[0].date()} to {weekly.index[-1].date()}, n={len(weekly)})")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(paper_dir / "alpha_asymmetry_analysis.png", dpi=200)
    plt.close(fig)

    series = {"Asymmetry (0.75)": strategy_returns, **benchmarks}
    colors = ["#6e0e1e", "#888888", "#4a6a8a", "#b0892d"]
    fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True, gridspec_kw={"height_ratios": [2.2, 1]})
    for (label, rets), color in zip(series.items(), colors):
        curve = (1 + rets).cumprod()
        axes[0].plot(curve.index, (curve - 1) * 100, label=label, color=color, lw=1.4)
        axes[1].plot(curve.index, (curve / curve.cummax() - 1) * 100, color=color, lw=1.2)
    axes[0].axhline(0, color="black", lw=0.7)
    axes[0].set_ylabel("Cumulative return (%)")
    axes[0].legend(frameon=False, fontsize=9)
    axes[1].set_ylabel("Drawdown (%)")
    fig.suptitle("Strategy equity curves and drawdowns, one-lag Friday-close convention")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(paper_dir / "backtest_results.png", dpi=200)
    plt.close(fig)


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    lines = []

    def log(message=""):
        print(message)
        lines.append(str(message))

    log("=" * 80)
    log("ALPHA-ASYMMETRY CORRECTED REPLICATION PIPELINE")
    log(f"Generated UTC: {datetime.now(timezone.utc).isoformat()}")
    log("Timing: Friday-close signal, one shift, next Friday-close return")
    log("=" * 80)

    datasets, manifest = load_datasets(args.cache_dir, refresh=args.refresh, offline=args.offline)
    # The committed data_manifest.json is the *reference*: it records the inputs
    # the committed results were produced from, and analysis/fetch_data.py checks
    # a reader's downloads against it.  Writing this run's *observed* manifest
    # over it would overwrite the reference with whatever the reader happens to
    # have, and the comparison would then be against itself.  Keep the two apart.
    write_manifest(manifest, args.output_dir / "data_manifest.observed.json")
    for name, info in manifest["datasets"].items():
        log(f"{name:7s}: {info['rows']} rows, {info['first_date']} to {info['last_date']}, sha256={info['sha256'][:12]}...")
    log("LIMITATION: original raw snapshots were not committed; exact numerical reproduction of the archived run cannot be claimed.")

    weekly = build_weekly_alphas(datasets["EURJPY"], datasets["DXY"])
    n = len(weekly)
    log(f"Analysis-ready weekly sample: n={n}, {weekly.index[0].date()} to {weekly.index[-1].date()}")

    table_stats = {}
    for col in ALPHA_COLS:
        x = weekly[col].dropna()
        skew = float(stats.skew(x, bias=False))
        kurt = float(stats.kurtosis(x, bias=False))
        ci, bse = block_bootstrap_skew_ci(x)
        lb = acorr_ljungbox(x, lags=[4], return_df=True)
        sw, sw_p = stats.shapiro(x)
        k2, k2_p = stats.normaltest(x)
        n_col = len(x)
        jb = n_col / 6 * (skew ** 2 + kurt ** 2 / 4)
        table_stats[col] = {
            "n": n_col, "skew": skew, "ex_kurt": kurt, "skew_ci": list(ci),
            "skew_boot_se": bse, "ai": compute_ai(x), "por": float((x > 0).mean() * 100),
            "skew_t_iid": skew / np.sqrt(6 / n_col), "jb": float(jb), "sw": float(sw), "sw_p": float(sw_p),
            "k2": float(k2), "k2_p": float(k2_p), "lb_q4": float(lb["lb_stat"].iloc[0]),
            "lb_q4_p": float(lb["lb_pvalue"].iloc[0]),
        }
        log(f"{col:15s} skew={skew:6.2f} CI=[{ci[0]:.2f},{ci[1]:.2f}] AI={table_stats[col]['ai']:.2f}")

    base = run_asymmetry_strategy(weekly, 0.75)
    log(f"Baseline: return={base.metrics['return']:.2f}% Sharpe={base.metrics['sharpe']:.3f} "
        f"episodes={base.metrics['holding_episodes']} legs={base.metrics['execution_legs']} "
        f"reversals={base.metrics['reversals']} turnover={base.metrics['turnover']:.2f}")
    base.position_ledger.to_csv(args.output_dir / "position_ledger.csv", date_format="%Y-%m-%d")
    base.trade_ledger.to_csv(args.output_dir / "trade_ledger.csv", index=False, date_format="%Y-%m-%d")

    ma20 = weekly["Close"].rolling(20).mean()
    sd20 = weekly["Close"].rolling(20).std()
    z = (weekly["Close"] - ma20) / sd20
    positions = {
        "Momentum (20w)": np.sign(weekly["Close"].pct_change(20, fill_method=None)).fillna(0.0),
        "Mean reversion (2.0 sigma)": pd.Series(np.where(z > 2, -1.0, np.where(z < -2, 1.0, 0.0)), index=weekly.index),
        "Buy and hold": pd.Series(1.0, index=weekly.index),
    }
    benchmark_returns = {name: simple_strategy(pos, weekly["weekly_return"]) for name, pos in positions.items()}
    table3 = {"Asymmetry": performance(base.returns, base.position)}
    table3.update({name: performance(benchmark_returns[name], pos) for name, pos in positions.items()})

    selected = {}
    for year in range(2018, 2026):
        train = weekly.loc[: f"{year - 1}-12-31"]
        scores = [(t, run_asymmetry_strategy(train, t).metrics["sharpe"]) for t in GRID]
        selected[year] = max(scores, key=lambda item: item[1])[0]
    oos_data = weekly.loc["2017-12-29":].copy()
    threshold_path = pd.Series([selected.get(date.year, selected[2018]) for date in oos_data.index], index=oos_data.index)
    oos = run_asymmetry_strategy(oos_data, threshold_path)
    oos_rows = []
    for year, threshold in selected.items():
        rets = oos.returns[oos.returns.index.year == year]
        events = oos.position_ledger[oos.position_ledger.index.year == year]
        applied_year = oos.applied_position[oos.applied_position.index.year == year]
        active_rets = rets[applied_year.abs() > 0]
        sd = float(rets.std())
        oos_rows.append({"year": year, "threshold": threshold, "return": float((1 + rets).prod() - 1) * 100,
                         "sharpe": float(rets.mean() / sd * np.sqrt(52)) if sd > 0 else 0.0,
                         "hit": float((active_rets > 0).mean() * 100) if len(active_rets) else None,
                         "new_episodes": int(events["event_type"].isin(["entry", "reversal"]).sum())})
    pooled = oos.returns[oos.returns.index.year >= 2018]
    pooled_applied = oos.applied_position[oos.applied_position.index.year >= 2018]
    pooled_active = pooled[pooled_applied.abs() > 0]
    table5 = {"rows": oos_rows, "pooled": {
        "cum_return": float((1 + pooled).prod() - 1) * 100,
        "annualized_return": float(((1 + pooled).prod() ** (52 / len(pooled)) - 1) * 100),
        "sharpe": float(pooled.mean() / pooled.std() * np.sqrt(52)) if pooled.std() > 0 else 0.0,
        "hit": float((pooled_active > 0).mean() * 100) if len(pooled_active) else None,
        "new_episodes": int(oos.position_ledger.loc["2018-01-01":, "event_type"].isin(["entry", "reversal"]).sum())}}

    vix_weekly = datasets["VIX"]["Close"].resample("W-FRI").mean().reindex(weekly.index)
    regimes = {}
    for name, mask in {"low_vix": vix_weekly < 20, "high_vix": vix_weekly >= 20}.items():
        mask = mask.fillna(False)
        regimes[name] = {"n": int(mask.sum()), "tail_skew": float(stats.skew(weekly.loc[mask, "tail_alpha"], bias=False)),
                         "fast_skew": float(stats.skew(weekly.loc[mask, "fast_alpha"], bias=False)),
                         "pricing_skew": float(stats.skew(weekly.loc[mask, "pricing_alpha"], bias=False)),
                         "strategy_return": float((1 + base.returns.loc[mask]).prod() - 1) * 100}
    temporal_masks = {
        "pre_covid": weekly.index.year <= 2019,
        "covid_2020": weekly.index.year == 2020,
        "post_covid": weekly.index.year >= 2021,
        "rate_hike_2022_2025": weekly.index.year >= 2022,
    }
    for name, mask in temporal_masks.items():
        regimes[name] = {
            "n": int(mask.sum()),
            "tail_skew": float(stats.skew(weekly.loc[mask, "tail_alpha"], bias=False)),
            "fast_skew": float(stats.skew(weekly.loc[mask, "fast_alpha"], bias=False)),
            "pricing_skew": float(stats.skew(weekly.loc[mask, "pricing_alpha"], bias=False)),
            "strategy_return": float((1 + base.returns.loc[mask]).prod() - 1) * 100,
        }
    sensitivity = {str(t): run_asymmetry_strategy(weekly, t).metrics for t in GRID}

    factor = pd.DataFrame(index=weekly.index)
    factor["strat"] = base.returns
    factor["dollar"] = datasets["DXY"]["Close"].resample("W-FRI").last().pct_change(fill_method=None).reindex(weekly.index)
    aud = datasets["AUDJPY"]["Close"].resample("W-FRI").last().pct_change(fill_method=None).reindex(weekly.index)
    nzd = datasets["NZDJPY"]["Close"].resample("W-FRI").last().pct_change(fill_method=None).reindex(weekly.index)
    factor["carry"] = pd.concat([aud, nzd], axis=1).mean(axis=1)
    factor["mom"] = simple_strategy(np.sign(weekly["Close"].pct_change(12, fill_method=None)), weekly["weekly_return"])
    factor = factor.dropna()
    inpos_mask = base.applied_position.reindex(factor.index).abs() > 0
    factors = {"full": hac_reg(factor), "in_position": hac_reg(factor.loc[inpos_mask]), "n_in_position": int(inpos_mask.sum())}

    cost_rows = []
    for label, pips in [("Zero cost", 0.0), ("Prime brokerage", 0.3), ("Institutional", 0.7), ("Retail tight", 1.3), ("Retail wide", 2.0)]:
        result = run_asymmetry_strategy(weekly, 0.75, round_trip_cost_pips=pips)
        sd = float(result.net_returns.std())
        cost_rows.append({"name": label, "pips": pips, "net_return": result.metrics["net_return"],
                          "sharpe": float(result.net_returns.mean() / sd * np.sqrt(52)) if sd > 0 else 0.0})
    if base.metrics["return"] <= 0:
        break_even = None
    else:
        lo, hi = 0.0, 100.0
        for _ in range(60):
            mid = (lo + hi) / 2
            net = run_asymmetry_strategy(weekly, 0.75, round_trip_cost_pips=mid).metrics["net_return"]
            lo, hi = (mid, hi) if net > 0 else (lo, mid)
        break_even = (lo + hi) / 2
    costs = {"rows": cost_rows, "break_even_pips": break_even,
             "break_even_note": "not applicable when the zero-cost strategy return is non-positive" if break_even is None else None}

    candidates = {}
    for col in ALPHA_COLS:
        sk = weekly[col].rolling(20, min_periods=10).apply(lambda x: stats.skew(x, bias=False), raw=False)
        candidates[f"asym_{col}"] = simple_strategy(((sk > 0.75) & (weekly[col] > 0)).astype(float), weekly["weekly_return"])
    candidates["asym_full"] = base.returns
    for k in [10, 20, 40]:
        candidates[f"momentum_{k}w"] = simple_strategy(np.sign(weekly["Close"].pct_change(k, fill_method=None)), weekly["weekly_return"])
    for k in [1.5, 2.0]:
        candidates[f"mean_reversion_{k}"] = simple_strategy(pd.Series(np.where(z > k, -1.0, np.where(z < -k, 1.0, 0.0)), index=weekly.index), weekly["weekly_return"])
    candidates["always_long"] = benchmark_returns["Buy and hold"]
    rng_random = np.random.default_rng(SEED)
    candidates["random_candidate"] = simple_strategy(pd.Series(rng_random.choice([-1.0, 1.0], len(weekly)), index=weekly.index), weekly["weekly_return"])
    universe = pd.DataFrame(candidates).fillna(0.0)
    values = universe.to_numpy()
    n_obs, n_k = values.shape
    means = values.mean(axis=0)
    observed_rc = np.sqrt(n_obs) * means.max()
    rng_boot = np.random.default_rng(SEED)
    boot_means = np.empty((1000, n_k))
    for b in range(1000):
        boot_means[b] = values[stationary_bootstrap_indices(n_obs, rng=rng_boot)].mean(axis=0)
    boot_rc = np.sqrt(n_obs) * (boot_means - means).max(axis=1)
    omega = np.sqrt(n_obs) * boot_means.std(axis=0, ddof=1)
    omega[omega == 0] = 1e-12
    t_spa = np.sqrt(n_obs) * means / omega
    observed_spa = max(float(t_spa.max()), 0.0)
    cutoff = -omega / np.sqrt(n_obs) * np.sqrt(2 * np.log(np.log(max(n_obs, 3))))
    recenter = np.where(means >= cutoff, means, 0.0)
    boot_spa = np.maximum((np.sqrt(n_obs) * (boot_means - recenter) / omega).max(axis=1), 0.0)
    snooping = {"formal_benchmark": "zero weekly return", "random_role": "prespecified candidate strategy, not benchmark",
                 "n_strategies": n_k, "white_rc_stat": observed_rc, "white_rc_p": float((boot_rc >= observed_rc).mean()),
                 "spa_stat": observed_spa, "spa_p": float((boot_spa >= observed_spa).mean()),
                 "best_candidate": universe.mean().idxmax(),
                 "annualized_mean_pct": {k: float(v * 52 * 100) for k, v in universe.mean().items()}}

    ret = weekly["weekly_return"].dropna()
    threshold_u = float(ret.abs().quantile(0.95))
    exceed_idx = np.where(ret.abs().to_numpy() > threshold_u)[0]
    theta = ferro_segers_theta(exceed_idx)
    gaps = np.diff(exceed_idx)
    rng_evt = np.random.default_rng(SEED)
    theta_boot = [ferro_segers_theta(np.r_[0, np.cumsum(rng_evt.choice(gaps, len(gaps), replace=True))]) for _ in range(2000)]
    clusters, current = [], [exceed_idx[0]]
    for idx in exceed_idx[1:]:
        if idx - current[-1] <= 5:
            current.append(idx)
        else:
            clusters.append(current)
            current = [idx]
    clusters.append(current)
    excess = np.array([ret.abs().to_numpy()[cluster].max() for cluster in clusters]) - threshold_u
    xi, _, scale = stats.genpareto.fit(excess, floc=0)
    ks_stat, ks_p = stats.kstest(excess, "genpareto", args=(xi, 0, scale))
    xi_boot = []
    for _ in range(2000):
        try:
            xi_boot.append(stats.genpareto.fit(rng_evt.choice(excess, len(excess), replace=True), floc=0)[0])
        except Exception:
            pass
    evt = {"input": "absolute Friday-close-to-Friday-close EURJPY returns", "threshold_pct": threshold_u * 100,
           "raw_exceedances": len(exceed_idx), "clusters": len(clusters),
           "theta": theta, "theta_ci": list(np.percentile(theta_boot, [2.5, 97.5])), "xi": xi,
           "xi_ci": list(np.percentile(xi_boot, [2.5, 97.5])), "scale": scale, "ks_stat": ks_stat, "ks_p": ks_p}

    rng_ci = np.random.default_rng(SEED)
    ann_boot, sharpe_boot = [], []
    xret = base.returns.to_numpy()
    for _ in range(2000):
        sample = xret[stationary_bootstrap_indices(len(xret), rng=rng_ci)]
        growth = float(np.prod(1 + sample))
        ann_boot.append((growth ** (52 / len(sample)) - 1) * 100)
        sample_sd = sample.std(ddof=1)
        sharpe_boot.append(sample.mean() / sample_sd * np.sqrt(52) if sample_sd > 0 else 0.0)
    inference = {"annualized_return": ((1 + base.metrics["return"] / 100) ** (52 / len(xret)) - 1) * 100,
                 "annualized_return_ci": list(np.percentile(ann_boot, [2.5, 97.5])),
                 "sharpe": base.metrics["sharpe"], "sharpe_ci": list(np.percentile(sharpe_boot, [2.5, 97.5]))}

    cross_market = {}
    for name in ["EURJPY", "GBPUSD", "SPY", "GLD"]:
        market_weekly = weekly if name == "EURJPY" else build_weekly_alphas(datasets[name])
        if "hedge_alpha" not in market_weekly:
            market_weekly["hedge_alpha"] = np.nan
        result = run_asymmetry_strategy(market_weekly, 0.75)
        cross_market[name] = {"n": len(market_weekly), "tail_skew": float(stats.skew(market_weekly["tail_alpha"], bias=False)),
                              "fast_skew": float(stats.skew(market_weekly["fast_alpha"], bias=False)),
                              "pricing_skew": float(stats.skew(market_weekly["pricing_alpha"], bias=False)),
                              "coverage_skew": float(stats.skew(market_weekly["coverage_alpha"], bias=False)),
                              "strategy_return": result.metrics["return"], "holding_episodes": result.metrics["holding_episodes"],
                              "buy_hold_return": float(market_weekly["Close"].iloc[-1] / market_weekly["Close"].iloc[0] - 1) * 100}

    make_figures(weekly, table_stats, base.returns, benchmark_returns, args.paper_dir)

    results = {
        "specification": {"execution": "Friday-close signal and execution proxy; position earns next Friday-close return (one shift)",
                          "max_holding_return_periods": 4, "simultaneous_signals": "flat", "weekly_resizing": False,
                          "position_size_units": "1.0 to 2.0 gross notional units; values above 1 imply leverage",
                          "hedge_alpha": "100-day rolling correlation multiplied by fixed -0.02 proxy",
                          "evt_input": "absolute Friday-close-to-Friday-close returns, separate from daily tail-alpha flags"},
        "data_manifest": manifest,
        "sample": {"raw_weekly_start": "2015-11-06", "analysis_start": weekly.index[0], "analysis_end": weekly.index[-1], "n": n},
        "alpha_statistics": table_stats, "baseline": base.metrics, "benchmarks": table3,
        "walk_forward": table5, "regimes": regimes, "sensitivity": sensitivity,
        "factor_attribution": factors, "transaction_costs": costs, "data_snooping": snooping,
        "evt": evt, "return_inference": inference, "cross_market": cross_market,
    }

    safe_results = json_safe(results)
    (args.output_dir / "full_pipeline_results.json").write_text(json.dumps(safe_results, indent=2) + "\n", encoding="utf-8")
    log(f"Regime rows: low VIX={regimes['low_vix']['n']}, high VIX={regimes['high_vix']['n']} (classified after one full run)")
    log(f"White RC p={snooping['white_rc_p']:.3f}; SPA p={snooping['spa_p']:.3f}; best candidate={snooping['best_candidate']}")
    log(f"Outputs: {portable_path(args.output_dir)}")
    (args.output_dir / "full_pipeline_results.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Values published in commit 4d21c69. The original raw files were absent,
    # so these are a reported-results reference, not an independently rerun control.
    old_base = {"return": 3.6016, "sharpe": 0.1489, "mdd": -7.9572,
                "trades": 17, "in_position_weeks": 25}
    old_ai = {"tail_alpha": 0.1716, "fast_alpha": 0.9577,
              "pricing_alpha": 0.8050, "coverage_alpha": 3.4533,
              "hedge_alpha": 1.4018}
    comparisons = [
        ("Baseline cumulative return (%)", old_base.get("return"), base.metrics["return"], "holding rule + removal of extra lag + corrected AI sizing"),
        ("Baseline Sharpe", old_base.get("sharpe"), base.metrics["sharpe"], "same corrected return chronology"),
        ("Baseline maximum drawdown (%)", old_base.get("mdd"), base.metrics["mdd"], "same corrected return chronology"),
        ("Holding episodes", old_base.get("trades"), base.metrics["holding_episodes"], "episode ledger replaces position-change-events/2"),
        ("Execution legs", None, base.metrics["execution_legs"], "dated turnover accounting"),
        ("In-position weeks", old_base.get("in_position_weeks"), base.metrics["in_position_weeks"], "hold until opposition/expiry instead of exit on signal loss"),
        ("Walk-forward cumulative return (%)", 2.46, table5["pooled"]["cum_return"], "corrected strategy and sequential OOS state path"),
        ("Walk-forward new episodes", 3, table5["pooled"]["new_episodes"], "episode ledger replaces event-pairs"),
        ("Low-VIX strategy return (%)", 2.38, regimes["low_vix"]["strategy_return"], "attribute one full-calendar strategy run by weekly VIX"),
        ("High-VIX strategy return (%)", 2.67, regimes["high_vix"]["strategy_return"], "attribute one full-calendar strategy run by weekly VIX"),
        ("Full-sample factor intercept", 0.00008, factors["full"]["coef"]["const"]["b"], "corrected dependent return series"),
        ("In-position factor sample", 25, factors["n_in_position"], "corrected holding periods"),
        ("Retail-wide net return (%)", 3.22, costs["rows"][-1]["net_return"], "corrected strategy plus dated turnover costs"),
        ("White Reality Check p-value", 0.15, snooping["white_rc_p"], "corrected full-strategy candidate; common one-lag timing"),
        ("Hansen SPA p-value", 0.28, snooping["spa_p"], "corrected candidate universe; common one-lag timing"),
        ("Annualized return (%)", 0.366, inference["annualized_return"], "corrected strategy return series"),
        ("GBP/USD strategy return (%)", 17.18, cross_market["GBPUSD"]["strategy_return"], "corrected strategy chronology/holding/AI"),
        ("SPY strategy return (%)", 11.66, cross_market["SPY"]["strategy_return"], "corrected strategy; adjusted-price download fixed explicitly"),
        ("GLD strategy return (%)", -30.26, cross_market["GLD"]["strategy_return"], "corrected strategy chronology/holding/AI"),
    ]
    for col in ALPHA_COLS:
        comparisons.append((f"{col} AI", old_ai[col], table_stats[col]["ai"],
                            "overall-mean squared deviations replace subgroup sample variances"))
    pd.DataFrame(comparisons, columns=["metric", "before_committed", "after_corrected", "reason"]).to_csv(
        args.output_dir / "before_after_results.csv", index=False
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
