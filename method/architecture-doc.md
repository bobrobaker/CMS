# Architecture doc — evergreen current-state at the module/seam altitude

**Trigger:** read when a repo's module decomposition outgrows what the always-on
`CLAUDE.md` Map can carry — multiple modules, especially with a cross-repo ownership
seam — and a session keeps re-deriving "who owns what, and where the boundary is."
Also read before authoring or reviewing such a doc, or when its references start
going stale. Operative artifact: `starter/architecture.md.template`.

## The gap this closes

`CLAUDE.md` Map is the ~10-line always-on orientation — paid for every session, so it
stays a flat surface list. The roadmap is forward-looking; `docs/decisions/` and specs
are dated history. None of them answers, at a glance, *the current shape*: which module
owns which responsibility, and exactly where one module's ownership ends and another
repo's begins. A session that needs that re-reads the tree and re-infers the seams every
time. The architecture doc is the one place that current decomposition lives — evergreen,
not historical.

This is **one doctype, two homes** (see [Two homes](#two-homes)): the convention is what
a fork adopts; where the doc physically lives is the fork's call.

## Altitude — modules and seams, never file:line

The unit is a **module** and a **seam**, not a line of code. Each entry says *module M
owns responsibility X*; each seam says *the boundary between M and N (or between this repo
and repo R) is at anchor A*. State ownership and boundaries; do not narrate
implementation.

- **Too coarse** (useless): "the backend handles requests." No module, no owner, no seam.
- **Right altitude:** "`api/` owns HTTP routing and request validation; it hands
  validated commands to `core/` across the boundary at `core/commands.py:Command`."
- **Too fine** (drifts): "`api/handlers.py` line 212 calls `Command.validate()` then
  branches on `cmd.kind == 'order'`." That's a call trace, not architecture; it rots on
  the next refactor and the freshness check (below) can't keep it honest.

The altitude rule and the freshness invariant reinforce each other: a reference coarse
enough to survive ordinary refactoring is also one a mechanical check can verify. File:line
fails both — so it is out of bounds.

## Section template

An architecture doc carries these sections. Omit one only when the repo genuinely has
nothing for it (a single-module repo has no Seams section — and probably needs no arch
doc at all).

1. **Modules and ownership** — one entry per module: its name (as a path anchor), the
   responsibility it owns, and a pointer to its deeper docs if any. One responsibility per
   module is the goal; if an entry needs "and also," that is a seam waiting to be named.
2. **Seams** — one entry per boundary that matters: the two sides, the direction of
   dependence, and the **anchor** where the contract lives (a `file:symbol`, see
   [Reference syntax](#reference-syntax)). A cross-repo seam names the other repo
   explicitly: "this repo's `X` consumes `R:path:symbol`, owned by repo `R`." This is the
   altitude invariant's payload — the doc exists to make seams legible.
3. **Pointers / index** — links out to the contracts, decisions, roadmap sections, and
   per-module docs that own the detail. This section is where "see `road.md` §2" lives.
   It indexes; it never restates (see [Index, don't duplicate](#index-dont-duplicate)).

## Reference syntax

Every claim an architecture doc makes about *where* something lives is written as a
**reference** in one of exactly three forms. This grammar is the contract the freshness
check parses, so it is precise and closed — do not invent a fourth form.

- **Path reference** — a repo-relative path to a file or directory:
  `core/commands.py` or `api/`. Resolves if the path exists. A trailing slash marks a
  directory. A path reference **contains a `/`** — a bare dotted token with no slash
  (`config.yaml`, `v1.2`) reads as prose, not a reference, and the check skips it; to
  reference a top-level file, anchor it (`road.md:## 2 Plan`) or write it under its directory.
- **Symbol reference** — a path, a colon, and a symbol name (function, class, constant,
  or section): `core/commands.py:Command` or `road.md:## 2 Plan`. Resolves if the path exists
  **and** the symbol is findable in it (a definition for code; a heading for a doc). The symbol
  after the colon is the **grep anchor** — a literal substring search, so it must be text that
  *appears verbatim* in the target. For a section that means the heading's **actual text**
  (`road.md:## 2 Plan`), not a `§N` shorthand the heading doesn't literally contain. (Substring,
  not symbol-resolution, is deliberate — it stays zero-dep and language-agnostic; the tradeoff is
  that `:Command` also matches inside `Commander`, an accepted limit of grep-anchor freshness.)
- **Cross-repo reference** — a repo handle, a colon, then a path or symbol reference:
  `shared-types:schema/order.ts` or `shared-types:schema/order.ts:Order`. The handle
  before the first colon names another repo in the fleet. A cross-repo reference resolves
  only when that repo is reachable; when it is not, the freshness check **self-gates to
  silence** (it cannot verify what it cannot see) rather than reporting a false miss.
  *Reachable* concretely means **a sibling directory named by the handle**, alongside this
  repo — the same fleet layout the rest of the machinery assumes.

Rules that keep references checkable:

- Write every reference as a **code span** (backticks). Prose path names are invisible to
  the check and read as broken links to a linter.
- The grep anchor must be **literal** — the exact identifier or heading text as it appears
  in the target, not a paraphrase. "the validate method" is not an anchor; `:validate` is.
- Prefer the **coarsest reference that still locates the thing.** A path beats a symbol
  when the whole file is the unit; a symbol beats a line because lines are not a reference
  form at all.

## Freshness — the named invariant

**Invariant `FRESH`:** every reference in an architecture doc resolves against the current
tree (per the reference syntax above), or the doc is non-conformant. An architecture doc
is *evergreen-current* only if a passing freshness check backs the claim; an "evergreen"
label backed by nothing but good intentions is exactly the anti-goal this convention
exists to prevent.

The **mechanical check** (`check_architecture_freshness`, in the managed linter) enforces
`FRESH` — it parses the three reference forms defined above, resolves each, and reports
unresolved references; cross-repo references self-gate to silence when the other repo is
unreachable. This doc defines *what checkable means*; the check *enforces it*. Until that
check passes on a doc, the doc may not claim to be evergreen.

**How the check finds a conforming doc.** A doc opts into this doctype with the frontmatter
marker `doctype: architecture` — *that* is what the freshness check keys on (not a filename),
so the convention works in both homes: a standalone `architecture.md` and an in-place
`docs/DESIGN.md` both carry the marker. A doc without the marker is invisible to the check
(self-gated to silence), so adoption is opt-in per doc. A leading-slash token (a `/slash-command`
or an absolute path) is not a repo-relative reference: a slash-command is skipped; an absolute
path is flagged (references are repo-relative).

**When the check flags a reference — fix, don't reword to green.** If a flagged path is a real
in-tree reference that *drifted*, fix the path. Reword the span to prose (drop the backticks)
**only** when it's a category-error — the path genuinely isn't in this repo's tree (a fork file,
another repo, a retired thing), so it was never a valid reference. Rewording a real reference to
silence the check hollows out the invariant. (For a mixed-content in-place doc whose non-architecture
sections legitimately name out-of-tree paths, that's expected prose — but watch for the day those
should be *structured* cross-repo references instead, which is the signal to scope the marker to a
region rather than the whole file.)

`FRESH` is about references, not prose. The check cannot know whether "`api/` owns HTTP
routing" is still *true* — only whether `api/` still exists. Keeping the ownership prose
honest is the author's job, prompted by this doc's trigger; keeping the anchors resolvable
is the check's job. The two together are what "evergreen" buys.

## Evergreen-current, not a changelog

The architecture doc states *what is true now* and nothing about how it got that way. It
has no dated entries, no "previously X, now Y," no superseded sections left in place for
history. When the architecture changes, you **overwrite** the affected entry — you do not
append.

History has its own homes: `docs/decisions/` owns the *why* of each call (dated,
immutable, `status: decided|superseded`), and specs/roadmap own planned and past work. The
architecture doc **points at** those for the story behind a seam; it never carries the
story itself. If you find yourself writing a date into an architecture doc, the content
belongs in a decision doc, and the architecture doc should reference it instead.

## Index, don't duplicate

A pointer like "see `road.md` §2" or "contract: `core/commands.py:Command`" is the
correct way to connect the architecture doc to detail it does not own. Restating that
detail — copying a schema, an interface signature, a contract clause — is a defect: the
copy drifts from the source, and now two places disagree with no signal which is right.

The test: for every fact in the architecture doc, ask *who owns this fact?* If another
doc or symbol owns it, the architecture doc holds a **reference**, not a copy. The
architecture doc owns exactly one kind of fact — the decomposition itself (which modules
exist, what each owns, where the seams are) — and indexes everything else.

## Two homes

This is the **fleet doctype** a fork adopts: it defines the altitude, the section
template, the reference syntax, and the `FRESH` invariant. It does **not** dictate the
file's location or name. A fork instantiates `starter/architecture.md.template` wherever
its current-architecture content naturally lives.

A repo that already keeps its live architecture in an existing design doc adopts the
convention **in place** — it makes that doc conform to the altitude, section template,
reference syntax, and `FRESH` invariant, rather than splitting a second file out. "Repo R
keeps its current architecture in `docs/DESIGN.md`" is then an *instance* of this
convention, not an exception to it. The doctype is the shape; the home is the fork's call.

## Wiring

Multi-module repos. A single-module repo whose decomposition fits the `CLAUDE.md` Map does
not need a separate architecture doc — the Map is its architecture doc, and that is a
conformant instance too. Ships as the conforming current-architecture doc (from
`starter/architecture.md.template`); the `FRESH` check runs in the project's pre-commit
linter alongside the other structural checks.
