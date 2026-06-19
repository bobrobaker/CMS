# Tooling — thin skills, and the three-tier enforcement split

**Trigger:** read when adding or editing skills, hooks, or linter checks — here or in a
fork. The operative artifacts are `.claude/skills/`,
`tools/craft_reminder.py`, and `tools/lint_skeleton.py`.

## Thin skills

Skills are themselves context payloads; the biggest lever on their cost is **what
loads when**. Two moves:

1. **Keep the registered skill thin** — a trigger description (when to fire, and
   explicitly when *not* to, including disambiguation against sibling skills) plus a
   pointer to the doc holding the procedure. The body says it outright: *"the logic is
   not in this skill — it lives in a procedure doc so it can be edited and improved."*
   What the split buys: the procedure is editable mid-session and versioned with the
   corpus; the registered surface never churns; only trigger descriptions are
   always-on, so the always-on share stays near zero.
2. **Early-exit gate before the heavy load.** A skill that can be invoked on the wrong
   kind of input checks the kind *before* loading its procedure — and the check reads
   only the cheap thing (the small input), never the expensive thing it's deciding
   about. Put the gate in the thin loader, not inside the procedure (a gate inside the
   heavy doc fires after the cost is paid), and **state the saving as a number** in
   the skill text — a quantified gate is a load-bearing decision a future editor won't
   "simplify" away.

A skill registered at user level can load its procedure from a hub repo by absolute
path — one skill, one procedure doc, firable from any project.

## The enforcement split

A governed corpus has rules of two kinds, and conflating them ruins both.
**Mechanical invariants** (a link resolves, frontmatter parses) are decidable by
code — enforce them with code, hard. **Semantic fit** (is this lede a thesis? does
this doc belong here?) requires judgment — keep it in governance docs and review, and
never pretend a regex checks it. Enforce with the cheapest sufficient mechanism; three
mechanisms at three price points cover the space.

### Tier 1 — linter at commit time (blocking)

A pre-commit linter checks only mechanical invariants. **ERROR blocks; WARN advises** —
and the ERROR/WARN assignment *is* the split: a check is ERROR only if a violation is
unambiguously wrong. This is also what makes autonomous work safe: the hook path is
shared, so an unsupervised worker's bad commit never happens rather than needing
revert.

The subtle part is the **high-precision backstop**: a deliberately loose mechanical
shadow of a semantic rule, set to catch only egregious cases, always WARN (e.g. a
length cap on an opening sentence backstops "open with a one-sentence thesis"). Each
check's comment names the governance rule it shadows — the linter is *indexed to* the
semantic layer, not a replacement for it. Corollary: when a semantic rule keeps being
violated, don't force it into the linter; tighten its mechanical shadow and leave the
judgment where judgment lives.

The linter also owns **derived views**: anything computable from the corpus is
regenerated at commit time, never hand-maintained.

### Tier 2 — hook at edit time (reminding)

A PreToolUse hook fires when a write targets governed material and injects one line:
*you are editing governed material; consult these craft docs first.* Properties that
make it work: trigger → payload (path match → pointer; the harness guarantees firing,
the agent supplies the judgment); **once per session** via a marker file (a reminder
that repeats becomes noise); **never blocks, fails open** (malformed input exits
silently — enforcement strength matches confidence, and a reminder has no business
stopping work).

### Tier 3 — audit on cadence (judging)

A standing conformance pass runs the checks a linter can't: drift between summaries
and what they summarize, merge candidates, whether the always-on layer stayed lean.
It **reports and proposes; it auto-applies only the mechanical class** — the same
split, applied to the auditor's own write permissions.

## Wiring

- Both profiles get tier 1 (`tools/lint.py` + `.githooks/pre-commit`; project checks
  go in the marked slots, each with a comment naming the rule it shadows).
- Both profiles get session-end observability (`tools/session_tokens.py` wired as
  SessionEnd in `.claude/settings.json`): sums API usage counters across the session's
  transcript and subagent transcripts and appends a `tokens:` line to the global log
  (`~/.claude/logs/sessions.md`). With `--print`, reports provisional counts without
  writing — consumed by `/wrap-session` before the hook fires its final write.
- Full profile adds tier 2 (`tools/craft_reminder.py` wired in
  `.claude/settings.json`, governed paths set to the project's docs dir).
- Tier 3's orphan/staleness slice is shipped as the `/housekeep` skill (transient-store
  residue: unwrapped sessions, dead-session flags, stale handoffs/confer threads,
  abandoned worktrees). Its doc-drift / merge-candidate / always-on-leanness slice is
  still a manual "audit the docs against their own rules" prompt; codify that into a
  skill when the project runs it a third time.
