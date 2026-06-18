#!/usr/bin/env bash
#
# bootstrap.sh — install the CMS context-management machinery.
#
#   ./bootstrap.sh                 in-place: set this clone up to run the machinery
#   ./bootstrap.sh --link-global   in-place, and symlink shared skills into ~/.claude
#   ./bootstrap.sh /path/to/repo   apply-to-target: copy the machinery into another repo
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

# ---- output ---------------------------------------------------------------
step() { printf '\n==> %s\n' "$*"; }
log()  { printf '    %s\n' "$*"; }
warn() { printf '  ! %s\n' "$*" >&2; }
die()  { printf '\nError: %s\n' "$*" >&2; exit 1; }

usage() {
  sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

# ---- steps (each idempotent) ----------------------------------------------

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
  if [ -d "$root/monition/.dolt" ] || [ -f "$root/monition/store.db" ]; then
    log "store already present in monition/ — skipping init"
    return
  fi
  log "creating a fresh store (SQLite) in monition/"
  monition init --root "$root"
  if [ -f "$root/monition/dump.sql" ]; then
    log "note: monition/dump.sql is a reviewable snapshot of the reference store;"
    log "      it is not auto-loaded — your store starts empty."
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
  # Portable machinery only — NOT cms_lint.py (the incubator's own linter).
  for t in craft_reminder.py autoflag.py session_tokens.py extract_session.py lint_skeleton.py; do
    [ -f "$src/tools/$t" ] && cp "$src/tools/$t" "$dst/tools/$t"
  done
  # The skeleton becomes the target's own linter; extend it in the marked slot.
  [ -f "$dst/tools/lint.py" ] || cp "$src/tools/lint_skeleton.py" "$dst/tools/lint.py"
  log "copied portable tools/ (lint_skeleton.py -> tools/lint.py)"

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
  local link=0 target=""
  while [ $# -gt 0 ]; do
    case "$1" in
      -h|--help) usage 0 ;;
      --link-global) link=1 ;;
      --reinstall) REINSTALL=1 ;;
      -*) die "unknown option: $1 (see --help)" ;;
      *) [ -z "$target" ] || die "only one target path is allowed"; target="$1" ;;
    esac
    shift
  done

  if [ -n "$target" ]; then
    [ "$link" = "1" ] && die "--link-global applies to in-place mode, not a target path"
    apply_to_target "$target"
  else
    in_place "$link"
  fi
}

main "$@"
