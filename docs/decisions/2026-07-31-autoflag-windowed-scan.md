---
status: decided
---

# Autoflag scans a windowed since-last-Stop range, not the last message

## Call

`tools/autoflag.py` no longer scores only the final assistant message. Each Stop
invocation scans **all assistant text since the previous invocation's read point**,
tracked as a persisted per-session line offset (`/tmp/autoflag_scanpos_<session>.json`,
carrying a hash of the last counted line so a same-path rewrite can't smuggle a
numerically-valid offset onto different content; a torn newline-less tail line is
never counted). Invalid or missing state falls back to **current-turn-only**
(assistant lines after the last real user prompt; nothing at all if no real prompt
exists) — never the whole file. Code spans (fences + inline backticks, **never**
quote characters or apostrophes) are blanked with equal-length spaces that preserve
`.!?\n`; the cap (16k chars, newest kept) is applied **after** stripping, since a
cap cut inside a fence would orphan the closing ``` and blank all following prose.
The regex floor matches the stripped text; only the lexical layer additionally gets
the mutilation guard (skip sentences losing >40% of tokens to blanking — a
Jaccard-specific hazard, fragments score high). Matches are found in blanked text
and reported from the original, with both layers using one sentence splitter so
they converge on one dedup key per moment. The regex floor flags up to 3 per
invocation, counting **writes, not attempts** (marker-deduped no-ops must not
starve a new admission on a rescan). The lexical layer gets a 150ms wall-clock
budget scanning sentences **newest-first** (`score_text(budget_ms=…)`), and
`AUTOFLAG_DEBUG=1` logs one JSON line per invocation to
`~/.claude/logs/autoflag.log` (2MB rotation).

## Why

- **The last-message design lost a flush race by construction.** The hook fires within
  tens of ms of the final message being flushed (measured 2026-07-31: flush→hook gaps
  58ms–1.7s vs a 52–147ms hook runtime), so it routinely scored the *penultimate*
  message; expected fires replayed at 3-of-13, observed 0. Downstream, the corpus
  feedback loop never ran — 220 entries, zero ever credited. The offset makes the
  window *overlapping in effect*: text flushed after this invocation reads sits past
  the saved offset and is scanned by the next one. Retry/backoff was rejected — p90
  flush latency (~1.7s) would stall every Stop. Known residual: the session-final
  block has no next invocation and can still lose the race.
- **Equal-length blanking is what makes "match on stripped, report from original"
  free.** Offsets and sentence boundaries stay identical, so `matched_sentence()`
  needs no bookkeeping and both layers report the same original sentence — keeping
  the dedup key ("first writer wins") convergent between layers.
- **Never strip apostrophes/quotes**: admissions are contraction-heavy first-person
  prose; apostrophe-stripping destroys the target class (measured in the repair
  handoff: 4 genuine admissions killed). The mutilation guard exists because
  stripping *shrinks the Jaccard union*, which inflates scores on fragments —
  stripping without the guard manufactures false positives.
- **Offset vs stateless overlapping window** (red-team preferred the latter,
  2026-07-31): the fragility arguments against the offset (resume → unbounded
  rescan; compaction; /tmp cleanup) are all answered by the bounded
  current-turn-only fallback, and the offset gives exact delta scanning for
  arbitrarily long autonomous turns where "last K turns" and a char cap interact
  badly. Divergence recorded deliberately: if the offset state proves flaky in
  practice, the stateless capped-overlap design is the sanctioned fallback — the
  (session, snippet) dedup markers make re-scans idempotent either way.

## Consequences

Mid-turn narration is now reachable (previously invisible by construction). Fire
volume measured on real transcripts (456 turns): regex 9→11, lexical 12 — wider
reach, with code-quote false positives removed by the blanking. Recall tuning
(regex-floor additions, threshold moves) stays frozen until the corpus feedback loop
has demonstrably run — today's corpus is an artifact of the race.

A review lesson is baked into the shape above: the four precision mechanisms
(mutilation guard, flag cap, window cap, score budget) each individually traded
recall for precision, and as first drafted they **composed** against the canonical
flag-worthy turn (code-heavy, ending in an admission) — guard blanking backticked
admissions from the regex floor, cap-attempt counting starving rescans, cap-cut
fences blanking trailing prose, budget dropping newest text. Evaluate precision
knobs at their intersection on the good-outcome class, not one at a time.
