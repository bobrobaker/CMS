# Bucket [B04]: Evergreen architecture-doc convention (fleet doctype)

Parent: ../workstream.md
State: done
Goal for session: Define the fleet-wide current-architecture doctype (method + starter).
Target duration: 30 min
Context budget: Read parent + this bucket + required touchpoints only.

## Conceptual mapping

- Convention *design*, not code: one `method/` doc stating the doctype's trigger, altitude,
  section template, and index-don't-duplicate rule, plus a `starter/` template forks instantiate.
  Different mental model from the propagation buckets — keep separate.

## Tasks

- [ ] Write `method/architecture-doc.md`: the trigger (when a repo needs a current-architecture doc), the **coarse module/seam altitude** rule, the section template, and the "index, don't duplicate" rule (pointers like "see road.md §2" are valid; never restate a contract).
- [ ] Add a `starter/` template (e.g. `starter/architecture.md.template`) with `{{PLACEHOLDERS}}` per the starter convention.
- [ ] State the freshness requirement as a named invariant the doctype carries (the check is built in B05) — an arch doc claiming evergreen without a passing freshness check is non-conformant.
- [ ] Wire the new doctype into the bucket-generator's contract-doc / doctype awareness only if needed (conditional).

## Required touchpoints

- `method/  grep -rln "trigger"  one existing method doc`
  Match the "one doc per discipline, each stating its trigger" shape and altitude.
- `starter/CLAUDE.md.template  (full)`
  The `{{PLACEHOLDER}}` template convention to mirror.
- `docs/DESIGN.md  §"Current architecture"`
  The reference instance the convention must fit (CMS dogfoods it in B06) — read for shape, do not edit here.

## Do-not-read / avoid

- `docs/DESIGN.md §Roadmap`
  Already settled; the design call is decided. Do not relitigate altitude/shape here — implement it.

## Design direction

- **Altitude must express seams**, not a flat module list: "module owns X; boundary to repo Y
  is here." A consumer's decomposition can be N modules in M clusters with cross-repo ownership
  seams — the template must land on that without forcing a misshape.
- **Track a moving target without becoming a changelog** — evergreen-current, not append-only
  history. The dated decision/spec/charter layer owns history; this doctype points at it.
- **Two distinct homes (cross-bucket invariant):** this is the fleet doctype forks adopt; CMS's
  own current-architecture stays in `DESIGN.md`. Write the convention so "CMS uses DESIGN.md" is
  an instance of the convention, not an exception that forces everyone onto DESIGN.md.
- **No "evergreen" without B05.** State the freshness invariant here; the mechanism is B05. The
  convention is not complete until B05 lands (cross-bucket invariant).
- Behavior-changing method/starter additions go through the consent gate per repo rules — these
  files are the teaching surface; write for an external reader, no provenance.

## Validation

- `tools/cms_lint.py` passes on the new `method/` doc and `starter/` template (provenance +
  structure clean).
- The doctype, applied on paper to a non-trivial multi-module decomposition with a cross-repo
  ownership seam, expresses the seam without restating contracts — sanity-check before B06.

## Done criteria

- [ ] Tasks complete.
- [ ] Validation passes.
- [ ] Bucket `Updates` records discoveries/gotchas/handoff (esp. the section template, for B05).
- [ ] Parent workstream progress updated.

## Updates

- [2026-06-19 14:30] Created. Handoff: none yet. Gotchas: none yet.
