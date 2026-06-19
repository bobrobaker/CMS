---
status: decided
---
# 2026-06-17 · Skills are self-contained three-layer artifacts; feedback stays text (for now)

**Decision.** A CMS skill is a **self-contained, progressively-disclosed three-layer
artifact**:
1. **`## Gotchas`** (top, after the description) — distilled *firing* lessons as
   `trigger → mitigation`, loaded every run. Earns a place only when it adds the *tell*
   that fires ahead of a mistake — never a duplicate of a body rule.
2. **Operational body** — the protocol the run follows.
3. **Feedback log** — dated provenance, consulted only when revising. A lean recent slice
   may stay in `SKILL.md` (`## Recent changes`, anti-loop context); the full log splits to
   a `feedback.md` **supporting file in the skill's own directory** once it outweighs the
   operational content.

All governance lives **inside the skill** — folded in and de-provenanced, never delegated
to an external file. This holds for CMS's shared skills and for project-specific skills in
their own repos.

**Cross-skill / external references.** The skill *directory* is the unit of
install/share/symlink (official Agent Skills model: supporting files are referenced
relatively or via `${CLAUDE_SKILL_DIR}`, both scoped to the skill's own folder — there is
no supported primitive for reaching outside it). So a skill **must not read another
skill's files or an external repo file** as a dependency — the reference dangles when the
skill is symlinked or installed elsewhere. Reference another skill by **invocation**
(`/handoff`) instead, and restate any small shared bit. This is why the prior
wrapper-delegates-to-external-directive pattern is retired (it dangled without the vault,
which is why those wrappers needed an inline fallback).

**Why.** Self-containment is what makes a skill forkable and symlink-able with no drift —
one directory, no external limbs. The three layers apply progressive disclosure *within*
the skill: always-on gotchas stay tiny, the body loads on use, the dated provenance loads
only at revision time (giving a revising session enough recent context to avoid
re-introducing fixed antipatterns).

**Worked example.** `confer` — folded the de-provenanced 66-line core protocol into the
body, distilled three gotchas, kept a 3-line `## Recent changes`, split the full
(de-provenanced) 9-entry log to `confer/feedback.md`.

**Open — may be picked up from here (caveat).** Whether/how skill feedback should
*graduate into monition* (rather than staying text) is **unresolved**. The in-session
synthesis ("monition can't serve this — it's probabilistic and probationary") was
incomplete: monition's `session_start` and `edit_path` triggers are deterministic; only
`on_demand` is fuzzy. **Interim call (this decision):** keep the text-based feedback log.
Revisit per `handoffs/deferred-actions.md` — that discussion resumes from where this
session left off, not from scratch.
