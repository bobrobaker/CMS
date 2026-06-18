# Lesson routing — where a mined lesson lands

**Trigger:** read when routing a candidate lesson during mining (`/mine-session`) or
codification (`/codify`) — after the lesson is drafted, before the consent-gate
proposal. Output: a destination plus one line of reasoning, shown at the gate.

**Version:** routing v1 (2026-06-12). This is the canonical text; monition's
mine-session skill template carries a domain-stripped copy (confer resolution,
2026-06-12). Bump this version on any change to the tests and hand off to
monition once — `monition sync` propagates from there.

Run the tests in order; the first decisive hit wins. Under uncertainty, prefer the
row (test 3): it is the only tier with an eval loop, and it retires cleanly.

1. **Behavior test.** State the lesson as "in situation S, do/avoid X." If S has no
   name yet, it is not routable — leave it in session notes; don't force a row.
2. **Owning surface.** Does an artifact already fire at S — a skill that runs then,
   a hook on that event, a prompt used for that task, a linter on that file class?
   Land the lesson inside that artifact: it is already a trigger with a payload,
   and a parallel row would duplicate its trigger with worse precision. Procedure
   changes always route here — a row can remind, but it can't restructure a skill.
   A destination with its own admission rules (caps, evidence gates, eval suites)
   keeps them — routing never bypasses the surface's own gate.
3. **Describable trigger.** No owning surface, but S compresses to an edit-path
   glob, session start, or on-demand keywords → takeaway row. This is also the
   default when evidence is thin (one occurrence, an unconfirmed hunch): rows are
   measurable and reversible; governance prose is neither. Domain-free rows get
   `--mirror candidate`.
4. **Always-on.** S is "every session" → a CLAUDE.md line, only if it earns being
   paid for every session forever; otherwise make it a session_start row, which
   stays measurable.
5. **Mechanical shadow.** If violating X is mechanically checkable and unambiguous,
   add a linter check (ERROR) or hook alongside whatever prose landed above;
   ambiguous shadows are WARN. For semantic artifacts — shipped prompts, rubrics,
   judge criteria — the project's eval suite plays the linter's role: a lesson
   landing in one must pass it before the consent gate closes.

**Re-route at audit cadence.** A row with a strong helpful record and a stable
footprint folds into its owning surface and is retired; always-on prose that stops
earning its line demotes to a row or dies. Routing is never one-shot.

Every landing — row or governance edit — goes through the consent gate, and the
proposal names which test decided.
