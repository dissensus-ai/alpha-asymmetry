# Alpha Asymmetry in Foreign Exchange Markets

**An Investigation of Exploitability**

[![DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.18638784-blue.svg)](https://doi.org/10.5281/zenodo.18638784)
[![Code licence: MIT](https://img.shields.io/badge/Code-MIT-yellow.svg)](LICENSE)
[![Paper licence: CC BY 4.0](https://img.shields.io/badge/Paper-CC_BY_4.0-lightgrey.svg)](LICENSE-CC-BY-4.0)
[![Status](https://img.shields.io/badge/Status-Preprint-green.svg)](https://doi.org/10.5281/zenodo.18638784)

**Working Paper DAI-2605** | [Dissensus](https://dissensus.ai)

## Abstract

This paper investigates whether distributional asymmetries in foreign-exchange signals are exploitable in EUR/JPY. The analysis-ready sample contains 504 Friday observations from January 2016 through August 2025. Coverage alpha is the only signal whose skewness interval excludes zero (1.75, 95% block-bootstrap CI [1.18, 2.16]). Under the corrected one-lag chronology (execution at the first trading-session open after each Friday signal), four-return-period holding rule, and equation-consistent asymmetry index, the headline strategy returns -0.73% gross (15 directional episodes; Sharpe +0.005). Its stationary-bootstrap Sharpe interval includes zero, and walk-forward selection produces only one OOS episode. Four pre-specified readings of the entry rule span 9.04 percentage points and change sign. White's Reality Check (p = 0.29) and Hansen's SPA (p = 0.55) find no statistically superior candidate against a zero-return benchmark. These are negative results; no parameter search was performed to make the strategy profitable.

## Key Findings

| Finding | Result |
|---------|--------|
| Alpha signals deviate from normality? | Mostly -- 4 of 5 reject; fast alpha does not reject normality |
| Skewness robust to serial dependence? | Only coverage alpha; the tail signal skews *negative* and fragilely |
| Pareto-type heavy tails in weekly absolute returns established? | No -- GPD shape -0.25, wide CI [-1.49, 0.27] |
| Corrected baseline | -0.73% gross; 15 episodes; Sharpe +0.005 |
| Strategy returns distinguishable from zero? | No -- stationary-bootstrap Sharpe interval [-0.73, 0.64] |
| Robust to the entry-rule specification? | No -- four pre-specified rules span 9.04 pp and change sign |
| Do transaction costs rescue the result? | No -- they monotonically worsen an already negative gross return |
| Survives data-snooping correction? | No -- RC p = 0.29, SPA p = 0.55 against zero return |
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
│   ├── fetch_data.py                # Fetch raw inputs and verify their hashes
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
├── LICENSE                          # MIT licence (code)
└── LICENSE-CC-BY-4.0                # CC BY 4.0 licence (paper and documentation)
```

## Reproduce

Python 3.12 is recommended. From the repository root:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pytest -q
.venv/bin/python analysis/fetch_data.py
.venv/bin/python analysis/full_pipeline.py --offline
```

`fetch_data.py` downloads the eight raw series, then checks each file's SHA-256
against the hashes recorded in `analysis/data_manifest.json` and tells you, per
series, whether you are working from the same bytes these results were produced
from. `full_pipeline.py --offline` then requires those exact cached files rather
than silently re-downloading. `--refresh` on the pipeline does the download
inline instead, if you would rather do it in one step.

### Data

**The raw CSVs are not committed.** Yahoo Finance data may be subject to
redistribution terms, so this repository records what the inputs were rather
than republishing them; a fresh clone has no inputs until you run
`fetch_data.py`. `analysis/data_manifest.json` holds retrieval dates, row
counts, date bounds, SHA-256 hashes, and the package versions actually used.

**Expect seven of eight hashes to reproduce, and SPY not to.** Six of the eight
series are FX spot rates or index levels. Nothing adjusts them for corporate
actions, so their stored history is fixed and their file hashes are reproducible
indefinitely. GLD made no cash distribution over the requested window. SPY is
the one file in the set that *can* change: it is a distributing ETF requested
with `auto_adjust=True`, so its entire price history is rescaled every time a
new distribution is paid.

That rescaling does not revise any observation and does not touch any percentage
return — it moves the stored price level, and therefore the bytes. On an
independent download five hours after the committed run, seven of eight files
matched byte-for-byte; SPY differed, and the difference moved five values in the
SPY cross-market row in their fifth or sixth significant figure, every one of
which rounds to the same printed number. Nothing else in the pipeline output
changed. `fetch_data.py` reports expected and unexpected differences separately
and only exits non-zero on the latter.

The repository did not contain the author's original raw snapshots, so the
archived July results cannot be claimed as an exact reproduction. Ask the owner
for those files and compare their hashes before making that claim.

## Versions

- **v3.1.1 (October 2026, this repository):** v3.1.0 plus the corrections of 6 Oct 2026. The return bootstrap and the performance statistics now exclude the non-executable final week (stationary-bootstrap Sharpe interval [-0.51, 0.49] → [-0.73, 0.64]; Reality Check p 0.30 → 0.29; SPA p 0.58 → 0.55); the execution-timing contrasts and the weekend-gap test are now pipeline output; robustness detail moved to appendices; the code is released under the MIT licence, and the paper and figures stay under CC BY 4.0. No conclusion changes. Details: `docs/CORRECTION_CHANGELOG.md`. Prepared as a new Zenodo version under the concept DOI, with Tofik Israfilov as co-author; until that version is published, the concept DOI resolves to v3.0.0.
- **v3.1.0 (PR #2 by Tofik Israfilov, merged 29 Sep 2026; not deposited):** corrected the holding rule, the execution lag, the asymmetry index, trade accounting and regime attribution against the published specification, and regenerated every downstream result without optimizing for profitability.
- **v3.0.0 (Zenodo record 21315494, 11 Jul 2026):** corrected the unsigned-magnitude tail skew and replaced the walk-forward, but its strategy figures came from code whose exit rule did not match the specification (3.60% gross, 17 trades); superseded by v3.1.x.
- **v2.0.x (Zenodo v2.0.0 and v2.0.1; SSRN 6147567):** pre-correction preprint reporting the unsigned-magnitude tail skew (5.05). The SSRN record was registered in February 2026 for this version.
- **v1.0.0 (Zenodo record 17918374, 13 Dec 2025; its own concept DOI, 10.5281/zenodo.17918373):** the first deposited version, titled "Alpha Asymmetry in Foreign Exchange Markets — Detection and Exploitation: Evidence from EUR/JPY and Cross-Market Analysis". It reports the unsigned-magnitude tail skew (5.05) and an asymmetry-strategy Sharpe ratio of 0.154, both superseded. The record carries a notice pointing to the concept DOI 10.5281/zenodo.18638784.

## Citation

```bibtex
@article{farzulla2026alpha,
  author  = {Farzulla, Murad and Israfilov, Tofik},
  title   = {Alpha Asymmetry in Foreign Exchange Markets: An Investigation of Exploitability},
  year    = {2026},
  journal = {Dissensus Working Paper DAI-2605},
  version = {3.1.1},
  doi     = {10.5281/zenodo.18638784}
}
```

Co-authorship takes effect from v3.1.x; the published deposits (Zenodo v1.0.0, v2.0.0, v2.0.1 and v3.0.0, SSRN 6147567) are sole-authored.

## Authors

- **Murad Farzulla** -- [Dissensus](https://dissensus.ai) & King's College London
  - ORCID: [0009-0002-7164-8704](https://orcid.org/0009-0002-7164-8704)
  - Email: murad@dissensus.ai
- **Tofik Israfilov** -- [Dissensus](https://dissensus.ai)
  - ORCID: [0009-0006-9095-7739](https://orcid.org/0009-0006-9095-7739)
  - Email: tofik@dissensus.ai

## Links

- **Paper (Zenodo):** [10.5281/zenodo.18638784](https://doi.org/10.5281/zenodo.18638784)
- **Paper (SSRN):** [SSRN:6147567](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6147567) -- registered for v2.0.0 and superseded; until it is revised it may still serve that version (see Versions)
- **Code (GitHub):** [github.com/dissensus-ai/alpha-asymmetry](https://github.com/dissensus-ai/alpha-asymmetry)
- **ASCRI Programme:** [systems.ac/2/DAI-2605](https://systems.ac/2/DAI-2605)
- **Dissensus:** [dissensus.ai](https://dissensus.ai)

## License

The code is released under the [MIT licence](LICENSE); the paper is released
under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)
([`LICENSE-CC-BY-4.0`](LICENSE-CC-BY-4.0)). Copyright 2025-2026 Murad Farzulla
and Tofik Israfilov.

- **MIT (`LICENSE`):** the software. Everything under `analysis/` (the Python
  code and scripts, and the results files, ledgers and data manifest they write
  there), everything under `tests/`, `pyproject.toml` and `requirements.txt`.
- **CC BY 4.0 (`LICENSE-CC-BY-4.0`):** the paper and its documentation.
  Everything under `paper/` (the manuscript's LaTeX source and bibliography, the
  compiled PDF and the figures), everything under `docs/`, this README,
  `CITATION.cff`, the earlier versions in `_archive/`, and any other file not
  listed under MIT.

The raw market data are not in the repository (see Data above) and are licensed
by neither file.
