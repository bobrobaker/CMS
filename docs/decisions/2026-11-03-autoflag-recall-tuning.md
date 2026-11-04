---
status: decided
---

# 2026-11-03 · Autoflag recall tuning after the t495 checkpoint

**Context.** The 2026-07-31 autoflag repair froze recall tuning (Item-5 regex additions,
threshold moves) until the lexical corpus showed its feedback loop working, tracked by
checkpoint row t495. The trigger was met (corpus entries with `helpful > 0`), and a
2026-09-09 replay over 213 sessions / 2056 turns re-measured the backstop: regex floor
precision 46–62%, lexical 53–65%, combined recall ≈48% (an upper bound). Full report in the
landing zone's archive, "2026-09-09 night eval — autoflag backstop recall re-measurement (t495)".

**Decisions.**
1. **Adopt the Item-5 regex subset** in `tools/autoflag.py` `PATTERNS`: `I mis-scoped`,
   `my reasoning was backwards`, `I need to correct something I told you`, `the problem is
   mine` (with a lookahead so it doesn't match "mine-session"). Measured +2 genuine fires,
   0 new noisy turns. The evidence is thin (both new catches came from one meta session),
   but the downside measured zero and recall is the bottleneck. Tests: `tools/test_autoflag.py`
   T-item5.
2. **Keep the lexical threshold at 0.4.** Raising it to 0.45 would drop 5 of 6 false
   positives but lose 2 genuine catches. For a backstop the costly error is a miss — a false
   flag costs one discard at mine time — so precision isn't worth recall at ≈48%.
3. **Demerit the five lexical entries that produced clear false positives** (each matched a
   fragment, an opposite claim, or a quoted row), including one previously credited entry.
   Corpus state is machine-local (`~/.claude/flag-corpus.json`).
4. **Retire t495.**

**Revisit when** a fresh replay is cheap and the corpus has grown materially past its
2026-11-03 size (~350 entries); re-measure recall before any threshold move.
