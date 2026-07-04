# deploy-check — feedback log

Dated provenance of how this check evolved: what was ambiguous, missed, or misapplied,
and the correction. Consult when **revising** the protocol. The distilled, firing form of
these lessons lives in `SKILL.md` (`## Gotchas` and the body) — this is the audit trail,
not loaded on every run.

- **2026-07-03** — Origin. Grew out of a recurring manual pattern: after implementing a
  CMS-machinery change, hand-checking that it was correct per standards *and* propagated
  across every surface (symlinks, bootstrap/fork cp, dotfiles channel, mirror-back,
  decision record, lint). First concrete instance was accepting the dangling
  `mine-session` rating-budget edit — the run had to verify the symlink made the edit live
  and that no bootstrap/mirror-back was owed.
- **2026-07-03** — Symlink-liveness check must read the *directory*, not a file inside it.
  During the origin run, `ls -la ~/.claude/skills/mine-session/SKILL.md` printed a plain
  `-rw-` file (it resolved *through* the parent symlink), which read as "not linked" and
  briefly contradicted the documented symlink deployment model. `readlink` on the dir
  showed the real symlink. → Gotcha: check `readlink <dir>`, never infer from a file stat.
- **2026-07-03** — A newly-added skill dir is invisible globally until linked.
  `--link-global` symlinks skill dirs *at bootstrap time*; one created afterward has no
  symlink and is not discoverable. This skill itself hit it at creation. → Gotcha +
  build-step: `ln -s` the new dir (or re-run `--link-global`) as part of deploying it.
