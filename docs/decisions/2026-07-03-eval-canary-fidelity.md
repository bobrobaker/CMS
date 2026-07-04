---
status: decided
---
# 2026-07-03 · Machinery-integration eval canary — fidelity (option B)

**Decision.** Build the Phase-2 machinery-integration eval canary
(`tools/eval_canary.py`) at **fidelity option (B): declarative wiring assert +
direct behavior assert, with no live `claude -p` run.** Each of the three tasks
proves the machinery is *both* wired (settings.json / git config actually declare
it) *and* behaves (the script/CLI produces the right output on a synthetic
payload). The harness trusts Claude Code to dispatch what settings.json declares —
it does not re-test the harness's own hook dispatcher.

**Why (B), not (A) or (C).** The Phase-2 spec named "three headless `claude -p`
tasks," but two other clauses of the same spec pull against a literal reading —
the scope clause ("catches wiring/config regressions, **not** vendor-model
regressions") and the exit criterion ("a deliberately-broken wiring — an unwired
hook — is caught"). Three fidelities were on the table:

- **(A) Direct machinery calls only** — pipe a synthetic payload into
  `craft_reminder.py`, run `--doctor`, call `monition add/list`. Deterministic and
  ~free, but testing a hook *script* in isolation never reads settings.json, so it
  cannot catch an *unwired* hook. **Fails the exit criterion.**
- **(B) Hybrid — declarative wiring + direct behavior** *(chosen)*. Asserts
  settings.json / git config *declare* each hook (this is what catches unwiring),
  and that each script/CLI produces the right output on a synthetic payload.
  Deterministic, model-insensitive, cheap (~5.5s for all three), and catches the
  unwired-hook regression. Trust boundary: we assume Claude Code fires what
  settings.json declares; we don't re-test the dispatcher.
- **(C) Live `claude -p` end-to-end** — real headless sessions that actually edit
  governed material / run mine-session. Highest fidelity, but slow, token-costly
  every week, and reintroduces the model-sensitivity the scope clause exists to
  exclude. Rejected for a weekly cron; a single optional (C)-style smoke run was
  considered and deferred as unnecessary for layer-1.

The "headless `claude -p`" framing in the spec predates this reconciliation. (B)
is the cleanest correct implementation; this is a deliberate, recorded divergence
from the spec's literal wording, not a silent one.

**The three tasks, each realizing (B).**

- **`bootstrap`** — clones the repo locally into a temp dir, bootstraps it
  *hermetically* (HOME + XDG_STATE_HOME redirected into the temp dir, hub env vars
  stripped, so a run never touches the real store — verified: the live hub held at
  226 rows across a full run), then parses `bootstrap.sh --doctor`. `doctor()`
  always exits 0, so the assertion reads the `N fail` summary line and the PASS set
  (git hooks armed, store live), not the exit code.
- **`craft_reminder`** — declarative: settings.json wires `craft_reminder.py` into
  a PreToolUse Write|Edit hook. Behavioral: it injects on a governed path
  (`docs/road.md`) and stays silent on an ungoverned one (`src/app.js`). A unique
  `session_id` per run sidesteps the hook's per-session firing marker.
- **`mine_routing`** — round-trips a planted lesson through a *scratch* monition
  store (init → add → list → dump), asserting kind (`gotcha/edit_path`, from
  `list`) and reach (from the SQL dump). The plant uses **`--reach general`** — a
  non-default, collision-free token — so a "reach flag ignored → defaulted to
  project" bug is actually caught; a `project` plant would silently match the
  default and prove nothing. This tests the routing **plumbing**, not an LLM's
  routing judgment (which would be model-sensitive, out of scope).

**Debounce.** Per-task consecutive-failure counts persist in a state file
(`XDG_STATE_HOME/cms-canary/state.json`). An ALERT (exit 1) fires only on the
**second** consecutive failure — one flake is swallowed. Demonstrated live: an
unwired-hook clone yields FAIL/exit-0 on run 1, ALERT/exit-1 on run 2.

**Scope boundaries (deliberate, for a later call).**

- **No LLM judge.** Judgment-band evaluation with tolerance bands is a separate,
  later increment (DESIGN.md's Tier-3 evaluation discipline), not this layer.
- **Not in `MANAGED_TOOLS`.** A fork-by-clone gets `eval_canary.py` automatically
  (it's in the repo). `MANAGED_TOOLS` governs only `--update` drift-stamping and
  copy-mode re-vendoring; adding the canary there expands the fork drift contract,
  which is a distinct propagation decision left for a future pass.
- **"Committed baseline" = the harness itself.** The tasks assert against the
  repo's own committed machinery (settings.json, bootstrap.sh, craft_reminder.py);
  the harness plus its inline expectations is the version-controlled baseline, so
  drift is caught at review time. No separate golden-output fixture is needed.

**Schedule.** The harness is self-contained and hermetic; run it weekly. Wiring a
live cron/scheduled agent is a deploy step, not part of the build — recipe:
`0 9 * * 1 cd <repo> && python3 tools/eval_canary.py --json >> <logpath> 2>&1`
(non-zero exit = an ALERT to route to a human).

**Update (2026-07-03) — cadence landed via `/housekeep`, not a standalone cron.** The
harness gained a `--if-due DAYS` self-gate (a `last_run` timestamp in its state file), and
`/housekeep` §K calls `eval_canary.py --if-due 7` every pass — the harness self-gates to
weekly and stays silent unless a task alerts. Rationale: a standalone script needing manual
or cron invocation rots unrun; folding it into the existing daily sweep guarantees it fires
(monition t95). The cron recipe above stays valid for a fork without `/housekeep`.
