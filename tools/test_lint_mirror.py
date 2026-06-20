#!/usr/bin/env python3
"""Mirror-parity guard for the cms_lint ↔ lint_skeleton duplication.

`tools/cms_lint.py` (CMS's own linter) and `tools/lint_skeleton.py` (the artifact vendored to
forks) deliberately **duplicate** a set of checks rather than share a module — a shared import
would break the fork's zero-dependency standalone guarantee (the rejected shared-module call).
The cost of that decision is an "edit both together" rule enforced only by a docstring promise.

This script converts that promise into a mechanical invariant: it runs every mirrored symbol in
both modules against a fixture corpus and asserts identical behavior. CMS-only (not vendored) —
so the fork's zero-dep set is untouched while drift between the two copies becomes loud.
Exit 1 on any divergence. Run by the pre-commit hook.

NOT a behavioral test of correctness — `backfill_decision_status.py`'s own validation covers that.
This asserts only that the two copies *agree*.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cms_lint as cl
import lint_skeleton as ls

failures = []


def _eq(label, a, b):
    if a != b:
        failures.append(f"{label}: cms_lint={a!r} != lint_skeleton={b!r}")


# Fixtures exercising the edge cases the two copies must agree on.
FM_TEXTS = [
    "---\nstatus: decided\n---\n# body\ntext",
    "---\nstatus: superseded\nsuperseded_by: x.md\n---",        # no trailing newline
    "---\r\ndoctype: architecture\r\n---\r\nbody",              # CRLF
    "# no frontmatter at all\nbody",
    "---\nstatus: decided\n---\n",
]
CODE_TEXTS = [
    "a `fenced`\n```\nblock `x`\n```\n and inline `y` span",
    "link `[a](b.md)` inside span",
    "plain text no code",
]
REF_TOKENS = [
    "core/commands.py", "api/", "core/commands.py:Command", "road.md:## 2",
    "shared-types:schema/order.ts", "shared-types:schema/order.ts:Order",
    "config.yaml", "v1.2", "e.g.", ".cms-version", "Command", "/abs/path", "../up.md",
    "/wrap-session", "/mine-session", "/etc/passwd", "shared:/abs/x",  # slash-command vs absolute
]
SUPERSEDED = [("/x/a.md", "b.md"), ("/x/a.md", ""), ("/x/a.md", "nope.md")]


def run():
    # Pure-function parity (return values).
    for t in FM_TEXTS:
        _eq(f"_frontmatter({t!r:.30})", cl._frontmatter(t), ls._frontmatter(t))
    for t in CODE_TEXTS:
        _eq(f"strip_code({t!r:.30})", cl._strip_code(t), ls.strip_code(t))
    for tok in REF_TOKENS:
        _eq(f"_parse_arch_reference({tok!r})", cl._parse_arch_reference(tok), ls._parse_arch_reference(tok))
    for path, target in SUPERSEDED:
        _eq(f"validate_superseded_target({path},{target})",
            cl.validate_superseded_target(path, target), ls.validate_superseded_target(path, target))

    # Path-dependent + side-effecting parity: point both at one fixture tree and compare the
    # errors/warnings each check accumulates on identical input.
    with tempfile.TemporaryDirectory() as d:
        os.makedirs(os.path.join(d, "docs", "decisions"))
        os.makedirs(os.path.join(d, "core"))
        open(os.path.join(d, "core", "commands.py"), "w").write("class Command: pass\n")
        cl.ROOT = ls.ROOT = d

        for path in [os.path.join(d, "docs", "decisions", "x.md"),
                     os.path.join(d, "docs", "decisions", "README.md"),
                     os.path.join(d, "core", "commands.py")]:
            _eq(f"is_decision_doc({os.path.basename(path)})", cl.is_decision_doc(path), ls.is_decision_doc(path))

        cases = [
            (os.path.join(d, "docs", "decisions", "a.md"), "---\nstatus: superseded\nsuperseded_by: gone.md\n---\n#x"),
            (os.path.join(d, "docs", "decisions", "b.md"), "---\nstatus: bogus\n---\n#x"),
            (os.path.join(d, "docs", "arch.md"),
             "---\ndoctype: architecture\n---\n`core/commands.py:Command` `core/gone.py` `../esc.md`"),
            (os.path.join(d, "docs", "typo.md"), "---\ndoctype: architecure\n---\n`core/gone.py`"),
        ]
        for check in ("check_decision_status", "check_architecture_freshness"):
            for path, text in cases:
                cl.errors.clear(); cl.warnings.clear(); ls.errors.clear(); ls.warnings.clear()
                getattr(cl, check)(path, text)
                getattr(ls, check)(path, text)
                _eq(f"{check} errors ({os.path.basename(path)})", sorted(cl.errors), sorted(ls.errors))
                _eq(f"{check} warns ({os.path.basename(path)})", sorted(cl.warnings), sorted(ls.warnings))

    if failures:
        print("MIRROR DRIFT — cms_lint and lint_skeleton disagree (edit both together):")
        for f in failures:
            print("  ", f)
        return 1
    print("mirror parity OK — cms_lint and lint_skeleton agree on all fixtures")
    return 0


if __name__ == "__main__":
    sys.exit(run())
