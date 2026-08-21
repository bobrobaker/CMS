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
# Shadow of the de-provenancing rule (CLAUDE.md): source-project names and
# machine-local paths must not appear in method/, starter/, or skill doc bodies.
# Greppable strings only — whether a hit is legitimate stays a judgment call, so
# this is WARN, never ERROR.
PROVENANCE_RE = re.compile(r"\bvvsim\b|\bbrain2\b|\bMTG\b|\bbolun\b|~/projects/|/home/", re.I)
PROVENANCE_DIRS = ("method", "starter", os.path.join(".claude", "skills"))

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
    for m in LINK_RE.finditer(_strip_code(text)):
        target = m.group(1).split("#")[0]
        if not target or "://" in target or target.startswith("mailto:"):
            continue
        resolved = os.path.normpath(os.path.join(os.path.dirname(path), target))
        if not os.path.exists(resolved):
            error(path, f"broken relative link: {m.group(1)}")


def check_provenance(path, text):
    """Shadows: 'write for an external reader — no source-project provenance in
    method/, starter/, or skill doc bodies'. Loose backstop → always WARN."""
    rel = os.path.relpath(path, ROOT)
    if not rel.startswith(PROVENANCE_DIRS):
        return
    for i, line in enumerate(text.splitlines(), 1):
        m = PROVENANCE_RE.search(line)
        if m:
            warn(path, f"line {i}: provenance string '{m.group(0)}'")


def check_unfilled_placeholders(path, text):
    """Shadows: 'placeholders are instantiation slots' — they belong ONLY in
    starter templates; anywhere else one is an unfinished edit. Mechanical → ERROR.
    Mentions in code spans/blocks don't count — only bare occurrences."""
    rel = os.path.relpath(path, ROOT)
    if rel.startswith("starter"):
        return
    prose = re.sub(r"```.*?```", "", text, flags=re.S)
    prose = re.sub(r"`[^`]*`", "", prose)
    if "{{" in prose:
        error(path, "unfilled {{placeholder}} outside starter/")


# 'proposed' = drafted, awaiting ratification — valid but advisory-nagged (see the WARN
# in check_decision_status): a proposal is a live decision surface, not lint debt; it
# must resolve to decided/rejected/superseded, so the WARN keeps it visible without
# blocking commits. (Codified 2026-08-20, monition-origin.)
DECISION_STATUSES = {"decided", "superseded", "rejected", "proposed"}
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
        error(path, "decision doc missing frontmatter `status:` (expected decided|superseded|rejected|proposed)")
        return
    if status not in DECISION_STATUSES:
        error(path, f"decision doc `status: {status}` not in {sorted(DECISION_STATUSES)}")
        return
    if status == "proposed":
        warn(path, "decision doc is `status: proposed` — awaiting ratification; "
                   "resolve to decided/rejected (or supersede) before it goes stale")
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


# --- Doc-currency probes (two-headed decision doc + gated-vs-shipped) -------------------------
# Mirror of lint_skeleton's shared block — edit both together (test_lint_mirror.py guards parity).
# SUPERSEDE_RE/BANNER_RE are single-sourced in lint_skeleton for the vendored backfill helper;
# CMS's standalone linter keeps its own copy here (the same duplicate-not-share bargain).
SUPERSEDE_RE = re.compile(r"supersed|deprecat|obsolet|retir|replac", re.I)
BANNER_RE = re.compile(r"^>\s*\*\*\s*superseded by\s*\[[^\]]*\]\(([^)\s]+)\)", re.I | re.M)
_REVERSAL_RE = re.compile(r"revers|revert|overturn|rescind|abandon|no-go|rolled back|"
                          r"backed out|no longer (?:the|holds|stands|hold)|does not hold", re.I)
_UPDATE_RE = re.compile(r"^#{1,6}\s+updates?\b", re.I | re.M)
_BQ_MARKER_RE = re.compile(r"^>.*(?:supersed|revers|no longer|replac|retir).*$", re.I | re.M)


def check_two_headed_decision(path, text):
    """Shadows: 'reconcile a reversal to the top of a decision doc — don't append-only'
    (docs/decisions/README.md). A `status: decided` doc with a later `## Update` that reverses/
    supersedes it and no reconciling banner above that Update leaves a top-down reader inheriting
    a dead verdict. Loose semantic shadow → always WARN. Deliberate PARTIAL supersessions (still
    `decided` + an inline banner above the Update, per README) are NOT flagged. Mirror of
    lint_skeleton.check_two_headed_decision — edit both together."""
    if not is_decision_doc(path):
        return
    if _frontmatter(text).get("status") != "decided":
        return
    m = _UPDATE_RE.search(text)
    if not m:
        return
    above, update = text[:m.start()], text[m.start():]
    if not (SUPERSEDE_RE.search(update) or _REVERSAL_RE.search(update)):
        return
    if BANNER_RE.search(above) or _BQ_MARKER_RE.search(above):
        return
    warn(path, "decision doc is `status: decided` but a later `## Update` reverses/supersedes it "
               "with no reconciling banner above it — a top-down reader inherits the dead verdict. "
               "Reconcile the top (add a banner + flip `status:`), or split out a superseding doc.")


_NOT_BUILT_RE = re.compile(r"not yet implemented|not (?:yet )?built|\bunbuilt\b|"
                           r"not shipped|gated only on", re.I)
_TWO_TOKEN_CLI_RE = re.compile(r"`([a-z][\w.-]*)\s+([a-z][a-z0-9-]+)`")
_ADD_PARSER_RE = re.compile(r"""add_parser\(\s*["']([a-z][a-z0-9-]+)["']""")
_cli_verbs_cache = {}


def _cli_verbs():
    """Argparse subcommand verbs registered under `<ROOT>/src/**/*.py`. Empty (→ no-op) with no
    `src/` or no argparse CLI. Cached per ROOT. Mirror of lint_skeleton._cli_verbs — edit both."""
    if ROOT in _cli_verbs_cache:
        return _cli_verbs_cache[ROOT]
    verbs = set()
    src = os.path.join(ROOT, "src")
    if os.path.isdir(src):
        for dirpath, _, names in os.walk(src):
            for n in names:
                if n.endswith(".py"):
                    try:
                        with open(os.path.join(dirpath, n), encoding="utf-8") as f:
                            verbs.update(_ADD_PARSER_RE.findall(f.read()))
                    except OSError:
                        pass
    _cli_verbs_cache[ROOT] = verbs
    return verbs


def check_gated_vs_shipped(path, text):
    """Shadows: 'designed/gated language must not outlive the build' — the opposite polarity of
    check_architecture_freshness. Fires when a line calls a feature unbuilt while a `` `src/…py` ``
    ref it names resolves, or a `` `tool verb` `` names a registered CLI subcommand. Loose
    semantic shadow → always WARN. Self-gates with no `src/`/CLI. Mirror of
    lint_skeleton.check_gated_vs_shipped — edit both together."""
    verbs = None
    for i, line in enumerate(text.splitlines(), 1):
        if not _NOT_BUILT_RE.search(line):
            continue
        for m in _ARCH_CODESPAN_RE.finditer(line):
            tok = m.group(1).strip()
            ref = _parse_arch_reference(tok)
            if ref is None or ref[0] is not None or not ref[1].startswith("src/"):
                continue
            if _resolve_arch_reference(ref, tok) is None:
                warn(path, f"line {i}: calls `{tok}` unbuilt/gated, but it resolves in the live "
                           "tree — reconcile, the feature shipped.")
        if verbs is None:
            verbs = _cli_verbs()
        if verbs:
            for m in _TWO_TOKEN_CLI_RE.finditer(line):
                if m.group(2) in verbs:
                    warn(path, f"line {i}: calls `{m.group(1)} {m.group(2)}` unbuilt/gated, but "
                               f"`{m.group(2)}` is a registered CLI verb — reconcile, it shipped.")


_PENDING_RE = re.compile(r"\b(?:pending|awaits?|awaiting)\b", re.I)
_RATIFY_RE = re.compile(r"\b(?:ratif\w+|go-live)\b", re.I)
_LINE_DATE_RE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")


def check_stale_pending_ratification(path, text):
    """Shadows: 'a pending-user-decision claim goes stale the moment the human acts, and
    nothing in the doc pipeline fires on the commit that acts' — the highest-yield drift
    class Tier-3 audits keep finding. Fires on a line pairing pending/awaits language with
    ratification/go-live language whose newest inline date is >30 days old. Dateless
    matches are skipped: without a date the age is unknowable here, and the Tier-3 audit
    owns that judgment. Loose semantic shadow → always WARN. Mirror of
    lint_skeleton.check_stale_pending_ratification — edit both together."""
    for i, line in enumerate(text.splitlines(), 1):
        if not (_PENDING_RE.search(line) and _RATIFY_RE.search(line)):
            continue
        dates = []
        for tok in _LINE_DATE_RE.findall(line):
            try:
                dates.append(datetime.strptime(tok, "%Y-%m-%d").date())
            except ValueError:
                pass
        if dates and (date.today() - max(dates)).days > 30:
            warn(path, f"line {i}: 'pending ratification'-shaped claim dated {max(dates)} "
                       "(>30d old) — the decision has likely since been made; verify and reconcile")


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
          check_architecture_freshness, check_two_headed_decision, check_gated_vs_shipped,
          check_stale_pending_ratification]
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
