# Bucket [B05]: Architecture-doc freshness check (mechanical)

Parent: ../workstream.md
State: done
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
- [ ] Wire into the lint run in **both** standalone units (they don't import each other), per the documented "edit both together" convention: add to `lint_skeleton.py`'s `SHARED_CHECKS` (so forks receive it) **and** `cms_lint.py`'s `CHECKS` (so CMS's own pre-commit gate fires it — B06's dogfood gates through `cms_lint.py`). Wiring only one leaves either forks without the check or B06 unable to gate.

## Required touchpoints

- `method/architecture-doc.md  §section template, §reference syntax`
  B04's output — defines what a reference is. **Hard dependency: B04 must be done.**
- `tools/lint_skeleton.py  grep -n "check_relative_links"  path-resolution pattern`
  Reuse path/symbol resolution; do not reinvent. Reuse the **vendored** copy here, not
  `cms_lint.py`'s: this check is part of the managed vendored set and must run zero-dep
  standalone in a fork.
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
- [2026-06-20] Built `check_architecture_freshness` in `lint_skeleton` (+ mirrored `cms_lint`),
  wired into BOTH `SHARED_CHECKS` (forks) and `cms_lint.CHECKS` (CMS's own gate, for B06 dogfood).
  Identification: a conforming doc carries frontmatter `doctype: architecture` (added to
  `starter/architecture.md.template`; documented in `method/architecture-doc.md`) — works for
  both homes (standalone arch.md / in-place DESIGN.md), self-gates when absent. Parses the three
  reference forms; cross-repo resolves to a sibling dir by handle and self-gates when unreachable.
- **ERROR vs WARN — decided ERROR** (the done-criterion to record). Rationale: the check fires
  only on a doc that *opted in* (the marker is deliberate), and an unresolved repo-relative path
  is unambiguously stale → it fits the skeleton's "mechanical → ERROR" rule, same tier as
  `check_relative_links`/`check_decision_status`. The brand-new-convention risk that argued for
  WARN-first was a *false-positive* risk; with that surface closed (see below) ERROR is safe.
- [2026-06-20] **Confer with brain2 + 2 code-review finders.** Fixes built + re-validated:
  - **False-positive heuristic (was the blocker under ERROR):** a bare dotted-slashless code span
    (`config.yaml`, `v1.2`, `e.g.`, `.cms-version`) was parsed as a path reference and ERRORed. Now
    a bare path reference must contain `/`; top-level files are referenced with an anchor or under a
    dir. Narrows B04's path-reference form — documented in `method/architecture-doc.md`.
  - **Path containment:** `os.path.join(base, "/abs")` silently dropped `base` (`/etc/passwd`
    false-PASS; repo-root-relative `/tools/x` false-ERROR), and `..` escaped ROOT. Now rejects
    absolute paths and asserts the resolved target stays under `base`.
  - **CRLF frontmatter:** `_FM_RE` opening `^---\n` missed `\r\n`, silently self-gating an opted-in
    Windows-authored doc (also affected decision docs). Hardened to `\r?\n` in both linters.
  - **C parks (known choices):** the cms_lint↔lint_skeleton arch mirror is now ~6 symbols under the
    unenforced "edit both together" rule — a CMS-only meta-test asserting mirror parity on a fixture
    corpus would make divergence loud without breaking fork zero-dep (deferred; shared module stays
    rejected per `2026-...` DESIGN call). Windows drive-letter paths (`C:/...`) misparse as
    cross-repo (Unix fleet — accepted). Symbol resolution is literal substring (grep-anchor) by
    B04 design, not symbol-definition parsing — a known, documented looseness.
