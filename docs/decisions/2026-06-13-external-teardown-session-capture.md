---
status: decided
---
# 2026-06-13 · Capturing a session an external runner tears down

**Decision.** A session that an external runner closes before it can self-wrap must still
leave a findable archive entry. Conventions, settled with the orchestrator that consumes
them (provenance below):

- **Capture-then-close (light).** The session writes its rung-2 summary from its live
  window as its *final turn*; the runner gates teardown on that artifact existing. The
  runner never hands CMS a live session and CMS never touches the process — the rung-2
  *format* travels to the session (installed payload, else injected into the final-turn
  prompt) and only the file returns. Forced by `summaries.md` §Capture's from-the-window
  rule: a closed session can only be summarized from its transcript (rung-3-degraded),
  the lossy rediscovery the archive exists to prevent.
- **Granularity — per run.** One rung-1 index line + one rung-2 summary per run, with N
  workers as sub-sections; an independently-findable worker is promoted via
  `/mine-session`, not a second entry. (N near-identical index lines pollute the rung
  retrieval ranks over.)
- **Artifact — `/wrap-session`, not `/handoff`.** Handoff is resume-oriented and deleted
  once consumed — wrong for accepted, merged work. Reserve it for a rejected/parked unit
  a future session must resume.
- **Boundary.** A finished session hands the runner three files/strings — the rung-2
  summary, the transcript path (`extract_session.py --files` derives the surviving
  `files:` field, and it is the rung-3 fallback), and the commit SHA + branch. The
  runner's ledger *references* the rung-1 index line, never duplicates the summary. The
  dependency is one-way: the runner knows the archive format; CMS knows nothing about the
  runner.
- **Commit hooks.** Workers honor the *target repo's* pre-commit hooks — no blanket
  `--no-verify`. The hook is the repo's admission gate (here, `cms_lint.py`: ERROR
  blocks, WARN advises); committing past it defeats the gate. A hook ERROR is a real
  signal: fail the unit and park it for the user, don't force-commit. Per-repo policy the
  runner honors, not a global override; an interactive-only hook is a repo-config bug to
  fix there.

**Why now.** An orchestrator was about to tear down finished workers with only a commit +
a transient transcript, losing each unit's reasoning — exactly what the session archive
exists to prevent. The `--no-verify` a worker had used to bypass a repo's pre-commit was
the symptom of an unspecified hook policy.

**CMS implements.** This decision file; the operative "wrapping a session something else
tears down" note in `method/summaries.md` §Capture. `extract_session.py --files` stays
the mechanical `files:` deriver. The runner-side work (final-turn capture, teardown
gating, hook handling, ledger reference) is the consumer's.
