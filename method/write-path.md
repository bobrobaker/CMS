# Write path — govern what enters the durable store

**Trigger:** read when adding to a project's durable corpus — recording a design
decision, codifying a rule or convention, or deciding what a session should leave
behind. The operative artifacts are the consent gate (`/codify` + the "never codify
silently" line in `CLAUDE.md`), the `docs/decisions/` shelf, and the craft-reminder
hook (`tools/craft_reminder.py`).

## The consent gate (admission control)

Nothing enters durable governance silently. A correction or convention becomes a rule
only through `/codify`: route it to the cheapest sufficient destination, show the
*exact* text and destination, name the behavior it changes, and write only after the
user accepts. Changing how future sessions behave is a human-approval action by
construction.

The asymmetry that justifies the gate: a durable governance line is paid forever and
reverts only when someone notices it; a takeaway block or a file-local gotcha is
measurable and cheap to retire. So under thin evidence, prefer the reversible
destination — `lesson-routing.md` decides *where*, the gate decides *whether*.

## The write trigger (craft reminder)

A discipline that doesn't fire at write time is invisible — agents don't re-read the
rules before every edit. The craft-reminder hook (PreToolUse on `Write|Edit`) injects
a once-per-session pointer to the craft rules whenever a session edits governed
material. Three properties are load-bearing: it fires once per session per pointer (a
repeated reminder becomes noise), never blocks, and fails open. The managed body ships a
doc-agnostic default `RULES` table (path fragment → pointer, most-specific-first) so a
bare fork's reminders fire out of the box — a more-specific surface like `docs/decisions/`
earns its own pointer. A fork overrides or adds rows in the fork-local
`craft_reminder_local.py` (merged by `key`; local wins). That file is deliberately not
a managed tool, so `--update` re-vendoring never touches it — per-project pointer text
survives an upgrade with no special-casing in the installer.

This is the write-side mirror of the read path's companion-note trigger: creating the
rule is half the job; wiring the thing that surfaces it at the edit is the other half.

## Corpus shaping — what earns durable space

Durable homes are earned bottom-up, never created preemptively. A decision file, a
rule line, a shared-vocabulary entry exists because a real session needed it, not
because the structure looked tidy. Two rules keep the corpus lean:

- **Write the smallest durable edit that captures the rule**, and keep its *why* on
  the same line, so a later reader inherits the reasoning instead of relitigating it.
- **The always-on layer is the most expensive shelf** — every line in `CLAUDE.md` is
  paid every session. A rule earns a place there only if it applies every session;
  otherwise it lands on demand (a doc rule, a row) where it stays measurable, and a
  line that stops earning its keep demotes or dies.

Design calls land as date-slug files in `docs/decisions/`: the call plus its why, one
file each. Cross-cutting calls that outlive the project graduate to the cross-project landing
zone (`landing/decisions/`). Authoring one is a **backward-looking** act, not just a
forward record: audit the existing shelf (and the roadmap) for what the new call
supersedes or contradicts, mark the superseded doc `status: superseded`, and cite the
contract section it affirms — otherwise the retired decision keeps reading as live. The
craft-reminder's `docs/decisions/` pointer fires this audit at write time.

## Evidence vs. provenance

A durable claim separates two things a later reader must keep apart:

- **Evidence** — the re-consultable backing for the claim (a source, a benchmark, a
  link with a location anchor). Cite it; don't restate it. The test: *could a reader
  re-consult this outside the project?*
- **Provenance** — the record of how the claim came to land here (a decision's why, the
  audit trail of a metabolized input). Keep it separate from the claim itself.

A durable note cites its evidence as backing and may link its provenance as origin —
never the reverse. The `docs/decisions/` shelf is the provenance side made concrete;
evidence lives wherever it stays re-consultable and is referenced, not copied.

## Wiring

- Both profiles: the consent-gate line and `/codify` ship in `CLAUDE.md` from day one;
  the `docs/decisions/` shelf is a day-one convention.
- Craft-reminder hook: wire once the corpus holds governed material worth protecting;
  CMS ships default rules in the managed body, and a fork adds per-project rows in the
  fork-local `craft_reminder_local.py` (one rule per governed surface that earns a
  distinct pointer), preserved across `--update`.
- Evidence-vs-provenance is a convention, not yet a lint check — a WARN candidate once
  a project has a citable source store and the split is mechanically detectable.
