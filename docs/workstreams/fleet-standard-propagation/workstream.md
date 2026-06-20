# Workstream: Fleet propagation of shared standards + evergreen architecture-doc convention

Progress: **WS2 CLOSED (2026-06-20).** All buckets done: B01,B02,B04,B07 (propagation + arch-doctype) + B03 (backfill scaffold) + B05 (arch-doc freshness check + mirror-parity guard) + B06 (dogfood DESIGN.md + fork rollout handoff). B03/B05/B06 were each built, code-reviewed, and confer-reviewed with the brain2 architect to convergence; every A/B concern implemented + re-validated, C/D parks logged in bucket Updates. Fork rollout queued in the landing zone (opt-in).
Blocked: none

## Objective

Close the gap WS1 left: a CMS-owned check ships to *new* forks at bootstrap but never reaches an
already-bootstrapped fork (copy-once, no downstream sync). Deliver opt-in propagation
(vendored-copy + version-stamp + `cms update` + drift-warn) that preserves the zero-dependency
standalone fork; a scaffold-with-confirmation backfill for existing decision docs; and the
evergreen architecture-doc convention (fleet doctype + mechanical freshness check). Design is
settled — see `docs/DESIGN.md §Roadmap → Workstream 2`. This workstream builds it.

## Execution Protocol (do not change)

1. Read this workstream first. For B01, read the full file. For B02+, do NOT use `cat` — run `grep -n "^##" workstream.md` first to get section line anchors, then use bounded reads for only: Objective, Execution Protocol, Bucket Index, and Cross-Bucket Invariants — skip Deferred/Non-Goals, Estimate, and any lower boilerplate sections.
2. Use `Progress` and `Bucket Index` to select the active bucket; if none is active, select the next bucket.
2a. If the index references a bucket file that does not exist yet, read `## Bucket template` in `starter/prompts/workstream_bucket_generator.md` before creating it.
3. Open only the selected bucket file. If its `State` is not `active`, update it to `active` before reading touchpoints.
4. Read only that bucket's required touchpoints before reporting.
5. Report first: selected bucket, required touchpoints read, current behavior, proposed edits, validation plan, extra touchpoints if needed.
6. Only edit after the plan is clear.
7. Run the bucket's validation.
8. Update the bucket file's `Updates` section with completed tasks, discoveries, gotchas, test results, and handoff notes.
9. Update this workstream's `Progress`, `Bucket Index`, and `Updates` only for progress, sequencing changes, cross-bucket discoveries, and cross-bucket gotchas. Also update the next bucket file's `State` from `later` to `next`. Use the Read tool (not Bash `cat`) to open workstream.md before editing it.
10. Keep only one bucket active at a time unless the user explicitly authorizes parallel execution.

## Bucket Index

| B | State | File | Goal | Depends |
|---|---|---|---|---|
| B01 | done | buckets/B01_propagation-mechanism.md | Managed/local seam + version stamp + `cms update` verb | — |
| B02 | done | buckets/B02_drift-warn-check.md | Drift-warn check; self-gates disconnected | B01 |
| B03 | done | buckets/B03_backfill-scaffold.md | Scaffold-with-confirmation backfill helper | B01 |
| B04 | done | buckets/B04_arch-doc-convention.md | Fleet arch-doc doctype (method + starter) | — |
| B05 | done | buckets/B05_arch-doc-freshness-check.md | Mechanical freshness check for the doctype | B04 |
| B06 | done | buckets/B06_dogfood-and-rollout.md | Reconcile CMS DESIGN.md; queue fork rollout | B01,B03,B04,B05,B07 |
| B07 | done | buckets/B07_assisted-lint-migration.md | Migrate frozen-copy forks to the wrapper (4 auto, 1 flag) | B01 |

States: `next`, `active`, `blocked`, `done`, `deferred`, `later`.

## Cross-Bucket Invariants

- **Zero-dep standalone preserved.** Every vendored artifact runs in a fork with no CMS install and no network present. No bucket may introduce a runtime import of a CMS-only package into the vendored set.
- **Never auto-mutate consumer content.** No bucket writes a `status:` (or any doc edit) into a consumer's decision doc without one-pass human confirmation. A false `decided` is worse than unmarked.
- **Self-gate bare repos.** Any new check emits nothing in a repo lacking the machinery / lacking a reachable canonical reference — fail open to silence, never to error or noise.
- **Two distinct doctypes.** CMS's own current-architecture lives in `docs/DESIGN.md`; the fleet-wide arch-doctype is a separate convention. Do not collapse them.
- **No "evergreen" without the freshness mechanism.** B04's convention is not "done" until B05's freshness check exists — the anti-goal is an evergreen claim backed only by a promise.
- **Propagation contract:** preserve `docs/contracts/shared-machinery-propagation.md`; buckets that touch the vendored set, the version stamp, or the drift-check must read the relevant section before editing.

## Deferred / Non-Goals

- **Two-tier propagation** (live-import for an internal tier) — rejected at design time; contradicts opt-in pickup.
- **Grandfather backfill** (WARN-only on legacy, never mark) — rejected; leaves the existing-fleet gap open.
- **Forced regeneration / auto-rewriting consumer docs** — violates the consent-gate invariant.
- **Executing the backfill inside consumer repos.** Each consumer runs its own backfill once against its own registry; this workstream delivers the *mechanism* and *coordinates* rollout (B06), it does not reach into other repos. The concrete downstream-fork list lives in the landing-zone rollout handoff, not in this public repo.
- **The disconnected-fork drift blind spot** — a fork with no reachable canonical cannot learn it is behind. Accepted limit (honest dormancy); not a bug to "fix" here.

## Global Implementation Notes

- The managed/local seam in `tools/` is the load-bearing prerequisite: today `bootstrap.sh` copies `lint_skeleton.py → lint.py` once (`[ -f lint.py ] || cp`) and forks extend `lint.py` in place. Re-vendoring is only safe once managed checks are separable from fork-local extensions (B01).
- Reuse existing landing-zone resolution idioms (`${CMS_LANDING_ZONE:+…}` + git repo-root) rather than inventing new path logic — see `handoff`/`housekeep` skills.
- `cms update` is a new `bootstrap.sh` mode alongside in-place / `--link-global` / apply-to-target — extend, don't fork the script.
- **Stamp = committed manifest, single-source (confer 2026-06-19, Q3).** bash is the sole hash producer: it writes the fork's stamp **and** a committed canonical `tools/.cms-manifest`. The python drift check *reads* `$CMS_SRC/tools/.cms-manifest` and string-compares — no bash at check time, no re-derived hash, no second `MANAGED_TOOLS` list. One fail-loud CMS pre-commit guard asserts the committed manifest matches the recomputed hash. (Replaces the original two-impl `compute_stamp`/`_stamp_of` design — rework B01/B02 internals.)
- **`CMS_SRC` (confer Q2):** document + bootstrap-suggest **and** set in global `~/.claude/settings.json` (like `CMS_LANDING_ZONE`) — "user sets once" is dormant-by-forgetting. No untracked per-fork file (YAGNI). This *finishes* B02.
- **Legacy-fork handling (confer Q1):** (1) never advance the stamp when a wrapper is left legacy; (2) a managed check WARNs on every lint run when `lint.py` lacks `import lint_skeleton`. Both in-scope B01/B02 fixes. The auto-migrator itself is **B07** (proposed, pending user OK).

## Updates

- [2026-06-19 14:30] Initial plan created from the settled WS2 design. Next: B01/propagation-mechanism.
- [2026-06-19 15:05] **B01 done + validated** (main checkout). Seam landed: `lint_skeleton.py` = managed module (`SHARED_CHECKS`+`run(extra_checks)`), `tools/lint.py` = fork-local wrapper, stamp in `tools/.cms-version`, new `./bootstrap.sh --update` verb. The Global-Implementation-Note prerequisite (seam) is now satisfied — later buckets can assume it.
- [2026-06-19 15:05] **B04 done in worktree `worktree-agent-a4033ca05c174ba66` (UNMERGED).** Delivered `method/architecture-doc.md` + `starter/architecture.md.template`. Key B05 handoff (the reference grammar): three closed reference forms — `path`, `path:symbol` (literal grep anchor), `repo:path[:symbol]` (self-gates to silence when repo unreachable); freshness invariant `FRESH` = every reference resolves. B05 builds its check against exactly this grammar. **Merge B04 before starting B05.**
- [2026-06-19 15:05] **Cross-bucket gotcha (tooling):** an agent worktree created under `.claude/worktrees/` is walked by the *parent* `tools/cms_lint.py` (and the skeleton's `md_files`), so the worktree's `starter/*.template` placeholders surface as false ERRORs in the main tree's lint. Validation for code buckets must lint the main tree with the worktree absent/merged, or `cms_lint` should exclude `.claude/worktrees/`. Flagged for a decision.
- [2026-06-19 15:20] **B02 done + validated.** `check_stamp_drift` added to `lint_skeleton.py` (repo-level managed check via new `REPO_CHECKS`); canonical resolved via `CMS_SRC`; self-gates when disconnected/unstamped. Note: stamp algorithm now lives in both bash (`compute_stamp`) and python (`_stamp_of`) — both must change together if `MANAGED_TOOLS` changes.
- [2026-06-19 15:20] **Tooling gotcha RESOLVED:** `tools/cms_lint.py` now prunes `.claude/worktrees/` from its walk — lint is clean with an agent worktree present (no more false template ERRORs).
- [2026-06-19 16:40] **B07 done — propagation half complete (B01/B02/B04/B07).** `tools/migrate_lint.py`: classify + dry-run + `--apply` (CLEAN only), clean path reuses `bootstrap.sh --update`. Code-review (1 independent finder) found 4; **fixed 3** (indentation-bounded block extraction; `SHARED` derived from `lint_skeleton` — the review caught it as *almost re-introducing the `MANAGED_TOOLS` duplication WS2 had just removed*; `migrate_clean` backup-restore + per-fork loop continues on error). **Accepted 1** (pre-commit manifest hashes working tree not staged blobs — niche; the clean fix would reintroduce a hardcoded tool list). **Session stopping after B07** (this session's deep propagation context is spent); B03 → B05 → B06 handed to a fresh session.
- [2026-06-19 16:00] **B01/B02 reworked per confer; B04 merged into tree; B07 created.** Stamp is now a committed `tools/.cms-manifest` — bash is the sole hash producer (`--refresh-manifest`, kept fresh by CMS pre-commit); the drift check string-compares it via `$CMS_SRC` (removed `MANAGED_TOOLS`/`_stamp_of`/`hashlib` from `lint_skeleton.py` — the duplication is gone). Legacy move-1 done (don't advance the stamp on a legacy `lint.py`). **Move-2 dropped as incoherent** — a WARN living in `lint_skeleton` can't fire in a legacy fork (the frozen `lint.py` never imports it); the `--update` warning + B07 migration are the real signals. `CMS_SRC` documented in `method/tooling.md`; **setting it in global `~/.claude/settings.json` was blocked by the self-modification guard → needs the user.** Full reworked integration test green. Two trivial fixes from the review also applied earlier (confer `xargs`, method-doc phrasing).
- [2026-06-19 15:40] **Code-review (high) + confer with brain2 done.** Review confirmed 3 design forks; 2 trivial bugs fixed (confer `xargs` stdin-trap → while-read; method-doc line-99 phrasing). Confer resolved (archived `2026-06-19-confer-ws2-impl-review.md`): Q2 `CMS_SRC`→settings.json + docs; Q3 stamp→committed-manifest single-source; Q1 legacy reach → **propose new bucket B07 (assisted lint.py migration)**. brain2 verified the fleet: 4/5 forks clean frozen copies (auto-migratable), fathom diverged (1 manual flag). **B07 escalated to user before creation.** B01/B02 reopen for the Q2/Q3 rework once B07 is decided.
