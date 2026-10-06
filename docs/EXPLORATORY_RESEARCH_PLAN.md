# Exploratory research plan (not executed)

This plan is intentionally separate from the corrected confirmatory analysis. The audited baseline is frozen at the code, data hashes, thresholds, and outputs recorded on 2026-09-02. A null result is acceptable, and no exploratory result should replace the frozen baseline.

## Governance shared by all experiments

Before running a specification, register its economic rationale, variables, sign or non-directional target, information timestamp, execution timestamp, sample split, cost model, leverage cap, turnover cap, minimum observations, and minimum directional episodes. Keep a complete machine-readable registry of every attempted specification. Use training data for estimation, a validation period for a single model choice, and an untouched final test. Report exposure-matched benchmarks, spreads, financing, and dependence-aware confidence intervals. Apply family-level multiple-testing control and a final Reality Check/SPA-style assessment across the complete tried universe.

Suggested prespecified split, subject to the owner's approval and data coverage: training through 2019, validation 2020--2022, untouched test 2023--2025. With weekly data this is short; minimum sample and episode rules may require a broader pair panel before any credible frozen test.

## A. Skewness-filter ablation

Question: does the rolling-skewness filter add incremental information beyond the sign/level entry conditions?

- Freeze the corrected timing, four-return-period hold, entry-only sizing, simultaneous-signal rule, costs, sample, and leverage.
- Compare the complete baseline against one ablation that removes only the skewness threshold.
- Match gross exposure or volatility ex ante so activity alone cannot explain the comparison.
- Primary outcome: next-period net return differential; secondary outcomes: episode count, turnover, drawdown, and exposure.
- Use paired block-bootstrap inference on weekly return differences and include both candidates in the multiple-testing universe.
- Do not tune a replacement threshold after seeing validation or test outcomes.

## B. Coverage-alpha forecasting

Question: does coverage alpha forecast next-period realized volatility, absolute return, or downside risk?

Coverage alpha is non-directional, so the first-stage targets are `|r_{t+1}|`, realized volatility over a fixed horizon, and downside-loss indicators—not the sign of EUR/JPY.

- Estimate simple monotonic or linear forecasts with trailing inputs only.
- Compare against historical-volatility and unconditional baselines using out-of-sample loss functions appropriate to volatility, plus calibration plots.
- If and only if predictive evidence survives validation and multiplicity control, predefine one exposure-reduction or volatility-targeting rule.
- Evaluate that risk rule against an exposure-matched strategy with realistic spread, turnover, leverage, and financing constraints.
- Keep forecasting evidence distinct from trading profitability.

## C. Broader currency sample

Question: does one prespecified model generalize across liquid pairs?

- Choose the pair universe before retrieval, preferably major liquid crosses with sufficient common history.
- Use pair-specific pip sizes, spreads, holiday calendars, quote directions, and dated financing or forward points.
- Freeze one model across pairs; do not retune windows or signs pair by pair.
- Use panel or hierarchical methods and inference robust to cross-pair dependence.
- Hold out both time and, if feasible, some currency pairs.
- Report results for every pair and specification, including exclusions and download failures.

## Stop rules

Do not proceed to the untouched test unless the preregistered validation criteria and minimum episode count are met. Run the final test once. A failed criterion or null final test ends the confirmatory claim; further work returns to a newly labeled exploratory cycle.
