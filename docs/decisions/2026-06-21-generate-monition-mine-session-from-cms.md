---
status: decided
---
# 2026-06-21 · Generate monition's mine-session copy from CMS, don't hand-mirror it

**Decision.** monition's fork-facing `mine-session` skill (and the `lesson-routing.md`
it needs) is now **generated** from CMS canonical, not hand-maintained. CMS's
`.claude/skills/mine-session/SKILL.md` carries `<!-- forkgen:strip -->` / `<!-- forkgen:swap KEY -->`
sentinels (inert HTML comments) marking the one genuinely CMS-only block (step 6 — CMS is
the upstream, so it *promotes*; a fork *queues*), whose fork variant is single-sourced in
`mine-session.fork-overrides.md`. monition's `tools/regen_from_cms.py` strips/swaps and
writes the generated `SKILL_MINE_SESSION` + a bundled-verbatim `METHOD_LESSON_ROUTING`
into `src/monition/_generated_cms.py`; `monition sync` now installs the bundled doc into
forks (hash-checked like skills); and a **dev-only parity test** byte-compares the
committed output to a fresh regen, so any un-regenerated CMS edit fails loudly. You edit
CMS, run the regen, commit monition — the hand-transcribed mirror is gone.

**Why.**

- **Single-source can't cross the standalone-package boundary.** CMS symlinks its own
  skills into `~/.claude` (one inode, zero drift), but monition installs into forks that
  have **no CMS on disk** — a symlink would dangle. That one constraint (standalone
  installability, monition's whole purpose) is the hard blocker to a literal symlink, so
  the seam *forces a copy*.
- **The copy wasn't the pain — the hand-authored transform was.** The old mirror diverged
  for two reasons: mostly **staleness** (monition lacked CMS's steps 0a/0b/0d — notably
  0d, so a fork's flag corpus was *dead*), plus exactly **one** real carveout (step 6).
  Removing the manual transform (mark step 6, bundle the referenced doc so the skill
  references instead of inlines a drift-prone digest) makes the copy a *mechanical regen*
  + parity test — the same pattern CMS already uses for its other forced duplication
  (`cms_lint` ↔ `lint_skeleton`, guarded by `test_lint_mirror.py`).
- **Generate-and-check beats eliminate.** A literal single source would mean dropping
  standalone installability (a shared content package both repos depend on) — a much
  larger move than the drift annoyance warranted. Regen + parity gets the single-source
  *experience* (edit one place, can't silently drift) without breaking monition's
  standalone property.

**v1 scope (deliberate, named).** Only step 6 is carved out; a few author-specific spots
(step 5's Dolt-hub framing, depth doc-refs beyond `lesson-routing.md`) still leak to forks
as soft imperfections — *current and drift-free*, just not perfectly fork-tailored. Growing
the carveout set (more `forkgen:strip` blocks) and bundling more docs are clean follow-ups.

**Relationship to prior work (not a formal supersession).** This evolves, but does not
retire, the routing-version guards built earlier this session: the dev-only regen-parity
test now subsumes content/version drift in the skill body, so the hand-re-strip handoff it
was guarding no longer exists. The `ROUTING_VERSION` legend pin is kept as a cheap
always-on human-readable guard. Those decisions stand; this one supplies the mechanism
that makes their "remember to re-strip" obligation obsolete.

**Cross-cutting note.** This is a CMS↔monition contract; the sentinel convention lives in
CMS (canonical), the regen + parity in monition. Recorded here because the contract
originates in CMS; a future move of the canonical content to the landing zone would
relocate this decision with it.
