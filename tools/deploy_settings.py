#!/usr/bin/env python3
"""Deploy-time settings merges for the CMS deploy path — the JSON surgery bootstrap.sh
(and the /deploy skill) can't do safely in bash.

Two idempotent operations:

  approve-mcp <repo-root> [server ...]
      Merge MCP enablement into <root>/.claude/settings.local.json (gitignored, machine-local):
      enabledMcpjsonServers += server(s) (default "monition"), enableAllProjectMcpServers=true,
      and the monition commit/dump permission allows. This is the project-MCP "approval" that
      never travels with a clone (settings.local.json is gitignored).

  wire-harness-hooks <repo-root> [--global-archive present|absent]
      Merge the CMS harness hooks into <root>/.claude/settings.json, honoring the global-archive
      pattern. craft_reminder (governs THIS repo's docs/) is always wired per-repo. autoflag +
      session_tokens write to a MACHINE-WIDE store (~/.claude/logs, ~/.claude/session-flags), so
      they belong in the global ~/.claude/settings.json via the ~/.claude/cms anchor — wired
      per-repo ONLY as a fallback when that anchor is absent (--global-archive absent), so the
      repo is self-sufficient. With the anchor present, only craft_reminder is added.
      Default (no flag): the anchor is auto-detected at ~/.claude/cms.

Both are merge-not-clobber: load existing config, add by exact identity, write back. They FAIL
LOUD on malformed JSON — this is a deploy step a human is watching, not a fail-open hot path.
The monition hooks (fire/prompt/session) are NOT our concern here: `monition instrument` owns
those. We only wire the three CMS-owned harness hooks.
"""
from __future__ import annotations  # lazy annotations — keep `str | None` working on Python 3.9

import json
import os
import sys
from pathlib import Path

# The three CMS-owned harness hooks. (event, matcher, command, always_per_repo)
#   always_per_repo=True  → wire regardless of the global anchor (state is THIS repo's)
#   always_per_repo=False → wire only when the global anchor is absent (else global owns it)
HARNESS_HOOKS = [
    ("PreToolUse", "Write|Edit", 'python3 "$CLAUDE_PROJECT_DIR/tools/craft_reminder.py"', True),
    ("Stop", None, 'python3 "$CLAUDE_PROJECT_DIR/tools/autoflag.py"', False),
    ("SessionEnd", None, 'python3 "$CLAUDE_PROJECT_DIR/tools/session_tokens.py"', False),
]

MCP_PERMISSION_ALLOWS = ["Bash(monition commit *)", "Bash(monition dump *)"]


def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    text = path.read_text()
    if not text.strip():
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        sys.exit(f"deploy_settings: {path} is not valid JSON ({e}); refusing to clobber it. "
                 f"Fix it by hand and re-run.")
    if not isinstance(data, dict):
        sys.exit(f"deploy_settings: {path} is not a JSON object; refusing to touch it.")
    return data


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def _ensure_hook(settings: dict, event: str, matcher, command: str) -> bool:
    """Append a command hook to `event` (under `matcher`) if its exact command isn't already
    present anywhere in that event. Returns True if it added one."""
    hooks = settings.setdefault("hooks", {})
    groups = hooks.setdefault(event, [])
    for g in groups:
        for h in g.get("hooks", []):
            if h.get("command") == command:
                return False  # already wired — idempotent
    target = None
    for g in groups:
        gm = g.get("matcher")
        if matcher is None and gm in (None, ""):
            target = g
            break
        if matcher is not None and gm == matcher:
            target = g
            break
    if target is None:
        target = {} if matcher is None else {"matcher": matcher}
        groups.append(target)
    target.setdefault("hooks", []).append({"type": "command", "command": command})
    return True


def approve_mcp(root: Path, servers) -> None:
    servers = servers or ["monition"]
    path = root / ".claude" / "settings.local.json"
    data = _load(path)
    enabled = data.setdefault("enabledMcpjsonServers", [])
    added = []
    for s in servers:
        if s not in enabled:
            enabled.append(s)
            added.append(s)
    data["enableAllProjectMcpServers"] = True
    allows = data.setdefault("permissions", {}).setdefault("allow", [])
    for p in MCP_PERMISSION_ALLOWS:
        if p not in allows:
            allows.append(p)
    _write(path, data)
    print(f"approve-mcp: {path} — enabled {servers}"
          + (f" (added {added})" if added else " (already enabled)"))


def wire_harness_hooks(root: Path, global_archive: bool) -> None:
    path = root / ".claude" / "settings.json"
    data = _load(path)
    added, skipped_global = [], []
    for event, matcher, command, always in HARNESS_HOOKS:
        if not always and global_archive:
            skipped_global.append(event)
            continue
        if _ensure_hook(data, event, matcher, command):
            added.append(event)
    _write(path, data)
    msg = f"wire-harness-hooks: {path} — "
    msg += f"wired {added}" if added else "nothing to add (already wired)"
    if skipped_global:
        msg += f"; left {skipped_global} to the global ~/.claude/cms archive hooks"
    print(msg)


def _global_archive_present(flag: str | None) -> bool:
    if flag == "present":
        return True
    if flag == "absent":
        return False
    return (Path.home() / ".claude" / "cms").exists()


def main(argv) -> None:
    if not argv:
        sys.exit(__doc__)
    cmd, rest = argv[0], argv[1:]
    if cmd == "approve-mcp":
        if not rest:
            sys.exit("usage: deploy_settings.py approve-mcp <repo-root> [server ...]")
        approve_mcp(Path(rest[0]).resolve(), rest[1:])
    elif cmd == "wire-harness-hooks":
        flag = None
        args = []
        i = 0
        while i < len(rest):
            if rest[i] == "--global-archive":
                flag = rest[i + 1]
                i += 2
            else:
                args.append(rest[i])
                i += 1
        if not args:
            sys.exit("usage: deploy_settings.py wire-harness-hooks <repo-root> "
                     "[--global-archive present|absent]")
        wire_harness_hooks(Path(args[0]).resolve(), _global_archive_present(flag))
    else:
        sys.exit(f"deploy_settings.py: unknown command {cmd!r} (approve-mcp | wire-harness-hooks)")


if __name__ == "__main__":
    main(sys.argv[1:])
