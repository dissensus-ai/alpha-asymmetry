#!/usr/bin/env python3
"""
Phase 0: Data Verification for Alpha Asymmetry Major Revision
=============================================================

Critical investigation before any paper edits:
1. Verify actual sample date range and observation count
2. Run threshold sensitivity analysis
3. Compute EVT declustering metrics (extremal index, cluster maxima)

The paper claims 646 weekly observations from Nov 2015 to Aug 2025.
Math: Nov 2015 to Aug 2025 = ~9 years 9 months = ~508 weeks.
This is a 27% overstatement if the dates are correct.
"""

import yfinance as yf
import pandas as pd
import numpy as np
from scipy import stats
from datetime import datetime
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

print("=" * 70)
print("PHASE 0: CRITICAL DATA VERIFICATION")
print("=" * 70)

# =============================================================================
# 1. SAMPLE COUNT VERIFICATION
# =============================================================================

print("\n" + "=" * 70)
print("1. SAMPLE COUNT VERIFICATION")
print("=" * 70)

# Download EURJPY weekly data
# Try multiple date ranges to see what's actually available
data = yf.download('EURJPY=X', start='2010-01-01', end='2025-12-31', interval='1wk', progress=False)

print(f"\nFull available data range:")
print(f"  Start: {data.index[0].strftime('%Y-%m-%d')}")
print(f"  End:   {data.index[-1].strftime('%Y-%m-%d')}")
print(f"  Total weekly observations: {len(data)}")

# Check the claimed date range
claimed_start = '2015-11-01'
claimed_end = '2025-08-31'

sample_claimed = data.loc[claimed_start:claimed_end]
print(f"\nClaimed date range (Nov 2015 - Aug 2025):")
print(f"  Actual observations in this range: {len(sample_claimed)}")
print(f"  Paper claims: 646")
print(f"  Discrepancy: {646 - len(sample_claimed)} observations")

# What date range would give ~646 observations?
# 646 weeks = ~12.4 years
target_weeks = 646
weeks_per_year = 52
years_needed = target_weeks / weeks_per_year
print(f"\n646 weeks = {years_needed:.1f} years")

# Count backwards from Aug 2025
end_date = pd.Timestamp('2025-08-31')
start_needed = end_date - pd.Timedelta(weeks=646)
print(f"To get 646 weeks ending Aug 2025, start would be: {start_needed.strftime('%Y-%m-%d')}")

# Check if data actually goes back that far
extended_sample = data.loc['2013-01-01':'2025-08-31']
print(f"\nJan 2013 - Aug 2025 range:")
print(f"  Observations: {len(extended_sample)}")

# Let's find what start date gives exactly 646 obs
for year in range(2010, 2020):
    for month in [1, 6, 11]:
        test_start = f'{year}-{month:02d}-01'
        test_sample = data.loc[test_start:'2025-08-31']
        if 640 <= len(test_sample) <= 650:
            print(f"  {test_start} to 2025-08-31: {len(test_sample)} observations")

# =============================================================================
# 2. COMPUTE ALPHA SIGNALS (simplified for verification)
# =============================================================================

print("\n" + "=" * 70)
print("2. COMPUTING ALPHA SIGNALS")
print("=" * 70)

# Use the actual sample we'll work with
# Let's use the claimed dates and see what we get
df = data.loc['2015-11-01':'2025-08-31'].copy()

# Handle yfinance multi-index columns
if isinstance(df.columns, pd.MultiIndex):
    df.columns = df.columns.get_level_values(0)

df['returns'] = df['Close'].pct_change()

# Fast Alpha: 5-week momentum / 20-week vol (simplified from daily)
df['fast_alpha'] = df['returns'].rolling(5).sum() / (df['returns'].rolling(20).std() * np.sqrt(5))

# Rolling skewness of fast alpha (20-week window)
df['fast_skew_20w'] = df['fast_alpha'].rolling(20).apply(lambda x: stats.skew(x, nan_policy='omit'), raw=False)

# Clean up
df = df.dropna(subset=['fast_alpha', 'fast_skew_20w'])
print(f"Sample after computing signals: {len(df)} observations")
print(f"Date range: {df.index[0].strftime('%Y-%m-%d')} to {df.index[-1].strftime('%Y-%m-%d')}")

# =============================================================================
# 3. THRESHOLD SENSITIVITY ANALYSIS
# =============================================================================

print("\n" + "=" * 70)
print("3. THRESHOLD SENSITIVITY ANALYSIS")
print("=" * 70)

thresholds = [0.50, 0.75, 1.00, 1.25]

results = []
for thresh in thresholds:
    # Entry signal: skewness > threshold AND fast_alpha > 0
    signals = (df['fast_skew_20w'] > thresh) & (df['fast_alpha'] > 0)

    # Simple strategy: go long when signal, else flat
    # Weekly returns when in position
    df['position'] = signals.shift(1).fillna(0).astype(int)  # Lag signal by 1 week
    df['strategy_return'] = df['position'] * df['returns']

    # Performance metrics
    total_return = df['strategy_return'].sum()
    cum_returns = (1 + df['strategy_return']).cumprod()
    max_dd = ((cum_returns / cum_returns.cummax()) - 1).min()
    n_trades = (df['position'].diff().abs() > 0).sum()
    n_weeks_in = df['position'].sum()

    # Hit rate (profitable weeks when in position)
    in_position = df['strategy_return'] != 0
    if in_position.sum() > 0:
        hit_rate = (df.loc[in_position, 'strategy_return'] > 0).mean()
    else:
        hit_rate = np.nan

    # Annualized Sharpe
    weekly_mean = df['strategy_return'].mean()
    weekly_std = df['strategy_return'].std()
    sharpe = (weekly_mean / weekly_std) * np.sqrt(52) if weekly_std > 0 else 0

    results.append({
        'threshold': thresh,
        'total_return': total_return * 100,
        'sharpe': sharpe,
        'max_dd': max_dd * 100,
        'n_trades': n_trades,
        'hit_rate': hit_rate * 100 if not np.isnan(hit_rate) else 0,
        'weeks_in': n_weeks_in
    })

print("\nThreshold Sensitivity Table:")
print("-" * 80)
print(f"{'Threshold':>10} {'Return':>10} {'Sharpe':>10} {'MDD':>10} {'Trades':>10} {'Hit Rate':>10}")
print("-" * 80)
for r in results:
    print(f"{r['threshold']:>10.2f} {r['total_return']:>9.2f}% {r['sharpe']:>10.3f} {r['max_dd']:>9.2f}% {r['n_trades']:>10} {r['hit_rate']:>9.2f}%")
print("-" * 80)

# =============================================================================
# 4. EVT DECLUSTERING ANALYSIS
# =============================================================================

print("\n" + "=" * 70)
print("4. EVT DECLUSTERING ANALYSIS")
print("=" * 70)

# Tail alpha: extreme returns above 95th percentile
tail_alpha = df['returns'].abs()
threshold_95 = tail_alpha.quantile(0.95)

print(f"\n95th percentile threshold: {threshold_95:.6f}")

# Raw exceedances
exceedances_mask = tail_alpha > threshold_95
raw_exceedances = exceedances_mask.sum()
print(f"Raw exceedances (tail_alpha > 95th pctl): {raw_exceedances}")

# Runs declustering with minimum 5-week separation
# Cluster = consecutive exceedances with gaps < 5 weeks
exceedance_indices = np.where(exceedances_mask)[0]
exceedance_dates = df.index[exceedances_mask]

if len(exceedance_indices) > 0:
    # Identify clusters: new cluster if gap >= 5 weeks
    cluster_labels = [0]
    current_cluster = 0

    for i in range(1, len(exceedance_indices)):
        gap = exceedance_indices[i] - exceedance_indices[i-1]
        if gap >= 5:  # New cluster
            current_cluster += 1
        cluster_labels.append(current_cluster)

    n_clusters = current_cluster + 1

    # Cluster maxima
    cluster_maxima = []
    for c in range(n_clusters):
        cluster_idx = [exceedance_indices[j] for j, label in enumerate(cluster_labels) if label == c]
        max_val = tail_alpha.iloc[cluster_idx].max()
        cluster_maxima.append(max_val)

    print(f"Number of clusters (5-week separation): {n_clusters}")
    print(f"Cluster maxima count: {len(cluster_maxima)}")

    # Extremal index estimation (intervals estimator)
    # theta = n_clusters / raw_exceedances (simplified)
    # More rigorous: based on inter-exceedance times
    theta = n_clusters / raw_exceedances
    print(f"\nExtremal index (theta) estimate: {theta:.3f}")

    # Interpretation
    if theta > 0.9:
        interp = "weak clustering (near i.i.d.)"
    elif theta > 0.7:
        interp = "moderate clustering"
    elif theta > 0.4:
        interp = "strong clustering"
    else:
        interp = "very strong clustering"
    print(f"Interpretation: {interp}")

    # Bootstrap CI for theta
    n_boot = 1000
    boot_thetas = []
    for _ in range(n_boot):
        # Resample exceedance indices
        resample_idx = np.random.choice(len(exceedance_indices), size=len(exceedance_indices), replace=True)
        resample_exceedances = np.sort(exceedance_indices[resample_idx])

        # Count clusters in resample
        boot_clusters = 1
        for i in range(1, len(resample_exceedances)):
            if resample_exceedances[i] - resample_exceedances[i-1] >= 5:
                boot_clusters += 1
        boot_thetas.append(boot_clusters / len(exceedance_indices))

    theta_ci_low = np.percentile(boot_thetas, 2.5)
    theta_ci_high = np.percentile(boot_thetas, 97.5)
    print(f"95% CI for theta: [{theta_ci_low:.3f}, {theta_ci_high:.3f}]")

else:
    print("No exceedances found!")
    n_clusters = 0
    theta = np.nan

# =============================================================================
# 5. GPD FIT TO CLUSTER MAXIMA
# =============================================================================

print("\n" + "=" * 70)
print("5. GPD FIT TO CLUSTER MAXIMA")
print("=" * 70)

if len(cluster_maxima) > 10:
    from scipy.stats import genpareto

    # Fit GPD to exceedances above threshold
    exceedances_values = tail_alpha[exceedances_mask] - threshold_95

    # Fit to cluster maxima (more appropriate for EVT)
    cluster_maxima_exceedances = np.array(cluster_maxima) - threshold_95

    # MLE fit
    shape, loc, scale = genpareto.fit(cluster_maxima_exceedances, floc=0)

    print(f"\nGPD Parameters (fitted to cluster maxima):")
    print(f"  Shape (xi): {shape:.3f}")
    print(f"  Scale (sigma): {scale:.3f}")
    print(f"  Threshold: {threshold_95:.6f}")
    print(f"  Number of cluster maxima: {len(cluster_maxima)}")

    # KS test for goodness of fit
    ks_stat, ks_pval = stats.kstest(cluster_maxima_exceedances, 'genpareto', args=(shape, 0, scale))
    print(f"\nKS Test for GPD fit:")
    print(f"  KS statistic: {ks_stat:.3f}")
    print(f"  p-value: {ks_pval:.3f}")
    print(f"  Interpretation: {'Fail to reject GPD' if ks_pval > 0.05 else 'Reject GPD'}")

    # Bootstrap CI for shape parameter
    boot_shapes = []
    for _ in range(500):
        boot_sample = np.random.choice(cluster_maxima_exceedances, size=len(cluster_maxima_exceedances), replace=True)
        try:
            bs, bl, bsc = genpareto.fit(boot_sample, floc=0)
            boot_shapes.append(bs)
        except:
            pass

    if boot_shapes:
        shape_ci_low = np.percentile(boot_shapes, 2.5)
        shape_ci_high = np.percentile(boot_shapes, 97.5)
        print(f"\n95% CI for shape (xi): [{shape_ci_low:.3f}, {shape_ci_high:.3f}]")

else:
    print("Insufficient cluster maxima for GPD fit")

# =============================================================================
# 6. SUMMARY FOR PAPER REVISION
# =============================================================================

print("\n" + "=" * 70)
print("SUMMARY FOR PAPER REVISION")
print("=" * 70)

print(f"""
CRITICAL FINDINGS:

1. SAMPLE COUNT ISSUE:
   - Paper claims: 646 observations from Nov 2015 - Aug 2025
   - Actual observations in that range: {len(sample_claimed)}
   - Discrepancy: {646 - len(sample_claimed)} observations

   OPTIONS:
   a) If 646 is correct, the date range should be ~Jan 2013 to Aug 2025
   b) If Nov 2015 is correct, the sample count should be ~{len(sample_claimed)}

2. THRESHOLD SENSITIVITY:
   - See table above
   - Baseline 0.75 threshold: {[r for r in results if r['threshold'] == 0.75][0]['total_return']:.2f}% return

3. EVT DECLUSTERING:
   - Raw exceedances: {raw_exceedances}
   - Cluster maxima (5-week separation): {n_clusters}
   - Extremal index (theta): {theta:.3f} (95% CI: [{theta_ci_low:.3f}, {theta_ci_high:.3f}])
   - Interpretation: {interp}

4. GPD PARAMETERS:
   - Shape (xi): {shape:.3f}
   - Scale (sigma): {scale:.3f}
   - KS test p-value: {ks_pval:.3f}
""")

# Save results to file for reference
output_file = Path(__file__).resolve().parent / 'phase0_results.txt'
with open(output_file, 'w') as f:
    f.write("PHASE 0 RESULTS FOR ALPHA ASYMMETRY REVISION\n")
    f.write("=" * 60 + "\n\n")
    f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
    f.write(f"SAMPLE VERIFICATION:\n")
    f.write(f"  Claimed range: Nov 2015 - Aug 2025\n")
    f.write(f"  Claimed count: 646\n")
    f.write(f"  Actual count in range: {len(sample_claimed)}\n\n")
    f.write(f"THRESHOLD SENSITIVITY:\n")
    for r in results:
        f.write(f"  {r['threshold']}: Return={r['total_return']:.2f}%, Sharpe={r['sharpe']:.3f}, MDD={r['max_dd']:.2f}%\n")
    f.write(f"\nEVT DECLUSTERING:\n")
    f.write(f"  Raw exceedances: {raw_exceedances}\n")
    f.write(f"  Cluster maxima: {n_clusters}\n")
    f.write(f"  Extremal index: {theta:.3f} (95% CI: [{theta_ci_low:.3f}, {theta_ci_high:.3f}])\n")
    f.write(f"\nGPD PARAMETERS:\n")
    f.write(f"  Shape (xi): {shape:.3f}\n")
    f.write(f"  Scale (sigma): {scale:.3f}\n")
    f.write(f"  KS p-value: {ks_pval:.3f}\n")

print(f"\nResults saved to: {output_file}")
