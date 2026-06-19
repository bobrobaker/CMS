---
status: decided
---
# 2026-06-14 · Tech-debt shelf — where to drain, and the relevance gate

**Decision.** The shelf has **three drain/remind triggers, three jobs** — not one
boundary doing everything:

| Trigger | Act | Scope |
|---|---|---|
| Start of chunk (`/dispatch` execute) | **Execute** — fold in | *Relevant* items only (path-intersection) |
| Session wrap-up | **Remind** — health signal | Count/staleness, no execution |
| Saturation / scheduled | **Bulk drain** — dedicated sweep | The long tail, by safety |

**Built this pass:** trigger #1, the **debt relevance gate**. Between reading a bucket's
required touchpoints and report-first, grep `docs/debt.md` for those same paths; surface
hits with a **fold-in / sibling-bucket / leave-parked** call (fold in only within the
bucket's budget). It is the capture trigger's mirror — capture parks debt while the
function is open; the gate spends it when the function reopens. The check is a plain
`grep -F` of paths the agent already holds — deterministic, no LLM judgment.

**Deferred (recorded, not built):** the wrap-up *reminder* and the saturation *sweep*.
The autonomous-triage sweep remains a documented discipline in `dispatch.md` whose
firing artifact is stood up on demand ("when a backlog saturates").

**Why.** Draining is cheapest where the code is already open — the same logic that put
*capture* at the chunk boundary. So *execution* belongs at chunk-start, not wrap-up:
wrap-up draining drains by **recency** (what you touched this session), the weaker
signal, where the gate drains by **relevance** (the files you're about to reopen); and
executing at wrap-up fights the end-cleanly intent and risks leaving half-done work,
violating "maximize completed reversible work, surface only the judgment."

**Alternatives weighed.**
- *Wrap-up as the execution trigger* (the prior reference approach) — rejected as a
  *drain*; demoted to a *reminder*. Wrap-up is the right place to flag shelf size/
  staleness so it doesn't rot, the wrong place to start fixes.
- *Whole-shelf surfacing at chunk-start* — rejected: yak-shaves a feature into a cleanup
  marathon. Mitigated by relevance-gating (only items touching this bucket's files) plus
  the budget gate (fold in only if it fits the bucket's one-window budget; else a
  sibling bucket; else leave parked).
- *A `/dispatch` triage subcommand or sweep runner now* — deferred: the gate captures the
  cheap, high-frequency wins; the bulk sweep is lower-frequency and earns its own build
  when a backlog actually saturates.

**Ownership & propagation.** Canonical owner: this repo — `method/dispatch.md` holds the
discipline; the firing artifacts are `payload/prompts/workstream_bucket_generator.md`
(execution-protocol step 4a + step 5), `payload/skills/dispatch/SKILL.md` (direct-execute
path), and the `payload/CLAUDE.md.template` tech-debt block. Propagation channel:
`/instantiate` carries these to **new** full-profile projects at creation. Existing
generated projects do not auto-update (incubator property) — they pick it up only on a
manual payload refresh; not in scope here.

**Also corrected.** `payload/CLAUDE.md.template` previously said "`/dispatch` sweeps it as
a backlog" — false (no sweep mode ships). Rewritten to describe the relevance gate.

**Provenance.** This design conversation, 2026-06-14. The wrap-up-judgment pattern from a
downstream project is the reference, reframed here from *drain* to *reminder*.
