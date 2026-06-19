---
status: decided
---
# 2026-06-13 · Mirror-back: dispatch disciplines + a decisions shelf

**Decision.** Landed three generic candidates from monition's upstream-candidates
queue, through the consent gate, domain-stripped:

1. **Reconcile vocabulary against the schema before building** → `method/dispatch.md`
   and the payload dispatch skill. When executing from a roadmap/spec, check its
   informal framing against the real data model first; surface mismatches before
   writing code.
2. **Identity is the slug, not the number** → same two homes. Phases/buckets are named
   by content-slug; a bare number more than one scheme defines is ambiguous — ask.
3. **Design calls leave a record** → this `docs/decisions/` shelf, the payload
   CLAUDE.md template, and CMS's own CLAUDE.md.

**Why.** All three originated downstream (in monition) as generic disciplines, not
monition-specific. The mirror-back protocol routes such lessons upstream so the
*template* — and therefore every future generated project — inherits them, instead of
each project re-deriving them.

**Owner + channel (t9).** Canonical owner of 1 and 2 is `method/dispatch.md`; the
propagation channel to generated projects is `payload/skills/dispatch/SKILL.md`,
edited in the same change so the discipline actually reaches instantiated projects.
Candidate 3's channel is the payload CLAUDE.md template.

**Alternative weighed.** Landing 3 (the design-review convention) was nearly deferred
for its own pass — it carried the most source-specific provenance (a personal
design-review protocol path, a named cross-project store). Resolved by stripping to
the externally-meaningful core: the `docs/decisions/` shelf + a generic
"portfolio-level decision store" reference, no personal paths.

**Deferred.** The `export-firings` (P2) field-alignment + `resurrection`
count-vs-exclude question stays queued — it belongs to tier-3 (P3), which is not built
(gated on labeled-trace volume).
