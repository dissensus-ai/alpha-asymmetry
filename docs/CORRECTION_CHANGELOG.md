# Correction changelog

**Baseline for every comparison in this document:** `4d21c69`, the published
July 2026 version of the paper and its committed pipeline. Every "published"
figure below is transcribed from `4d21c69:analysis/full_pipeline_results.json`,
`4d21c69:analysis/full_pipeline_results.txt`, or the tables of
`4d21c69:paper/alpha-asymmetry.tex`. The original raw inputs were not committed,
so these are the reported results of that run rather than an independent rerun
of it.

Changes are grouped by what kind of claim they make on the reader, so that each
group can be accepted or rejected on its own terms:

| | Category | What it means |
|---|---|---|
| **(a)** | Implementation defects corrected | The paper specified X, the code did Y by accident, the code now does X |
| **(b)** | Methodological changes proposed | The paper and the code agreed, and we are proposing something different |
| **(c)** | Manuscript corrections | The code is doing something defensible and the paper describes it wrongly |
| **(d)** | Prose corrected without a wrong figure | Sentences whose argument depends on a result that no longer holds |
| **(e)** | Provenance footnotes restored | The paper's own record of its earlier corrections |
| **(f)** | Reproducibility | Inputs, hashes, environment |

Nothing appears in (a) unless the published paper and the published code
genuinely disagreed. `analysis/before_after_results.csv` gives every changed
figure with its published value, its corrected value, and the category that
produced the change.

---

## The single most important number

**The published strategy held a position in 25 of 504 weeks.** The corrected one
holds a position in 55.

The published code closed any open position the moment its entry signal stopped
firing, which was not the rule the paper described. The strategy was therefore in
the market about five percent of the time, and every headline result — the
+3.60% return, the 0.149 Sharpe ratio, the factor regression with its
25-observation effective sample, the "immaterial" transaction costs — described
that five percent.

This is why the published null result had little content. A strategy that is
almost never invested cannot demonstrate much of anything, in either direction.
Correcting it is what moves the paper from a weak null to a substantive one.

---

## (a) Implementation defects corrected

Three. In each, the published paper stated a rule and the published code did
something else.

### a1. Positions closed whenever the entry signal stopped firing

**Paper (`4d21c69`, §2.4):** "Exit: Signal reversal (opposite entry condition
met) OR 4-week maximum holding period reached."

**Code (`4d21c69:analysis/full_pipeline.py`):** the branch intended to hold a
position through a quiet week was guarded by
`prev_pos > 0 and not long_signal.iloc[i-1]`, but that branch was only reachable
when `not long_signal.iloc[i-1]` was already true. The condition was therefore
always satisfied, `new_pos = prev_pos` was unreachable for any open position, and
every position closed as soon as its entry signal stopped firing.

**Now:** a position is held through no-signal weeks, reverses on the opposing
signal, and expires after four realized weekly returns, as the paper says.

**Effect:** exposure 25 → 55 weeks of 504. This is the dominant driver of nearly
every changed figure in the paper.

### a2. The headline strategy carried two execution lags; everything else carried one

**Paper (`4d21c69`, §2.4):** "Entry: Monday open following Friday signal
generation" — one period between signal and return.

**Code:** signals were read at `iloc[i-1]` inside the strategy loop, the
resulting position was stored at `i`, and realized returns were then computed as
`position.shift(1) * weekly_return`. Two lags. The benchmarks
(`simple_strategy`) and the momentum factor used one, so the headline strategy
was being compared against benchmarks on a different clock.

**Now:** signals are formed at Friday close `t`, the position is recorded at `t`,
and it earns the return ending at Friday `t+1`. One lag, applied identically to
the headline strategy, the benchmarks, the walk-forward, the factor regression,
the cost analysis and the data-snooping universe.

### a3. The asymmetry index did not implement Equation 5

**Paper (`4d21c69`, Equation 5):** the ratio of mean squared deviations above and
below the *overall* sample mean, each divided by its own count.

**Code:** `pos.var() / neg.var()`, which re-centres each subgroup on its own mean
and uses `n−1` denominators. A different statistic. The code also returned `1.0`
— a valid-looking neutral value — for degenerate cases and for windows shorter
than five observations, silently reporting an asymmetry index where none was
defined.

**Now:** Equation 5 as printed. Undefined cases return a missing value, and a
one-observation side is valid, because a mean square about the overall mean is
not a subgroup sample variance.

**Effect:** every AI value in Table 1 changes; tail alpha 0.17 → 0.03,
coverage 3.45 → 2.22.

---

## (b) Methodological changes proposed

Three. In each the published paper and the published code agreed with each other,
and we are proposing to depart from them. These are judgement calls, not defects,
and each can be rejected independently without disturbing (a).

### b1. Sizing during held-but-unsignalled weeks

Fixing a1 creates a state the published specification never had to describe. The
published rule was "Rebalancing: Weekly (end of Friday close)" with Equation 10
evaluated at the contemporaneous `AI_t`, and the published code did resize on
every bar where the entry signal fired — which, given a1, was every bar on which
any position was held. Paper and code agreed.

But neither ever faced a week in which a direction is *held while no signal
fires*, because the published implementation could not reach that state. Both
available answers are extensions:

- **evaluate the sizing equation weekly** while a direction is held — keeps the
  published rebalancing frequency and Equation 10's contemporaneous subscript,
  and requires changing no published sentence;
- **freeze the notional at entry** — a smaller notional path, but it contradicts
  both the published equation and the published rebalancing line.

**Proposed:** weekly evaluation, as the smaller extension. The argument against
it is recorded rather than omitted: weekly resizing lets the asymmetry index
change exposure on new information every week, which makes it closer to a second
timing signal than to a sizing multiplier.

**Both are reported.** The frozen-notional alternative is computed in the same
run and appears under `sizing_variants` in `full_pipeline_results.json`.

| | weekly (proposed) | frozen (alternative) |
|---|---|---|
| Cumulative gross return | −6.64% | −7.57% |
| Sharpe | −0.153 | −0.173 |
| Maximum drawdown | −12.56% | −14.29% |
| Hit rate | 47.27% | 47.27% |
| In-position weeks | 55 | 55 |
| Holding episodes | 15 | 15 |
| Execution legs | 61 | 30 |
| Turnover (units) | 52.00 | 49.15 |

Entries, exits, direction and exposure are identical under both. **No conclusion
in the paper depends on the choice.**

### b2. "Trades" redefined as holding episodes and execution legs

The published paper defined its own metric explicitly — "Trades = completed round
trips (position-change events divided by two, a sign flip counting as one event)"
— and the code implemented exactly that. They agreed.

They were nonetheless inconsistent with each other: events ÷ 2 does not count
completed round trips when a sign flip is treated as one event. For the momentum
benchmark it reported 27 "round trips" for what are 54 directional holdings and
107 executions.

**Proposed:** report *holding episodes* (one continuous directional position) and
*execution legs* (entries and exits counted separately, so a reversal is two)
separately, plus resizing and absolute turnover, all from dated ledgers
(`analysis/position_ledger.csv`, `analysis/trade_ledger.csv`).

**Effect on the headline:** 17 published "trades" → 15 holding episodes and 61
execution legs. The underlying returns are unchanged by this item.

### b3. Single-episode statistics are no longer reported as performance

The published walk-forward reported a pooled Sharpe ratio of 0.419 and a 60% hit
rate from three trades; the corrected walk-forward opens one episode.

**Proposed:** a Sharpe ratio, a hit rate and an annualized return are sample
statistics. Below two holding episodes they are not estimates of anything, and
we decline to print them. The rule is enforced in code
(`MIN_EPISODES_FOR_INFERENCE`), applied wherever such statistics arise rather
than table by table, and logged when it fires. Suppressed values remain in
`full_pipeline_results.json` so the decision stays checkable.

Affects the walk-forward table and the 1.25 row of the threshold-sensitivity
table — which is, in fact, the same single 2020 episode. Withheld figures are
removed with the reason stated, never replaced by an unexplained placeholder.

---

## (c) Manuscript corrections

The code does something defensible; the published paper describes it wrongly, or
describes something the code never did. Split by whether keeping the code was the
obvious call.

### c1. The paper mis-stated its own code

- **Fast alpha** was printed as `(P_t − P_{t−5}) / (σ_20 √5)`, a price difference
  divided by a volatility estimated from percentage returns — dimensionally
  incoherent, and not what the code computed. The equation now shows
  `(P_t/P_{t−5} − 1)`, which is the only reading under which the signal is the
  z-score the paper calls it.
- **Position size** was printed as `max(0.5, min(2.0, 1 + |AI_t − 1|))` with the
  claim of "no leverage" and a stated range of [0.5, 2.0]. The 0.5 floor is
  unreachable: the inner expression is never below 1. The real range is [1, 2]
  gross-notional units, and values above one imply leverage against one unit of
  capital. Both are now stated.
- **Hedge alpha** was printed as `ρ_t × Δr_t` with a time-varying JPY−USD rate
  differential. No dated rate series exists anywhere in the repository; the code
  multiplies the correlation by a fixed −2%. The published prose already
  conceded this in passing; the equation now shows the constant, and the signal
  is labelled a fixed-rate correlation proxy rather than a measure of changing
  rate regimes.
- **Tail alpha** was described with a "rolling 52-week 95th percentile"; the code
  uses a trailing 252 trading days with a 60-observation warm-up. The same
  horizon, stated as implemented.

### c2. Paper and code disagreed, and we kept the code — argued, not assumed

These are exceptions to the rule that the code gets fixed to match the paper.
Each is stated so it can be overruled.

- **Monday-open execution.** The paper specifies entry at the Monday open
  following a Friday signal. The code uses the Friday close. We have kept the
  Friday close and **corrected a false statement about why**: an earlier draft of
  this correction asserted that Monday opening prices are not present in the
  dataset. They are — the daily bars carry an `Open` column. The Friday-close
  proxy is therefore a choice, not a data limitation, and the paper now says so.
  Implementing Monday-open execution is a separate change and is on the backlog.
- **The EVT section.** The paper presents the GPD fit as characterising the
  tail-alpha exceedance distribution — the strategy's own premise. The code fits
  absolute Friday-to-Friday returns, which is a different sample. The section and
  table are relabelled as a weekly-return tail diagnostic. **The ground rule says
  the code should have been changed instead**, and refitting to tail alpha is on
  the backlog; the relabelling is honest in the meantime but should not be
  mistaken for the fix.

### c3. Sample description

The published text said the raw sample comprised 513 weekly observations, of
which the first 9 were consumed by rolling-window warm-up. That is arithmetically
correct. The dates are now stated explicitly: the raw weekly grid begins
6 November 2015, and the analysis-ready sample runs 8 January 2016 to
29 August 2025, n = 504. **The analysis sample is unchanged from the published
paper in both size and span.**

---

## (d) Prose corrected without a wrong figure

Recorded separately because a figure-by-figure sweep does not find these, and
because it is the most transferable lesson in the correction.

The published paper argued that a modest gross edge survived measurement and was
not eliminated by transaction costs. Every sentence resting on that architecture
is wrong under the corrected numbers **regardless of the digits it contains**,
because there is no edge. Four examples, none of which contained an incorrect
figure:

| Location | Published text | Why it is wrong |
|---|---|---|
| Robustness intro | "an in-sample backtest whose returns are **statistically indistinguishable from zero**" | Defensible on the interval, but presents a losing strategy as a null one. The point estimate is a loss. |
| Robustness intro | "(3) Do trading costs **erode strategy returns**?" | Presupposes returns to erode. Not merely unanswerable — the wrong question. |
| Backtest performance | drawdown "only **modestly smaller**" than buy-and-hold's | Framing, not arithmetic. Presented as mitigating what is damning: four-fifths of a permanently invested position's drawdown, incurred while exposed in 55 of 504 weeks. |
| Trading frequency | "**no resizing**" | Simply false under weekly sizing: there are 31. |

Sentences of this kind must be hunted by reading for the argument, not by
checking figures.

### The break-even statement

The published paper reported a break-even round-trip cost of **19.2 pips** and
read it as reassurance: costs would have to be implausibly wide before they
consumed the strategy's edge.

**There is now no break-even cost at all.** Not larger, not smaller, not harder
to estimate — it does not exist. The corrected strategy returns −6.64% before any
cost is applied, so there is no positive cost at which it crosses zero. A
break-even presumes a profit to be consumed.

This is a cleaner statement of the paper's null than the cost table it replaces,
and it is now made in the cost section, the cost-table note, the abstract and the
conclusion.

### The cost model's blind spot

Costs remain immaterial in magnitude (0.38 percentage points at two pips), but
that is partly a property of the model. Spread is charged strictly in proportion
to notional traded, with **no fixed or minimum per-order component**. The
corrected specification generates 31 resizings averaging 0.19 units of notional —
exactly the population a per-ticket charge falls hardest on. The reported drag is
a lower bound, and "costs are immaterial" is a claim this model cannot make.

---

## (e) Provenance footnotes restored

`4d21c69` carried nine table notes recording the paper's own earlier corrections.
Seven had been removed during the drafting of this branch and are restored.

| Table | What the note recorded |
|---|---|
| Asymmetry statistics | tail-signal skewness of 5.05 described the *unsigned* exceedance magnitude |
| Backtest performance | benchmark rows (momentum −15.66%, mean reversion 34.03%, buy-and-hold 2.31%) that traced to no committed code |
| Cross-market | aggregated "MR/TF/HAT" categories that traced to no committed code |
| Walk-forward | 141 pooled trades, not reproducible from the strategy specification |
| Transaction costs | net return *rising* with costs at low tiers — an inconsistent carry treatment |
| Factor attribution | a marginally significant 21 bps weekly intercept with F = 20.8, internally inconsistent with its own R² |
| **Data snooping** | **RC = 2.14 (p = 0.042), not reproducible from any specification of the stated universe** |

The data-snooping note deserves singling out. `RC = 2.14, p = 0.042` is the
paper's most quotable statistic — the one number in it that reported a
*significant* result. The note recorded that this figure had already been found
irreproducible. Removing the note removed the record that the paper's most
citable statistic was known to be unreliable.

Two of the nine survived. Keeping two of nine is not an editorial decision; it is
what happens when notes are dropped while the prose around them is rewritten.

**Method.** Each note is restored verbatim, with any current value appended as a
following sentence rather than woven into the original. These notes are a dated
record of what was wrong and when; editing them to agree with today's numbers
would destroy the thing that makes them worth keeping.

**Verification.** Preservation was enforced mechanically — every one of the nine
original sentences from `4d21c69` is checked to appear in the current source as
an exact substring. That check earned its place: a first attempt inserted the
words "then reported" *inside* the factor-attribution sentence, a two-word
rewrite of the historical record that reading would not have caught. The claim of
verbatim restoration is worth something only because it was machine-enforced
rather than eyeballed.

---

## (f) Reproducibility

- The pipeline retrieves eight Yahoo Finance series and records retrieval time,
  row counts, date bounds, SHA-256 hashes and actual package versions in
  `analysis/data_manifest.json`.
- `analysis/fetch_data.py` downloads the inputs and checks each file's hash
  against that manifest, separating expected differences from unexpected ones.
- **Seven of the eight files reproduce byte-for-byte** on an independent
  download. Six are FX spot rates or index levels, which carry no
  corporate-action adjustment and structurally cannot drift; GLD paid no
  distribution over the window. SPY is a distributing ETF fetched with
  `auto_adjust=True`, so its whole history is rescaled by each new distribution —
  the only file in the set that could differ, and it did. That difference moves
  five values in the SPY cross-market row in their fifth or sixth significant
  figure, every one of which rounds to the same printed number.
- The raw CSVs are **not committed.** Yahoo data may carry redistribution terms;
  that is the repository owner's decision to make knowingly, and is raised in the
  pull request rather than taken here.
- `full_pipeline.py` no longer overwrites `data_manifest.json` with its own
  observed hashes, which had destroyed the reference that verification compares
  against.
- Machine-specific absolute output paths are replaced by repository-relative
  paths with command-line overrides.
- 14 deterministic unit tests cover the AI edge cases, the dated timing
  convention, entry, hold, expiry, reversal, simultaneous signals, no-signal
  periods, both sizing modes, resize cost accounting and reversal accounting.
- After every rerun: n = 504 spanning 2016-01-08 to 2025-08-29; the factor
  intercept matches the strategy's own mean weekly return; the low- and high-VIX
  returns compound to the full-sample return.

---

## Standing limitations

Unchanged by this work, and in several cases sharpened by it.

- Yahoo Finance quotes are indicative mid-rates, not executable bid/ask. End-of-
  bar fills are an assumption.
- The original raw snapshots underlying the published results were never
  committed, so exact reproduction of the July figures cannot be claimed from the
  repository alone.
- Financing is omitted from the cost model, and exposure reaches two notional
  units across 55 weeks.
- The cost model has no per-order component (see (d)).
- 15 holding episodes, one out-of-sample episode, 20 declustered tail maxima and
  55 in-position factor observations are small samples. HAC standard errors
  adjust the inference; they do not enlarge the evidence.
- The factor series are single-market proxies, not the published cross-sectional
  FX factors. `Mom` is a twelve-week rule on EUR/JPY itself, so a strong loading
  of a single-pair strategy on it is less surprising and less transferable than a
  loading on a genuine cross-sectional factor.
- Failure to reject a null is not proof of the null.
- Cross-market checks omit pair-specific costs, financing and dependence-aware
  inference.
- The PDF is rebuilt from the corrected source and compiles clean (27 pages, no
  overfull or underfull boxes, no undefined references, bibliography resolved).
  An earlier statement in this document that no LaTeX toolchain was available and
  the PDF could not be rebuilt was true when written and is no longer true; it is
  corrected here rather than removed silently.

---

## Backlog — deliberately out of scope

0. **Reconcile the version identifiers.** `paper/alpha-asymmetry.tex` carried
   `3.0.0` for the July manuscript, `CITATION.cff` called it `2.1.0-dev`, and the
   last deposited version is `v2.0.1`. This branch sets both to 3.1.0 to follow
   the number printed on the paper, but which of the three is authoritative is
   the author's to settle.
1. Refit the EVT section to tail alpha, as the published paper describes (c2).
2. Decide Monday-open versus Friday-close execution on the merits, now that the
   Open column is known to be available (c2).
3. Source a dated EUR–JPY rate or forward series so hedge alpha stops being a
   constant multiplied by a correlation (c1).
4. Report the Sharpe ratio of exposed weeks alongside the full-sample figure. The
   full-sample Sharpe divides by the standard deviation of all 504 weeks, 449 of
   which are exactly zero, which shrinks the volatility and pulls the ratio
   toward zero.
5. Add financing/carry to the cost model.
6. Add a per-order or minimum-ticket cost component (d).

---

## Provenance of this branch

The working branch began from an unreviewed draft produced by an AI agent
(Codex), committed here unmodified as `5135bac` and labelled as such. That commit
is a starting point that was **audited rather than adopted**: its claims were
checked against `4d21c69` and its manuscript edits were reviewed line by line,
several were reversed, and every change that survives is justified in this
document against the published paper rather than against that draft. It is kept
in the history so that the work done after it is separately reviewable, and it
carries no authority.

`docs/REVIEW_NOTES.md` is the working audit record for that process, including
originator attribution for every change. It is not part of the argument of this
pull request.
