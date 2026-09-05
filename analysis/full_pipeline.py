#!/usr/bin/env python3
"""
Full reproduction pipeline for the alpha-asymmetry paper (DAI-2605).

Built 2026-07-07 to close panel-review T0.1 and the T1 recompute cluster:
every table the paper reports is generated here from ONE strategy object
(run_asymmetry_strategy, identical to recompute_tables.py) and one data pull.

Covers:
  [A] Tables 1-3   : moments, AI, PNR, normality tests, t-stats on true n,
                     per-series Ljung-Box, block-bootstrap skewness CIs
  [B] Table 4      : full-sample backtest (reproduction check: 17 trades, 3.60%)
  [C] Table 5      : walk-forward OOS (expanding train, threshold selected on
                     train Sharpe, tested on next calendar year) -- REBUILD
  [D] Table 8      : factor regression with HONEST PROXY factors (DXY dollar,
                     AUD/NZD-vs-JPY spot carry proxy, 12w TS-momentum), both
                     full-sample and in-position-weeks-only -- REBUILD
  [E] Table 10     : transaction costs, monotone by construction (carry
                     excluded uniformly) + break-even pips -- REBUILD
  [F] Table 11     : White Reality Check + Hansen SPA, stationary bootstrap
                     (l=4, B=1000, seeded), 13-strategy universe -- REBUILD
  [G] Table 9      : GPD tail fit (runs declustering, 5-week separation, with
                     bootstrap xi CI) + Ferro-Segers extremal index with a
                     VALID bootstrap CI (resampled inter-exceedance times)
  [H] Sec. 3.3     : stationary-bootstrap CIs for the annualized return and
                     Sharpe ratio of the baseline strategy (l=4, B=2000)
  [I] Table 3      : strategy performance comparison -- benchmark rows
                     (20w TS-momentum, 2.0-sigma mean reversion, buy & hold)
                     computed on the same weekly plumbing as the Table 11
                     universe (return series asserted identical) -- REBUILD
  [J] Table 4      : cross-market check (GBP/USD, SPY, GLD): identical alpha
                     construction (hedge excluded, EUR/JPY-specific), signed
                     weekly skewness + asymmetry-strategy and buy-and-hold
                     returns per market -- REBUILD

Data: yfinance (EURJPY=X, DX-Y.NYB, ^VIX, AUDJPY=X, NZDJPY=X, GBPUSD=X,
SPY, GLD). Seeds fixed; results written to full_pipeline_results.txt + .json.
"""

import json
import warnings
from datetime import datetime

import numpy as np
import pandas as pd
import yfinance as yf
from scipy import stats

warnings.filterwarnings("ignore")
np.random.seed(42)

OUT_TXT = "/home/purrpower/work/projects/papers/papers-official/alpha-asymmetry/analysis/full_pipeline_results.txt"
OUT_JSON = "/home/purrpower/work/projects/papers/papers-official/alpha-asymmetry/analysis/full_pipeline_results.json"

RESULTS = {}
LINES = []


def log(s=""):
    print(s)
    LINES.append(str(s))


log("=" * 80)
log("ALPHA-ASYMMETRY FULL PIPELINE")
log(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
log("=" * 80)

# =============================================================================
# 1. DATA
# =============================================================================
log("\n[1] Downloading data...")


def dl(ticker):
    d = yf.download(ticker, start="2014-06-01", end="2025-08-31",
                    interval="1d", progress=False)
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = d.columns.get_level_values(0)
    return d


daily = dl("EURJPY=X")
dxy_daily = dl("DX-Y.NYB")
vix_daily = dl("^VIX")
audjpy_daily = dl("AUDJPY=X")
nzdjpy_daily = dl("NZDJPY=X")

for name, d in [("EURJPY", daily), ("DXY", dxy_daily), ("VIX", vix_daily),
                ("AUDJPY", audjpy_daily), ("NZDJPY", nzdjpy_daily)]:
    log(f"  {name}: {len(d)} daily obs ({d.index[0].date()} .. {d.index[-1].date()})")

# =============================================================================
# 2. DAILY ALPHAS (verbatim from recompute_tables.py)
# =============================================================================
df = daily[["Close"]].copy()
df["returns"] = df["Close"].pct_change()

rolling_q95 = df["returns"].abs().rolling(252, min_periods=60).quantile(0.95)
df["tail_alpha"] = np.where(df["returns"].abs() > rolling_q95,
                            np.sign(df["returns"]) * df["returns"].abs(), 0.0)

df["ret_5d"] = df["Close"].pct_change(5)
df["vol_20d"] = df["returns"].rolling(20).std()
df["fast_alpha"] = df["ret_5d"] / (df["vol_20d"] * np.sqrt(5))

df["ma_60d"] = df["Close"].rolling(60).mean()
df["std_60d"] = df["Close"].rolling(60).std()
df["pricing_alpha"] = (df["Close"] - df["ma_60d"]) / df["std_60d"]

df["vol_20d_lag5"] = df["vol_20d"].shift(5)
df["coverage_alpha"] = df["vol_20d"] / df["vol_20d_lag5"] - 1

dxy_returns = dxy_daily["Close"].pct_change()
merged_corr = pd.DataFrame({"eurjpy_ret": df["returns"],
                            "dxy_ret": dxy_returns}).dropna()
rolling_corr = merged_corr["eurjpy_ret"].rolling(100).corr(merged_corr["dxy_ret"])
rate_diff = -0.02
df["hedge_alpha"] = rolling_corr.reindex(df.index) * rate_diff

# =============================================================================
# 3. WEEKLY AGGREGATION (verbatim)
# =============================================================================
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
N = len(weekly)
log(f"\n[2] Weekly analysis sample: n={N} ({weekly.index[0].date()} .. {weekly.index[-1].date()})")
RESULTS["n_weekly"] = N


# =============================================================================
# 4. STRATEGY (verbatim from recompute_tables.py)
# =============================================================================
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

    strategy_returns = (position.shift(1) * d["weekly_return"]).fillna(0)
    cum = (1 + strategy_returns).prod() - 1
    cum_series = (1 + strategy_returns).cumprod()
    mdd = ((cum_series / cum_series.cummax()) - 1).min()
    mu, sd = strategy_returns.mean(), strategy_returns.std()
    sharpe = (mu / sd) * np.sqrt(52) if sd > 0 else 0.0
    in_pos = strategy_returns[position.shift(1).abs() > 0]
    hit = (in_pos > 0).mean() * 100 if len(in_pos) > 0 else np.nan
    n_trades = int((position.diff().abs() > 0).sum() // 2)
    return {"return": cum * 100, "sharpe": sharpe, "mdd": mdd * 100,
            "trades": n_trades, "hit": hit, "rets": strategy_returns,
            "position": position}


# =============================================================================
# 5. [B] TABLE 4 REPRODUCTION CHECK
# =============================================================================
log("\n[3] Table 4 reproduction (threshold=0.75, full sample):")
base = run_asymmetry_strategy(weekly, 0.75)
log(f"  Return={base['return']:.2f}%  Sharpe={base['sharpe']:.3f}  "
    f"MDD={base['mdd']:.2f}%  Trades={base['trades']}  Hit={base['hit']:.1f}%")
RESULTS["table4"] = {k: (round(float(v), 4) if isinstance(v, (int, float, np.floating)) else None)
                     for k, v in base.items() if k not in ("rets", "position")}

# =============================================================================
# 6. [A] TABLES 1-3: MOMENTS + TESTS ON THE TRUE SAMPLE
# =============================================================================
log("\n[4] Tables 1-3: moments and tests on true n...")
alpha_cols = ["tail_alpha", "fast_alpha", "pricing_alpha", "coverage_alpha", "hedge_alpha"]
tab123 = {}
rng = np.random.default_rng(42)


def block_bootstrap_skew_ci(x, B=2000, block=13, seed=42):
    """Circular block bootstrap percentile CI for skewness (dependence-robust)."""
    r = np.random.default_rng(seed)
    x = np.asarray(x)
    n = len(x)
    nblocks = int(np.ceil(n / block))
    boot = np.empty(B)
    for b in range(B):
        starts = r.integers(0, n, nblocks)
        idx = (starts[:, None] + np.arange(block)[None, :]).ravel() % n
        boot[b] = stats.skew(x[idx[:n]])
    return np.percentile(boot, [2.5, 97.5]), boot.std(ddof=1)


for c in alpha_cols:
    x = weekly[c].dropna()
    n = len(x)
    g1 = stats.skew(x)
    g2 = stats.kurtosis(x)  # excess
    se_g1 = np.sqrt(6.0 / n)
    t_g1 = g1 / se_g1
    jb = (n / 6.0) * (g1 ** 2 + g2 ** 2 / 4.0)
    sw_stat, sw_p = stats.shapiro(x) if n <= 5000 else (np.nan, np.nan)
    k2_stat, k2_p = stats.normaltest(x)
    # per-series Ljung-Box Q(4)
    from statsmodels.stats.diagnostic import acorr_ljungbox
    lb = acorr_ljungbox(x, lags=[4], return_df=True)
    q4, q4p = float(lb["lb_stat"].iloc[0]), float(lb["lb_pvalue"].iloc[0])
    (ci_lo, ci_hi), bse = block_bootstrap_skew_ci(x)
    mean_val = x.mean()
    pos = x[x > mean_val] - mean_val
    neg = x[x < mean_val] - mean_val
    ai = pos.var() / neg.var() if len(neg) > 0 and neg.var() > 0 else 1.0
    pnr = (x > 0).mean() * 100
    tab123[c] = dict(n=n, skew=g1, ex_kurt=g2, t=t_g1, jb=jb, sw=sw_stat, sw_p=sw_p,
                     k2=k2_stat, k2_p=k2_p, lb_q4=q4, lb_q4_p=q4p,
                     skew_ci=[ci_lo, ci_hi], skew_boot_se=bse, ai=ai, pnr=pnr)
    log(f"  {c:<15} n={n} skew={g1:6.2f} t={t_g1:6.1f} (SE={se_g1:.3f}) "
        f"exkurt={g2:7.2f} JB={jb:9.0f} K2={k2_stat:7.1f} LB4={q4:7.1f}(p={q4p:.3f}) "
        f"skewCI(block)=[{ci_lo:.2f},{ci_hi:.2f}] AI={ai:.2f} PNR={pnr:.1f}")
RESULTS["tables123"] = {k: {kk: (list(np.round(vv, 4)) if isinstance(vv, list) else round(float(vv), 4))
                            for kk, vv in v.items()} for k, v in tab123.items()}

# =============================================================================
# 7. [C] TABLE 5 REBUILD: WALK-FORWARD OOS
# =============================================================================
log("\n[5] Table 5 REBUILD: walk-forward OOS (expanding train, threshold by train Sharpe)...")
GRID = [0.50, 0.75, 1.00, 1.25]
oos_rows = []
pooled_rets = []

for test_year in range(2018, 2026):
    train = weekly.loc[: f"{test_year - 1}-12-31"]
    test_start, test_end = f"{test_year}-01-01", f"{test_year}-12-31"
    if len(weekly.loc[test_start:test_end]) < 4:
        continue
    # select threshold on training window
    best_t, best_sharpe = None, -np.inf
    for t in GRID:
        r = run_asymmetry_strategy(train, t)
        if r["trades"] == 0:
            continue
        if r["sharpe"] > best_sharpe:
            best_sharpe, best_t = r["sharpe"], t
    if best_t is None:
        best_t = 0.75
    # run on full data with chosen threshold, slice test year
    full = run_asymmetry_strategy(weekly, best_t)
    tr = full["rets"].loc[test_start:test_end]
    tpos = full["position"].loc[test_start:test_end]
    cum = (1 + tr).prod() - 1
    sd = tr.std()
    shp = (tr.mean() / sd) * np.sqrt(52) if sd > 0 else 0.0
    in_pos = tr[full["position"].shift(1).loc[test_start:test_end].abs() > 0]
    hit = (in_pos > 0).mean() * 100 if len(in_pos) > 0 else np.nan
    ntr = int((tpos.diff().abs() > 0).sum() // 2)
    pooled_rets.append(tr)
    oos_rows.append(dict(year=test_year, thresh=best_t, ret=cum * 100,
                         sharpe=shp, hit=hit, trades=ntr))
    hit_s = f"{hit:.1f}" if np.isfinite(hit) else "---"
    log(f"  {test_year}: train->{best_t:.2f}  OOS ret={cum*100:6.2f}%  "
        f"Sharpe={shp:5.2f}  hit={hit_s}%  trades={ntr}")

pool = pd.concat(pooled_rets)
pool_cum = (1 + pool).prod() - 1
pool_ann = (1 + pool_cum) ** (52 / len(pool)) - 1
pool_shp = (pool.mean() / pool.std()) * np.sqrt(52) if pool.std() > 0 else 0.0
pool_trades = sum(r["trades"] for r in oos_rows)
in_pos_all = pool[pool != 0]
pool_hit = (in_pos_all > 0).mean() * 100 if len(in_pos_all) else np.nan
log(f"  POOLED: cum={pool_cum*100:.2f}% (ann={pool_ann*100:.2f}%)  Sharpe={pool_shp:.2f}  "
    f"trades={pool_trades}  hit={pool_hit:.1f}%")
RESULTS["table5"] = dict(rows=oos_rows, pooled=dict(
    cum=round(pool_cum * 100, 2), ann=round(pool_ann * 100, 2),
    sharpe=round(pool_shp, 3), trades=pool_trades,
    hit=round(float(pool_hit), 1) if np.isfinite(pool_hit) else None))

# =============================================================================
# 8. [D] TABLE 8 REBUILD: FACTOR REGRESSION WITH HONEST PROXIES
# =============================================================================
log("\n[6] Table 8 REBUILD: factor regression (proxy factors, NW-HAC)...")
import statsmodels.api as sm

wk = pd.DataFrame(index=weekly.index)
wk["strat"] = base["rets"]
wk["dollar"] = dxy_daily["Close"].resample("W-FRI").last().pct_change().reindex(weekly.index)
aud = audjpy_daily["Close"].resample("W-FRI").last().pct_change().reindex(weekly.index)
nzd = nzdjpy_daily["Close"].resample("W-FRI").last().pct_change().reindex(weekly.index)
wk["carry"] = pd.concat([aud, nzd], axis=1).mean(axis=1)
trailing12 = weekly["Close"].pct_change(12)
wk["mom"] = (np.sign(trailing12).shift(1) * weekly["weekly_return"]).reindex(weekly.index)
wk = wk.dropna()


def hac_reg(dat, label):
    X = sm.add_constant(dat[["carry", "mom", "dollar"]])
    m = sm.OLS(dat["strat"], X).fit(cov_type="HAC", cov_kwds={"maxlags": 4})
    log(f"  [{label}] n={int(m.nobs)}  R2={m.rsquared:.3f}  F={m.fvalue:.2f}")
    for nm in ["const", "carry", "mom", "dollar"]:
        log(f"    {nm:<7} b={m.params[nm]: .5f}  t={m.tvalues[nm]: .2f}  p={m.pvalues[nm]:.3f}")
    return dict(n=int(m.nobs), r2=round(m.rsquared, 4), adj_r2=round(m.rsquared_adj, 4),
                F=round(float(m.fvalue), 2),
                coef={nm: dict(b=round(m.params[nm], 5), t=round(m.tvalues[nm], 2),
                               p=round(m.pvalues[nm], 4)) for nm in
                      ["const", "carry", "mom", "dollar"]})


full_reg = hac_reg(wk, "full sample incl. flat weeks")
inpos_mask = base["position"].shift(1).reindex(wk.index).abs() > 0
inpos_reg = hac_reg(wk[inpos_mask], "in-position weeks only") if inpos_mask.sum() > 10 else None
log(f"  In-position weeks: {int(inpos_mask.sum())} of {len(wk)} (effective N)")
RESULTS["table8"] = dict(full=full_reg, in_position=inpos_reg,
                         n_inpos=int(inpos_mask.sum()))

# =============================================================================
# 9. [E] TABLE 10 REBUILD: TRANSACTION COSTS (MONOTONE BY CONSTRUCTION)
# =============================================================================
log("\n[7] Table 10 REBUILD: transaction costs (carry excluded uniformly)...")
price_avg = weekly["Close"].mean()
pip = 0.01  # EURJPY pip


def net_of_costs(total_pips_roundtrip):
    """Cost charged per position-change leg, proportional to |dPos|."""
    legs = base["position"].diff().abs().fillna(0)
    cost_per_unit = (total_pips_roundtrip / 2.0) * pip / price_avg
    cost_stream = legs * cost_per_unit
    net = base["rets"] - cost_stream
    cum = (1 + net).prod() - 1
    sd = net.std()
    shp = (net.mean() / sd) * np.sqrt(52) if sd > 0 else 0.0
    return cum * 100, shp


scenarios = [("Zero Cost (Baseline)", 0.0), ("Prime Brokerage", 0.3),
             ("Institutional", 0.7), ("Retail (Tight)", 1.3), ("Retail (Wide)", 2.0)]
tab10 = []
for name, pips in scenarios:
    ret, shp = net_of_costs(pips)
    tab10.append(dict(name=name, pips=pips, net=round(ret, 2), sharpe=round(shp, 3)))
    log(f"  {name:<22} {pips:>4.1f} pips  net={ret:6.2f}%  Sharpe={shp:.3f}")

lo, hi = 0.0, 50.0
for _ in range(60):
    mid = (lo + hi) / 2
    if net_of_costs(mid)[0] > 0:
        lo = mid
    else:
        hi = mid
breakeven = (lo + hi) / 2
log(f"  Break-even: {breakeven:.1f} pips round-trip")
RESULTS["table10"] = dict(rows=tab10, breakeven=round(breakeven, 2))

# =============================================================================
# 10. [F] TABLE 11 REBUILD: WHITE RC + HANSEN SPA
# =============================================================================
log("\n[8] Table 11 REBUILD: White RC + Hansen SPA (stationary bootstrap, l=4, B=1000)...")


def simple_strategy(position_series):
    return (position_series.shift(1) * weekly["weekly_return"]).fillna(0)


candidates = {}
# 5 asymmetry variants: long-only, per-alpha skew signal (simplified template)
for c in alpha_cols:
    sk = weekly[c].rolling(20, min_periods=10).apply(
        lambda x: stats.skew(x, nan_policy="omit"), raw=False)
    pos = ((sk > 0.75) & (weekly[c] > 0)).astype(float)
    candidates[f"asym_{c.split('_')[0]}"] = simple_strategy(pos)
# full two-sided strategy (the paper's headline object)
candidates["asym_full"] = base["rets"]
# momentum 10/20/40w
for k in [10, 20, 40]:
    pos = np.sign(weekly["Close"].pct_change(k))
    candidates[f"mom_{k}w"] = simple_strategy(pos)
# mean reversion 1.5 / 2.0 sigma
ma20 = weekly["Close"].rolling(20).mean()
sd20 = weekly["Close"].rolling(20).std()
z = (weekly["Close"] - ma20) / sd20
for k in [1.5, 2.0]:
    pos = pd.Series(0.0, index=weekly.index)
    pos[z > k] = -1.0
    pos[z < -k] = 1.0
    candidates[f"mr_{k}"] = simple_strategy(pos)
# carry-only (always long) and random benchmark
candidates["carry_only"] = simple_strategy(pd.Series(1.0, index=weekly.index))
rng_r = np.random.default_rng(42)
candidates["random"] = simple_strategy(
    pd.Series(rng_r.choice([-1.0, 1.0], size=len(weekly)), index=weekly.index))

F = pd.DataFrame(candidates).fillna(0)  # f_k,t = candidate return - benchmark(0)
n_obs, n_k = F.shape
log(f"  Universe: {n_k} strategies x {n_obs} weeks")
fbar = F.mean().values
obs_stat = np.sqrt(n_obs) * fbar.max()


def stationary_bootstrap_indices(n, expected_block=4.0, size=None, r=None):
    size = size or n
    p = 1.0 / expected_block
    idx = np.empty(size, dtype=int)
    idx[0] = r.integers(0, n)
    for t in range(1, size):
        if r.random() < p:
            idx[t] = r.integers(0, n)
        else:
            idx[t] = (idx[t - 1] + 1) % n
    return idx


B = 1000
r = np.random.default_rng(42)
boot_max = np.empty(B)
boot_means = np.empty((B, n_k))
Fv = F.values
for b in range(B):
    idx = stationary_bootstrap_indices(n_obs, 4.0, r=r)
    m = Fv[idx].mean(axis=0)
    boot_means[b] = m
    boot_max[b] = np.sqrt(n_obs) * (m - fbar).max()
rc_p = float((boot_max >= obs_stat).mean())
log(f"  White RC: stat={obs_stat:.3f}  p={rc_p:.3f}")

# Hansen SPA (consistent p-value)
omega = np.sqrt(n_obs) * boot_means.std(axis=0, ddof=1)
omega[omega == 0] = 1e-12
t_spa = np.sqrt(n_obs) * fbar / omega
obs_spa = max(t_spa.max(), 0.0)
thresh = -omega / np.sqrt(n_obs) * np.sqrt(2 * np.log(np.log(max(n_obs, 3))))
recenter = np.where(fbar >= thresh, fbar, 0.0)
boot_spa = np.empty(B)
for b in range(B):
    tb = np.sqrt(n_obs) * (boot_means[b] - recenter) / omega
    boot_spa[b] = max(tb.max(), 0.0)
spa_p = float((boot_spa >= obs_spa).mean())
log(f"  Hansen SPA: stat={obs_spa:.3f}  p={spa_p:.3f}")
best = F.mean().idxmax()
log(f"  Best candidate by mean return: {best}")
RESULTS["table11"] = dict(rc_stat=round(obs_stat, 3), rc_p=rc_p,
                          spa_stat=round(obs_spa, 3), spa_p=spa_p,
                          n_strategies=n_k, best=best,
                          means_annualized_pct={k: round(float(v) * 52 * 100, 2)
                                                for k, v in F.mean().items()})

# =============================================================================
# 11. [G] TABLE 9: GPD + FERRO-SEGERS THETA WITH VALID CI
# =============================================================================
log("\n[9] Table 9: EVT tail fit + extremal index with valid bootstrap CI...")
ret = weekly["weekly_return"].dropna()
u = ret.abs().quantile(0.95)
exceed_idx = np.where(ret.abs().values > u)[0]
n_exc = len(exceed_idx)


def ferro_segers_theta(exc_idx):
    T = np.diff(exc_idx)
    if len(T) < 2:
        return np.nan
    if T.max() <= 2:
        num = 2 * (T.sum()) ** 2
        den = len(T) * (T ** 2).sum()
    else:
        num = 2 * ((T - 1).sum()) ** 2
        den = len(T) * ((T - 1) * (T - 2)).sum()
    return min(1.0, num / den) if den > 0 else np.nan


theta = ferro_segers_theta(exceed_idx)
r2 = np.random.default_rng(42)
T_gaps = np.diff(exceed_idx)
boot_theta = []
for b in range(2000):
    gaps = r2.choice(T_gaps, size=len(T_gaps), replace=True)
    idx_b = np.concatenate([[0], np.cumsum(gaps)])
    th = ferro_segers_theta(idx_b)
    if np.isfinite(th):
        boot_theta.append(th)
theta_ci = np.percentile(boot_theta, [2.5, 97.5])
log(f"  Exceedances (|r|>q95={u*100:.2f}%): {n_exc}")
log(f"  Ferro-Segers theta={theta:.3f}  95% CI=[{theta_ci[0]:.3f}, {theta_ci[1]:.3f}]  "
    f"(bootstrap on inter-exceedance times, B=2000)")

# GPD fit on cluster maxima (runs declustering, minimum 5-week separation,
# as stated in Sec. 5.4 of the paper)
RUN_LEN = 5
clusters = []
current = [exceed_idx[0]]
for i in exceed_idx[1:]:
    if i - current[-1] <= RUN_LEN:
        current.append(i)
    else:
        clusters.append(current)
        current = [i]
clusters.append(current)
cluster_max = np.array([ret.abs().values[c].max() for c in clusters])
excesses = cluster_max - u
xi, loc, sc = stats.genpareto.fit(excesses, floc=0)
ks_stat, ks_p = stats.kstest(excesses, "genpareto", args=(xi, 0, sc))
# xi CI: nonparametric bootstrap of the cluster maxima (B=2000, seeded)
r3 = np.random.default_rng(42)
boot_xi = []
for b in range(2000):
    s = r3.choice(excesses, size=len(excesses), replace=True)
    try:
        xb, _, _ = stats.genpareto.fit(s, floc=0)
        boot_xi.append(xb)
    except Exception:
        pass
xi_ci = np.percentile(boot_xi, [2.5, 97.5])
log(f"  Clusters: {len(clusters)} (run length {RUN_LEN}); GPD xi={xi:.3f} "
    f"CI=[{xi_ci[0]:.2f}, {xi_ci[1]:.2f}] sigma={sc:.4f}  KS p={ks_p:.3f}")
RESULTS["table9"] = dict(n_exceed=n_exc, n_clusters=len(clusters),
                         theta=round(float(theta), 3),
                         theta_ci=[round(float(x), 3) for x in theta_ci],
                         xi=round(float(xi), 3),
                         xi_ci=[round(float(x), 3) for x in xi_ci],
                         sigma=round(float(sc), 4),
                         ks_p=round(float(ks_p), 3), u_pct=round(float(u) * 100, 3))

# =============================================================================
# 11b. [H] SEC 3.3: STATIONARY-BOOTSTRAP CIs FOR ANNUALIZED RETURN AND SHARPE
# =============================================================================
log("\n[10] Sec 3.3: stationary-bootstrap CIs for annualized return + Sharpe (l=4, B=2000)...")
x_sig = base["rets"].values
n_sig = len(x_sig)
r4 = np.random.default_rng(42)
boot_ann, boot_shp = [], []
for b in range(2000):
    idx = stationary_bootstrap_indices(n_sig, 4.0, r=r4)
    xb = x_sig[idx]
    cumb = (1 + xb).prod() - 1
    boot_ann.append(((1 + cumb) ** (52 / n_sig) - 1) * 100)
    sd = xb.std()
    boot_shp.append((xb.mean() / sd) * np.sqrt(52) if sd > 0 else 0.0)
ann_ci = np.percentile(boot_ann, [2.5, 97.5])
shp_ci = np.percentile(boot_shp, [2.5, 97.5])
point_ann = ((1 + base["return"] / 100) ** (52 / n_sig) - 1) * 100
log(f"  Annualized return: point={point_ann:.2f}%  95% CI=[{ann_ci[0]:.2f}%, {ann_ci[1]:.2f}%]")
log(f"  Annualized Sharpe: point={base['sharpe']:.3f}  95% CI=[{shp_ci[0]:.2f}, {shp_ci[1]:.2f}]")
RESULTS["statsig"] = dict(ann_return_pct=round(float(point_ann), 3),
                          ann_return_ci=[round(float(v), 2) for v in ann_ci],
                          sharpe=round(float(base["sharpe"]), 3),
                          sharpe_ci=[round(float(v), 2) for v in shp_ci])

# =============================================================================
# 12. [I] TABLE 3 REBUILD: STRATEGY PERFORMANCE COMPARISON
# =============================================================================
log("\n[11] Table 3 REBUILD: benchmarks on the same weekly plumbing as Table 11...")


def perf_metrics(rets, position):
    """Six Table-3 metrics. Sortino uses the annualized mean over the standard
    deviation of negative-return weeks (the definition the asymmetry row's
    published 0.062 corresponds to). Trades = position-change events // 2
    (completed round trips; a sign flip counts as one event)."""
    cum = (1 + rets).prod() - 1
    mu, sd = rets.mean(), rets.std()
    vol_ann = sd * np.sqrt(52) * 100
    sharpe = (mu / sd) * np.sqrt(52) if sd > 0 else 0.0
    neg = rets[rets < 0]
    ddev = neg.std()
    sortino = (mu / ddev) * np.sqrt(52) if len(neg) > 1 and ddev > 0 else 0.0
    cs = (1 + rets).cumprod()
    mdd = ((cs / cs.cummax()) - 1).min() * 100
    legs = position.diff().abs().fillna(position.abs())
    n_events = int((legs > 0).sum())
    return dict(ret=round(float(cum) * 100, 2), vol=round(float(vol_ann), 2),
                sharpe=round(float(sharpe), 3), sortino=round(float(sortino), 3),
                mdd=round(float(mdd), 2), trades=n_events // 2, events=n_events)


# benchmark positions: identical definitions to the Table 11 universe, with
# NaN warmup weeks treated as flat so trades can be counted
pos_mom20 = np.sign(weekly["Close"].pct_change(20)).fillna(0.0)
pos_mr20 = pd.Series(0.0, index=weekly.index)
pos_mr20[z > 2.0] = -1.0
pos_mr20[z < -2.0] = 1.0
pos_bh = pd.Series(1.0, index=weekly.index)

# the flat-warmup positions must reproduce the Table 11 candidate returns
assert np.allclose(simple_strategy(pos_mom20), candidates["mom_20w"].fillna(0))
assert np.allclose(simple_strategy(pos_mr20), candidates["mr_2.0"].fillna(0))
assert np.allclose(simple_strategy(pos_bh), candidates["carry_only"].fillna(0))

tab3 = {}
for name, rets_s, pos_s in [
        ("asymmetry", base["rets"], base["position"]),
        ("momentum_20w", simple_strategy(pos_mom20), pos_mom20),
        ("meanrev_2.0", simple_strategy(pos_mr20), pos_mr20),
        ("buy_hold", simple_strategy(pos_bh), pos_bh)]:
    m = perf_metrics(rets_s, pos_s)
    if name == "buy_hold":
        m["trades"] = 1  # single initial purchase, held throughout
    tab3[name] = m
    log(f"  {name:<14} ret={m['ret']:7.2f}%  vol={m['vol']:5.2f}%  "
        f"Sharpe={m['sharpe']:6.3f}  Sortino={m['sortino']:6.3f}  "
        f"MDD={m['mdd']:7.2f}%  trades={m['trades']}")

spot_move = (weekly["Close"].iloc[-1] / weekly["Close"].iloc[0] - 1) * 100
log(f"  Sanity: EURJPY spot move over sample = {spot_move:.2f}% "
    f"({weekly['Close'].iloc[0]:.2f} -> {weekly['Close'].iloc[-1]:.2f}); "
    f"buy & hold cum = {tab3['buy_hold']['ret']:.2f}%")
assert abs(spot_move - tab3["buy_hold"]["ret"]) < 0.02
RESULTS["table3"] = dict(rows=tab3, spot_move_pct=round(float(spot_move), 2))

# =============================================================================
# 13. [J] TABLE 4 REBUILD: CROSS-MARKET CHECK
# =============================================================================
log("\n[12] Table 4 REBUILD: cross-market check (identical alpha construction)...")


def build_weekly_alphas(daily_px):
    """Same transformations as the EUR/JPY blocks above; hedge alpha excluded
    (its JPY-USD rate differential and DXY correlation are pair-specific)."""
    d2 = daily_px[["Close"]].copy()
    d2["returns"] = d2["Close"].pct_change()
    q95 = d2["returns"].abs().rolling(252, min_periods=60).quantile(0.95)
    d2["tail_alpha"] = np.where(d2["returns"].abs() > q95,
                                np.sign(d2["returns"]) * d2["returns"].abs(), 0.0)
    d2["ret_5d"] = d2["Close"].pct_change(5)
    d2["vol_20d"] = d2["returns"].rolling(20).std()
    d2["fast_alpha"] = d2["ret_5d"] / (d2["vol_20d"] * np.sqrt(5))
    d2["ma_60d"] = d2["Close"].rolling(60).mean()
    d2["std_60d"] = d2["Close"].rolling(60).std()
    d2["pricing_alpha"] = (d2["Close"] - d2["ma_60d"]) / d2["std_60d"]
    d2["coverage_alpha"] = d2["vol_20d"] / d2["vol_20d"].shift(5) - 1
    w = d2.resample("W-FRI").last()
    w["weekly_return"] = w["Close"].pct_change()
    w = w.loc["2015-11-01":"2025-08-31"]
    w["fast_skew_20w"] = w["fast_alpha"].rolling(20, min_periods=10).apply(
        lambda x: stats.skew(x, nan_policy="omit"), raw=False)
    w["price_skew_20w"] = w["pricing_alpha"].rolling(20, min_periods=10).apply(
        lambda x: stats.skew(x, nan_policy="omit"), raw=False)
    w["pricing_std_20w"] = w["pricing_alpha"].rolling(20, min_periods=10).std()
    w["ai_20w"] = w["fast_alpha"].rolling(20, min_periods=10).apply(compute_ai, raw=False)
    return w.dropna(subset=["fast_skew_20w", "price_skew_20w", "ai_20w"])


xmkt = {"EURJPY": dict(
    n=N,
    tail_skew=RESULTS["tables123"]["tail_alpha"]["skew"],
    fast_skew=RESULTS["tables123"]["fast_alpha"]["skew"],
    pricing_skew=RESULTS["tables123"]["pricing_alpha"]["skew"],
    coverage_skew=RESULTS["tables123"]["coverage_alpha"]["skew"],
    strat_ret=round(float(base["return"]), 2),
    strat_trades=int(base["trades"]),
    bh_ret=tab3["buy_hold"]["ret"])}
for tick, label in [("GBPUSD=X", "GBPUSD"), ("SPY", "SPY"), ("GLD", "GLD")]:
    w = build_weekly_alphas(dl(tick))
    res = run_asymmetry_strategy(w, 0.75)
    bh_cum = float((w["Close"].iloc[-1] / w["Close"].iloc[0] - 1) * 100)
    xmkt[label] = dict(
        n=len(w),
        tail_skew=round(float(stats.skew(w["tail_alpha"].dropna())), 2),
        fast_skew=round(float(stats.skew(w["fast_alpha"].dropna())), 2),
        pricing_skew=round(float(stats.skew(w["pricing_alpha"].dropna())), 2),
        coverage_skew=round(float(stats.skew(w["coverage_alpha"].dropna())), 2),
        strat_ret=round(float(res["return"]), 2),
        strat_trades=int(res["trades"]),
        bh_ret=round(bh_cum, 2))
for k, v in xmkt.items():
    log(f"  {k:<7} n={v['n']}  tail={v['tail_skew']:6.2f}  fast={v['fast_skew']:6.2f}  "
        f"pricing={v['pricing_skew']:6.2f}  coverage={v['coverage_skew']:6.2f}  "
        f"strat={v['strat_ret']:7.2f}% ({v['strat_trades']} trades)  "
        f"B&H={v['bh_ret']:7.2f}%")
RESULTS["table_crossmarket"] = xmkt

# =============================================================================
# 14. SAVE
# =============================================================================
with open(OUT_TXT, "w") as f:
    f.write("\n".join(LINES) + "\n")
with open(OUT_JSON, "w") as f:
    json.dump(RESULTS, f, indent=2, default=str)
log(f"\nSaved: {OUT_TXT}")
log(f"Saved: {OUT_JSON}")
