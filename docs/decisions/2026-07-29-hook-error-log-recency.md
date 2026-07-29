---
status: decided
date: 2026-07-29
---

# The hook state-log health check ages its evidence instead of counting it

## Context

The hooks fail open: rather than break a session, they swallow an error and append it to
a per-machine state log. That log is the only evidence a hook ever failed, so the deploy
doctor reads it. The check asked `grep -c` for error-shaped lines and, on any hit,
emitted `hooks are failing` with the file's mtime.

Both halves are unsound over an append-only file:

- **The count latches.** With no retention, "contains an error" answers *has anything
  ever gone wrong*, not *is anything wrong now*. One bad day makes the WARN permanent,
  with no path back to PASS by any amount of fixing.
- **The mtime lies.** The same file carries the routine per-prompt accounting lines, so
  its mtime tracks the *healthy* path. Observed on the authoring machine: mtime minutes
  old, newest actual error ~447 lines back. The stamp reads as fresh breakage.

Live state at the time of the call: 3,512 lines / 515 KB, 33 error-shaped lines, all of
them historical — schema errors resolved by a migration, plus a transient syntax error in
a dependency that no longer exists. So every deploy on that machine WARNed, while the
deploy skill's step 4 instructs the operator to treat this check as evidence hooks have
been failing silently. A check that always cries wolf is worse than an absent one: it
trains dismissal of the single signal that catches total machinery failure.

## Decision

Date the evidence at the writer, age it at the reader.

1. **The structured writer timestamps its own lines** (local ISO-8601, one space, then
   the message). One funnel covers every structured emitter.
2. **`tools/hook_error_scan.py` classifies each failure by age** — recent / historical /
   legacy — and the doctor WARNs only on recent, reporting the last *error* time, never
   the file mtime.

Four sub-calls carry the weight, each of which looked optional and is not:

**The reader imports nothing from the writer.** Ownership argues for putting the parser
in the writing package — the format is its own. Rejected: the loudest failure in scope is
that package being dead at import (this is what the historical tracebacks were), and a
checker that cannot run when its subject is broken does not check anything. Pure stdlib,
no import, works on a corpse.

**Undated lines are bracketed forward, not backward.** Raw interpreter stderr reaches the
log through the hook wiring's `2>>` redirect and cannot be timestamped at source — an
import-time traceback is written before any of the package's code runs. Since the log is
one chronological stream, an undated line can inherit an age from a neighbour. It must be
the *following* dated line, or the file mtime when none follows. Bracketing backward
looks equivalent and inverts the check: when the writer dies at import it stops emitting
dated lines, so every later traceback would inherit the last healthy timestamp, and a
total ongoing outage would age out of the window and report PASS. The bound has to lean
toward alarm, because the alarm is the point. (Caught in red-team, not in design.)

**A file with failures and no dated line at all is its own alarm state.** Lines before
the first dated line are legacy — written before the writer was dating anything — and are
reported without alarming. Extending that to a file with *zero* dated lines would wave
through the worst case: the shell redirect creates this file on its own, so a package
that has never once imported produces exactly that shape. It gets its own WARN, which
also covers version skew (new doctor, older writer) at no extra cost. The message names
both causes rather than asserting the scarier one; a single successful structured write
clears the state either way.

**Failures are counted as events, not lines.** A traceback is a header, indented frames,
and a closing exception line — three matches for one failure. The block is consumed
whole. (An early cut counted only traceback headers and silently dropped 27 of the 30
events in the real log; the mixed-run case is now a regression test.)

## Rejected

- **Soften the wording only.** Leaves the permanent WARN intact — politer noise.
- **Replace the check with a store-schema probe.** Answers a different question and is
  blind to the import-failure class, which is the severe one.
- **Split routine lines from error lines into separate files.** The interleaving is what
  makes forward-bracketing work, and one chronological stream is forensically useful.
- **A high-water mark** (persist the last-scanned byte offset; alarm on anything past
  it). Genuinely competitive — it answers the deploy-gate question directly at a third
  the code and handles the never-installed case trivially. Rejected because it makes a
  read-only doctor stateful (an unacknowledged run advances the offset and eats the
  errors), yields no absolute age in the message, and leaves the log itself as undated as
  it was — which is the underlying defect, not just its symptom at the doctor.

## Consequences

- Rotation stays size-based (5 MB) and is now also scanned in its rotated generation:
  rotation is a rename, so a process holding the old descriptor can append a *fresh*
  failure to a file whose name says history.
- The window (default 7 days) is a real dial but an arbitrary constant. It is safe only
  because of the forward bracket: an ongoing failure necessarily produces instances
  inside any window, since hooks run per prompt.
- Severity is reported but not separately gated — a handled degradation and a crashed
  process both WARN, with the wording distinguishing them. Splitting the gate is
  available later if the WARN proves too broad.
- The doctor fails loud if the scanner is missing or errors, rather than passing quietly.
