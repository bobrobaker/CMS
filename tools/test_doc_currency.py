#!/usr/bin/env python3
"""Behavioral tests for the two doc-currency probes in `lint_skeleton.py`:
`check_two_headed_decision` (probe 1) and `check_gated_vs_shipped` (probe 2).

Correctness, not parity — `test_lint_mirror.py` separately asserts `cms_lint` agrees with the
skeleton on these. Both probes are WARN-only, so we assert on the accumulated `warnings` list.
Each probe is exercised on its FAILING case AND its look-alike negatives (a deliberate
partial-supersession must not trip probe 1; a genuinely-unbuilt feature must not trip probe 2).
Plain script: exit 0 on pass, 1 on failure. Run by .githooks/pre-commit."""
import os
import sys
import tempfile

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
import lint_skeleton as ls


def _run(check, path, text):
    ls.errors.clear()
    ls.warnings.clear()
    getattr(ls, check)(path, text)
    assert not ls.errors, f"{check} emitted an ERROR (should be WARN-only): {ls.errors}"
    return list(ls.warnings)


# --- Probe 1: two-headed decision doc ---------------------------------------------------------
# All probe-1 fixtures live under a decisions/ dir so is_decision_doc() is satisfied; ls.ROOT is
# irrelevant to probe 1 (it inspects text only), but the path must look like a decision doc.
_DEC = "/repo/docs/decisions/x.md"
_DECIDED = "---\nstatus: decided\n---\n"


def test_p1_reversing_update_no_banner_warns():
    text = _DECIDED + "## Decision\nWe will do X.\n\n## Update\nReversed: we no longer do X."
    w = _run("check_two_headed_decision", _DEC, text)
    assert len(w) == 1, f"expected one WARN for the two-headed doc, got: {w}"


def test_p1_supersede_vocab_in_update_warns():
    text = _DECIDED + "## Decision\nAdopt Y.\n\n## Update\nThis is superseded by the new plan."
    assert len(_run("check_two_headed_decision", _DEC, text)) == 1


def test_p1_partial_supersession_banner_not_flagged():
    # Deliberate PARTIAL per docs/decisions/README.md: stays `decided`, carries an inline banner
    # above the Update. The banner reconciles the top → must NOT flag.
    text = (_DECIDED + "## Decision\nAdopt Y.\n"
            "> **Superseded by [refined](refined.md)** for the Z part only.\n\n"
            "## Update\nThe Z part is now replaced.")
    assert _run("check_two_headed_decision", _DEC, text) == []


def test_p1_plain_addendum_not_flagged():
    # An `## Update` that only ADDS (no reversal/supersession vocab) is not a contradiction.
    text = _DECIDED + "## Decision\nAdopt Y.\n\n## Update\nAdded benchmark numbers below."
    assert _run("check_two_headed_decision", _DEC, text) == []


def test_p1_already_superseded_not_flagged():
    # A whole-doc `superseded` is already marked dead — check_decision_status owns it.
    text = ("---\nstatus: superseded\nsuperseded_by: y.md\n---\n"
            "## Decision\nOld.\n\n## Update\nReversed and replaced.")
    assert _run("check_two_headed_decision", _DEC, text) == []


def test_p1_no_update_not_flagged():
    text = _DECIDED + "## Decision\nAdopt Y. This fully supersedes nothing."
    assert _run("check_two_headed_decision", _DEC, text) == []


def test_p1_non_decision_doc_ignored():
    text = _DECIDED + "## Decision\nX.\n## Update\nReversed."
    assert _run("check_two_headed_decision", "/repo/docs/notes/x.md", text) == []


# --- Probe 2: gated-vs-shipped --------------------------------------------------------------
def _fixture_repo(d):
    """A minimal fork tree: src/pkg/cli.py registering a `replay` verb and defining ReplayRunner."""
    os.makedirs(os.path.join(d, "src", "pkg"))
    with open(os.path.join(d, "src", "pkg", "cli.py"), "w") as f:
        f.write("sub.add_parser('replay')\nclass ReplayRunner:\n    pass\n")
    ls.ROOT = d
    ls._cli_verbs_cache.clear()


def test_p2_unbuilt_but_src_file_exists_warns():
    with tempfile.TemporaryDirectory() as d:
        _fixture_repo(d)
        w = _run("check_gated_vs_shipped", os.path.join(d, "docs", "road.md"),
                 "The `src/pkg/cli.py` runner is not yet built.")
        assert len(w) == 1, f"expected WARN for shipped-but-called-unbuilt src file, got: {w}"


def test_p2_unbuilt_but_verb_registered_warns():
    with tempfile.TemporaryDirectory() as d:
        _fixture_repo(d)
        w = _run("check_gated_vs_shipped", os.path.join(d, "docs", "road.md"),
                 "The `mytool replay` command is not yet implemented.")
        assert len(w) == 1, f"expected WARN for shipped-but-called-unbuilt CLI verb, got: {w}"


def test_p2_unbuilt_but_symbol_exists_warns():
    with tempfile.TemporaryDirectory() as d:
        _fixture_repo(d)
        w = _run("check_gated_vs_shipped", os.path.join(d, "docs", "road.md"),
                 "`src/pkg/cli.py:ReplayRunner` is unbuilt.")
        assert len(w) == 1, f"expected WARN for shipped-but-called-unbuilt symbol, got: {w}"


def test_p2_genuinely_unbuilt_file_not_flagged():
    with tempfile.TemporaryDirectory() as d:
        _fixture_repo(d)
        # The named src file does NOT exist → the feature really is unbuilt → must stay silent.
        assert _run("check_gated_vs_shipped", os.path.join(d, "docs", "road.md"),
                    "The `src/pkg/ghost.py` sync is not built.") == []


def test_p2_unregistered_verb_not_flagged():
    with tempfile.TemporaryDirectory() as d:
        _fixture_repo(d)
        assert _run("check_gated_vs_shipped", os.path.join(d, "docs", "road.md"),
                    "The `mytool ghost` command is not yet implemented.") == []


def test_p2_resolving_ref_without_unbuilt_language_not_flagged():
    with tempfile.TemporaryDirectory() as d:
        _fixture_repo(d)
        # The ref resolves, but the line does NOT call it unbuilt → not a currency drift.
        assert _run("check_gated_vs_shipped", os.path.join(d, "docs", "road.md"),
                    "The `src/pkg/cli.py` runner shipped in v2.") == []


def test_p2_non_src_path_not_flagged():
    with tempfile.TemporaryDirectory() as d:
        _fixture_repo(d)
        os.makedirs(os.path.join(d, "docs"))
        open(os.path.join(d, "docs", "future.md"), "w").close()
        # A resolving NON-src path is out of scope ("the feature's code shipped" is about src/).
        assert _run("check_gated_vs_shipped", os.path.join(d, "docs", "road.md"),
                    "The `docs/future.md` plan is not yet built.") == []


def test_p2_cross_repo_ref_not_flagged():
    with tempfile.TemporaryDirectory() as d:
        _fixture_repo(d)
        # A cross-repo ref self-gates in the resolver; must not be misread as "resolves".
        assert _run("check_gated_vs_shipped", os.path.join(d, "docs", "road.md"),
                    "The `otherrepo:src/pkg/cli.py` bridge is not built.") == []


def test_p2_no_src_dir_self_gates():
    with tempfile.TemporaryDirectory() as d:
        ls.ROOT = d  # no src/ at all
        ls._cli_verbs_cache.clear()
        assert ls._cli_verbs() == set()
        assert _run("check_gated_vs_shipped", os.path.join(d, "docs", "road.md"),
                    "The `mytool replay` verb is not built.") == []


def main():
    saved_root = ls.ROOT
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    try:
        for t in tests:
            try:
                t()
            except AssertionError as e:
                failed += 1
                print(f"FAIL {t.__name__}: {e}")
            except Exception as e:  # noqa: BLE001 — surface any unexpected error as a failure
                failed += 1
                print(f"ERROR {t.__name__}: {type(e).__name__}: {e}")
    finally:
        ls.ROOT = saved_root
        ls._cli_verbs_cache.clear()
    if failed:
        print(f"\n{failed} of {len(tests)} doc-currency tests failed")
        return 1
    print(f"all {len(tests)} doc-currency tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
