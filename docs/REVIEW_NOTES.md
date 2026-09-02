# Review notes

Running record of every change on branch `fix/strategy-specification`, who
originated it, and whether it is a **bug fix** (code did not do what the
published paper said) or a **specification decision** (a choice that changes
what the paper claims, and that no amount of code reading can settle).

Originators:

- **Murad** — Murad Farzulla / Dissensus AI, author of the published preprint
  and of everything at `upstream/master` (`4d21c69`).
- **Codex** — the AI agent that produced `alpha-asymmetry-corrected-branch.zip`,
  imported here as commit `5135bac`. Not reviewed at the time of import.
- **Claude** — this audit.
- **Tofig** — the contributor submitting this pull request.

Base for every comparison below: `upstream/master` = `4d21c69`
("Voice pass + README/CFF/DOI currency fixes", 21 Jul 2026).

Ground rule adopted for this branch, at Tofig's direction:

> Where the code and the paper disagree, fix the code. Any exception gets
> argued in the open and disclosed, never edited in quietly.

---

## Step 0 — Repository set up and Codex branch imported

**Originator:** Tofig (instruction), Claude (execution). **Neither a bug fix nor
a specification decision — provenance only.**

Cloned `plut777/alpha-asymmetry`, added `dissensus-ai/alpha-asymmetry` as
`upstream`, branched `fix/strategy-specification` from `upstream/master`, and
committed the Codex archive unmodified as a single labelled commit (`5135bac`)
so that every later change is separately reviewable. Nothing in that commit is
endorsed by this review.

---

## Step 0b — Audit of the Codex branch against the real history

**Originator:** Claude. **No files changed; findings only.**

### Verified: the four original bug claims

Checked against `git show 4d21c69:analysis/full_pipeline.py`.

| # | Claim | Verdict | Direction |
|---|---|---|---|
| 1 | Exit branch was dead code | **Confirmed** | Code was wrong, paper was right → fix the code ✔ |
| 2 | Strategy carried two lags, benchmarks one | **Confirmed** | Code was wrong, paper was right → fix the code ✔ |
| 3 | `compute_ai` used `pos.var()/neg.var()` | **Confirmed** | Code was wrong, paper (Eq. 5) was right → fix the code ✔ |
| 4 | Trade counter counted events, not round trips | **Confirmed as behaviour, misclassified as a bug** | Code matched the paper's own stated formula → see SD-3 |

Detail on 1: in the original loop the hold branch was guarded by
`prev_pos > 0 and not long_signal.iloc[i-1]`, but that branch was only reached
when `not long_signal.iloc[i-1]` was already true. The condition was therefore
always satisfied and `new_pos = prev_pos` was unreachable for any open
position. A position closed the moment its entry signal stopped firing.

Detail on 2: signals were read at `iloc[i-1]` inside the loop, stored at `i`,
then multiplied by `position.shift(1)`. Two lags. Benchmarks
(`simple_strategy`, `wk["mom"]`) used one.

Detail on 3: the original also returned `1.0` — not a missing value — for
`len(x) < 5` and for degenerate denominators, silently reporting a neutral
asymmetry index where the statistic was undefined.

### Verified: the "before" column is accurate

Codex hard-codes the pre-correction results as Python literals in
`analysis/full_pipeline.py` labelled "Values published in commit 4d21c69".
Every one of them checks out against `4d21c69:analysis/full_pipeline_results.json`
and `...results.txt`: return 3.6016, Sharpe 0.1489, MDD −7.9572, trades 17,
in-position weeks 25, walk-forward 2.46 % / 3 trades, and all five AI values
(0.1716, 0.9577, 0.8050, 3.4533, 1.4018). An earlier draft of this review
doubted these; the doubt was unfounded.

### Specification decisions Codex made and did not label as such

**SD-1 — The rebalancing rule was rewritten to match the code. Undisclosed.**
**Originator: Codex. Specification decision, presented as nothing at all.**

- `4d21c69:paper/alpha-asymmetry.tex:313` — `Rebalancing: Weekly (end of Friday close)`
- Codex `paper/alpha-asymmetry.tex:316` — `Rebalancing: none within an episode; changes occur only on entry, reversal, conflict, or expiry`

This change appears in no changelog entry and in no PR text. It is the failure
mode this correction exists to fix: the manuscript was edited so the paper
would agree with the code.

Compounding it, the original code *also* resized weekly in effect. Position size
was recomputed from the contemporaneous `ai_20w` on every bar where the entry
signal fired, and — because of bug 1 — those were the only bars on which a
position was held. Published paper and published code therefore **agreed** on
weekly resizing. Codex departed from both.

**SD-2 — Position size frozen at entry.**
**Originator: Codex. Listed as "confirmed implementation bug" #4; it is not a bug.**

Equation 10 is unchanged from the published version in its essentials and still
reads `1 + |AI_t - 1.0|` "where `AI_t` is the contemporaneous asymmetry index".
Codex appended "Size is fixed at entry and is not reset or resized by
subsequent same-direction signals" to the same paragraph, so the branch now
contradicts itself within four sentences.

Note that fixing bug 1 creates a question the original specification never had
to answer: what size applies during a *held* week in which no signal fires?
The original code never reached that state. Both answers are extensions of the
published rule; weekly resizing is the smaller one, because it preserves the
paper's stated words.

**SD-3 — "Trades" redefined as holding episodes and execution legs.**
**Originator: Codex. Listed as "confirmed implementation bug" #5; it is not a bug.**

The published paper defined its own metric explicitly: "Trades = completed
round trips (position-change events divided by two, a sign flip counting as one
event)". The code implemented exactly that. Code and paper agreed. Codex
changed both.

The change is nonetheless defensible, because the published paper's *label*
disagreed with the published paper's *formula*: events ÷ 2 does not count
completed round trips when a sign flip is treated as one event. This is an
internal inconsistency in the paper, and resolving it is worthwhile — but it is
a decision that changes a reported column, not a bug fix.

**SD-4 — The EVT input was changed from tail alpha to weekly absolute returns.**
**Originator: Codex. Disclosed in the changelog. Substantive.**

The published paper presented the GPD fit as characterising the tail-alpha
exceedance distribution — the strategy's own premise. The code fits absolute
Friday-to-Friday returns. Codex relabelled the section and table rather than
changing the code. Under the ground rule the code should have been changed.
Deferred (see backlog); the disclosure is honest in the meantime.

### Paper-follows-code changes that are disclosed and, in this review's
### judgement, correct — but that are exceptions to the ground rule

**EX-1 — Fast alpha equation.** Published: `(P_t − P_{t−5}) / (σ_20 √5)`.
Codex: `(P_t/P_{t−5} − 1) / (σ_20 √5)`. The published formula divides a yen
price difference by a volatility estimated from dimensionless returns, which is
dimensionally incoherent; the code's percentage return is the only reading that
makes the signal a z-score. Recommendation: keep the paper edit, argue it
explicitly rather than listing it as a mere difference.

**EX-2 — Hedge alpha equation.** Published: `ρ_t × Δr_t` with prose already
admitting the pipeline substitutes a constant −2 %. Codex moved the constant
into the equation. Fixing the code would require an interest-rate series the
repository does not contain. Recommendation: keep, disclose as data-limited.

**EX-3 — Monday-open execution.** Published: "Entry: Monday open following
Friday signal generation". Codex replaced it with a Friday-close proxy and
added the assertion that "Monday opening prices are not present in the
dataset."

**That assertion appears to be false.** `analysis/data_access.py` downloads
daily bars via `yf.download(..., interval="1d")`, which returns Open, High,
Low, Close and Volume; `_normalise_download` preserves every column. Monday's
open is in the data. Verification pending against a live download. If it is
present, the paper is asserting a data limitation that does not exist, and the
honest options are to implement Monday-open execution or to state plainly that
the Friday-close proxy is a *choice*. Flagged, not yet acted on.

**EX-4 — Position size range.** Published: `max(0.5, min(2.0, 1 + |AI−1|))`
with "No leverage; positions bounded to [0.5, 2.0]". The 0.5 floor is
unreachable because the inner expression is never below 1. Codex removed the
floor and stated the real [1, 2] range and its leverage implication. This
corrects a mathematical impossibility in the published paper. Correct and
disclosed.

**EX-5 — Tail alpha window wording.** Published: "rolling 52-week 95th
percentile"; Codex: "trailing 252 trading days" with a 60-observation warm-up.
Equivalent horizon, and `sgn(r)·|r| ≡ r`. Cosmetic. Not previously listed.

### Other findings

**F-1 — Provenance footnotes were deleted.** `4d21c69` recorded its own earlier
corrections inside table notes: the tail-skew 5.05 unsigned-magnitude error
(Table 1), benchmark rows that "traced to no committed code" (Table 3), "141
pooled trades" that could not be reproduced (Table 5), a "marginally
significant intercept of 21 bps" (Table 8), and `RC = 2.14 (p = 0.042)`
(Table 11). Codex rewrote those notes and dropped all of them except the GPD
one. In a paper whose contribution is a documented correction history, deleting
the correction history is a real loss. Recommend restoring.

**F-2 — Sharpe ratios are diluted, not risk-adjusted.** `_performance` divides
by the standard deviation of all 504 weeks, 449 of which are exactly zero
because the strategy is flat. −0.173 is a full-sample number, not the Sharpe of
the bets. Inherited from Murad's original; not introduced by Codex; not changed
here. Worth knowing before defending the figure.

**F-3 — `p = 0.037` would not survive the paper's own multiple-testing
discipline.** The manuscript applies Bonferroni at family size 5 elsewhere. The
full-sample momentum loading is marginal by comparison; the in-position
estimate (t = −3.53) is the one that carries weight.

---

## Backlog — out of scope for this pull request

Recorded so they are not lost. None of these are actioned here.

1. Fit the EVT section to tail alpha as the published paper claimed (SD-4).
2. Decide Monday-open versus Friday-close execution on the merits, once the
   presence of the Open column is confirmed (EX-3).
3. Source a dated EUR–JPY rate or forward series so hedge alpha stops being a
   constant multiplied by a correlation (EX-2).
4. Report the Sharpe ratio of exposed weeks alongside the full-sample figure
   (F-2).
5. Add financing/carry to the cost model, now that exposure reaches two
   notional units across 55 weeks.
