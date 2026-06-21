#!/usr/bin/env python3
"""Behavioral tests for the self-improving lexical flag matcher (flag_corpus.py).

Plain-script style (no pytest, matching test_lint_mirror.py): collect failures, print
them, exit 1 on any. Run by the pre-commit hook.

These assert FIRING behavior at the conservative threshold, not raw score rankings —
the threshold, not IDF alone, is what separates real flag-worthy phrasings from benign
stopword-sharing decoys (IDF narrows the gap but does not guarantee a clean ranking on
a small corpus). The mutator tests run against a tmp live corpus, never ~/.claude.
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import flag_corpus as fc

failures = []


def check(label, cond):
    if not cond:
        failures.append(label)


SEED = fc._read(fc.SEED_CORPUS)
check("seed corpus loads and is non-empty", SEED and SEED["entries"])


def fires(text, corpus=SEED):
    return fc.score_text(text, corpus=corpus) is not None


# --- firing behavior at the default threshold --------------------------------

# Exact and near-variant admitted-error phrasings fire.
hit = fc.score_text("I was wrong about that.", corpus=SEED)
check("exact seed phrase fires", hit is not None)
check("exact match carries the entry label", hit and hit["label"] == "GOVERNANCE")
check("near variant fires (wrong about the config)",
      fires("I was wrong about the config."))
check("near variant fires (should have checked the logs)",
      fires("I should have checked the logs."))

# A benign sentence that shares only filler + one mid-salience token does NOT fire —
# the conservative threshold suppresses it even though it out-scores some true misses.
check("stopword decoy is suppressed", not fires("I was on the call about that."))
check("unrelated text does not fire",
      not fires("The deploy finished and all tests pass."))

# Sentences thinner than MIN_TOKENS are skipped — the regex floor in autoflag.py owns
# short exact phrases like "my mistake".
check("sub-MIN_TOKENS sentence is skipped", not fires("My mistake."))

# Degenerate corpora fail open to no hit, never an error.
check("empty corpus yields no hit",
      fc.score_text("I was wrong about that.", corpus={"version": 1, "entries": []}) is None)

# A pruned (mostly-noise) entry stops firing even on an exact match.
pruned = {"version": 1, "entries": [
    {"phrase": "the build is flaky again", "label": "GENERAL",
     "helpful": 0, "noise": 9, "weight": 0.1}]}
check("pruned entry (weight < floor) does not fire",
      fc.score_text("the build is flaky again.", corpus=pruned) is None)


# --- mutators: write to a TMP live corpus, never ~/.claude -------------------

with tempfile.TemporaryDirectory() as td:
    fc.LIVE_CORPUS = Path(td) / "flag-corpus.json"   # redirect writes off the real store

    msg = fc.add("the migration silently dropped rows", "MONITION")
    check("add reports success", "added" in msg)
    live = fc._read(fc.LIVE_CORPUS)
    check("add materializes live corpus from seed (carries seed entries)",
          live and len(live["entries"]) == len(SEED["entries"]) + 1)
    check("added entry is present and findable",
          fires("the migration silently dropped rows.", corpus=fc.load_corpus()))

    check("duplicate add is rejected",
          "already present" in fc.add("the migration silently dropped rows", "MONITION"))
    check("invalid label is rejected", "invalid label" in fc.add("x y z", "BOGUS"))

    # demerit decays weight toward the floor; credit lifts it back.
    def weight_of(phrase):
        for e in fc._read(fc.LIVE_CORPUS)["entries"]:
            if e["phrase"].lower() == phrase.lower():
                return e["weight"]
        return None

    p = "the migration silently dropped rows"
    check("fresh entry weight is 1.0", weight_of(p) == 1.0)
    fc.demerit(p)
    check("one demerit -> 0.5", weight_of(p) == 0.5)
    fc.demerit(p); fc.demerit(p); fc.demerit(p); fc.demerit(p)  # noise now 5
    check("five demerits prune below floor", weight_of(p) < fc.WEIGHT_FLOOR)
    check("pruned added entry stops firing",
          not fires("the migration silently dropped rows.", corpus=fc.load_corpus()))
    fc.credit(p); fc.credit(p); fc.credit(p)  # helpful 3, noise 5
    check("credit lifts weight back above floor", weight_of(p) > fc.WEIGHT_FLOOR)

    check("demerit on absent phrase is a no-op message",
          "no corpus entry" in fc.demerit("nothing matches this phrase at all"))

    # Corrupt live corpus -> load_corpus falls back to the seed, never raises.
    fc.LIVE_CORPUS.write_text("{ not valid json", encoding="utf-8")
    fallback = fc.load_corpus()
    check("corrupt live corpus falls back to seed",
          fallback["entries"] and len(fallback["entries"]) == len(SEED["entries"]))


if failures:
    print("FAIL:")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
print(f"ok — flag_corpus behavioral tests passed")
