---
status: decided
---
# 2026-07-03 · Fork-variant skills belong to monition sync; CMS deploy must not raw-ship them

**Decision.** A skill whose *deployed* form is produced by monition's regen — marked by a
sibling `*.fork-overrides.md` in its skill directory — is **owned by `monition sync`** in
host/adopted repos, not by CMS's deploy/bootstrap. `bootstrap.sh`'s two raw skill-copy sites
(the `--update` re-vendor and apply-to-target's initial copy, both formerly
`cp -R "$src/.claude/skills/." "$dst/…"`) now go through a `vendor_skills` helper that
**excludes** any such skill directory and **never copies the `*.fork-overrides.md`** authoring
source into a downstream repo. Today this scopes to exactly one skill (`mine-session` is the
only `*.fork-overrides.md` in CMS); the marker gates it, so a future fork-variant skill
auto-excludes with no per-skill list to maintain.

**Why.** `mine-session`'s canonical `SKILL.md` is an *authoring source*, not a deployable
artifact: it carries `forkgen:strip`/`forkgen:swap step6` markers whose fork-facing
replacement is single-sourced in `mine-session.fork-overrides.md`, and the transform that
turns source → deployable (strip + swap) lives only in monition's regen. CMS has no regen, so
CMS *cannot* produce the correct deployed form. Raw-shipping the canonical source delivered the
**wrong artifact** to adopted repos: CMS-only step-6 ("CMS is the upstream, promote don't
queue" — a wrong instruction for a downstream repo, which must *queue* transferable lessons
upstream), raw `forkgen:` markers, and **unstamped**, which pinned `monition sync`'s
`_managed_state → edited` so sync WARN-skipped the copies forever. Two owners writing the same
file, neither recognizing the other, was the root seam bug. This extends the existing deploy
principle — *consumer-owned files are guarded, not overwritten* (settings merged, foreign
pre-commit left alone) — to a monition-owned skill.

**Completeness: exclusion is paired with a sync, so a fresh repo isn't left with nothing.**
Excluding the skill from the copy would regress a freshly-onboarded repo from "wrong artifact"
to "no artifact" unless something else installs it. Both deploy paths close that loop:
- **apply-to-target** already reaches `monition instrument` (via `init_store`) *after* the skill
  copy, and instrument materializes the stamped fork variant — so with the skill excluded from
  the copy, instrument sees it `absent` and installs the correct body. Exclusion alone suffices.
- **`--update`** never reaches `instrument`, so it now invokes **`monition sync --root "$dst"`**
  explicitly after the re-vendor (fail-open if the monition CLI is absent). CMS orchestration
  *runs* the sync; monition *writes* the stamped artifact — the "who runs the last step"
  division, with ownership unchanged.

**Steady state.** `monition sync` owns `mine-session` going forward and keeps `SKILLS`
carrying it; CMS never hand-writes monition's stamp. The one-time reconciliation that closed
this out (installing monition's packaged fork variant + stamp into the three already-broken
repos from the CMS seat) was an acceptable repair of pre-existing broken state, verified
byte-exact against monition's own `_stamp`; steady-state delivery runs through the sync path
above.

**Delivered (2026-07-03, verified on disk).** The three adopted repos each now carry the
stamped domain-stripped fork variant (`<!-- monition-skill v0.5.0 sha256:96e63fa3… -->`,
`per ~2 MB` present, step-6 "queue it upstream", forkgen markers stripped); live
`monition sync` reports "no changes (everything current)" in all three, and the leaked
`*.fork-overrides.md` was removed from each. This delivered `0548640`'s transcript-scaled
rating-walk budget, whose content decision is
`2026-07-03-mine-session-rating-budget-scaling.md`.

**Builds on.** `2026-06-21-generate-monition-mine-session-from-cms.md` established the *upstream*
half — monition's regen single-sources the fork variant from CMS canonical (so it can't drift by
hand). This decision is the *downstream* half: given that regen output is the deployable form,
CMS's raw copy must step aside for it. Complements the content decision
`2026-07-03-mine-session-rating-budget-scaling.md` (`0548640`) — this is its delivery channel.

**Governs.** `bootstrap.sh` (`vendor_skills`, the `--update` sync invocation); the `/deploy`
skill's skill-copy step; `method/deploy.md` (guarded-files section). Cross-project seam thread:
the mine-session deploy-channel confer between CMS and monition, resolved 2026-07-03.
