# Alpha Asymmetry in Foreign Exchange Markets

**An Investigation of Exploitability**

[![DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.18638784-blue.svg)](https://doi.org/10.5281/zenodo.18638784)
[![License: CC BY 4.0](https://img.shields.io/badge/License-CC_BY_4.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/)
[![Status](https://img.shields.io/badge/Status-Preprint-green.svg)](https://doi.org/10.5281/zenodo.18638784)

**Working Paper DAI-2605** | [Dissensus AI](https://dissensus.ai)

## Abstract

This paper investigates whether distributional asymmetries in foreign-exchange signals are exploitable in EUR/JPY. The analysis-ready sample contains 504 Friday observations from January 2016 through August 2025. Coverage alpha is the only signal whose skewness interval excludes zero (1.75, 95% block-bootstrap CI [1.18, 2.16]). Under the corrected one-lag chronology, four-return-period holding rule, and equation-consistent asymmetry index, the headline strategy loses 7.57% gross (15 directional episodes; Sharpe -0.17). Its stationary-bootstrap return and Sharpe intervals include zero, and walk-forward selection produces only one OOS episode. White's Reality Check (p = 0.15) and Hansen's SPA (p = 0.26) find no statistically superior candidate against a zero-return benchmark. These are negative results; no parameter search was performed to make the strategy profitable.

## Key Findings

| Finding | Result |
|---------|--------|
| Alpha signals deviate from normality? | Mostly -- 4 of 5 reject; fast alpha does not reject normality |
| Skewness robust to serial dependence? | Only coverage alpha; the tail signal skews *negative* and fragilely |
| Pareto-type heavy tails in weekly absolute returns established? | No -- GPD shape -0.25, wide CI [-1.49, 0.27] |
| Corrected baseline | -7.57% gross; 15 episodes; Sharpe -0.17 |
| Strategy returns distinguishable from zero? | No -- annualized-return CI [-3.57%, 1.48%] |
| Do transaction costs rescue the result? | No -- they monotonically worsen an already negative gross return |
| Survives data-snooping correction? | No -- RC p = 0.15, SPA p = 0.26 against zero return |
| Cross-market generalization? | No -- the tail-skew signature reverses sign in GBP/USD, SPY, and GLD |

## Why This Matters

This is a **null result paper**, and the null starts earlier than the usual backtest disappointment: under dependence-robust measurement, most of the claimed asymmetry was never there. An earlier version of this paper reported pronounced positive tail skewness (5.05); that figure described the *unsigned* exceedance magnitude, which is right-skewed by construction. The corrected paper documents that measurement failure from the inside -- a case study in how higher-moment "stylized facts" can be manufactured by sign conventions. Null findings of this kind are underreported in quantitative finance ([Harvey, 2017](https://doi.org/10.1111/jofi.12530)), yet they prevent wasted research effort and capital allocation to spurious patterns.

## Alpha Types Analyzed

| Alpha Type | Description | Skew (signed series) |
|-----------|-------------|----------------------|
| Tail Alpha | Signed returns beyond the rolling 95th-percentile magnitude threshold | -1.48 (CI [-3.10, 0.54]) |
| Fast Alpha | 5-day return normalized by 20-day realized volatility | 0.01 |
| Pricing Alpha | Deviation from 60-day fair value (mean reversion) | -0.17 |
| Coverage Alpha | Volatility compression ratio σ₂₀(t)/σ₂₀(t−5) − 1 | 1.75 (CI [1.18, 2.16]) |
| Hedge Alpha | 100-day DXY correlation × fixed −0.02 proxy | 0.15 |

Skewness computed on the signed weekly series (n = 504) with 95% circular block bootstrap intervals; only coverage alpha's interval excludes zero.

## Keywords

null result, alpha asymmetry, foreign exchange, skewness, market efficiency, extreme value theory

## JEL Codes

G11, G14, G15, C58

## Repository Structure

```
alpha-asymmetry/
├── paper/
│   ├── alpha-asymmetry.tex          # LaTeX source
│   ├── alpha-asymmetry.pdf          # Compiled paper
│   ├── references.bib               # Bibliography
│   └── *.png                        # Figures
├── analysis/
│   ├── full_pipeline.py             # Replication pipeline (all tables & stats)
│   ├── full_pipeline_results.json   # Pipeline outputs (machine-readable)
│   ├── full_pipeline_results.txt    # Pipeline outputs (human-readable)
│   ├── strategy.py                  # Shared strategy, AI, and ledger engine
│   ├── data_access.py               # Cached-data loader and hash manifest
│   ├── position_ledger.csv          # Dated weekly decision/execution ledger
│   ├── trade_ledger.csv             # Directional holding episodes
│   ├── make_asymmetry_figure.py     # Figure 1 script
│   ├── make_backtest_figure.py      # Figure 2 script
│   ├── phase0_data_verification.py  # Data verification
│   └── recompute_tables.py          # Legacy table recomputation
├── tests/                           # Deterministic chronology/AI/ledger tests
├── docs/                            # Audit, exploratory plan, and PR draft
├── requirements.txt                 # Exact packages used for this run
├── pyproject.toml                   # Python and test configuration
├── CITATION.cff
└── LICENSE
```

## Reproduce

Python 3.12 is recommended. From the repository root:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pytest -q
.venv/bin/python analysis/full_pipeline.py --refresh
```

The first pipeline run caches Yahoo Finance CSVs under `analysis/cache/` and writes `analysis/data_manifest.json` with retrieval dates, row counts, SHA-256 hashes, and actual package versions. Raw snapshots are not committed because redistribution terms may apply. Repeat the exact cached run with:

```bash
.venv/bin/python analysis/full_pipeline.py --offline
```

The repository did not contain the author's original raw snapshots, so the archived July results cannot be claimed as an exact reproduction. Ask the owner for those files and compare their hashes before making that claim.

## Versions

- **Current correction branch:** fixes strategy state, execution timing, AI, trade accounting, regime attribution, output portability, and reproducibility; regenerates downstream results without optimizing for profitability.
- **v2.0.x (Zenodo/SSRN):** pre-correction preprint reporting the unsigned-magnitude tail skew (5.05); superseded by this version. The Zenodo concept DOI resolves to the latest deposited version.

## Citation

```bibtex
@article{farzulla2026alpha,
  author  = {Farzulla, Murad},
  title   = {Alpha Asymmetry in Foreign Exchange Markets: An Investigation of Exploitability},
  year    = {2026},
  journal = {Dissensus AI Working Paper DAI-2605},
  doi     = {10.5281/zenodo.18638784}
}
```

## Authors

- **Murad Farzulla** -- [Dissensus AI](https://dissensus.ai) & King's College London
  - ORCID: [0009-0002-7164-8704](https://orcid.org/0009-0002-7164-8704)
  - Email: murad@dissensus.ai

## Links

- **Paper (Zenodo):** [10.5281/zenodo.18638784](https://doi.org/10.5281/zenodo.18638784)
- **Paper (SSRN):** [SSRN:6147567](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6147567)
- **Code (GitHub):** [github.com/dissensus-ai/alpha-asymmetry](https://github.com/dissensus-ai/alpha-asymmetry)
- **ASCRI Programme:** [systems.ac/2/DAI-2605](https://systems.ac/2/DAI-2605)
- **Dissensus AI:** [dissensus.ai](https://dissensus.ai)

## License

Paper content: [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/)
