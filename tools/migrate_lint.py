#!/usr/bin/env python3
"""Assisted migration of a fork's frozen-copy tools/lint.py to the wrapper form (WS2 / B07).

A fork bootstrapped before the managed/local seam has a *frozen copy* lint.py (a full copy of an
old lint_skeleton, no `import lint_skeleton`), so re-vendoring the skeleton never reaches its
checks. This classifies a fork's lint.py and, for a *clean* frozen copy (only CMS-shared checks,
no local additions), migrates it to the thin wrapper — a strict upgrade that finally lets the
fork run the current managed checks. A *diverged* copy (locally added checks, or a shared check
edited in place) is never touched: it gets a worklist for manual extraction into FORK_CHECKS.

CMS-side tool — run it from the CMS clone against a fork path; the clean path reuses
`./bootstrap.sh --update` to lay the wrapper (single source for the wrapper text).

    python3 tools/migrate_lint.py /path/to/fork [/path/to/fork2 ...]   # dry-run: classify + plan
    python3 tools/migrate_lint.py --apply /path/to/fork                # migrate the CLEAN class

Confirmation-gated: --apply acts only on forks classified CLEAN; DIVERGED is reported, never
auto-modified.
"""
import argparse
import os
import re
import subprocess
import sys

CMS_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(CMS_ROOT, "tools"))
import lint_skeleton  # noqa: E402 — CMS-side tool; the skeleton is the single source of check names

# Derive the managed check names from the skeleton itself — never hand-maintain a second list
# (the duplication WS2 just removed). A frozen copy whose only check defs are in this set has no
# fork-local checks to preserve.
SHARED = tuple(c.__name__ for c in lint_skeleton.SHARED_CHECKS + lint_skeleton.REPO_CHECKS)


def _check_blocks(text):
    """{check_name: source_block} for each top-level `def check_*`, bounded by indentation (the
    def line plus following blank/indented lines) so trailing module-level code — CHECKS=, main(),
    helper consts — is NOT swallowed into the last function's block (which would make the last
    check always look 'edited')."""
    out = {}
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        m = re.match(r"def (check_\w+)\(", lines[i])
        if not m:
            i += 1
            continue
        block = [lines[i]]
        i += 1
        while i < len(lines) and (lines[i].strip() == "" or lines[i][:1] in (" ", "\t")):
            block.append(lines[i])
            i += 1
        while block and block[-1].strip() == "":
            block.pop()
        out[m.group(1)] = "\n".join(block)
    return out


def classify(repo):
    """Return (state, local_checks, body_diffs).
    state: 'no-lint' | 'wrapper' | 'clean' | 'diverged'.
    local_checks: check defs not in SHARED (drive the diverged worklist).
    body_diffs: shared checks whose body differs from the current skeleton (possible in-place
    edit — surfaced for human confirmation, since we have no skeleton lineage to prove age)."""
    lint = os.path.join(repo, "tools", "lint.py")
    if not os.path.exists(lint):
        return "no-lint", [], []
    text = open(lint, encoding="utf-8").read()
    if "import lint_skeleton" in text:
        return "wrapper", [], []
    blocks = _check_blocks(text)
    local = sorted(n for n in blocks if n not in SHARED)
    skel = _check_blocks(open(os.path.join(CMS_ROOT, "tools", "lint_skeleton.py"), encoding="utf-8").read())
    body_diffs = sorted(n for n in blocks if n in SHARED and n in skel and blocks[n] != skel[n])
    return ("diverged" if local else "clean"), local, body_diffs


def migrate_clean(repo):
    """Clean path: drop the frozen lint.py, then `bootstrap.sh --update` lays the wrapper +
    stamps. Reuses bootstrap so the wrapper text has a single source. The frozen content is held
    and restored if bootstrap fails, so a failure never leaves the fork without a lint.py."""
    lint = os.path.join(repo, "tools", "lint.py")
    with open(lint, encoding="utf-8") as f:
        backup = f.read()
    os.remove(lint)
    try:
        subprocess.run([os.path.join(CMS_ROOT, "bootstrap.sh"), "--update", repo], check=True)
    except Exception:
        with open(lint, "w", encoding="utf-8") as f:  # restore — never leave the fork broken
            f.write(backup)
        raise


def main(argv=None):
    ap = argparse.ArgumentParser(description="Assisted lint.py migration (WS2 / B07).")
    ap.add_argument("repos", nargs="+", help="fork repo root(s) to classify/migrate")
    ap.add_argument("--apply", action="store_true", help="migrate forks classified CLEAN")
    args = ap.parse_args(argv)

    migrated = 0
    for repo in args.repos:
        state, local, body_diffs = classify(repo)
        if state == "no-lint":
            print(f"{repo}: no tools/lint.py — skip (bare repo or unbootstrapped)")
        elif state == "wrapper":
            print(f"{repo}: already the wrapper — nothing to do")
        elif state == "diverged":
            print(f"{repo}: DIVERGED — has fork-local check(s): {', '.join(local)}")
            print("  → manual: migrate, then move these into the wrapper's FORK_CHECKS. NOT auto-touched.")
        else:  # clean
            note = ""
            if body_diffs:
                note = (f"  ⚠ shared check(s) differ from current skeleton: {', '.join(body_diffs)} "
                        "— almost certainly just an older version, but confirm it's not a local edit.")
            if args.apply:
                try:
                    migrate_clean(repo)
                    print(f"{repo}: CLEAN → migrated to wrapper (now runs the current managed checks).")
                    migrated += 1
                except Exception as e:  # one fork's failure must not abort the rest of the sweep
                    print(f"{repo}: CLEAN → migration FAILED ({e}); left as-is (frozen lint.py restored).")
            else:
                print(f"{repo}: CLEAN → would migrate to wrapper (re-run with --apply).")
            if note:
                print(note)
    if not args.apply:
        print("\n(dry-run — no files changed; pass --apply to migrate the CLEAN forks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
