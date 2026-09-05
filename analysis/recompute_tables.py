#!/usr/bin/env python3
"""
Recompute Tables 6 (Subsample Stability) and 7 (Threshold Sensitivity)
for alpha-asymmetry paper using full strategy specification.

Strategy spec from paper Section 2.4:
  - Entry Long: rolling skewness of fast_alpha (20-week) > threshold AND fast_alpha > 0
  - Entry Short: rolling skewness of pricing_alpha (20-week) > threshold AND pricing_alpha > 0.5*sigma_pricing
  - Exit: signal reversal OR 4-week max holding period
  - Position sizing: max(0.5, min(2.0, 1 + |AI_t - 1.0|))
  - Execution: 1-week lag (signal Friday, execute Monday)

Alpha signals are computed from daily data then aggregated to weekly.
"""

import yfinance as yf
import pandas as pd
import numpy as np
from scipy import stats
from datetime import datetime
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

print("=" * 80)
print("RECOMPUTATION: Tables 6 & 7 for Alpha Asymmetry Paper")
print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 80)

# =============================================================================
# 1. DATA DOWNLOAD
# =============================================================================

print("\n[1] Downloading data...")

# Daily data for alpha computation
daily = yf.download('EURJPY=X', start='2014-06-01', end='2025-08-31',
                     interval='1d', progress=False)
if isinstance(daily.columns, pd.MultiIndex):
    daily.columns = daily.columns.get_level_values(0)

# DXY for hedge alpha
dxy_daily = yf.download('DX-Y.NYB', start='2014-06-01', end='2025-08-31',
                         interval='1d', progress=False)
if isinstance(dxy_daily.columns, pd.MultiIndex):
    dxy_daily.columns = dxy_daily.columns.get_level_values(0)

# VIX for subsample splits
vix_daily = yf.download('^VIX', start='2014-06-01', end='2025-08-31',
                         interval='1d', progress=False)
if isinstance(vix_daily.columns, pd.MultiIndex):
    vix_daily.columns = vix_daily.columns.get_level_values(0)

print(f"  EUR/JPY daily: {len(daily)} obs ({daily.index[0].date()} to {daily.index[-1].date()})")
print(f"  DXY daily: {len(dxy_daily)} obs")
print(f"  VIX daily: {len(vix_daily)} obs")

# =============================================================================
# 2. COMPUTE DAILY ALPHA SIGNALS
# =============================================================================

print("\n[2] Computing daily alpha signals...")

df = daily[['Close']].copy()
df['returns'] = df['Close'].pct_change()

# Tail Alpha: modified z-score beyond rolling 95th percentile (252-day ~ 52 weeks)
rolling_q95 = df['returns'].abs().rolling(252, min_periods=60).quantile(0.95)
df['tail_alpha'] = np.where(
    df['returns'].abs() > rolling_q95,
    np.sign(df['returns']) * df['returns'].abs(),
    0.0
)

# Fast Alpha: 5-day return / (20-day vol * sqrt(5))
df['ret_5d'] = df['Close'].pct_change(5)
df['vol_20d'] = df['returns'].rolling(20).std()
df['fast_alpha'] = df['ret_5d'] / (df['vol_20d'] * np.sqrt(5))

# Pricing Alpha: (P - MA60) / sigma60
df['ma_60d'] = df['Close'].rolling(60).mean()
df['std_60d'] = df['Close'].rolling(60).std()
df['pricing_alpha'] = (df['Close'] - df['ma_60d']) / df['std_60d']

# Coverage Alpha: sigma_20d(t) / sigma_20d(t-5) - 1
df['vol_20d_lag5'] = df['vol_20d'].shift(5)
df['coverage_alpha'] = df['vol_20d'] / df['vol_20d_lag5'] - 1

# Hedge Alpha: corr(EURJPY, DXY) * (r_JPY - r_USD)
# Use rolling 100-day correlation (~20 weeks) for daily data
dxy_returns = dxy_daily['Close'].pct_change()
merged_corr = pd.DataFrame({
    'eurjpy_ret': df['returns'],
    'dxy_ret': dxy_returns
}).dropna()

rolling_corr = merged_corr['eurjpy_ret'].rolling(100).corr(merged_corr['dxy_ret'])

# Interest rate differential: approximate with constant spread
# JPY rates near 0 most of the period, USD rates varied 0-5.5%
# Use a simplified proxy: negative spread (JPY lower than USD most of period)
# This is a simplification; FRED data would be ideal but this captures the direction
rate_diff = -0.02  # ~-2% JPY-USD differential on average
df['hedge_alpha'] = rolling_corr.reindex(df.index) * rate_diff

print("  All 5 daily alphas computed.")

# =============================================================================
# 3. AGGREGATE TO WEEKLY (Friday close)
# =============================================================================

print("\n[3] Aggregating to weekly frequency...")

# Resample to weekly (Friday)
weekly = df.resample('W-FRI').last()
weekly['weekly_return'] = weekly['Close'].pct_change()

# Filter to the paper's date range
weekly = weekly.loc['2015-11-01':'2025-08-31']
print(f"  Weekly observations: {len(weekly)}")
print(f"  Date range: {weekly.index[0].date()} to {weekly.index[-1].date()}")

# =============================================================================
# 4. COMPUTE ROLLING STATISTICS FOR STRATEGY SIGNALS
# =============================================================================

print("\n[4] Computing rolling statistics...")

# Rolling 20-week skewness of fast alpha and pricing alpha
weekly['fast_skew_20w'] = weekly['fast_alpha'].rolling(20, min_periods=10).apply(
    lambda x: stats.skew(x, nan_policy='omit'), raw=False
)
weekly['price_skew_20w'] = weekly['pricing_alpha'].rolling(20, min_periods=10).apply(
    lambda x: stats.skew(x, nan_policy='omit'), raw=False
)

# Rolling std of pricing alpha for short entry threshold
weekly['pricing_std_20w'] = weekly['pricing_alpha'].rolling(20, min_periods=10).std()

# Asymmetry Index (AI) - rolling 20-week window
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

weekly['ai_20w'] = weekly['fast_alpha'].rolling(20, min_periods=10).apply(
    compute_ai, raw=False
)

# Drop warmup period
weekly = weekly.dropna(subset=['fast_skew_20w', 'price_skew_20w', 'ai_20w'])
print(f"  After warmup drop: {len(weekly)} observations")
print(f"  Date range: {weekly.index[0].date()} to {weekly.index[-1].date()}")

# =============================================================================
# 5. FULL ASYMMETRY STRATEGY IMPLEMENTATION
# =============================================================================

def run_asymmetry_strategy(data, threshold=0.75, verbose=False):
    """
    Full asymmetry strategy as described in Section 2.4.

    Entry Long: fast_skew_20w > threshold AND fast_alpha > 0
    Entry Short: price_skew_20w > threshold AND pricing_alpha > 0.5 * pricing_std
    Exit: reversal OR 4-week max hold
    Position sizing: max(0.5, min(2.0, 1 + |AI - 1|))
    Execution lag: 1 week
    """
    df = data.copy()

    # Generate signals
    long_signal = (df['fast_skew_20w'] > threshold) & (df['fast_alpha'] > 0)
    short_signal = (df['price_skew_20w'] > threshold) & (df['pricing_alpha'] > 0.5 * df['pricing_std_20w'])

    # Track positions with holding period logic
    position = pd.Series(0.0, index=df.index)
    position_size = pd.Series(0.0, index=df.index)
    hold_counter = pd.Series(0, index=df.index)
    trade_count = 0

    for i in range(1, len(df)):
        prev_pos = position.iloc[i-1]
        prev_hold = hold_counter.iloc[i-1]

        # Check for max holding period exit
        if prev_hold >= 4:
            position.iloc[i] = 0.0
            hold_counter.iloc[i] = 0
            if prev_pos != 0:
                trade_count += 1
            continue

        # Use lagged signals (signal at t-1, execute at t)
        if i >= 2:
            sig_long = long_signal.iloc[i-1]
            sig_short = short_signal.iloc[i-1]
        else:
            sig_long = False
            sig_short = False

        # Position sizing from lagged AI
        ai_val = df['ai_20w'].iloc[i-1]
        ps = max(0.5, min(2.0, 1.0 + abs(ai_val - 1.0)))

        if sig_long and not sig_short:
            new_pos = ps  # Long
        elif sig_short and not sig_long:
            new_pos = -ps  # Short
        elif sig_long and sig_short:
            new_pos = 0.0  # Conflicting signals -> flat
        else:
            # No signal - check for reversal exit
            if prev_pos > 0 and not long_signal.iloc[i-1]:
                new_pos = 0.0  # Long exit on signal loss
            elif prev_pos < 0 and not short_signal.iloc[i-1]:
                new_pos = 0.0  # Short exit on signal loss
            else:
                new_pos = prev_pos  # Hold existing position

        # Track trade entries
        if new_pos != 0 and prev_pos == 0:
            trade_count += 1
        elif new_pos == 0 and prev_pos != 0:
            pass  # Exit counted above

        position.iloc[i] = new_pos
        position_size.iloc[i] = abs(new_pos)

        # Update holding counter
        if new_pos != 0 and np.sign(new_pos) == np.sign(prev_pos):
            hold_counter.iloc[i] = prev_hold + 1
        elif new_pos != 0:
            hold_counter.iloc[i] = 1
        else:
            hold_counter.iloc[i] = 0

    # Compute strategy returns
    strategy_returns = position.shift(1) * df['weekly_return']
    strategy_returns = strategy_returns.fillna(0)

    # Performance metrics
    cum_return = (1 + strategy_returns).prod() - 1
    cum_returns_series = (1 + strategy_returns).cumprod()
    max_dd = ((cum_returns_series / cum_returns_series.cummax()) - 1).min()

    weekly_mean = strategy_returns.mean()
    weekly_std = strategy_returns.std()
    sharpe = (weekly_mean / weekly_std) * np.sqrt(52) if weekly_std > 0 else 0.0

    # Sortino
    downside = strategy_returns[strategy_returns < 0]
    downside_std = downside.std() if len(downside) > 0 else 1e-10
    sortino = (weekly_mean / downside_std) * np.sqrt(52) if downside_std > 0 else 0.0

    # Hit rate (profitable weeks when in position)
    in_pos = strategy_returns[position.shift(1).abs() > 0]
    hit_rate = (in_pos > 0).mean() * 100 if len(in_pos) > 0 else 0.0

    # Count distinct trades (entries)
    pos_changes = position.diff().abs()
    n_trades = int((pos_changes > 0).sum() // 2)  # Entry + exit = 1 trade

    if verbose:
        print(f"    Threshold={threshold:.2f}: Return={cum_return*100:.2f}%, "
              f"Sharpe={sharpe:.3f}, MDD={max_dd*100:.2f}%, "
              f"Trades={n_trades}, HitRate={hit_rate:.1f}%")

    return {
        'return': cum_return * 100,
        'sharpe': sharpe,
        'sortino': sortino,
        'mdd': max_dd * 100,
        'trades': n_trades,
        'hit_rate': hit_rate,
        'strategy_returns': strategy_returns,
        'position': position
    }


# =============================================================================
# 6. TABLE 7: THRESHOLD SENSITIVITY
# =============================================================================

print("\n[5] Recomputing Table 7 (Threshold Sensitivity)...")
print("-" * 80)
print(f"{'Threshold':>10} {'Return':>10} {'Sharpe':>10} {'MDD':>10} {'Trades':>10} {'Hit Rate':>10}")
print("-" * 80)

thresholds = [0.50, 0.75, 1.00, 1.25]
sensitivity_results = {}

for thresh in thresholds:
    result = run_asymmetry_strategy(weekly, threshold=thresh, verbose=True)
    sensitivity_results[thresh] = result

print("-" * 80)

# =============================================================================
# 7. TABLE 6: SUBSAMPLE STABILITY
# =============================================================================

print("\n[6] Recomputing Table 6 (Subsample Stability)...")

# Get VIX data aligned to weekly EUR/JPY dates
vix_weekly = vix_daily['Close'].resample('W-FRI').mean()  # Monthly average approximated weekly
vix_aligned = vix_weekly.reindex(weekly.index, method='ffill')

# Define subsamples
subsamples = {
    'Pre-COVID (2015-2019)': weekly.loc[:'2019-12-31'],
    'COVID Shock (2020)': weekly.loc['2020-01-01':'2020-12-31'],
    'Post-COVID (2021-2025)': weekly.loc['2021-01-01':],
}

# VIX-based splits
low_vix_mask = vix_aligned < 20
high_vix_mask = vix_aligned >= 20
# Handle NaN VIX as neither
low_vix_mask = low_vix_mask.fillna(False)
high_vix_mask = high_vix_mask.fillna(False)

subsamples['Low VIX (VIX < 20)'] = weekly[low_vix_mask]
subsamples['High VIX (VIX >= 20)'] = weekly[high_vix_mask]
subsamples['Rate Hike (2022-2025)'] = weekly.loc['2022-01-01':'2025-08-31']

print("\n" + "-" * 100)
print(f"{'Subsample':<30} {'N':>5} {'Tail Skew':>10} {'Fast Skew':>10} {'Price Skew':>10} {'Strat Ret':>10}")
print("-" * 100)

subsample_results = {}

for name, subset in subsamples.items():
    n = len(subset)

    # Compute skewness within subsample
    tail_skew = stats.skew(subset['tail_alpha'].dropna()) if len(subset['tail_alpha'].dropna()) > 5 else np.nan
    fast_skew = stats.skew(subset['fast_alpha'].dropna()) if len(subset['fast_alpha'].dropna()) > 5 else np.nan
    price_skew = stats.skew(subset['pricing_alpha'].dropna()) if len(subset['pricing_alpha'].dropna()) > 5 else np.nan

    # Run strategy on subsample
    if n >= 25:  # Need enough data
        result = run_asymmetry_strategy(subset, threshold=0.75)
        strat_ret = result['return']
    else:
        strat_ret = np.nan

    subsample_results[name] = {
        'n': n,
        'tail_skew': tail_skew,
        'fast_skew': fast_skew,
        'price_skew': price_skew,
        'strat_ret': strat_ret
    }

    print(f"  {name:<28} {n:>5} {tail_skew:>10.2f} {fast_skew:>10.2f} {price_skew:>10.2f} {strat_ret:>9.2f}%")

print("-" * 100)

# Verify sums
temporal_sum = (subsample_results['Pre-COVID (2015-2019)']['n'] +
                subsample_results['COVID Shock (2020)']['n'] +
                subsample_results['Post-COVID (2021-2025)']['n'])
vix_sum = (subsample_results['Low VIX (VIX < 20)']['n'] +
           subsample_results['High VIX (VIX >= 20)']['n'])

print(f"\n  Temporal sum: {temporal_sum} (should equal total: {len(weekly)})")
print(f"  VIX sum: {vix_sum} (should equal total: {len(weekly)})")

# =============================================================================
# 8. FULL-SAMPLE STATISTICS FOR REFERENCE
# =============================================================================

print("\n[7] Full-sample reference statistics...")

# Table 1 (Asymmetry Metrics) verification
for alpha_name in ['tail_alpha', 'fast_alpha', 'pricing_alpha', 'coverage_alpha', 'hedge_alpha']:
    col = weekly[alpha_name].dropna()
    skew = stats.skew(col)
    kurt = stats.kurtosis(col)

    # Asymmetry index
    mean_val = col.mean()
    pos_dev = col[col > mean_val] - mean_val
    neg_dev = col[col < mean_val] - mean_val
    ai = pos_dev.var() / neg_dev.var() if len(neg_dev) > 0 and neg_dev.var() > 0 else 1.0

    # PNR
    pnr = (col > 0).mean() * 100

    print(f"  {alpha_name:<20}: Skew={skew:.2f}, Kurt={kurt:.2f}, AI={ai:.2f}, PNR={pnr:.2f}%")

# Full-sample strategy with 0.75 threshold
print("\n  Full-sample strategy (threshold=0.75):")
full_result = run_asymmetry_strategy(weekly, threshold=0.75, verbose=True)

# =============================================================================
# 9. GENERATE LATEX TABLE SNIPPETS
# =============================================================================

print("\n" + "=" * 80)
print("LATEX TABLE SNIPPETS")
print("=" * 80)

# Table 6
print("\n--- Table 6 (Subsample Stability) ---")
for name, r in subsample_results.items():
    latex_name = name.replace('>=', '$\\geq$').replace('<', '$<$')
    print(f"{latex_name} & {r['n']} & {r['tail_skew']:.2f} & {r['fast_skew']:.2f} "
          f"& {r['price_skew']:.2f} & {r['strat_ret']:.2f}\\% \\\\")

# Table 7
print("\n--- Table 7 (Threshold Sensitivity) ---")
for thresh in thresholds:
    r = sensitivity_results[thresh]
    print(f"{thresh:.2f} & {r['return']:.2f}\\% & {r['sharpe']:.2f} & "
          f"$-${abs(r['mdd']):.1f}\\% & {r['trades']} & {r['hit_rate']:.1f}\\% \\\\")

# =============================================================================
# 10. NARRATIVE CHECK
# =============================================================================

print("\n" + "=" * 80)
print("NARRATIVE CHECK")
print("=" * 80)

baseline = sensitivity_results[0.75]
print(f"\n  Baseline (0.75) return: {baseline['return']:.2f}%")
print(f"  Baseline Sharpe: {baseline['sharpe']:.3f}")

if baseline['return'] > 0:
    print("  --> POSITIVE return at baseline (consistent with paper narrative)")
else:
    print("  --> NEGATIVE return at baseline (CONTRADICTS paper narrative!)")
    print("  --> The paper's central finding that asymmetry strategy generates")
    print("     'positive gross returns' may need revision.")

# Check non-monotonicity
returns_by_thresh = [sensitivity_results[t]['return'] for t in thresholds]
is_monotonic = all(returns_by_thresh[i] <= returns_by_thresh[i+1] for i in range(len(returns_by_thresh)-1)) or \
               all(returns_by_thresh[i] >= returns_by_thresh[i+1] for i in range(len(returns_by_thresh)-1))

if not is_monotonic:
    print("  --> Non-monotonic threshold response (consistent with paper narrative)")
else:
    print("  --> MONOTONIC threshold response (paper claims non-monotonic)")

# Check subsample skewness patterns
pre_fast = subsample_results['Pre-COVID (2015-2019)']['fast_skew']
covid_fast = subsample_results['COVID Shock (2020)']['fast_skew']
post_fast = subsample_results['Post-COVID (2021-2025)']['fast_skew']

if covid_fast > pre_fast and covid_fast > post_fast:
    print("  --> COVID amplifies fast alpha skewness (consistent)")
else:
    print(f"  --> COVID fast skew ({covid_fast:.2f}) vs pre ({pre_fast:.2f}) / post ({post_fast:.2f})")
    print("     May need narrative adjustment for temporal stability discussion")

# Check VIX conditioning
low_vix_fast = subsample_results['Low VIX (VIX < 20)']['fast_skew']
high_vix_fast = subsample_results['High VIX (VIX >= 20)']['fast_skew']

if high_vix_fast > low_vix_fast:
    print("  --> High VIX shows stronger skewness (consistent with paper)")
else:
    print(f"  --> High VIX fast skew ({high_vix_fast:.2f}) <= Low VIX ({low_vix_fast:.2f})")
    print("     Paper claims high-VIX shows stronger skewness -- needs check")

# Save results
output_file = Path(__file__).resolve().parent / 'recompute_results.txt'
with open(output_file, 'w') as f:
    f.write(f"RECOMPUTATION RESULTS\n")
    f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    f.write(f"Total observations: {len(weekly)}\n\n")

    f.write("TABLE 7 (Threshold Sensitivity):\n")
    for thresh in thresholds:
        r = sensitivity_results[thresh]
        f.write(f"  {thresh:.2f}: Return={r['return']:.2f}%, Sharpe={r['sharpe']:.3f}, "
                f"MDD={r['mdd']:.2f}%, Trades={r['trades']}, HitRate={r['hit_rate']:.1f}%\n")

    f.write("\nTABLE 6 (Subsample Stability):\n")
    for name, r in subsample_results.items():
        f.write(f"  {name}: N={r['n']}, TailSkew={r['tail_skew']:.2f}, "
                f"FastSkew={r['fast_skew']:.2f}, PriceSkew={r['price_skew']:.2f}, "
                f"StratRet={r['strat_ret']:.2f}%\n")

print(f"\nResults saved to: {output_file}")
