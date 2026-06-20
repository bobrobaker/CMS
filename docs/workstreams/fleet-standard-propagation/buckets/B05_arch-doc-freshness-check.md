# Bucket [B05]: Architecture-doc freshness check (mechanical)

Parent: ../workstream.md
State: later
Goal for session: A check that the arch doc's referenced paths/symbols still resolve.
Target duration: 20 min
Context budget: Read parent + this bucket + required touchpoints only.

## Conceptual mapping

- The mechanism that makes "evergreen" real: parse the arch doc's references and verify they
  resolve against the live tree. A check in the vendored lint unit — same surface as B02, new
  function. Consumes B04's section template.

## Data contract / provenance

- Inputs: the arch doc's referenced **paths** and **symbols** (the doctype's reference syntax,
  defined in B04). Read `method/architecture-doc.md` (B04 output) for what a "reference" is.
- Outputs: an ERROR/WARN when a referenced path or symbol does not resolve.
- Provenance: the check reads references from the conforming arch doc only — no broad scan.

## Tasks

- [ ] Parse references from a conforming arch doc (paths, and `file:symbol` / grep-able anchors per B04's syntax).
- [ ] Verify each: path exists; symbol/anchor is findable in that path.
- [ ] Emit on failure; self-gate when no arch doc exists in the repo (bare repo → silent).
- [ ] Wire into the lint run.

## Required touchpoints

- `method/architecture-doc.md  §section template, §reference syntax`
  B04's output — defines what a reference is. **Hard dependency: B04 must be done.**
- `tools/cms_lint.py  grep -n "check_relative_links"  path-resolution pattern`
  Reuse path/symbol resolution; do not reinvent.
- `B04_arch-doc-convention.md  grep "## Updates", then read from that offset`
  Handoff: the exact reference syntax B04 settled on.

## Design direction

- **Self-gate (cross-bucket invariant):** no conforming arch doc present → emit nothing. The
  check only fires where the convention is adopted.
- Decide ERROR vs WARN deliberately: an unresolved path is a real staleness signal — ERROR is
  defensible (it's the whole point of "evergreen with teeth"), but match the repo's existing
  tier conventions; if forks adopt gradually, WARN-first may be the safer rollout. Record the
  choice and rationale in `Updates`.
- Symbol resolution is a `grep`-findability check, not a parser — keep it cheap and zero-dep.
- Part of the managed vendored set (propagates via B01).

## Validation

- Arch doc with all references resolving → check passes.
- Break one referenced path → check fails (the named path is reported).
- Repo with no arch doc → check silent.

## Done criteria

- [ ] Tasks complete.
- [ ] Validation passes (all three cases).
- [ ] Bucket `Updates` records the ERROR-vs-WARN choice + rationale.
- [ ] Parent workstream progress updated.

## Updates

- [2026-06-19 14:30] Created. Handoff: none yet. Gotchas: none yet.
