"""CMS's own craft-reminder rules — the fork-local overlay for this repo.

Merged into craft_reminder.RULES by `key` (local wins; see craft_reminder.py). CMS's
durable corpus is wider than the doc-agnostic defaults: method/, starter/, and the
shared skills are all teaching surface (CLAUDE.md, Rules). This file is deliberately
NOT a managed tool — `--update` never touches a fork's copy — and it doubles as the
worked example of the overlay mechanism.
"""

RULES = [
    {"key": "method", "path": "method/",
     "pointer": "Editing method/ — teaching surface: write for an external reader "
                "(no source-project provenance) and gate behavior changes through "
                "consent (never codify silently)."},
    {"key": "starter", "path": "starter/",
     "pointer": "Editing starter/ — live templates shipped to forks: keep "
                "placeholder slots intact, write for an external reader, and read "
                "the method/ doc governing the template first."},
    {"key": "skills", "path": ".claude/skills/",
     "pointer": "Editing a shared skill — keep it thin (method/tooling.md) and gate "
                "behavior changes through consent (never codify silently)."},
]
