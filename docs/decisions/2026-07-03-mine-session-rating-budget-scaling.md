---
status: decided
---
# 2026-07-03 · Scale mine-session's rating walk budget to transcript size

**Decision.** The mine-session rating walk (`SKILL.md` step 3, "Walk the top N")
changes its budget from a fixed `~15` firings to `~15 per ~2 MB of transcript JSONL
(wc -c), minimum 15, no hard cap`. The transcript byte count is read the same way the
recall sweep reads it. The natural stops are unchanged and still govern: head-not-tail,
stop when `rating_priority` drops off or evidence runs out, skip the long tail. Bulk
noise labels remain mechanical and outside the (now scaled) budget.

**Why.** A fixed ~15 thins rating rigor on long sessions purely because volume rose,
not because the marginal firing stopped being worth rating. The governing contract in
`method/takeaway-store.md` ("Head, not tail — spend a bounded budget on the highest-value
firings first; skip the long tail") locates the real bound at the `rating_priority`
drop-off, not at the number 15 — 15 was an arbitrary proxy. Scaling the numeric budget
with session size while keeping the priority-drop-off and head-not-tail stops is faithful
to that contract: it lets a long session's genuinely high-priority firings still get
rated instead of being truncated by an arbitrary count. Removing the hard cap does not
risk the method doc's anti-padding rule ("no evidence → no rating") because the
evidence-runs-out stop still gates every label.

**Provenance.** Originated as an uncommitted working-tree edit predating the 2026-07-03
audit-remediation session; accepted after structural verification against the method
contract rather than on the edit's own summary. This is a coverage-contract change to a
governed skill, so it lands through the consent gate with this record per "design calls
leave a record."
