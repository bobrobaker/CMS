---
status: decided
---
# 2026-06-19 · The Monition hub lives at the landing zone (`$CMS_LANDING_ZONE/monition/`)

**Decision.** The single cross-repo Monition takeaway hub is hosted at the **landing
zone**: `$CMS_LANDING_ZONE/monition/`, with the in-repo `landing/` fallback for forks
that haven't set a landing zone. The backend is **Dolt** for our own hub (the
audience split — SQLite stays the default for external/standalone forkers — is
monition's call; see monition `docs/decisions/2026-06-18-dolt-default-ours-sqlite-external.md`).

CMS owns standing up the hub and populating `MONITION_STORE`:
- *For us:* `CMS_LANDING_ZONE` and `MONITION_STORE` (= `$CMS_LANDING_ZONE/monition`) are
  set in Claude `settings.json` `env` (hooks inherit them). That mapping is **personal
  config and stays out of this committed tree** (forkable hygiene); the literal machine
  path is not recorded here.
- *For forks:* `bootstrap.sh` is the fork path — it `dolt init`s the hub at the resolved
  landing-zone path once per machine and exports `MONITION_STORE`.
  > **Corrected 2026-06-19 (impl):** "`dolt init`s the hub" is wrong for the fork path —
  > forkers default to **SQLite** (the 122 MB Dolt binary is the #1 adoption barrier; see
  > monition `2026-06-18-dolt-default-ours-sqlite-external.md`). As built, `bootstrap.sh`
  > creates the hub via `monition init-store` (SQLite default) and points `MONITION_STORE`
  > via `monition instrument`; it never forces Dolt. A Dolt hub (ours) is created
  > out-of-band with `monition init-store <hub> --dolt` — the `--dolt` was *our* setup
  > leaking into the forker-facing description.

The store stays local and unpublished. When the landing zone is a **private** repo, its
`dump.sql` may be tracked there for offsite backup while the `.dolt/` working dir stays
gitignored; native Dolt versioning is primary, `dump.sql` is a backup snapshot kept fresh
by a dump-on-commit hook.

**Why.** The landing zone already *is* the cross-project home (`decisions/`, `handoffs/`
that outlive any one repo). A cross-repo takeaway hub is exactly that kind of artifact, so
it belongs with the landing zone rather than in a separate machine location — one
cross-project home, not two. Co-locating in a private, backed-up landing-zone repo also
gives the hub durable offsite backup for free. The Dolt-for-us backend restores Dolt's
data-VCS value once stores collapse into one hub (see monition's single-store decision).

**Alternatives weighed.**
- *An `$XDG_STATE_HOME` machine dir (e.g. `~/.local/state/monition/`)* — rejected: it
  fragments cross-project memory into two homes (landing zone + an XDG dir) for no gain,
  and by XDG's own taxonomy the store is important *data*, not transient *state*. This was
  briefly floated in confer (lifted from a stale handoff) and corrected by both sides.
- *A dedicated top-level dotdir (`~/.monition/`)* — rejected for the same one-home reason.

**Pointers.**
- Confer resolution (archived in the **monition** repo):
  `monition/handoffs/archive/2026-06-18-confer-hub-path-confirmation.md`
  (monition↔CMS, the hub-path + Dolt-backend confirmation).
- Hub model + ownership split: monition `docs/decisions/2026-06-18-single-store-general-project-scoping.md`.
- Supersedes the open question in `handoffs/2026-06-18 CMS monition-hub-location.md`.
