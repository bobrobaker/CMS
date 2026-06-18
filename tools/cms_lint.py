#!/usr/bin/env python3
"""CMS's own pre-commit linter — tier 1 of the enforcement split, applied to the
incubator itself (it eats its own cooking; see method/tooling.md).

ERROR blocks the commit; WARN advises. Each check's docstring names the governance
rule it shadows.
"""
import os
import re
import sys
from datetime import date, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
_CODE_BLOCK_RE = re.compile(r"```.*?```", re.DOTALL)
_CODE_SPAN_RE = re.compile(r"`[^`]+`")


def _strip_code(text: str) -> str:
    """Remove fenced code blocks and inline code spans so link/provenance
    checks don't fire on example syntax inside code."""
    text = _CODE_BLOCK_RE.sub("", text)
    return _CODE_SPAN_RE.sub("", text)
# Shadow of the de-provenancing rule (CLAUDE.md): source-project names must not
# appear in method/ or payload/ doc bodies. Greppable strings only — whether a hit
# is legitimate stays a judgment call, so this is WARN, never ERROR.
PROVENANCE_RE = re.compile(r"\bvvsim\b|\bbrain2\b|\bMTG\b", re.I)
PROVENANCE_DIRS = ("method", "payload")

errors = []
warnings = []


def error(path, msg):
    errors.append(f"ERROR  {os.path.relpath(path, ROOT)}: {msg}")


def warn(path, msg):
    warnings.append(f"WARN   {os.path.relpath(path, ROOT)}: {msg}")


def md_files():
    for dirpath, dirs, names in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d != ".git"]
        for n in names:
            if n.endswith(".md") or n.endswith(".md.template"):
                yield os.path.join(dirpath, n)


def check_relative_links(path, text):
    """Shadows: 'every pointer targets an existing file'. Mechanical → ERROR."""
    if "payload" in os.path.relpath(path, ROOT).split(os.sep):
        return  # payload links resolve in the *generated* project, not here
    for m in LINK_RE.finditer(_strip_code(text)):
        target = m.group(1).split("#")[0]
        if not target or "://" in target or target.startswith("mailto:"):
            continue
        resolved = os.path.normpath(os.path.join(os.path.dirname(path), target))
        if not os.path.exists(resolved):
            error(path, f"broken relative link: {m.group(1)}")


def check_provenance(path, text):
    """Shadows: 'write for an external reader — no source-project provenance in
    method/ or payload/ doc bodies'. Loose backstop → always WARN."""
    rel = os.path.relpath(path, ROOT)
    if not rel.startswith(PROVENANCE_DIRS):
        return
    for i, line in enumerate(text.splitlines(), 1):
        m = PROVENANCE_RE.search(line)
        if m:
            warn(path, f"line {i}: provenance string '{m.group(0)}'")


def check_unfilled_placeholders(path, text):
    """Shadows: 'placeholders are instantiation slots' — they belong ONLY in
    payload templates; anywhere else one is an unfinished edit. Mechanical → ERROR.
    Mentions in code spans/blocks don't count — only bare occurrences."""
    rel = os.path.relpath(path, ROOT)
    if rel.startswith("payload") or rel.startswith("starter"):
        return
    prose = re.sub(r"```.*?```", "", text, flags=re.S)
    prose = re.sub(r"`[^`]*`", "", prose)
    if "{{" in prose:
        error(path, "unfilled {{placeholder}} outside payload/")


CANDIDATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\s*\|")


def check_upstream_candidates(_path=None, _text=None):
    """Warns when the oldest unresolved upstream candidate is >3 days old."""
    candidates_path = os.path.join(ROOT, "handoffs", "upstream-candidates.md")
    if not os.path.exists(candidates_path):
        return
    with open(candidates_path, encoding="utf-8") as f:
        lines = f.readlines()
    oldest = None
    for line in lines:
        line = line.strip()
        if line.startswith("#") or not line:
            continue
        m = CANDIDATE_RE.match(line)
        if m:
            try:
                d = datetime.strptime(m.group(1), "%Y-%m-%d").date()
                if oldest is None or d < oldest:
                    oldest = d
            except ValueError:
                pass
    if oldest and (date.today() - oldest).days > 3:
        age = (date.today() - oldest).days
        warnings.append(
            f"WARN   handoffs/upstream-candidates.md: oldest unresolved candidate is "
            f"{age} days old — consider a back-sweep"
        )


CHECKS = [check_relative_links, check_provenance, check_unfilled_placeholders]
GLOBAL_CHECKS = [check_upstream_candidates]


def main():
    for path in md_files():
        with open(path, encoding="utf-8") as f:
            text = f.read()
        for check in CHECKS:
            check(path, text)
    for check in GLOBAL_CHECKS:
        check()

    for w in warnings:
        print(w)
    for e in errors:
        print(e)
    if errors:
        print(f"\n{len(errors)} error(s) — commit blocked. (Warnings are advisory.)")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
