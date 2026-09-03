# Proposed pull request

## Title

Correct strategy chronology, AI, trade accounting, and reproducibility

## Description

### Summary

This PR audits the current manuscript against the current code and corrects confirmed specification errors without optimizing the strategy for a positive result. The corrected baseline is negative: -7.57% cumulative gross, Sharpe -0.173, across 15 directional holding episodes.

### Confirmed corrections

- preserve positions until an opposing signal, simultaneous-signal conflict, or four-return-period expiry;
- use one Friday-close-to-next-Friday-close execution lag for the headline strategy, benchmarks, walk-forward, factor analysis, costs, and candidate universe;
- calculate AI as mean squared deviations from the overall mean, matching the displayed equation;
- fix entry size for the duration of an episode and document the actual 1--2 unit leveraged range;
- replace position-change-events/2 with dated position and episode ledgers;
- attribute VIX regimes after one complete chronological strategy run;
- replace machine-specific paths with repository-relative paths and CLI overrides;
- cache local inputs, record SHA-256 hashes/retrieval dates/software versions, and support `--offline` reproduction;
- revise the Monday-open, fast-alpha, hedge-proxy, sample-date, hypothesis-test, tail, and random-candidate descriptions.

### Main result changes

- baseline gross return: +3.60% -> -7.57%;
- Sharpe: 0.149 -> -0.173;
- maximum drawdown: -7.96% -> -14.29%;
- exposed weeks: 25 -> 55;
- accounting: 15 directional episodes, 30 execution legs, one reversal, no resizing;
- walk-forward: one OOS episode and +2.74% cumulative, too sparse for inference;
- low/high-VIX attributed returns: -5.78% / -1.90%;
- retail-wide net return: -7.93%; positive-cost break-even is not applicable;
- White RC p=0.15 and SPA p=0.26 against a zero-return benchmark.

`analysis/before_after_results.csv` records additional changes and causes.

### Verification

- deterministic unit tests cover AI edge cases, dated timing, entry, hold, expiry, reversal, simultaneous signals, no-signal periods, both sizing modes, resize cost accounting, and reversal accounting (14 tests, all passing);
- the complete online pipeline was run and inputs were cached with hashes;
- the complete pipeline was rerun successfully with `--offline`;
- seven of the eight input files reproduced byte-for-byte on an independent download; the eighth is explained below;
- all affected figures and manuscript tables were regenerated;
- after every rerun: the analysis sample is n = 504 spanning 2016-01-08 to 2025-08-29, the factor intercept matches the strategy's own mean weekly return, and the low- and high-VIX returns compound to the full-sample return.

**The committed PDF is stale and must be rebuilt before submission.**
`paper/alpha-asymmetry.pdf` is the September build produced by the Codex agent.
It predates every change in this branch and does not reflect the corrected
manuscript. No LaTeX toolchain was available in the session that prepared these
changes, so the PDF could not be recompiled and was not visually inspected.

An earlier draft of this document asserted that "LaTeX was compiled and the
resulting PDF was rendered and visually inspected." That assertion originated
with the Codex agent, is not true of this branch, and has been removed. Flagging
it here rather than deleting it silently, because unverified assertions are the
subject of this pull request.

What was done instead, on the LaTeX source directly:

- brace balance checked across the whole file (648 open, 648 close);
- `table`, `tabular` and `equation` environments checked for matched
  `\begin`/`\end` pairs (11 of each);
- every edited table's row-by-row column count checked against its column
  specification, including `\multicolumn` spans.

These confirm the source is structurally well formed. They do not confirm that
it typesets correctly, that floats place sensibly, or that no text overflows.
**Please rebuild the PDF and inspect it.**

### Reproduction

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pytest -q
.venv/bin/python analysis/full_pipeline.py --refresh
.venv/bin/python analysis/full_pipeline.py --offline
```

### Limitations and owner decisions

The original raw snapshots are absent, so exact historical reproduction is not claimed. Yahoo closes are indicative, Monday-open execution is not implemented, and financing is omitted. Please confirm the simultaneous-signal/expiry precedence, leveraged sizing intent, preferred executable-price convention, whether original raw files can be supplied, and whether an approved EUR--JPY rate or forward series should be added in a separate change.

No branch was pushed, no pull request was opened, and nothing was merged.
