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

# The CMS-managed portable tools — re-vendored wholesale by `--update` and covered by the
# version stamp. The fork's tools/lint.py wrapper is NOT in this set (it's fork-local).
MANAGED_TOOLS="craft_reminder.py autoflag.py lint_skeleton.py backfill_decision_status.py"

# ---- output ---------------------------------------------------------------
step() { printf '\n==> %s\n' "$*"; }
log()  { printf '    %s\n' "$*"; }
warn() { printf '  ! %s\n' "$*" >&2; }
die()  { printf '\nError: %s\n' "$*" >&2; exit 1; }

usage() {
  sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'
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
}

install_monition() {
  step "monition (the takeaway store; SQLite backend by default)"
  # Detect the CLI on PATH — that's what the hooks invoke. (Checking
  # `python3 -c 'import monition'` is wrong: monition lives in its own isolated
  # environment, not the system Python, and that check false-positives from any
  # directory containing a monition/ subfolder.)
  if command -v monition >/dev/null 2>&1 && [ "${REINSTALL:-0}" != "1" ]; then
    log "monition CLI already on PATH — skipping (--reinstall to force)"
    return
  fi
  local src="${MONITION_SRC:-$MONITION_SRC_DEFAULT}"

  # Install in isolation — never `pip install` into the system Python, which
  # modern distros refuse (PEP 668, "externally-managed-environment"). Prefer a
  # dedicated CLI-tool installer; fall back to a hand-rolled venv if none exists.
  if command -v uv >/dev/null 2>&1; then
    if [ -d "$src" ]; then uv tool install --editable "$src"; else uv tool install "monition @ $MONITION_GIT"; fi
    log "installed via uv tool"
  elif command -v pipx >/dev/null 2>&1; then
    if [ -d "$src" ]; then pipx install --editable "$src"; else pipx install "monition @ $MONITION_GIT"; fi
    log "installed via pipx"
  else
    install_monition_venv "$src"
  fi

  command -v monition >/dev/null 2>&1 \
    || warn "monition installed but not on PATH — ensure ~/.local/bin is on your PATH"
}

# Fallback when neither uv nor pipx is present: a dedicated virtual environment
# plus a launcher symlinked onto PATH. No extra tools, no writes to system Python.
install_monition_venv() {
  local src="$1"
  local venv="${MONITION_VENV:-$HOME/.local/share/monition/venv}"
  local bindir="$HOME/.local/bin"
  log "no uv/pipx found — installing into an isolated venv at $venv"
  if ! python3 -m venv "$venv" 2>/dev/null; then
    die "could not create a venv — install the python3-venv package (e.g. 'sudo apt install python3-venv') and re-run"
  fi
  if [ -d "$src" ]; then
    log "installing editable from $src"
    "$venv/bin/pip" install -q -e "$src"
  else
    log "installing from $MONITION_GIT"
    "$venv/bin/pip" install -q "monition @ $MONITION_GIT"
  fi
  mkdir -p "$bindir"
  ln -sf "$venv/bin/monition" "$bindir/monition"
  log "symlinked $bindir/monition -> $venv/bin/monition"
  case ":${PATH}:" in
    *":$bindir:"*) ;;
    *) warn "$bindir is not on your PATH — add it so the 'monition' command is found" ;;
  esac
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
  if [ -d "$root/.githooks" ]; then
    git -C "$root" config core.hooksPath .githooks
    log "armed pre-commit hooks (core.hooksPath=.githooks)"
  else
    warn "no .githooks/ in $root — skipping hook arming"
  fi
}

init_store() {
  local root="$1"
  # Resolve a configured hub: $MONITION_STORE wins, else CMS maps $CMS_LANDING_ZONE.
  # A hub means "join this repo to the shared store" — instrument only, no per-repo store
  # (the fused `monition init` would litter a dead store the hub-wired hooks then ignore).
  local hub=""
  if [ -n "${MONITION_STORE:-}" ]; then
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
    if [ -d "$root/monition/.dolt" ] || [ -f "$root/monition/store.db" ]; then
      log "store already present in monition/ — skipping init"
      return
    fi
    log "creating a fresh per-repo store (SQLite) in monition/"
    monition init --root "$root"
  fi
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
  [ "$link" = "1" ] && link_global "$root"
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
  cat > "$dst/.githooks/pre-commit" <<'HOOK'
#!/bin/sh
# Tier-1 enforcement: mechanical invariants block, semantic judgment doesn't.
# Arm once per clone: git config core.hooksPath .githooks
ROOT="$(git rev-parse --show-toplevel)"
python3 "$ROOT/tools/lint.py" || exit 1
# Derived view: keep the takeaway store reviewable in git diffs.
if [ -d "$ROOT/monition/.dolt" ] || [ -f "$ROOT/monition/store.db" ]; then
  command -v monition >/dev/null 2>&1 \
    && monition dump >/dev/null 2>&1 \
    && git -C "$ROOT" add monition/dump.sql 2>/dev/null || true
fi
exit 0
HOOK
  chmod +x "$dst/.githooks/pre-commit"
  log "wrote portable .githooks/pre-commit"

  step "starter identity docs (only where absent — never clobbered)"
  local laid=0
  while read -r tmpl final; do
    if [ -f "$src/starter/$tmpl" ] && [ ! -f "$dst/$final" ]; then
      cp "$src/starter/$tmpl" "$dst/$final"
      laid=$((laid + 1))
    fi
  done <<'DOCS'
CLAUDE.md.template CLAUDE.md
road.md.template road.md
debt.md.template debt.md
DOCS
  log "laid down $laid starter doc(s); fill their {{PLACEHOLDERS}}"

  install_monition
  check_dolt
  step "git hooks"
  arm_hooks "$dst"
  step "takeaway store"
  init_store "$dst"
  step "landing zone"
  log "set 'export CMS_LANDING_ZONE=/path/to/store' to share a cross-project home"

  step "done"
  log "fill the {{PLACEHOLDERS}} in $dst/CLAUDE.md (and road.md, debt.md), then commit."
}

# ---- entry ----------------------------------------------------------------

main() {
  local link=0 update=0 refresh=0 target=""
  while [ $# -gt 0 ]; do
    case "$1" in
      -h|--help) usage 0 ;;
      --link-global) link=1 ;;
      --update) update=1 ;;
      --refresh-manifest) refresh=1 ;;
      --reinstall) REINSTALL=1 ;;
      -*) die "unknown option: $1 (see --help)" ;;
      *) [ -z "$target" ] || die "only one target path is allowed"; target="$1" ;;
    esac
    shift
  done

  if [ "$refresh" = "1" ]; then
    refresh_manifest
  elif [ "$update" = "1" ]; then
    [ "$link" = "1" ] && die "--update and --link-global are different modes"
    [ -n "$target" ] || die "--update needs a target path: ./bootstrap.sh --update /path/to/fork"
    update_target "$target"
  elif [ -n "$target" ]; then
    [ "$link" = "1" ] && die "--link-global applies to in-place mode, not a target path"
    apply_to_target "$target"
  else
    in_place "$link"
  fi
}

main "$@"
