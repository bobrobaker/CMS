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
   always-on. That share is small but **budgeted**: the harness reserves a fixed fraction of
   the context window for the skill listing, and past that budget the least-used skills are
   listed by name only — their trigger text, the thing that makes them fire, silently drops.
   Keep descriptions lean for redundancy (never by cutting a sibling-disambiguating NOT
   clause), and if the installed skill set outgrows the budget, raise the budget in the
   harness settings rather than trimming triggers until they stop working.
2. **Early-exit gate before the heavy load.** A skill that can be invoked on the wrong
   kind of input checks the kind *before* loading its procedure — and the check reads
   only the cheap thing (the small input), never the expensive thing it's deciding
   about. Put the gate in the thin loader, not inside the procedure (a gate inside the
   heavy doc fires after the cost is paid), and **state the saving as a number** in
   the skill text — a quantified gate is a load-bearing decision a future editor won't
   "simplify" away.
3. **Defaults, not decrees.** A shared skill phrases its rules as defaults and checks for
   project overrides first; a project records an override in a decision doc naming the
   exact skill clauses, plus a one-line pointer in its always-loaded `CLAUDE.md` so the
   override is seen before the skill's default is followed.

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

**Propagation across forks.** The managed checks (`lint_skeleton.py` + the portable hooks)
are vendored into each fork, where `tools/lint.py` is a thin fork-local wrapper that imports
them and adds the fork's own checks via `FORK_CHECKS`. `./bootstrap.sh --update <fork>`
re-vendors the managed set and re-stamps the fork's `tools/.cms-version`. A repo-level WARN
check (`check_stamp_drift`) string-compares that stamp against the canonical
`tools/.cms-manifest` committed in the CMS clone pointed at by **`$CMS_SRC`** — so a fork
learns when its checks fell behind. Set `CMS_SRC` once as a machine-global env (in
`~/.claude/settings.json`, like `$CMS_LANDING_ZONE`); unset, the drift check self-gates to
silence (a disconnected fork — honest dormancy). Bash is the **sole hash producer** (it writes
the committed manifest); the drift check only compares strings, never recomputes — so the two
sides can't silently diverge.

### Tier 2 — hook at edit time (reminding)

A PreToolUse hook fires when a write targets governed material and injects one line:
*you are editing governed material; consult these craft docs first.* Properties that
make it work: trigger → payload (a rules table of path fragment → pointer, most
specific match wins; the harness guarantees firing, the agent supplies the judgment);
**once per session per pointer** via marker files (a reminder that repeats becomes
noise); **never blocks, fails open** (malformed input exits silently — enforcement
strength matches confidence, and a reminder has no business stopping work). Rule
sourcing and the fork-local overlay are specified in `write-path.md`.

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
  `.claude/settings.json`; project-specific rules go in `tools/craft_reminder_local.py`).
- Tier 3's orphan/staleness slice is shipped as the `/housekeep` skill (transient-store
  residue: unwrapped sessions, dead-session flags, stale handoffs/confer threads,
  abandoned worktrees, takeaway rows due for audit — noise-heavy or never-firing, read
  off `monition report`; plus global skill-farm drift — loose dirs or dangling links in
  `~/.claude/skills/`). Its doc-drift / merge-candidate / always-on-leanness slice is
  the `/audit-docs` skill, cadence-nagged monthly by `/housekeep` §M (the same
  detection-vs-resolution split: §M reports "due", the skill resolves — report and
  propose, consent-gated). Two *currency* subclasses of doc-drift now
  carry a tier-1 backstop (the tighten-the-mechanical-shadow corollary above): a decision
  doc whose top verdict is contradicted by a later `## Update` (`check_two_headed_decision`),
  and a doc line calling a feature unbuilt while its symbol/CLI verb already ships
  (`check_gated_vs_shipped`) — both WARN, both loose shadows, so the tier-3 judgment pass
  still owns the ambiguous cases.
