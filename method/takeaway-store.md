# Takeaway store — lessons as rows, triggers as data, firings as eval data

**Trigger:** read when mining takeaways (`/mine-session`), designing a takeaway's
trigger, wiring the store into a fork, or building anything on the firings data. The
operative artifacts: the Monition store — a single cross-repo **hub** at the landing
zone (`$CMS_LANDING_ZONE/monition`, joined via `monition instrument`; a standalone
fork with no hub gets its own local SQLite store instead) — and the installed
Monition module (the `monition` CLI + its `fire-hook` / `session-brief` disclosure
executors), wired through `.claude/settings.json` with guarded fail-open commands.

## The design in one paragraph

A takeaway is a mined lesson stored as a row, and **its trigger is part of the row**:
`trigger_kind` (edit_path | session_start | on_demand) + `trigger_spec` (the glob or
keywords) say *when this lesson should reach a session*. The disclosure machinery is
deliberately dumb — executors that run whatever the rows specify — so improving
*what fires when* means editing data, not code. Every disclosure is logged to
`firings` with its context, and firings can be rated (`helpful` / `noise`), so both
halves of the open question — was the trigger right? was the payload worth its
cost? — accumulate eval data instead of opinions. That data is the substrate the
EV-scored firing engine (`monition score`) trains and evaluates against.

## Schema semantics

**`takeaways`** — `kind` (gotcha/rule/preference) · `scope` (human-facing tags) ·
`trigger_kind` + `trigger_spec` (comma-separated globs for edit_path; empty for
session_start; for on_demand, `trigger_spec` keywords are a human-facing hint — **matching
is semantic, not keyword**, see below) · `one_liner` (what gets injected — write it as a
trap-warning, **and** it is the embedding match text, see below) · `full_content` (the why
+ workaround; loaded only on demand — progressive disclosure) · `source` (origin
session/commit) · `violation_signature` (optional JSON probe,
`{"kind": "transcript_regex", "pattern": …}` — matched against extracted transcript
text by the recall sweep to catch the row's failure happening *without* the row
firing; see §Rating. Most rows won't have one, by design) · two orthogonal
axes (one column per meaning — a status that encodes two things turns
bookkeeping transitions into accidental kill switches):

- `status` — *whether* a row fires. `active` fires; `retired` is kept for
  history, never fires.
- `reach` + `origin_repo` — *where* it fires, independent of whether it fires.
  The store is a single hub shared across repos: `project` (the default) fires
  only where `origin_repo` matches the current repo; `general` fires in any repo.

**`firings`** — one row per disclosure: takeaway, time, session, trigger kind, what
matched (`trigger_context`), and a nullable `outcome` rated after the fact.
`fire_count` / `last_fired` are queries, never columns (single source).

## Disclosure rules

- **Once per takeaway per session**, deduped from the firings table itself (not a
  marker file) — so suppression behavior is part of the evaluable record.
- **Fail open, never block** — same contract as every tier-2 hook.
- **One-liners fire; full content is pulled** (`monition show <id>`). The injection
  always names the firing id so rating costs one short command.

## Mining (the write path)

Two entry points, one gate:

- **`/mine-session`** — end-of-session review pass; proposes rows, consent gate,
  inserts, then `monition commit`.
- **Mid-session** — when `/codify` lands something whose natural home is a trigger
  (not an always-on line or a doc rule), insert it as a takeaway instead.

Both entry points route candidates the same way — row vs. governance edit is
decided by the tests in `method/lesson-routing.md`, not here.

Designing the trigger is the craft step: ask "in what session would this lesson
have saved me?" and describe *that session's* footprint — not the broadest match
that contains it.

- **edit_path** — `trigger_spec` is comma-separated Python `fnmatch` patterns (not
  shell globs): `*` crosses `/` (so `method/*` already matches nested paths and `**`
  adds nothing), case-sensitive on Linux.
- **on_demand** — matching is **two-layer**. First **lexical**: each comma-separated
  `trigger_spec` keyword is substring-matched against the prompt, and a keyword hit
  fires directly — keywords are a real, deterministic match mechanism (and lexical
  hits are never dropped by the per-prompt cap), so choose them as words a triggering
  prompt would actually contain. Rows the lexical layer misses go to the **semantic**
  layer: `one_liner + trigger_spec` is embedded (fastembed) and cosine-matched
  against the prompt, thresholded and capped to the top few per prompt. So the craft
  is in **both fields**. The `one_liner` does double duty — the injected trap-warning
  *and* the match vector. Write it **embedding-dense**: front-load the *situation's*
  vocabulary (the nouns/verbs a triggering prompt would use), not just a tidy summary. A
  one-liner that reads well but omits the situation's words won't embed near the prompts
  that should retrieve it. State the trap in the prompt-writer's language, then the fix.

## Rating (the eval path)

Firings carry an `outcome` (`helpful` / `noise`); rated firings are the eval substrate
the fire/suppress gate trains against. Rating does **not** happen at fire time — the
`rate:` hint rides in every injection yet collects ~none, because a session mid-task
won't stop to grade an injection. So rating is a deliberate pass at the **front of
`/mine-session`** (step 0), run warm with the session still in context: **LLM-auto,
evidence-gated, bulk-confirmed.**

- **Evidence-gated, not coverage-gated.** Rate a firing only where *this session*
  evidences the injection mattered — it changed an action, was visibly ignored, or was
  contradicted — and cite that evidence in one line. Irrelevance is itself evidence:
  a fire on a context it doesn't apply to is `noise` regardless of trigger breadth,
  because the dilution is the cost (batch dumps may be noise-rated in bulk with one
  shared citation). **No evidence → no rating.** Padding
  to hit coverage puts directional bias in the eval set, which is worse than a label
  missing at random — sparse honest labels beat dense dutiful ones. A cold mine (an
  architect mining workers it didn't live through) evidences little and rates ~nothing.
- **Head, not tail.** Spend a bounded budget on the highest-value firings first:
  `export-firings --unrated-only --session <id> --order-by priority` orders by
  `rating_priority` (traffic × distance-to-fire/suppress-boundary; cold-start rows rank
  high). The boundary math lives in the store machinery (the substrate); the pass only
  consumes the order. Skip the long tail.
- **Bulk-confirm, lighter gate than rows.** Proposed ratings are presented as one batch
  for a single user accept with per-line veto — a rating is reversible eval data, not
  durable governance, so it earns a cheaper gate than a row (`write-path.md`).

Ratings are **precision-only** signal: they grade what fired, and nothing fires on a
missed trigger. The recall side is the **violation sweep** — a row may carry a
`violation_signature` (a transcript regex probing the *failure event itself*, never the
topic: one-liners discuss failures, so a topic-shaped pattern self-matches), and
`monition eval-session --transcript <path>` classifies each signature-bearing row
against the session: fired∧avoided, fired∧hit, or **not-fired∧hit**. Only the third
persists (a `violations` row, idempotent per row×session) — it is the
trigger-broadening evidence ratings structurally cannot produce, since nothing fired to
rate. The sweep runs inside the mining pass (step 0c), fail-open; widening a
`trigger_spec` off a violation stays a consented row edit. Author signatures
under-matching: a missed event costs nothing (the row stays precision-only), a false
one pollutes the signal.

Periodically (audit cadence): rows with many `noise` ratings get a narrower
`trigger_spec` or retirement; rows that never fire get their spec widened or fold into a
doc. `monition report` computes this read per row (fires / helpful / noise / precision)
and `/housekeep` surfaces the clear candidates on its sweep; the rating pass is what
feeds both. Acting on a candidate stays a consented row mutation (`monition retire`,
`monition set-trigger`, `monition calibrate --apply`).

## Dolt mechanics

The store is its own Dolt repository at the hub (the landing zone, `MONITION_STORE`),
not inside this git repo; the working repo gitignores all of `monition/` (`.dolt/`,
`store.db`, `dump.sql`) and the store stays local and unpublished. Snapshot it after
mining with `monition commit` — that native Dolt commit is the version control; use
`dolt log` / `dolt diff` inside the store for data history. Ad-hoc `rate` /
`log-recurrence` during a session leave uncommitted store state too — fold them into
the next `monition commit` (snapshot ratings on their own first if you want them in a
separate store commit). `dump.sql` is a derived backup snapshot (never hand-edit); where
the landing zone is a private repo it may be tracked *there* for offsite backup, not
carried into this repo. Fresh store from a dump: `dolt init && dolt sql < dump.sql`. The `dolt` binary lives on PATH
(`~/.local/bin/dolt`); everything fails open when it's absent.

## Wiring (downstream)

A store is created with `monition init` (Monition is a declared prerequisite). The
block format is defined in Monition's store contract (cite, never duplicate).
