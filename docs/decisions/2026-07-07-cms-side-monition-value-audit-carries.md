---
status: decided
---
# 2026-07-07 · CMS-side carries from the monition value-audit session

**Decision.** Two monition-decided value-audit items land in CMS-owned skills, because CMS
owns the *cadence and deployment seam* they fire in while monition owns the underlying verbs:

1. **`/housekeep` gains a value-ledger cost pass (§G3).** After the precision audit (§G2,
   `monition report`), the sweep runs `monition ledger --top 5` (read-only, advisory — it
   feeds no automated decision) and surfaces the flagged rows for a human keep / retire /
   tighten call. The ledger's `CANDIDATE` flag (`net ≥ 300 AND prec < 0.50 AND rated ≥ 3`)
   is the cost side that `monition report`'s precision read can't see. Two disciplines gate
   the reading: **batch-noise skepticism** (a row diluted mostly by broad session-opening
   batch dumps earns "leave + note", not retirement — the dilution is the batch's, not the
   row's) and a **keep-verdict → signature hook** (a KEEP despite high measured cost is a
   load-bearing claim; the step *prompts, never mandates*, authoring a targeted violation
   signature via `monition set-signature` so the claim becomes recall-monitored).

2. **`/eos` auto-captures a replay anchor (§4 Anchor).** After the commit step, a guarded
   fail-open `monition snapshot --session "$CLAUDE_CODE_SESSION_ID"` records a clean
   commit-ref → session-id join, so a later pass can causally re-grade the session's firings.
   It runs **only** when `monition` is on PATH and the repo is monition-wired, and a failure
   never blocks close-out.

**Why.** Both verbs shipped monition-side (`ledger`, `snapshot --session`) but rot unrun
without a discipline that invokes them on a cadence — the manual `snapshot` verb had exactly
one bare sanity-check anchor on disk, and a value-ledger nobody reads catches no expensive
low-value rows. CMS's `/housekeep` (weekly sweep) and `/eos` (every close-out) are the
existing cadence hooks; landing the invocations there is the CMS half of the split
(monition owns the verb, CMS owns when it fires) — the same division as the `/mine-session`
↔ `export-firings`/`rate` seam.

**Guarded, fail-open, consent-gated.** The ledger pass proposes; every row mutation stays a
consented `monition retire`/`set-trigger`/`set-signature`. The eos anchor swallows all
failure (no monition, no store, unset session id) so close-out never breaks. Neither adds a
per-repo dependency: both skip silently where monition isn't wired.

**Governs.** `.claude/skills/housekeep/SKILL.md` (§G intro + §G3); `.claude/skills/eos/SKILL.md`
(step 4); `method/takeaway-store.md` §Rating (audit-cadence paragraph, aligned to name the
ledger as the cost-side companion to `monition report`).

**Provenance.** Decided in the 2026-07-07 monition value-audit session (decisions #4 and #6,
user-consented); the underlying monition-side verbs and the two-sided retrain cert are
recorded in monition's own decision shelf. These items are B1 (`/eos` replay-anchor
auto-capture) and monition decision #4/#6 from that audit's clustered line items.
