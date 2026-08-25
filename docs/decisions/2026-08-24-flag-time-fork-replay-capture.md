---
status: decided
---
# 2026-08-24 · Flag-time fork-replay capture: contract and drain survival

**Decision.** `/flag` optionally captures, at flag time, what a later fork-replay of the
flagged moment needs and cannot be reconstructed afterwards: the fork coordinate (session
id + transcript record count) and a snapshot of the repo's dirty state. `/mine-session`'s
drain preserves each capture before deleting the flag file, making every capture
self-contained. The governing source for the contract is monition's decision record
`2026-08-24-flag-capture-drain-contract.md` (in the monition repo); this file restates it
in CMS terms for the surfaces CMS owns (`/flag`, `/mine-session`, `/housekeep`).

**Capture contract (in `/flag`, step 4):**
- Off by default; on when `MONITION_FLAG_CAPTURE=1` is set in the environment. A
  per-invocation argument always beats the env default: `--capture` forces on,
  `--no-capture` forces off.
- When capturing: append `> Fork-coordinate:` (session id + transcript line count) to the
  flag entry, snapshot the repo (`rsync -a --exclude .venv` → `~/.claude/p7-captures/
  <repo-basename>-<UTC-timestamp>/`), and append `> Snapshot: <path>`. If the repo can't
  be resolved, skip with a `> Snapshot: SKIPPED <reason>` line.

**Drain survival (in `/mine-session`, §0a).** The drain `rm`s flag files, and harness
transcripts expire on their own (~30-day cleanup) — so both halves of the coordinate are
mortal, and the coordinate must travel with the snapshot, not the flag file. Before
deleting a drained file: for every entry carrying a `> Snapshot:` line, copy the full
entry to `<snapshot-path>/FLAG.md` and the session's transcript
(`~/.claude/projects/<slug>/<session-id>.jsonl`) to `<snapshot-path>/transcript.jsonl`;
if the transcript is already gone, note that in `FLAG.md` rather than failing. Entries
without a snapshot line have no capture contract and drain as before.

**Retention (in `/housekeep`).** Capture dirs are propose-only residue: housekeep may
surface aged `~/.claude/p7-captures/` dirs for the user to reap, never auto-reap them —
a capture's value is exactly that it can't be reconstructed.

**Why.** Retroactive reconstruction of repo state leaks the future (VCS history, artifact
coherence), so flag-time capture is the only fidelity path; and a capture whose coordinate
dies with the flag file (or whose transcript expires) is a capture that silently can't be
replayed.
