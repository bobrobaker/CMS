---
name: audit-docs
description: Tier-3 doc-drift audit — verify the repo's governed docs against shipped reality (summary drift, two-headed decisions, overclaims), surface merge candidates and always-on-layer bloat, propose strike-in-place corrections through the consent gate. Use when the user invokes /audit-docs, says "run the doc audit" / "audit the docs against their own rules" / "doc-currency pass", or when /housekeep §M reports one due. NOT the orphan/staleness sweep (that's /housekeep), NOT a single-artifact deep pass (that's /scrutinize), and NOT a code-quality review (that's /code-review).
---

# audit-docs

You are running the Tier-3 conformance pass from `method/tooling.md` §The enforcement
split — the checks a linter can't decide: is what each governed doc *says* still true of
what the repo *ships*, and is the corpus still well-shaped? Its charter is Tier 3's own:
**report and propose; auto-apply only the mechanical class.** A doc correction is a
judgment call (which side of a mismatch is right?), so every content edit is
consent-gated.

Read `method/tooling.md` before your first run in a session — this skill is governed by
it. Scope is the **current repo's** docs; the pass is repo-generic (canonical CMS, a
fork, any machinery repo with governed docs).

1. **Assemble the doc set.** The governed, claim-bearing surfaces — typically:
   `docs/decisions/*.md`, the roadmap (`docs/road.md`), the live-verdict registry
   (`docs/DESIGN.md` or equivalent), workstream docs, `docs/contracts/`, `docs/debt.md`,
   and the always-on layer (`CLAUDE.md`, skill `description:` lines). Skip archives and
   struck-provenance blocks — they are records, not claims.

2. **Sweep for the three drift classes**, cheapest probe first:
   - **Summary drift / overclaims.** For each load-bearing claim ("X is built", "N
     checks", "fleet is in sync", "we use Y now"), verify **structurally** against
     shipped state — the symbol, the CLI verb, the file on disk, the live store — never
     nominally (a matching name or comment is not evidence). Adjudicate a mismatch
     against the **declared authority** first (the live-verdict registry outranks an
     early draft; counts evolve — a stale draft contradicting the binding record is a
     draft fix, not a registry fix). A "default = X" decision governs *new* instances:
     an existing non-X instance is drift only if a migration was actually mandated.
   - **Two-headed decisions.** A decision doc whose headline verdict is contradicted by
     a later `## Update` or by shipped state → propose `status: superseded` (+
     `superseded_by`) or a strike-in-place UPDATE at the headline. The linter's
     `check_two_headed_decision` / `check_gated_vs_shipped` WARNs are loose shadows of
     this — treat any current WARNs as the worklist's head, then sweep past them.
   - **Merge candidates + always-on leanness.** Two docs grown to cover the same ground
     → propose the merge (which absorbs which, what redirects remain). Always-on
     surfaces (`CLAUDE.md` lines, skill descriptions) that accreted content answerable
     from an on-demand doc → propose the move; the always-on share should stay near
     zero.

3. **Corrections are strikes, never silent deletes.** A refuted claim is corrected
   in place — strikethrough + REFUTED/UPDATE + pointer to what killed it — preserving
   the provenance of what was claimed and why it fell. Don't enshrine an unvalidated
   replacement as the new headline; mark it provisional until measured.

4. **Tighten shadows, don't relitigate.** When a drift class recurs across runs,
   propose a new WARN-only mechanical backstop for it in the managed linter (the
   tighten-the-mechanical-shadow corollary) — the judgment stays here; the linter gets a
   loose tripwire. Route the proposal through the normal consent gate, and via the
   mirror-back queue if you're in a fork.

5. **Present one proposal batch**, grouped by drift class, each item naming the doc,
   the refuted claim, the evidence, and the concrete edit. The only auto-applied class
   is mechanical derived views the repo already regenerates. Apply accepted edits;
   leave declined claims standing (optionally with a dated "audited, stands" note when
   a claim keeps getting re-flagged).

6. **Stamp the run** so `/housekeep` §M can gate the cadence (keyed per repo — the
   audit is repo-scoped, the state dir is machine-global):

   ```bash
   root="$(git rev-parse --show-toplevel)" && d="${XDG_STATE_HOME:-$HOME/.local/state}/cms"
   { mkdir -p "$d" && date -Is > "$d/doc-audit.$(basename "$root").last"; } 2>/dev/null || true
   ```

Anti-goals: never auto-apply a content correction; never delete a refuted claim
(strike it); don't force a recurring semantic rule *into* the linter as ERROR — tighten
its WARN shadow and leave the judgment in this pass.
