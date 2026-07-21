# Alpha Asymmetry in Foreign Exchange Markets

**An Investigation of Exploitability**

[![DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.18638784-blue.svg)](https://doi.org/10.5281/zenodo.18638784)
[![License: CC BY 4.0](https://img.shields.io/badge/License-CC_BY_4.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/)
[![Status](https://img.shields.io/badge/Status-Preprint-green.svg)](https://doi.org/10.5281/zenodo.18638784)

**Working Paper DAI-2605** | [Dissensus AI](https://dissensus.ai)

## Abstract

This paper investigates whether distributional asymmetries in foreign exchange alpha signals represent exploitable market inefficiencies. Using EUR/JPY data spanning November 2015--August 2025 (504 weekly observations after rolling window warmup), we find that the asymmetry premise itself largely dissolves under dependence-robust measurement: of five alpha signal types, only the volatility-expansion (coverage) signal exhibits skewness that survives block-bootstrap inference (1.75, 95% CI [1.17, 2.15]); the signed tail signal skews *negative* rather than positive (-1.47, CI [-3.09, 0.54]), and momentum, mean-reversion, and correlation signals are statistically indistinguishable from symmetry. The economic null is correspondingly stark: a skewness-threshold strategy earns 3.60% cumulative gross over the decade (17 trades, Sharpe 0.15), is nearly inert in walk-forward testing (3 trades in eight out-of-sample years), and carries no residual alpha against proxy carry, momentum, and dollar factors. Because the strategy trades so rarely, transaction costs are immaterial rather than decisive: net returns remain within 0.4 percentage points of gross even at wide retail spreads, with break-even near 19 pips round-trip. Data-snooping corrections complete the null: White's Reality Check (p = 0.15) and Hansen's SPA (p = 0.28) find no strategy in a 13-candidate universe that outperforms -- the best realized mean return belongs to the random benchmark. We conclude that alpha signal asymmetry in this setting is neither robustly detectable nor exploitable, and we caution that unsigned-magnitude constructions can manufacture the appearance of asymmetry where none exists.

## Key Findings

| Finding | Result |
|---------|--------|
| Alpha signals deviate from normality? | Mostly -- 4 of 5 reject; fast alpha is exactly Gaussian |
| Skewness robust to serial dependence? | Only coverage alpha; the tail signal skews *negative* and fragilely |
| Exploitable heavy tails? | No (GPD shape -0.25, CI [-1.62, 0.25]; weak clustering, extremal index 0.83) |
| Strategy returns distinguishable from zero? | No -- the central null; return and Sharpe CIs include zero *before* costs |
| Do transaction costs matter? | No -- immaterial at 17 trades/decade (break-even ~19 pips round-trip) |
| Survives data-snooping correction? | No -- RC p = 0.15, SPA p = 0.28; best raw performer is the random benchmark |
| Cross-market generalization? | No -- the tail-skew signature reverses sign in GBP/USD, SPY, and GLD |

## Why This Matters

This is a **null result paper**, and the null starts earlier than the usual backtest disappointment: under dependence-robust measurement, most of the claimed asymmetry was never there. An earlier version of this paper reported pronounced positive tail skewness (5.05); that figure described the *unsigned* exceedance magnitude, which is right-skewed by construction. The corrected paper documents that measurement failure from the inside -- a case study in how higher-moment "stylized facts" can be manufactured by sign conventions. Null findings of this kind are underreported in quantitative finance ([Harvey, 2017](https://doi.org/10.1111/jofi.12530)), yet they prevent wasted research effort and capital allocation to spurious patterns.

## Alpha Types Analyzed

| Alpha Type | Description | Skew (signed series) |
|-----------|-------------|----------------------|
| Tail Alpha | Signed returns beyond the rolling 95th-percentile magnitude threshold | -1.47 (CI [-3.09, 0.54]) |
| Fast Alpha | 5-day return normalized by 20-day realized volatility | 0.01 |
| Pricing Alpha | Deviation from 60-day fair value (mean reversion) | -0.17 |
| Coverage Alpha | Volatility compression ratio σ₂₀(t)/σ₂₀(t−5) − 1 | 1.75 (CI [1.17, 2.15]) |
| Hedge Alpha | DXY correlation × JPY--USD rate differential | 0.15 |

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
│   ├── make_asymmetry_figure.py     # Figure 1 script
│   ├── make_backtest_figure.py      # Figure 2 script
│   ├── phase0_data_verification.py  # Data verification
│   └── recompute_tables.py          # Legacy table recomputation
├── CITATION.cff
└── LICENSE
```

Data are retrieved programmatically from public sources (Yahoo Finance) by `analysis/full_pipeline.py`, which records retrieval counts and dates.

## Versions

- **v2.1 (July 2026, this repository):** corrected analysis -- signed tail-signal series, block-bootstrap skewness inference, recomputed benchmark and cost tables, valid extremal-index interval. Each correction is documented in the corresponding table note.
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
- **Code (GitHub):** [github.com/studiofarzulla/alpha-asymmetry](https://github.com/studiofarzulla/alpha-asymmetry)
- **ASCRI Programme:** [systems.ac/2/DAI-2605](https://systems.ac/2/DAI-2605)
- **Dissensus AI:** [dissensus.ai](https://dissensus.ai)

## License

Paper content: [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/)
