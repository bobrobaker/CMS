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
    checks don't fire on example syntax inside code. Behaviourally mirrored by
    `lint_skeleton.strip_code` (the vendored copy) — edit both together."""
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
        # Skip transient agent worktrees (.claude/worktrees/*): separate checkouts, not part
        # of this repo's governed tree — linting them surfaces false errors from their copies.
        if os.path.basename(dirpath) == ".claude" and "worktrees" in dirs:
            dirs.remove("worktrees")
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


DECISION_STATUSES = {"decided", "superseded"}
_FM_RE = re.compile(r"^---\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|$)", re.S)  # tolerate CRLF + a closing --- that ends the file
_FM_KEY_RE = re.compile(r"^([A-Za-z_][\w-]*):\s*(.*)$")


def _frontmatter(text):
    """Flat dict of top-level `key: value` pairs from a leading `---`…`---` block;
    {} if absent. Sufficient for `status:`/`superseded_by:` — not a full YAML parser."""
    m = _FM_RE.match(text)
    if not m:
        return {}
    out = {}
    for line in m.group(1).splitlines():
        km = _FM_KEY_RE.match(line)
        if km:
            out[km.group(1)] = km.group(2).strip().strip("\"'")
    return out


def is_decision_doc(path):
    """A decision doc: a `*.md` (not README) whose immediate parent dir is `decisions/`
    anywhere under `docs/`. Depth-robust. Single source of truth for *what the
    decision-status convention governs*, shared with `check_decision_status`.

    Kept verbatim in `tools/lint_skeleton.py` (the artifact bootstrap ships to forks; the
    backfill helper imports it there) — per the confer resolution, edit both together."""
    parts = os.path.relpath(path, ROOT).split(os.sep)
    if os.path.basename(path) == "README.md" or len(parts) < 2:
        return False
    return "docs" in parts[:-1] and parts[-2] == "decisions"


def validate_superseded_target(path, target):
    """Pure check for the `superseded_by:` rule: returns an error *message* (str) if
    `target` is missing or doesn't resolve to an existing sibling of `path`, else None.
    Mirrored in `lint_skeleton.validate_superseded_target` (the vendored copy the backfill
    helper calls before writing) — edit both together."""
    if not target:
        return ("`status: superseded` requires `superseded_by:` (a reversal with no "
                "successor is itself a new decision doc — see docs/decisions/README.md)")
    resolved = os.path.normpath(os.path.join(os.path.dirname(path), target))
    if not os.path.exists(resolved):
        return f"`superseded_by: {target}` resolves to no file"
    return None


def check_decision_status(path, text):
    """Shadows: 'a decision doc declares live-vs-dead at the file, not only in the
    verdict registry' (docs/decisions/README.md). Every decision doc (see `is_decision_doc`)
    carries frontmatter `status:` in {decided, superseded}; a `superseded` doc needs a
    `superseded_by:` resolving to an existing sibling. Mechanical → ERROR. Self-gates:
    a repo with no `docs/**/decisions/` dir never trips it.

    Kept verbatim in `tools/lint_skeleton.py` (the artifact bootstrap ships to forks) —
    a shared module bootstrap must also ship costs more than this duplication (per the
    confer resolution); edit both together."""
    if not is_decision_doc(path):
        return
    fm = _frontmatter(text)
    status = fm.get("status")
    if status is None:
        error(path, "decision doc missing frontmatter `status:` (expected decided|superseded)")
        return
    if status not in DECISION_STATUSES:
        error(path, f"decision doc `status: {status}` not in {sorted(DECISION_STATUSES)}")
        return
    if status == "superseded":
        msg = validate_superseded_target(path, fm.get("superseded_by"))
        if msg:
            error(path, msg)


ARCH_DOCTYPE = "architecture"
_ARCH_CODESPAN_RE = re.compile(r"`([^`]+)`")
# See lint_skeleton.py for the rationale — mirrored here (edit both together).
_REF_TOKEN_RE = re.compile(r"\A[\w.\-/§]+(?::[\w.\-/§]+){0,2}\Z")


def _looks_like_path(s):
    return "/" in s or "." in s


def _parse_arch_reference(token):
    """Parse a code-span token into (repo|None, path, symbol|None) per the three reference
    forms in method/architecture-doc.md, or None if it isn't a reference. Mirror of
    lint_skeleton._parse_arch_reference — edit both together."""
    if not _REF_TOKEN_RE.match(token):
        return None
    if token.startswith("/"):
        rest = token[1:]
        if "/" not in rest and "." not in rest:
            return None  # a `/slash-command` (single segment, no extension) — not a reference
        return (None, token, None)  # an absolute path → _resolve ERRORs (refs are repo-relative)
    parts = token.split(":")
    if len(parts) == 1:
        # Bare path ref must contain '/'; a dotted-slashless token is prose, not a reference.
        # See lint_skeleton.py for the rationale — edit both together.
        return (None, parts[0], None) if "/" in parts[0] else None
    if len(parts) == 2:
        if _looks_like_path(parts[0]):
            return (None, parts[0], parts[1])
        if _looks_like_path(parts[1]):
            return (parts[0], parts[1], None)
        return None
    return (parts[0], parts[1], parts[2])


def _resolve_arch_reference(ref, token):
    """Error message if `ref` doesn't resolve, else None; a cross-repo ref whose repo isn't a
    reachable sibling self-gates to silence. Mirror of lint_skeleton — edit both together."""
    repo, path, symbol = ref
    if repo:
        base = os.path.join(os.path.dirname(ROOT), repo)
        if not os.path.isdir(base):
            return None
    else:
        base = ROOT
    if os.path.isabs(path):
        return f"architecture reference `{token}` → must be repo-relative, not absolute"
    target = os.path.normpath(os.path.join(base, path.rstrip("/")))
    if target != base and not target.startswith(base + os.sep):
        return f"architecture reference `{token}` → escapes the repo root"
    if not os.path.exists(target):
        return f"architecture reference `{token}` → path does not resolve"
    if symbol:
        if os.path.isdir(target):
            return f"architecture reference `{token}` → symbol named on a directory"
        try:
            with open(target, encoding="utf-8") as f:
                if symbol not in f.read():
                    return f"architecture reference `{token}` → anchor `{symbol}` not found in {path}"
        except OSError:
            return f"architecture reference `{token}` → cannot read {path}"
    return None


def check_architecture_freshness(path, text):
    """Shadows the `FRESH` invariant (method/architecture-doc.md): a doc opting into the
    architecture doctype (frontmatter `doctype: architecture`) must have every reference (the
    three code-span forms) resolve. Mechanical → ERROR. Self-gates on missing marker and on an
    unreachable cross-repo sibling. A near-miss doctype value WARNs (typo-catch). Mirror of
    lint_skeleton.check_architecture_freshness — edit both together."""
    doctype = _frontmatter(text).get("doctype")
    if doctype != ARCH_DOCTYPE:
        if doctype and "arch" in doctype.lower():
            warn(path, f"frontmatter `doctype: {doctype}` is not the recognized `{ARCH_DOCTYPE}` "
                       "— typo? the architecture freshness check is being skipped for this doc")
        return
    for m in _ARCH_CODESPAN_RE.finditer(_CODE_BLOCK_RE.sub("", text)):
        ref = _parse_arch_reference(m.group(1).strip())
        if ref is None:
            continue
        msg = _resolve_arch_reference(ref, m.group(1).strip())
        if msg:
            error(path, msg)


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


CHECKS = [check_relative_links, check_provenance, check_unfilled_placeholders, check_decision_status,
          check_architecture_freshness]
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
