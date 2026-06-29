#!/usr/bin/env python3
"""Behavioral tests for tools/deploy_settings.py — the deploy-time JSON merges.

Guards the merge-not-clobber invariant (a deploy must never destroy a repo's own settings) and
the global-archive split (autoflag/session_tokens go per-repo ONLY when the ~/.claude/cms anchor
is absent). Plain script: exit 0 on pass, 1 on failure. Run by .githooks/pre-commit."""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import deploy_settings as ds


def _settings(root):
    return json.loads((Path(root) / ".claude" / "settings.json").read_text())


def _commands(data):
    out = []
    for groups in data.get("hooks", {}).values():
        for g in groups:
            for h in g.get("hooks", []):
                out.append(h.get("command", ""))
    return out


def main():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / ".claude").mkdir()

        # seed a pre-existing, unrelated hook + permission — must survive every merge
        seed = {
            "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo keepme"}]}]},
            "permissions": {"allow": ["Bash(ls *)"]},
        }
        (root / ".claude" / "settings.json").write_text(json.dumps(seed))

        # global anchor PRESENT → only craft_reminder lands; Stop/SessionEnd left to global
        ds.wire_harness_hooks(root, global_archive=True)
        cmds = _commands(_settings(root))
        assert any("craft_reminder.py" in c for c in cmds), "craft_reminder not wired"
        assert not any("autoflag.py" in c for c in cmds), "autoflag wired despite global anchor"
        assert not any("session_tokens.py" in c for c in cmds), "session_tokens wired despite anchor"
        assert "echo keepme" in cmds, "clobbered the pre-existing Stop hook"

        # anchor ABSENT → autoflag + session_tokens now land per-repo, existing hook still there
        ds.wire_harness_hooks(root, global_archive=False)
        cmds = _commands(_settings(root))
        assert any("autoflag.py" in c for c in cmds), "autoflag not wired when anchor absent"
        assert any("session_tokens.py" in c for c in cmds), "session_tokens not wired when absent"
        assert "echo keepme" in cmds, "clobbered the pre-existing hook on second merge"

        # idempotent: no duplicate commands
        before = sorted(_commands(_settings(root)))
        ds.wire_harness_hooks(root, global_archive=False)
        after = sorted(_commands(_settings(root)))
        assert before == after, f"not idempotent: {before} != {after}"

        # approve-mcp: enables the server, preserves the existing permission, idempotent
        ds.approve_mcp(root, ["monition"])
        ds.approve_mcp(root, ["monition"])
        local = json.loads((root / ".claude" / "settings.local.json").read_text())
        assert local.get("enableAllProjectMcpServers") is True
        assert local.get("enabledMcpjsonServers") == ["monition"], "duplicate/missing server entry"

        # malformed JSON must FAIL LOUD, never silently overwrite
        (root / ".claude" / "settings.json").write_text("{not json")
        try:
            ds.wire_harness_hooks(root, global_archive=False)
        except SystemExit:
            pass
        else:
            print("FAIL — malformed settings.json did not raise", file=sys.stderr)
            return 1

    print("ok — deploy_settings behavioral tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
