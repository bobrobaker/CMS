#!/usr/bin/env bash
#
# bootstrap.sh — install the CMS context-management machinery.
#
#   ./bootstrap.sh                 in-place: set this clone up to run the machinery
#   ./bootstrap.sh --link-global   in-place, and symlink shared skills into ~/.claude
#   ./bootstrap.sh /path/to/repo   apply-to-target: copy the machinery into another repo
#   ./bootstrap.sh --update /path  re-vendor managed machinery into an already-bootstrapped fork
#
# In-place is the primary path: fork/clone CMS, run this, and the machinery is live.
# Everything here is idempotent — safe to re-run. It never touches ~/.claude unless
# you pass --link-global.
#
set -euo pipefail

# ---- config ---------------------------------------------------------------
# Public source for the monition package. The publish step finalizes this URL;
# until then a local checkout (see MONITION_SRC) takes precedence when present.
MONITION_GIT="git+https://github.com/bobrobaker/monition.git"
MONITION_SRC_DEFAULT="$HOME/projects/monition"   # editable install if this exists
# Oldest monition whose CLI has the subcommands bootstrap invokes (init-store, instrument).
# Builds that predate `--version` are probed for the subcommands directly instead.
MONITION_MIN_VERSION="0.3.0"

# The CMS-managed portable tools — re-vendored wholesale by `--update` and covered by the
# version stamp. The fork's tools/lint.py wrapper is NOT in this set (it's fork-local).
# flag_corpus.py + its seed travel WITH autoflag.py: the Stop hook imports the former and
# the lexical layer reads the latter, so a fork missing either silently loses tier-2's
# self-improving half (the import fails open to regex-only).
MANAGED_TOOLS="craft_reminder.py autoflag.py flag_corpus.py flag_corpus_seed.json lint_skeleton.py backfill_decision_status.py"

# This script's own CMS clone — where the deploy-time helper tools (deploy_settings.py) live.
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
DEPLOY_SETTINGS="$SELF_DIR/tools/deploy_settings.py"

# monition extras. The registered MCP server (.mcp.json -> `monition mcp-serve`) is dead on
# arrival without the `mcp` extra, so install it by default; --embed adds the semantic extra,
# --no-mcp drops to the base package. `wire` (pymysql, the resident sql-server's MySQL-wire
# transport — monition docs/decisions/2026-07-02-wire-client-extra.md) is installed
# unconditionally alongside it: a guarded, fail-open import that's a no-op on a SQLite store
# and a ~160ms/query -> ~1ms win on a Dolt hub. It isn't gated on "targets a Dolt hub" because
# install_monition runs before init_store resolves the hub's backend — gating it there would
# mean duplicating that hub-resolution logic ahead of install, not worth it for a dependency
# this cheap (pure-python, tiny). Mutated by flag parsing in main().
MONITION_EXTRAS="[mcp,wire]"

# Deploy modifiers, set by flags in main() and read by the mode functions.
HUB_OVERRIDE=""        # --hub PATH : join this exact hub (overrides env)
STANDALONE=0           # --standalone : force a per-repo store (ignore any hub env)
APPROVE_MCP=0          # --approve-mcp : write the project-MCP approval into settings.local.json
FIXPATH=0              # --fix-path : ensure ~/.local/bin is on PATH
FORCE_HOOKSPATH=0      # --force-hookspath : override a core.hooksPath that isn't .githooks

# ---- output ---------------------------------------------------------------
step() { printf '\n==> %s\n' "$*"; }
log()  { printf '    %s\n' "$*"; }
warn() { printf '  ! %s\n' "$*" >&2; }
die()  { printf '\nError: %s\n' "$*" >&2; exit 1; }

usage() {
  cat <<'USAGE'
bootstrap.sh — install the CMS context-management machinery.

Modes:
  ./bootstrap.sh                 in-place: set this clone up to run the machinery
  ./bootstrap.sh --link-global   in-place, and symlink shared skills into ~/.claude
  ./bootstrap.sh /path/to/repo   apply-to-target: copy the machinery into another repo
  ./bootstrap.sh --update /path  re-vendor managed machinery into an already-bootstrapped fork
  ./bootstrap.sh --doctor [path] health-check a deployed repo (target, else cwd); writes nothing

Deploy modifiers (in-place / apply-to-target):
  --hub PATH        join this exact takeaway-store hub (overrides $MONITION_STORE)
  --standalone      force a per-repo store (ignore any hub env)
  --embed           also install monition's semantic [embed] extra
  --no-mcp          install the base monition package (skip the [mcp] extra)
  --approve-mcp     write the project-MCP approval into .claude/settings.local.json
  --fix-path        ensure ~/.local/bin is on your PATH (edits your shell profile)
  --reinstall       reinstall the monition CLI even if already on PATH
  --force-hookspath override an existing core.hooksPath that isn't .githooks

In-place is the primary path: fork/clone CMS, run this, and the machinery is live.
Everything is idempotent — safe to re-run. It never touches ~/.claude unless you pass
--link-global. The /deploy skill drives this end to end and walks the interactive steps.
USAGE
  exit "${1:-0}"
}

# ---- steps (each idempotent) ----------------------------------------------

# Portable sha256 (Linux: sha256sum; macOS: shasum -a 256).
_sha256() { if command -v sha256sum >/dev/null 2>&1; then sha256sum; else shasum -a 256; fi; }

# Content hash of the managed tools in $1 (a tools/ dir) — the canonical version stamp.
compute_stamp() {
  local d="$1" f
  for f in $MANAGED_TOOLS; do [ -f "$d/$f" ] && cat "$d/$f"; done | _sha256 | cut -d' ' -f1
}

# Stamp the fork's managed set so a drift check can tell when it falls behind canonical.
write_stamp() {  # $1 = dst repo root
  local stamp; stamp="$(compute_stamp "$1/tools")"
  printf '%s\n' "$stamp" > "$1/tools/.cms-version"
  log "stamped managed tools @ ${stamp:0:12}"
}

# Lay down tools/lint.py as a thin fork-local WRAPPER that imports the managed checks.
# Never clobber a fork's own lint.py; a legacy frozen-copy lint.py (pre-seam) is detected
# and flagged for manual migration, not overwritten.
lay_down_lint_wrapper() {  # $1 = dst repo root; returns 1 if a legacy lint.py was left unmigrated
  local lint="$1/tools/lint.py"
  if [ -f "$lint" ]; then
    if grep -q 'import lint_skeleton' "$lint"; then
      return 0  # already the wrapper — nothing to do
    fi
    warn "tools/lint.py is a legacy frozen copy (pre-seam) — NOT overwritten."
    warn "  migrate it to the wrapper (see the assisted migration, B07) so managed-check"
    warn "  updates land; move any fork-local checks into FORK_CHECKS."
    return 1
  fi
  cat > "$lint" <<'LINTPY'
#!/usr/bin/env python3
"""This fork's linter — a thin wrapper. Managed checks live in tools/lint_skeleton.py and are
re-vendored by `./bootstrap.sh --update`; do NOT edit that file. Add THIS fork's checks below
(they survive updates), then pass them to run()."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lint_skeleton

# ---- this fork's checks (survive `--update`) ------------------------------
# def check_mine(path, text):
#     """Shadows: '<the governance rule this backstops>'. <ERROR|WARN>."""
#     lint_skeleton.error(path, "...")   # or lint_skeleton.warn(path, "...")
FORK_CHECKS = []
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sys.exit(lint_skeleton.run(extra_checks=FORK_CHECKS))
LINTPY
  chmod +x "$lint"
  return 0
}

# Regenerate the canonical managed-tools manifest in the CMS clone — the SINGLE bash hash
# producer the fork drift-check reads (it never recomputes). Run from CMS's own pre-commit.
refresh_manifest() {
  local root; root="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)" \
    || die "bootstrap.sh --refresh-manifest must run from within the CMS git clone"
  compute_stamp "$root/tools" > "$root/tools/.cms-manifest"
  log "refreshed tools/.cms-manifest @ $(cut -c1-12 "$root/tools/.cms-manifest")"
}

# `--update`: re-vendor the managed set + stamp into an already-bootstrapped fork, opt-in.
# Touches only CMS-managed files; never the fork's lint.py wrapper, starter docs, or store.
update_target() {  # $1 = target path
  local src dst t
  src="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)" \
    || die "bootstrap.sh --update must be run from within the CMS git clone (the canonical source)"
  dst="$(git -C "$1" rev-parse --show-toplevel 2>/dev/null)" \
    || die "target is not a git repository: $1"
  step "cms update — re-vendor managed machinery into $dst"
  # Pre-seam migration guard: an old craft_reminder.py carried its per-project config
  # baked into the managed body; this re-vendor replaces it with CMS defaults.
  if [ -f "$dst/tools/craft_reminder.py" ] \
     && ! grep -q "import craft_reminder_local" "$dst/tools/craft_reminder.py" \
     && [ ! -f "$dst/tools/craft_reminder_local.py" ]; then
    warn "pre-seam craft_reminder.py: any customized pointer/paths in its body revert to CMS"
    warn "  defaults on this update — re-apply them as a RULES overlay in tools/craft_reminder_local.py"
  fi
  mkdir -p "$dst/tools" "$dst/.claude/skills"
  for t in $MANAGED_TOOLS; do
    [ -f "$src/tools/$t" ] && cp "$src/tools/$t" "$dst/tools/$t"
  done
  cp -R "$src/.claude/skills/." "$dst/.claude/skills/"
  if lay_down_lint_wrapper "$dst"; then
    write_stamp "$dst"
  else
    warn "left tools/.cms-version unchanged — a legacy lint.py isn't running the managed checks,"
    warn "  so advancing the stamp would falsely report 'in sync'. Migrate the wrapper first."
  fi
  log "managed tools + skills re-vendored; fork-local lint.py and extensions untouched"
  log "(the version stamp covers $MANAGED_TOOLS; skill drift is refreshed but unstamped)"
  # Keep the recovery pointer current: if this clone moved since the deploy, the recorded
  # env.CMS_SRC is where a future /deploy or --update would (wrongly) look.
  python3 "$DEPLOY_SETTINGS" set-env "$dst" "CMS_SRC=$src" \
    || warn "could not refresh env.CMS_SRC in $dst/.claude/settings.local.json"
}

install_monition() {
  step "monition (the takeaway store; SQLite backend by default)"
  # Detect the CLI on PATH — that's what the hooks invoke. (Checking
  # `python3 -c 'import monition'` is wrong: monition lives in its own isolated
  # environment, not the system Python, and that check false-positives from any
  # directory containing a monition/ subfolder.)
  if command -v monition >/dev/null 2>&1 && [ "${REINSTALL:-0}" != "1" ]; then
    log "monition CLI already on PATH — skipping install (--reinstall to force)"
  else
    local src="${MONITION_SRC:-$MONITION_SRC_DEFAULT}"
    local ex="$MONITION_EXTRAS"   # e.g. "[mcp,wire]" / "[mcp,wire,embed]" / "" — appended to the spec
    log "extras: ${ex:-<none, base package>}"

    # Install in isolation — never `pip install` into the system Python, which
    # modern distros refuse (PEP 668, "externally-managed-environment"). Prefer a
    # dedicated CLI-tool installer; fall back to a hand-rolled venv if none exists.
    # Extras ride the spec via standard pip syntax ("path[extra]" / "monition[extra] @ url").
    if command -v uv >/dev/null 2>&1; then
      if [ -d "$src" ]; then uv tool install --editable "$src$ex"; else uv tool install "monition$ex @ $MONITION_GIT"; fi
      log "installed via uv tool"
    elif command -v pipx >/dev/null 2>&1; then
      if [ -d "$src" ]; then pipx install --editable "$src$ex"; else pipx install "monition$ex @ $MONITION_GIT"; fi
      log "installed via pipx"
    else
      install_monition_venv "$src" "$ex"
    fi

    # bootstrap invokes `monition` moments from now (init_store), and under set -e a
    # command-not-found is a hard abort — so fix THIS process's PATH, not just the rc file.
    ensure_monition_on_path || die "monition installed but its binary was not found on PATH or in any known bin dir
  (~/.local/bin, uv's tool bin dir, \$PIPX_BIN_DIR, the monition venv) — check the installer output above."
  fi

  # Both paths (fresh install AND a pre-existing CLI) must pass the capability handshake:
  # a stale pre-existing install is exactly the failure mode the skip branch would hide.
  assert_monition_capable
}

# Make the just-installed monition invocable NOW. Installers drop the binary in a bin dir
# that may not be on this process's PATH; prepend the actual install dir to the CURRENT
# process PATH. Persistence in the shell rc stays with --fix-path — this is runtime-only.
ensure_monition_on_path() {
  command -v monition >/dev/null 2>&1 && return 0
  local d uv_bin=""
  command -v uv >/dev/null 2>&1 && uv_bin="$(uv tool dir --bin 2>/dev/null || true)"
  for d in "$HOME/.local/bin" "$uv_bin" "${PIPX_BIN_DIR:-}" "${MONITION_VENV:-$HOME/.local/share/monition/venv}/bin"; do
    [ -n "$d" ] && [ -x "$d/monition" ] || continue
    PATH="$d:$PATH"
    export PATH
    log "monition landed off-PATH — prepended $d for this run (persist with --fix-path)"
    return 0
  done
  return 1
}

# Numeric version from `monition --version`, empty if the flag predates the installed build.
_monition_version() {
  monition --version 2>/dev/null | grep -Eo '[0-9]+(\.[0-9]+)+' | head -1 || true
}

_version_ge() {  # is dotted version $1 >= $2 ?
  python3 -c 'import sys
a = tuple(int(x) for x in sys.argv[1].split("."))
b = tuple(int(x) for x in sys.argv[2].split("."))
sys.exit(0 if a >= b else 1)' "$1" "$2"
}

# Capability handshake for the installed monition CLI. Prints exactly one of:
#   ok:<version>   --version present and >= $MONITION_MIN_VERSION
#   ok:legacy      no --version yet, but the subcommands bootstrap invokes exist
#   stale:<version> --version present but < $MONITION_MIN_VERSION
#   incapable      lacks init-store/instrument — bootstrap would die mid-run on
#                  an opaque argparse "invalid choice" without this check
probe_monition_capability() {
  local ver
  ver="$(_monition_version)"
  if [ -n "$ver" ]; then
    if _version_ge "$ver" "$MONITION_MIN_VERSION"; then printf 'ok:%s' "$ver"; else printf 'stale:%s' "$ver"; fi
  elif monition init-store --help >/dev/null 2>&1 && monition instrument --help >/dev/null 2>&1; then
    printf 'ok:legacy'
  else
    printf 'incapable'
  fi
}

assert_monition_capable() {
  local cap
  cap="$(probe_monition_capability)"
  case "$cap" in
    ok:legacy) log "capability check: init-store/instrument present (build predates --version)" ;;
    ok:*)      log "capability check: monition ${cap#ok:} (>= $MONITION_MIN_VERSION)" ;;
    stale:*)   die "installed monition is ${cap#stale:}, but bootstrap needs >= $MONITION_MIN_VERSION.
  Likely cause: a stale published package, or an old local checkout at \$MONITION_SRC.
  Update the source, then re-run with --reinstall." ;;
    *)         die "installed monition ($(command -v monition)) lacks the init-store/instrument
  subcommands bootstrap invokes. Likely cause: a stale published package, or an old
  local checkout at \$MONITION_SRC. Update the source, then re-run with --reinstall." ;;
  esac
}

# Fallback when neither uv nor pipx is present: a dedicated virtual environment
# plus a launcher symlinked onto PATH. No extra tools, no writes to system Python.
install_monition_venv() {
  local src="$1"
  local ex="${2:-}"   # extras suffix, e.g. "[mcp]"
  local venv="${MONITION_VENV:-$HOME/.local/share/monition/venv}"
  local bindir="$HOME/.local/bin"
  log "no uv/pipx found — installing into an isolated venv at $venv"
  if ! python3 -m venv "$venv" 2>/dev/null; then
    die "could not create a venv — install the python3-venv package (e.g. 'sudo apt install python3-venv') and re-run"
  fi
  if [ -d "$src" ]; then
    log "installing editable from $src"
    "$venv/bin/pip" install -q -e "$src$ex"
  else
    log "installing from $MONITION_GIT"
    "$venv/bin/pip" install -q "monition$ex @ $MONITION_GIT"
  fi
  mkdir -p "$bindir"
  ln -sf "$venv/bin/monition" "$bindir/monition"
  log "symlinked $bindir/monition -> $venv/bin/monition"
  # off-PATH handling: the caller runs ensure_monition_on_path for the current process;
  # --fix-path persists it in the shell rc.
}

check_dolt() {
  # SQLite is the default backend (stdlib, zero install). Dolt is optional —
  # only needed if a store was created with `monition init --dolt`.
  if command -v dolt >/dev/null 2>&1; then
    log "dolt found — the optional Dolt backend is available"
  else
    log "dolt not found — using the SQLite backend (default; no install needed)"
  fi
}

arm_hooks() {
  local root="$1"
  if [ ! -d "$root/.githooks" ]; then
    warn "no .githooks/ in $root — skipping hook arming"
    return
  fi
  # Never silently repoint someone's existing hook setup: if core.hooksPath is already
  # set to something else, their hooks live there and redirecting disables them.
  local current
  current="$(git -C "$root" config core.hooksPath 2>/dev/null || true)"
  if [ -n "$current" ] && [ "$current" != ".githooks" ] && [ "$FORCE_HOOKSPATH" != "1" ]; then
    warn "core.hooksPath is already '$current' (not .githooks) — NOT changed."
    warn "  the CMS pre-commit will not run. Either chain .githooks/pre-commit from your"
    warn "  existing hooks, or re-run with --force-hookspath to repoint git at .githooks."
    return
  fi
  git -C "$root" config core.hooksPath .githooks
  log "armed pre-commit hooks (core.hooksPath=.githooks)"
}

init_store() {
  local root="$1"
  # Resolve a configured hub: --hub wins, then $MONITION_STORE, then CMS maps $CMS_LANDING_ZONE.
  # --standalone forces a per-repo store regardless of env. A hub means "join this repo to the
  # shared store" — instrument only, no per-repo store (the fused `monition init` would litter a
  # dead store the hub-wired hooks then ignore).
  local hub=""
  if [ "$STANDALONE" = "1" ]; then
    hub=""
    log "--standalone: creating a per-repo store (ignoring any hub env)"
  elif [ -n "$HUB_OVERRIDE" ]; then
    hub="$HUB_OVERRIDE"
  elif [ -n "${MONITION_STORE:-}" ]; then
    hub="$MONITION_STORE"
  elif [ -n "${CMS_LANDING_ZONE:-}" ]; then
    hub="$CMS_LANDING_ZONE/monition"
  fi

  if [ -n "$hub" ]; then
    if [ -d "$hub/.dolt" ] || [ -f "$hub/store.db" ]; then
      log "hub store present at $hub — joining this repo to it (no per-repo store)"
    else
      # SQLite default: the forker adoption-barrier call stands. A Dolt hub (ours) is
      # created out-of-band (`monition init-store <hub> --dolt`); bootstrap never forces dolt.
      log "creating the shared hub store at $hub (SQLite default)"
      monition init-store "$hub"
    fi
    monition instrument --root "$root" --store "$hub"
    log "instrumented $root at the hub (MONITION_STORE -> $hub; no per-repo store)"
  else
    # Standalone / forker: one repo, its own SQLite store + hooks (the fused composition).
    # No store-exists early return: `monition init` is idempotent, and always reaching it
    # is what makes a re-run the recovery path (a present store with missing hooks heals).
    if [ -d "$root/monition/.dolt" ] || [ -f "$root/monition/store.db" ]; then
      log "store already present in monition/ — re-running init to repair any missing hooks"
    else
      log "creating a fresh per-repo store (SQLite) in monition/"
    fi
    monition init --root "$root"
  fi
}

gitignore_store() {
  # Store-stays-local default (docs/DESIGN.md "Store-stays-local hygiene"): a per-repo
  # monition/ store is personal session telemetry, never published. Append the ignore
  # block once; a repo that already ignores it (or tracks it on purpose) is left alone.
  local dst="$1"
  if [ -f "$dst/.gitignore" ] && grep -q '^monition/store\.db$' "$dst/.gitignore" 2>/dev/null; then
    log "$dst/.gitignore already ignores the monition store"
    return
  fi
  {
    echo ""
    echo "# Monition store residue (per-repo store, if this repo isn't hub-joined) —"
    echo "# personal session telemetry, never published. Tracking a dump.sql backup is"
    echo "# an explicit opt-in (see the commented-out block in .githooks/pre-commit)."
    echo "monition/.dolt/"
    echo "monition/store.db"
    echo "monition/dump.sql"
  } >> "$dst/.gitignore"
  log "gitignored monition/ store residue in $dst/.gitignore"
}

report_landing_zone() {
  local root="$1"
  step "landing zone (cross-project decisions + handoffs)"
  if [ -n "${CMS_LANDING_ZONE:-}" ]; then
    log "using \$CMS_LANDING_ZONE=$CMS_LANDING_ZONE"
  else
    log "using the in-repo landing/ (zero-config default)"
    log "for a shared cross-project home: export CMS_LANDING_ZONE=/path/to/store"
    [ -d "$root/landing" ] || warn "expected $root/landing/ (the fallback) — not found"
  fi
}

link_global() {
  local root="$1"
  local dest="$HOME/.claude/skills"
  local backup="$HOME/.claude/skills.bak.$(date +%Y%m%d-%H%M%S)"
  step "symlinking shared skills into $dest (--link-global)"
  warn "this makes your global skills resolve to THIS clone; existing ones are backed up."
  mkdir -p "$dest"
  local linked=0 backed=0
  for skill_dir in "$root"/.claude/skills/*/; do
    [ -d "$skill_dir" ] || continue
    local name target
    name="$(basename "$skill_dir")"
    target="$dest/$name"
    if [ -L "$target" ] && [ "$(readlink "$target")" = "${skill_dir%/}" ]; then
      continue   # already the right symlink
    fi
    if [ -e "$target" ] || [ -L "$target" ]; then
      mkdir -p "$backup"
      mv "$target" "$backup/$name"
      backed=$((backed + 1))
    fi
    ln -s "${skill_dir%/}" "$target"
    linked=$((linked + 1))
  done
  if [ "$backed" -gt 0 ]; then
    log "linked $linked skill(s); backed up $backed existing entr(ies) to $backup"
  else
    log "linked $linked skill(s); nothing to back up"
  fi

  # Dotfile anchor for the global session-archive tooling. The archive is global
  # (one corpus under ~/.claude/logs/), so its tooling resolves through this stable
  # path — not $CLAUDE_PROJECT_DIR (the current repo) and not a hardcoded clone path.
  # The /wrap-session skill, the global SessionEnd hook, and the semantic MCP server
  # all reference ~/.claude/cms/...; repoint this symlink to move the canonical clone.
  ln -sfn "$root" "$HOME/.claude/cms"
  log "anchored session-archive tooling: ~/.claude/cms -> $root"
  log "  (point the global SessionEnd hook + semantic MCP server at ~/.claude/cms/…;"
  log "   see archive/semantic/runbook.md for the MCP registration)"
  log "  (if MONITION_STORE is set machine-wide in ~/.claude/settings.json env, also set"
  log "   MONITION_SQL_SERVER=1 and MONITION_EMBED_DAEMON=1 there — both warm daemons are"
  log "   live-validated (2026-07-02): hook latency roughly halves and variance disappears."
  log "   --doctor now flags a Dolt hub or embed extra missing either.)"
}

# Ensure ~/.local/bin (where the monition launcher lands) is on PATH — bootstrap otherwise
# only warns. Idempotent: no-op if already on PATH or already appended.
fix_path() {
  local bindir="$HOME/.local/bin"
  case ":${PATH}:" in
    *":$bindir:"*) log "~/.local/bin already on PATH"; return ;;
  esac
  local rc
  case "${SHELL:-}" in
    *zsh)  rc="$HOME/.zshrc" ;;
    *bash) rc="$HOME/.bashrc" ;;
    *)     rc="$HOME/.profile" ;;
  esac
  if [ -f "$rc" ] && grep -q 'CMS: ensure ~/.local/bin on PATH' "$rc"; then
    log "PATH line already in $rc — open a new shell (or 'source $rc') to pick it up"
    return
  fi
  printf '\n# CMS: ensure ~/.local/bin on PATH\nexport PATH="$HOME/.local/bin:$PATH"\n' >> "$rc"
  log "added ~/.local/bin to PATH in $rc — run 'source $rc' or open a new shell"
}

# Write the project-MCP approval (settings.local.json, gitignored) so the monition MCP server is
# enabled — it never travels with a clone, so a fresh deploy must assert it locally.
approve_mcp() {
  local root="$1"
  if python3 "$DEPLOY_SETTINGS" approve-mcp "$root"; then :; else
    warn "could not write MCP approval (approve it in-session instead)"
  fi
}

# Merge the CMS harness hooks into a target's settings.json, honoring the global-archive pattern:
# craft_reminder is always per-repo; autoflag/session_tokens are wired per-repo ONLY when the
# global ~/.claude/cms anchor is absent (else the global hooks own them). When wiring them
# per-repo, vendor session_tokens.py too (autoflag.py is already in the managed set).
wire_harness_hooks() {
  local dst="$1" anchor="absent"
  [ -e "$HOME/.claude/cms" ] && anchor="present"
  if [ "$anchor" = "absent" ] && [ -f "$SELF_DIR/tools/session_tokens.py" ]; then
    cp "$SELF_DIR/tools/session_tokens.py" "$dst/tools/session_tokens.py"
    log "vendored session_tokens.py (no global ~/.claude/cms archive anchor)"
  fi
  if python3 "$DEPLOY_SETTINGS" wire-harness-hooks "$dst" --global-archive "$anchor"; then :; else
    warn "could not wire harness hooks into $dst/.claude/settings.json"
  fi
}

# Read-only health check of a deployed repo: does the takeaway/MCP/archive loop actually work?
# Writes nothing. The /deploy skill parses this; a human reads it. PASS/WARN/FAIL per line.
doctor() {
  local root
  root="$(git -C "${1:-$PWD}" rev-parse --show-toplevel 2>/dev/null)" \
    || die "--doctor: not inside a git repo (pass a path: ./bootstrap.sh --doctor /path/to/repo)"
  printf 'CMS deploy doctor — %s\n\n' "$root"
  local pass=0 warnc=0 failc=0
  _chk() {  # $1=PASS|WARN|FAIL  $2=name  $3=detail
    printf '  %-4s  %-15s  %s\n' "$1" "$2" "$3"
    case "$1" in
      PASS) pass=$((pass + 1)) ;;
      WARN) warnc=$((warnc + 1)) ;;
      FAIL) failc=$((failc + 1)) ;;
    esac
  }

  # Base interpreter first — several checks below (and the CMS tools) need it.
  if command -v python3 >/dev/null 2>&1; then
    local pyv
    pyv="$(python3 -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])' 2>/dev/null || true)"
    if python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
      _chk PASS python3 "$pyv"
    else
      _chk FAIL python3 "found ${pyv:-<unknown>} — the CMS tools need >= 3.10"
    fi
  else
    _chk FAIL python3 "not found — hooks and the linter cannot run"
  fi

  local mon interp
  mon="$(command -v monition 2>/dev/null || true)"
  if [ -n "$mon" ]; then _chk PASS monition-cli "$mon"; else
    _chk FAIL monition-cli "not on PATH — run ./bootstrap.sh (then --fix-path)"; fi

  # Capability handshake: a CLI on PATH that predates init-store/instrument still
  # breaks bootstrap and the hooks — surface it here, not as an argparse error later.
  if [ -n "$mon" ]; then
    local cap
    cap="$(probe_monition_capability)"
    case "$cap" in
      ok:legacy) _chk PASS monition-ver "subcommands present (build predates --version)" ;;
      ok:*)      _chk PASS monition-ver "${cap#ok:} (>= $MONITION_MIN_VERSION)" ;;
      stale:*)   _chk FAIL monition-ver "${cap#stale:} < required $MONITION_MIN_VERSION — stale package/checkout; update + --reinstall" ;;
      *)         _chk FAIL monition-ver "lacks init-store/instrument (stale package/checkout) — update + --reinstall" ;;
    esac
  fi

  # mcp/embed extras — check via monition's OWN interpreter; never start the server (it blocks)
  if [ -n "$mon" ]; then
    interp="$(head -1 "$mon" 2>/dev/null | sed -n 's/^#! *//p')"
    case "$interp" in
      *python*)
        if "$interp" -c 'import mcp' >/dev/null 2>&1; then
          _chk PASS mcp-extra "monition[mcp] importable"
        else
          _chk FAIL mcp-extra "mcp extra missing — the .mcp.json server is dead; reinstall monition[mcp]"
        fi
        if "$interp" -c 'import fastembed' >/dev/null 2>&1; then
          _chk PASS embed-extra "monition[embed] importable"
          # Warm embedding daemon: live-validated 2026-07-02 (kills the ~1s cold model
          # load per semantic-eligible prompt). Opt-in, so only relevant once embed is on.
          if [ "${MONITION_EMBED_DAEMON:-}" = "1" ]; then
            _chk PASS embed-daemon "MONITION_EMBED_DAEMON=1 (embedding model stays warm)"
          else
            _chk WARN embed-daemon "MONITION_EMBED_DAEMON unset — ~1s cold model load per semantic-eligible prompt; export MONITION_EMBED_DAEMON=1"
          fi
        else
          _chk WARN embed-extra "embed extra absent — semantic search_sessions/match off (--embed)"
        fi ;;
      *) _chk WARN mcp-extra "couldn't locate monition's interpreter to check extras" ;;
    esac
  fi

  # Resolve the hub the way the RUNTIME does: --hub, then the repo's gitignored
  # settings.local.json env.MONITION_STORE (what `monition instrument --store` writes —
  # the hooks read it in-session even when the shell env is bare), then the shell env.
  local hub="" hub_src=""
  if [ -n "$HUB_OVERRIDE" ]; then
    hub="$HUB_OVERRIDE"; hub_src="--hub flag"
  fi
  if [ -z "$hub" ] && [ -f "$root/.claude/settings.local.json" ] && command -v python3 >/dev/null 2>&1; then
    hub="$(python3 -c 'import json, sys
try:
    cfg = json.load(open(sys.argv[1]))
except Exception:
    sys.exit(0)
print(cfg.get("env", {}).get("MONITION_STORE", ""), end="")' "$root/.claude/settings.local.json" 2>/dev/null || true)"
    [ -n "$hub" ] && hub_src="settings.local.json"
  fi
  if [ -z "$hub" ] && [ -n "${MONITION_STORE:-}" ]; then
    hub="$MONITION_STORE"; hub_src="shell env MONITION_STORE"
  fi
  if [ -z "$hub" ] && [ -n "${CMS_LANDING_ZONE:-}" ]; then
    hub="$CMS_LANDING_ZONE/monition"; hub_src="shell env CMS_LANDING_ZONE"
  fi

  # Store health is a live smoke test (`monition list`), not file existence — a present
  # file with a broken CLI or schema would false-PASS the loop this doctor exists to check.
  if [ -z "$mon" ]; then
    _chk FAIL store "cannot smoke-test a store without the monition CLI (see monition-cli)"
  elif [ -n "$hub" ]; then
    if monition list --store "$hub" >/dev/null 2>&1; then
      _chk PASS store "hub: $hub ('monition list' OK)"
    else
      _chk FAIL store "hub $hub (via $hub_src) — 'monition list' fails; run bootstrap"
    fi
  elif monition list --store "$root/monition" >/dev/null 2>&1; then
    _chk PASS store "per-repo: $root/monition ('monition list' OK)"
  else
    _chk FAIL store "no working store (no hub configured, 'monition list' fails on $root/monition) — run bootstrap"
  fi

  if [ -n "$hub" ]; then
    _chk PASS hub-env "hub $hub (via $hub_src)"
  else
    _chk WARN hub-env "no hub configured — standalone repo (export CMS_LANDING_ZONE for a shared hub)"
  fi

  # Resident dolt sql-server: only relevant for a Dolt hub (concurrent file-based Dolt
  # writes lose ~7/10 firings under contention — monition's write-path fix). Live-validated
  # 2026-07-02; opt-in, so a Dolt hub without it just means degraded-but-working.
  if [ -n "$hub" ] && [ -d "$hub/.dolt" ]; then
    if [ "${MONITION_SQL_SERVER:-}" = "1" ]; then
      _chk PASS sql-server "MONITION_SQL_SERVER=1 (Dolt writes routed through the resident server)"
      # Wire transport: only matters once the server is in play (above). Reuses the same
      # $interp resolved for the mcp/embed check — monition's OWN interpreter, never the
      # system Python (monition docs/decisions/2026-07-02-wire-client-extra.md).
      if [ -n "$interp" ]; then
        if "$interp" -c 'import pymysql' >/dev/null 2>&1; then
          _chk PASS wire-extra "monition[wire] importable (queries use the ~1ms MySQL-wire transport)"
        else
          _chk WARN wire-extra "pymysql not importable — hooks fall back to ~160ms/query dolt-CLI spawns; reinstall monition[wire] (./bootstrap.sh --reinstall)"
        fi
      else
        _chk WARN wire-extra "couldn't locate monition's interpreter to check the wire extra"
      fi
    else
      _chk WARN sql-server "MONITION_SQL_SERVER unset — concurrent Dolt writes can lose firings under contention; export MONITION_SQL_SERVER=1"
    fi
  fi

  # The hooks' designed silent-failure sink: they fail open and append stderr here.
  # Most lines are routine info (e.g. monition's "[capped] N semantic hit(s)..." note),
  # not failures — only warn on lines that actually look like an error (a raw traceback
  # from an uncaught exception, or one of monition's own "[xxx-error]" tags).
  local herr="${XDG_STATE_HOME:-$HOME/.local/state}/monition/hook-errors.log"
  if [ -s "$herr" ]; then
    local errlines
    errlines="$(grep -Ec 'Traceback \(most recent call last\)|[Ee]xception|[Ee]rror' "$herr" 2>/dev/null || true)"
    if [ "${errlines:-0}" -gt 0 ]; then
      _chk WARN hook-errors "$errlines error-like line(s) of $(wc -c < "$herr" | tr -d ' ') bytes, last write $(date -r "$herr" '+%Y-%m-%d %H:%M' 2>/dev/null || echo '?') — hooks are failing; read $herr"
    else
      _chk PASS hook-errors "present, informational only ($(wc -c < "$herr" | tr -d ' ') bytes, no error-like lines)"
    fi
  elif [ -f "$herr" ]; then
    _chk PASS hook-errors "present and empty ($herr)"
  else
    _chk PASS hook-errors "absent (no recorded hook failures)"
  fi

  if [ -f "$root/.mcp.json" ]; then _chk PASS mcp-json "present"; else
    _chk WARN mcp-json "absent — monition MCP server not registered here"; fi

  local sl="$root/.claude/settings.local.json"
  if [ -f "$sl" ] && grep -Eq '"enableAllProjectMcpServers": *true|"monition"' "$sl" 2>/dev/null; then
    _chk PASS mcp-approved "settings.local.json enables the project MCP"
  else
    _chk WARN mcp-approved "not approved — rerun with --approve-mcp (or approve in-session)"
  fi

  local s="$root/.claude/settings.json"
  if [ -f "$s" ] && grep -q 'autoflag.py' "$s" 2>/dev/null; then
    _chk PASS harness-hooks "wired per-repo"
  elif [ -e "$HOME/.claude/cms" ]; then
    _chk PASS harness-hooks "served globally via ~/.claude/cms"
  else
    _chk WARN harness-hooks "autoflag/session_tokens unwired (no per-repo hook, no ~/.claude/cms)"
  fi

  if [ -f "$s" ] && grep -q 'monition prompt-hook' "$s" 2>/dev/null; then
    _chk PASS monition-hooks "fire/prompt/session present"
  else
    _chk WARN monition-hooks "absent — run bootstrap (init_store → instrument)"
  fi

  if [ "$(git -C "$root" config core.hooksPath 2>/dev/null)" = ".githooks" ]; then
    _chk PASS githooks "core.hooksPath=.githooks"
  else
    _chk WARN githooks "not armed — git config core.hooksPath .githooks"
  fi

  case ":${PATH}:" in
    *":$HOME/.local/bin:"*) _chk PASS local-bin "on PATH" ;;
    *) _chk WARN local-bin "~/.local/bin not on PATH (--fix-path)" ;;
  esac

  printf '\n  %d pass · %d warn · %d fail\n' "$pass" "$warnc" "$failc"
  [ "$failc" -eq 0 ] || printf '  fails break the takeaway/MCP loop — the /deploy skill walks the fixes\n'
}

# ---- modes ----------------------------------------------------------------

in_place() {
  local root link="$1"
  root="$(git -C "$(dirname "$0")" rev-parse --show-toplevel 2>/dev/null)" \
    || die "bootstrap.sh must be run from within the CMS git clone"
  printf 'Bootstrapping CMS in place: %s\n' "$root"
  install_monition
  check_dolt
  step "git hooks"
  arm_hooks "$root"
  step "takeaway store"
  init_store "$root"
  report_landing_zone "$root"
  if [ "$FIXPATH" = "1" ]; then step "PATH"; fix_path; fi
  if [ "$APPROVE_MCP" = "1" ]; then step "MCP approval"; approve_mcp "$root"; fi
  [ "$link" = "1" ] && link_global "$root"
  step "health check"
  doctor "$root"
  step "done"
  log "machinery is live. Next: open this repo and start a session."
  [ "$link" = "1" ] || log "(to single-source your global skills from this clone: ./bootstrap.sh --link-global)"
}

apply_to_target() {
  local src dst
  src="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)" \
    || die "bootstrap.sh must be run from within the CMS git clone"
  dst="$(git -C "$1" rev-parse --show-toplevel 2>/dev/null)" \
    || die "target is not a git repository: $1"
  printf 'Applying CMS machinery into %s\n' "$dst"
  warn "copy mode duplicates machinery, which can drift from CMS."
  warn "for your own projects, prefer fork-and-bootstrap or --link-global (one source)."

  step "skills, hooks, and portable tools"
  mkdir -p "$dst/.claude/skills" "$dst/.githooks" "$dst/tools"
  cp -R "$src/.claude/skills/." "$dst/.claude/skills/"
  log "copied .claude/skills/"
  # Per-project machinery only. NOT cms_lint.py (CMS's own linter), and NOT the
  # session-archive tooling (session_tokens.py / extract_session.py): the archive is
  # global, so its tooling resolves through the ~/.claude/cms anchor, not a per-repo copy.
  for t in $MANAGED_TOOLS; do
    [ -f "$src/tools/$t" ] && cp "$src/tools/$t" "$dst/tools/$t"
  done
  # lint.py is a thin fork-local wrapper that imports the managed checks (lint_skeleton.py);
  # laid down once, never clobbered. The stamp lets the drift check detect when the fork is behind.
  if lay_down_lint_wrapper "$dst"; then
    write_stamp "$dst"
  else
    warn "left tools/.cms-version unwritten — migrate the legacy lint.py to the wrapper first."
  fi
  log "vendored managed tools/ + lint.py wrapper"

  # A portable pre-commit: run the target's linter, keep its store git-visible.
  # Write only a file we own (the CMS-MANAGED-HOOK marker) or an absent one — a repo's
  # existing pre-commit is its own machinery, and overwriting it destroys their checks.
  local hook="$dst/.githooks/pre-commit"
  if [ -f "$hook" ] && ! grep -q 'CMS-MANAGED-HOOK' "$hook"; then
    warn "existing .githooks/pre-commit is not CMS-managed — NOT overwritten."
    warn "  merge by hand: add 'python3 \"\$ROOT/tools/lint.py\" || exit 1' to your hook"
    warn "  (full template in bootstrap.sh, apply_to_target), or move your hook aside and re-run."
  else
    cat > "$hook" <<'HOOK'
#!/bin/sh
# CMS-MANAGED-HOOK — laid by bootstrap.sh; bootstrap refreshes any file carrying this marker.
# Tier-1 enforcement: mechanical invariants block, semantic judgment doesn't.
# Arm once per clone: git config core.hooksPath .githooks
ROOT="$(git rev-parse --show-toplevel)"
python3 "$ROOT/tools/lint.py" || exit 1
# Store-stays-local by default (docs/DESIGN.md "Store-stays-local hygiene"): a per-repo
# monition/ store is gitignored and NOT auto-dumped/tracked here. Tracking a dump.sql
# backup is an explicit opt-in — uncomment below (and drop monition/dump.sql from
# .gitignore) if you want this repo's pre-commit to git-track a derived dump:
#   if [ -d "$ROOT/monition/.dolt" ] || [ -f "$ROOT/monition/store.db" ]; then
#     command -v monition >/dev/null 2>&1 \
#       && monition dump >/dev/null 2>&1 \
#       && git -C "$ROOT" add monition/dump.sql 2>/dev/null
#   fi
exit 0
HOOK
    chmod +x "$hook"
    log "wrote portable .githooks/pre-commit"
  fi

  step "starter identity docs (only where absent — never clobbered)"
  # Consumers hardcode these homes: /dispatch and /update-roadmap read docs/road.md and
  # docs/debt.md, /dispatch reads docs/prompts/workstream_bucket_generator.md — so the
  # docs must land where the skills look, not at the repo root.
  mkdir -p "$dst/docs/prompts"
  local laid=0
  while read -r tmpl final; do
    if [ -f "$src/starter/$tmpl" ] && [ ! -f "$dst/$final" ]; then
      cp "$src/starter/$tmpl" "$dst/$final"
      laid=$((laid + 1))
    fi
  done <<'DOCS'
CLAUDE.md.template CLAUDE.md
road.md.template docs/road.md
debt.md.template docs/debt.md
architecture.md.template docs/architecture.md
prompts/workstream_bucket_generator.md docs/prompts/workstream_bucket_generator.md
DOCS
  log "laid down $laid starter doc(s); fill their {{PLACEHOLDERS}}"

  install_monition
  check_dolt
  step "git hooks"
  arm_hooks "$dst"
  step "takeaway store"
  init_store "$dst"
  step "gitignore the store"
  gitignore_store "$dst"
  step "harness hooks"
  wire_harness_hooks "$dst"
  step "CMS source pointer"
  # Recovery runs and --update need bootstrap.sh, which never travels with the target —
  # record where this clone lives (gitignored settings.local.json; merge, never clobber).
  if python3 "$DEPLOY_SETTINGS" set-env "$dst" "CMS_SRC=$src"; then
    log "recovery /deploy and --update resolve bootstrap.sh via env.CMS_SRC"
  else
    warn "could not record env.CMS_SRC in $dst/.claude/settings.local.json"
  fi
  step "landing zone"
  log "set 'export CMS_LANDING_ZONE=/path/to/store' to share a cross-project home"
  if [ "$FIXPATH" = "1" ]; then step "PATH"; fix_path; fi
  if [ "$APPROVE_MCP" = "1" ]; then step "MCP approval"; approve_mcp "$dst"; fi
  step "health check"
  doctor "$dst"
  step "done"
  log "fill the {{PLACEHOLDERS}} in $dst/CLAUDE.md (and docs/road.md, docs/debt.md, docs/architecture.md), then commit."
}

# ---- entry ----------------------------------------------------------------

# Fail fast on missing base dependencies — one clear error each, before any partial work.
# $1 = "install" when the mode will install monition (adds the network reachability check).
preflight() {
  command -v git >/dev/null 2>&1 \
    || die "git is required but not found — install git and re-run"
  command -v python3 >/dev/null 2>&1 \
    || die "python3 is required but not found — install Python >= 3.10 and re-run"
  python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null \
    || die "python3 is $(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:3])))' 2>/dev/null || echo '<unknown>') — CMS needs Python >= 3.10"
  if [ "${1:-}" = "install" ] && ! command -v monition >/dev/null 2>&1; then
    local src="${MONITION_SRC:-$MONITION_SRC_DEFAULT}"
    if [ ! -d "$src" ]; then
      # No local checkout, no installed CLI: the install must fetch MONITION_GIT.
      git ls-remote "${MONITION_GIT#git+}" >/dev/null 2>&1 \
        || die "cannot reach $MONITION_GIT (and no local checkout at $src) — the monition
  install would fail. Check network/DNS, or set MONITION_SRC to a local checkout."
    fi
  fi
}

main() {
  local link=0 update=0 refresh=0 doctor_mode=0 embed=0 nomcp=0 target=""
  while [ $# -gt 0 ]; do
    case "$1" in
      -h|--help) usage 0 ;;
      --link-global) link=1 ;;
      --update) update=1 ;;
      --refresh-manifest) refresh=1 ;;
      --doctor) doctor_mode=1 ;;
      --reinstall) REINSTALL=1 ;;
      --hub) HUB_OVERRIDE="${2:-}"; [ -n "$HUB_OVERRIDE" ] || die "--hub needs a path"; shift ;;
      --standalone) STANDALONE=1 ;;
      --embed) embed=1 ;;
      --no-mcp) nomcp=1 ;;
      --approve-mcp) APPROVE_MCP=1 ;;
      --fix-path) FIXPATH=1 ;;
      --force-hookspath) FORCE_HOOKSPATH=1 ;;
      -*) die "unknown option: $1 (see --help)" ;;
      *) [ -z "$target" ] || die "only one target path is allowed"; target="$1" ;;
    esac
    shift
  done

  # Resolve monition extras from flags: [mcp] by default, +embed, or base with --no-mcp.
  # `wire` (the sql-server MySQL-wire transport) rides along unconditionally regardless of
  # --no-mcp — see the MONITION_EXTRAS comment above for why it isn't gated on hub backend.
  local extras=""
  [ "$nomcp" = "1" ] || extras="mcp"
  extras="${extras:+$extras,}wire"
  [ "$embed" = "1" ] && extras="${extras:+$extras,}embed"
  if [ -n "$extras" ]; then MONITION_EXTRAS="[$extras]"; else MONITION_EXTRAS=""; fi

  if [ "$doctor_mode" = "1" ]; then
    preflight
    doctor "$target"
  elif [ "$refresh" = "1" ]; then
    refresh_manifest
  elif [ "$update" = "1" ]; then
    [ "$link" = "1" ] && die "--update and --link-global are different modes"
    [ -n "$target" ] || die "--update needs a target path: ./bootstrap.sh --update /path/to/fork"
    preflight
    update_target "$target"
  elif [ -n "$target" ]; then
    [ "$link" = "1" ] && die "--link-global applies to in-place mode, not a target path"
    preflight install
    apply_to_target "$target"
  else
    preflight install
    in_place "$link"
  fi
}

main "$@"
