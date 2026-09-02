# Correction changelog

Date: 2026-09-02

Audited base: `4d21c69`

Working branch: `fix/strategy-specification`

## Confirmed implementation bugs

1. Strategy state exited when the entry condition disappeared. It now holds through no-signal and same-direction-signal weeks, reverses on an opposing signal, flattens on simultaneous signals, and expires after four realized weekly returns. An opposing signal takes precedence on the expiry date.
2. The headline strategy lagged its signal inside the loop and shifted the resulting position again. Signals are now formed on Friday row `t`, stored on row `t`, and shifted once to earn only the return ending on Friday `t+1`. Benchmarks and candidate strategies use the same convention.
3. AI used `pos.var()/neg.var()`, which recenters each subgroup and uses sample-variance denominators. It now uses mean squared deviations from the overall window mean, divided by the count on each side, matching the manuscript equation. Undefined cases return a missing value; a one-observation side is valid.
4. Repeated same-direction signals silently changed notional size. Entry size is now fixed for the holding episode.
5. Position changes divided by two were presented as trades. Dated ledgers now distinguish directional holding episodes, execution legs, direct reversals, resizing, and absolute turnover.
6. The legacy VIX routine removed non-regime weeks and reran a stateful strategy, making nonconsecutive dates adjacent. The strategy now runs once on the full calendar and realized returns are attributed ex post using weekly-average VIX.
7. Absolute `/home/purrpower/...` output paths made every pipeline and figure entry point nonportable. Outputs now resolve from the repository or explicit command-line overrides.

## Paper/code specification differences

- The paper claimed Monday-open execution, but only daily/Friday closing prices are downloaded. The revision states the actual Friday-close bar-to-bar proxy and its limitation.
- The fast-alpha equation showed a price difference while code used a percentage return. The equation now uses `P_t/P_{t-5}-1`.
- The stated size range was 0.5--2.0 units with “no leverage.” The formula can only produce 1.0--2.0 units; values above one imply leverage relative to one unit of capital.
- The hedge signal has no dated interest-rate input. It is a rolling-correlation signal multiplied by a fixed `-0.02` proxy.
- The manuscript said VIX was monthly; the implemented attribution uses the mean daily VIX close in each Friday-ending week.
- The code used biased skewness and kurtosis estimators while displaying bias-corrected equations. The pipeline now requests bias-corrected estimators.
- The raw weekly grid begins in November 2015, while the 504-row analysis-ready sample begins on 8 January 2016.
- The EVT routine fits weekly absolute returns, not the Friday-sampled daily tail-alpha observations. The manuscript now labels this as a separate weekly-return tail diagnostic.

## Statistical and methodological limitations

- The original raw data snapshots and author environment were not committed. The July numerical output cannot be exactly reproduced from the repository alone.
- Yahoo Finance data are indicative and revisable, not executable bid/ask quotes. End-of-bar fills are an assumption.
- Financing is omitted despite positions as large as two notional units and 55 exposed weeks.
- Fifteen baseline episodes, one OOS episode, 20 declustered tail maxima, and 55 in-position factor observations provide limited inferential power.
- Failure to reject a null does not prove exact Gaussianity, zero effect, or a specific tail class.
- Cross-market checks omit pair-specific costs, financing, and dependence-aware inference.
- The factor series are single-market proxies, not published cross-sectional FX factors.

## Claims investigated but not confirmed

- No evidence was found that the code uses genuine Monday-open prices or a time-varying rate differential.
- No original raw snapshot, lock file, or package-version record was found in the audited base.
- The latest head did contain a newer July correction pass, so earlier review numbers were not assumed current; nevertheless, the state, timing, AI, accounting, regime, and path issues remained.
- The downloaded row counts and principal EUR/JPY price history matched the committed July counts, but matching counts do not prove byte-identical source data.

## Downstream impact

The corrected baseline changes from +3.60% to -7.57% gross, from Sharpe 0.149 to -0.173, and from 25 to 55 exposed weeks. The ledger records 15 directional episodes and 30 execution legs. AI values, walk-forward results, regime attribution, factor regression, costs, data-snooping candidates, cross-market strategy results, figures, abstract, discussion, and conclusion were regenerated or revised. See `analysis/before_after_results.csv` for the dated comparison.

## Reproducibility

Raw files are cached locally under ignored `analysis/cache/`. `analysis/data_manifest.json` records retrieval time, row counts, date bounds, SHA-256 hashes, and actual versions. Use `--offline` to require those exact cached files. The owner should supply original raw files if an exact historical reproduction is required.
