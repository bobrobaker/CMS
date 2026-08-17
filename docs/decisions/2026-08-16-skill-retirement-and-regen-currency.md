---
status: decided
---

# Skill retirement propagates under a vendor manifest; regen currency is checked at sync time

## Context

A fleet-wide sync audit found two silent failure modes in the vendor path, both of which let
`--update` report success while leaving forks wrong:

1. `vendor_skills()` only ever **copied**. When CMS retired a skill (e.g.
   `architecture-width-scan`, folded into `/scrutinize`), the standalone dir lived on in every
   fork that had received it — four forks still carried it at the identical retired hash. There
   was no mechanism to remove it, and the obvious one (delete anything CMS doesn't ship) would
   happily delete a fork's own native skills.
2. Monition-owned skills (`mine-session`) do not travel through that copy at all. CMS holds the
   authoring source; monition's `tools/regen_from_cms.py` bakes it into
   `src/monition/_generated_cms.py`; `monition sync` writes the baked constant into the fork.
   Edit CMS's `mine-session` and forget the regen, and every `--update` in the fleet succeeds
   while shipping the previous body — the failure is invisible at every station on the chain.

## Call

### 1. Retirement propagation, bounded by a vendor manifest

`vendor_skills()` writes `tools/.cms-skills-manifest` (alongside the existing `.cms-version`
pattern) listing exactly the skill names that vendor shipped. On the next vendor, a fork skill
dir is removed only when **all three** hold:

- (a) it appears in the fork's **previous** manifest — CMS put it there, so it is not fork-native;
- (b) this vendor no longer ships it;
- (c) CMS has no skill dir of that name at all.

The invariant, non-negotiable: **deletion authority extends only to what a previous CMS vendor
itself installed.** (a) is what makes fork-native skills structurally unreachable — they are
never written to the manifest, so no code path can name them for deletion. (c) is not redundant
with (b): a skill that becomes *monition-owned* (a `*.fork-overrides.md` marker added after it
was vendored) drops out of the shipped set while still existing in CMS, and without (c) the
retirement pass would read that as "retired" and delete monition's synced copy. Monition-owned
skills are excluded from the manifest for the same reason they are excluded from the copy.

A pre-manifest fork has **no manifest, hence no deletion authority**: the first run deletes
nothing and only records the baseline. That is deliberate — the alternative (synthesizing a
manifest from what happens to be on disk) would grant authority over dirs CMS never vendored.
The cost is that skills retired *before* the manifest existed need one manual removal, which is
how `architecture-width-scan` was cleared from Visualizer, procap, throughput-analyzer, and
VVsim in the same rollout.

### 2. Regen-currency check at the sync seam

`regen_from_cms.py` gains a `--check` mode (and, as a side effect of adding argparse, `--help`
no longer *runs* the generator): it rebuilds from CMS and compares against the on-disk
`_generated_cms.py`, writing nothing. Exit 0 current · 1 stale · 2 cannot check.

`bootstrap.sh --update` runs it right after `monition sync` and `--doctor` runs it as a
`regen-currency` check. The `--update` WARN names the whole remediation, because the confusing
part is that sync *succeeded*: run the regen in monition, then re-run `--update`.

Placement note: the check lives at the sync seam rather than in CMS's pre-commit, because the
staleness that matters is "what the fleet is receiving right now", which a CMS-side commit gate
cannot observe (the baked file lives in another repo and can go stale without any CMS commit).

Fail-open, matching the hooks: a missing monition checkout, or a regen predating `--check`,
produces no news rather than a block — a standalone forker without monition sources must not be
stopped. The capability is probed by grepping for the flag **before** invoking it, because a
pre-`--check` regen has no argparse and would silently *regenerate* (rewriting the baked file)
instead of reporting.

## Why not the alternatives

- **Delete-anything-CMS-doesn't-ship.** Simplest to write, and it destroys fork-native skills
  the first time anyone adds one. Rejected outright; the manifest exists to make that class of
  mistake unrepresentable rather than merely unlikely.
- **A per-skill retired-skills list in CMS.** Works, but it is a hand-maintained list that
  someone must remember to append to at exactly the moment they are deleting a directory — the
  same discipline the manifest removes the need for.
- **Hash recorded by the regen tool, compared by bootstrap without invoking monition.** Would
  avoid shelling out, but it puts a second hash-producer in play and answers "did the inputs
  change" instead of the load-bearing question, "would a regen change the output". Asking the
  generator itself keeps one producer.

## Consequences

- Every fork now carries `tools/.cms-skills-manifest`; the file is the record of CMS's delete
  authority in that fork, and hand-editing it grants or revokes that authority.
- The stamp (`tools/.cms-version`) deliberately does **not** cover the manifest — the stamp
  compares fork tools against CMS's own `tools/`, which has no manifest of its own.
- `--doctor` gains one check and can now WARN on a repo whose own files are all correct: the
  staleness being reported is upstream of the fork, which the message says explicitly.
