#!/usr/bin/env python3
"""Machinery-integration eval canary (layer-1) — CMS Phase 2.

A weekly headless integration check. **Programmatic assertions only — no LLM
judge.** It catches wiring/config regressions (an unwired hook, a broken
bootstrap, a dead routing path); it does NOT catch vendor-model regressions —
judgment-band evaluation is a later increment, not this layer.

Fidelity — option (B) of docs/decisions/2026-07-03-eval-canary-fidelity.md: each
task asserts wiring DECLARATIVELY (settings.json / git config actually declare the
machinery) AND behavior DIRECTLY (the script/CLI produces the right output on a
synthetic payload). There is no live `claude -p` run: the harness trusts Claude
Code to dispatch what settings.json declares — it does not re-test the harness's
own hook dispatcher, and it stays deterministic and model-insensitive by design.

Tasks:
  bootstrap       a scratch fork (a local clone, bootstrapped hermetically) →
                  `--doctor` reports 0 fail with git hooks armed and the store live.
  craft_reminder  settings.json declares the PreToolUse craft_reminder hook AND the
                  script injects on governed material / stays silent otherwise.
  mine_routing    the monition routing plumbing round-trips a planted lesson through
                  a scratch store with the expected kind/reach.

Debounce: per-task consecutive-failure counts persist in a state file; an ALERT
(exit 1) fires only when a task fails TWICE consecutively — one flake is swallowed.

Usage:
  python tools/eval_canary.py [--json] [--state PATH] [--only TASK[,TASK...]]

Exit: 0 = all tasks PASS/SKIP, or a task's first (debounced) failure.
      1 = an ALERT fired (a task failed twice consecutively).

Schedule weekly; the cron recipe lives in the decision doc above. The harness is
self-contained and hermetic — a run touches only temp dirs, never the real store.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"


class Result:
    def __init__(self, name, status, detail):
        self.name = name
        self.status = status
        self.detail = detail

    def as_dict(self):
        return {"task": self.name, "status": self.status, "detail": self.detail}


# ---- pure helpers (unit-tested; no I/O) -----------------------------------

DOCTOR_SUMMARY = re.compile(r"(\d+)\s+pass\D+(\d+)\s+warn\D+(\d+)\s+fail")


def parse_doctor(stdout):
    """Extract (pass, warn, fail) counts and the set of PASSing check names from
    `bootstrap.sh --doctor` output. `doctor()` always exits 0, so the summary line
    — not the exit code — is ground truth."""
    m = DOCTOR_SUMMARY.search(stdout)
    counts = {"pass": None, "warn": None, "fail": None}
    if m:
        counts = {"pass": int(m.group(1)), "warn": int(m.group(2)), "fail": int(m.group(3))}
    passing = set(re.findall(r"^\s*PASS\s+(\S+)", stdout, re.MULTILINE))
    return {"counts": counts, "passing": passing}


def craft_reminder_wired(cfg):
    """True iff settings.json declares craft_reminder.py inside a PreToolUse hook
    whose matcher covers Edit/Write. This is the declarative half that catches an
    *unwired* hook — the exit-criterion regression."""
    for entry in (cfg.get("hooks", {}) or {}).get("PreToolUse", []) or []:
        matcher = entry.get("matcher", "") or ""
        if "Edit" not in matcher and "Write" not in matcher:
            continue
        for hook in entry.get("hooks", []) or []:
            if "craft_reminder.py" in (hook.get("command", "") or ""):
                return True
    return False


def is_due(last_run, interval_days, now):
    """True if a sweep is due: never run before (last_run is None), or at least
    interval_days have elapsed since. The cadence gate for callers like /housekeep,
    which invoke the canary every pass but only want it to actually run weekly."""
    if last_run is None:
        return True
    return (now - last_run) >= interval_days * 86400


def debounce(prev_state, results):
    """Given the prior per-task consecutive-failure counts and this run's results,
    return (new_state, alert_names). A task alerts once its streak reaches 2; any
    non-FAIL result resets its streak."""
    new_state = dict(prev_state)
    alerts = []
    for r in results:
        if r.status == FAIL:
            new_state[r.name] = new_state.get(r.name, 0) + 1
            if new_state[r.name] >= 2:
                alerts.append(r.name)
        else:
            new_state[r.name] = 0
    return new_state, alerts


# ---- environment isolation -------------------------------------------------

def _hermetic_env(home):
    """A child-process env that cannot reach the real store/state: HOME and
    XDG_STATE_HOME redirected into a temp dir, hub env vars stripped. PATH is kept
    (monition resolves via its absolute ~/.local/bin entry), so install_monition
    still short-circuits on the already-present CLI."""
    env = dict(os.environ)
    env["HOME"] = str(home)
    env["XDG_STATE_HOME"] = str(Path(home) / ".local" / "state")
    for k in ("MONITION_STORE", "CMS_LANDING_ZONE", "MONITION_EMBED_DAEMON",
              "MONITION_SQL_SERVER"):
        env.pop(k, None)
    return env


def _run(cmd, timeout=120, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, **kw)


def _indent(text, prefix="      | "):
    return "\n".join(prefix + line for line in text.rstrip().splitlines())


# ---- tasks (live I/O) ------------------------------------------------------

def task_bootstrap():
    """Bootstrap a fresh local clone hermetically, then assert `--doctor` is clean
    (0 fail) with git hooks armed and the store live. Exercises bootstrap.sh's
    hook-arming and store-init — the surface a fork regression would break."""
    if not shutil.which("git"):
        return Result("bootstrap", SKIP, "git not on PATH")
    if not (REPO / "bootstrap.sh").exists():
        return Result("bootstrap", FAIL, "bootstrap.sh missing from repo")
    tmp = Path(tempfile.mkdtemp(prefix="cms-canary-boot-"))
    try:
        fork = tmp / "fork"
        home = tmp / "home"
        home.mkdir()
        clone = _run(["git", "clone", "--quiet", "--local", "--no-hardlinks",
                      str(REPO), str(fork)], timeout=120)
        if clone.returncode != 0:
            return Result("bootstrap", FAIL, "git clone failed: " + clone.stderr.strip()[:300])
        env = _hermetic_env(home)
        boot = _run(["bash", "bootstrap.sh"], cwd=str(fork), env=env, timeout=300)
        if boot.returncode != 0:
            return Result("bootstrap", FAIL,
                          "bootstrap.sh exited {}:\n{}".format(boot.returncode,
                                                               _indent(boot.stderr[-1500:] or boot.stdout[-1500:])))
        doc = _run(["bash", "bootstrap.sh", "--doctor", str(fork)], cwd=str(fork),
                   env=env, timeout=120)
        parsed = parse_doctor(doc.stdout)
        failc = parsed["counts"]["fail"]
        problems = []
        if failc is None:
            problems.append("could not parse doctor summary")
        elif failc != 0:
            problems.append("{} doctor fail(s)".format(failc))
        if "githooks" not in parsed["passing"]:
            problems.append("git hooks not armed (githooks not PASS)")
        if "store" not in parsed["passing"]:
            problems.append("store not live (store not PASS)")
        if problems:
            return Result("bootstrap", FAIL,
                          "; ".join(problems) + "\n" + _indent(doc.stdout))
        return Result("bootstrap", PASS,
                      "scratch fork: {} pass / {} warn / 0 fail, hooks armed, store live".format(
                          parsed["counts"]["pass"], parsed["counts"]["warn"]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def task_craft_reminder():
    """Declarative: settings.json wires craft_reminder into a PreToolUse Write|Edit
    hook. Behavioral: it injects on a governed path and stays silent on an
    ungoverned one. A unique session_id sidesteps the per-session firing marker."""
    problems = []
    settings = REPO / ".claude" / "settings.json"
    try:
        cfg = json.loads(settings.read_text())
    except Exception as e:
        return Result("craft_reminder", FAIL, "settings.json unreadable: {}".format(e))
    if not craft_reminder_wired(cfg):
        problems.append("craft_reminder.py not wired into a PreToolUse Write|Edit hook")

    script = REPO / "tools" / "craft_reminder.py"
    sid = "canary-" + uuid.uuid4().hex
    markers = []
    try:
        pos = _run(["python3", str(script)], timeout=30, input=json.dumps(
            {"tool_input": {"file_path": "docs/road.md"}, "session_id": sid + "-pos"}))
        injected = False
        try:
            injected = bool(json.loads(pos.stdout).get("hookSpecificOutput", {}).get("additionalContext"))
        except Exception:
            injected = False
        if not injected:
            problems.append("no injection on governed edit (docs/road.md)")

        neg = _run(["python3", str(script)], timeout=30, input=json.dumps(
            {"tool_input": {"file_path": "src/app.js"}, "session_id": sid + "-neg"}))
        if neg.stdout.strip():
            problems.append("injection fired on ungoverned edit (src/app.js)")
    finally:
        # Clean the per-session markers this task may have created.
        for suffix in ("-pos", "-neg"):
            for key in ("docs", "decisions"):
                try:
                    os.remove("/tmp/craft_reminder_{}{}_{}".format(sid, suffix, key))
                except OSError:
                    pass

    if problems:
        return Result("craft_reminder", FAIL, "; ".join(problems))
    return Result("craft_reminder", PASS,
                  "wired + injects on governed / silent on ungoverned")


def task_mine_routing():
    """Round-trip a planted lesson through a scratch monition store: init → add →
    list → dump, asserting the row surfaces with the expected kind and reach. Tests
    the routing PLUMBING, not an LLM's routing judgment. The plant uses reach=general
    (a non-default, collision-free token) so a 'reach flag ignored → defaulted to
    project' bug is actually caught — a project plant would silently match the default."""
    if not shutil.which("monition"):
        return Result("mine_routing", SKIP, "monition CLI not on PATH (minimal fork)")
    tmp = Path(tempfile.mkdtemp(prefix="cms-canary-mine-"))
    try:
        store = str(tmp / "store")
        init = _run(["monition", "init-store", store], timeout=60)
        if init.returncode != 0:
            return Result("mine_routing", FAIL, "init-store failed: " + init.stderr.strip()[:300])
        marker = "canary-planted-" + uuid.uuid4().hex[:8]
        add = _run(["monition", "add", "--store", store,
                    "--kind", "gotcha", "--trigger-kind", "edit_path",
                    "--trigger-spec", "tools/eval_canary.py",
                    "--one-liner", marker, "--reach", "general"], timeout=60)
        if add.returncode != 0:
            return Result("mine_routing", FAIL, "add failed: " + add.stderr.strip()[:300])

        # kind + trigger routing: the list line reads `[N] kind/trigger_kind(spec) one-liner`.
        lst = _run(["monition", "list", "--store", store], timeout=60)
        line = next((ln for ln in lst.stdout.splitlines() if marker in ln), None)
        if line is None:
            return Result("mine_routing", FAIL,
                          "planted row not surfaced by 'monition list':\n" + _indent(lst.stdout))
        if "gotcha/edit_path" not in line:
            return Result("mine_routing", FAIL,
                          "planted row mis-routed by kind/trigger: {!r}".format(line.strip()))

        # reach: not shown by `list`; read it from the SQL dump the row lands in.
        dump = _run(["monition", "dump", "--store", store], timeout=60)
        if dump.returncode != 0:
            return Result("mine_routing", FAIL, "dump failed: " + dump.stderr.strip()[:300])
        try:
            sql = (Path(store) / "dump.sql").read_text()
        except OSError as e:
            return Result("mine_routing", FAIL, "dump.sql unreadable: {}".format(e))
        row = next((ln for ln in sql.splitlines() if marker in ln), "")
        if "'general'" not in row:
            return Result("mine_routing", FAIL,
                          "reach not persisted as 'general' (routing plumbing dropped the flag)")
        return Result("mine_routing", PASS,
                      "planted lesson round-trips scratch store (init→add→list→dump), "
                      "kind=gotcha reach=general")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


TASKS = {
    "bootstrap": task_bootstrap,
    "craft_reminder": task_craft_reminder,
    "mine_routing": task_mine_routing,
}


# ---- state + runner --------------------------------------------------------

def default_state_path():
    base = os.environ.get("XDG_STATE_HOME") or os.path.join(
        os.path.expanduser("~"), ".local", "state")
    return os.path.join(base, "cms-canary", "state.json")


def load_state(path):
    """Full persisted state: {'streaks': {task: consecutive_fails}, 'last_run': epoch|None}."""
    try:
        with open(path) as fh:
            data = json.load(fh)
    except Exception:
        return {"streaks": {}, "last_run": None}
    streaks = {k: int(v) for k, v in (data.get("streaks") or {}).items()}
    last = data.get("last_run")
    return {"streaks": streaks, "last_run": float(last) if last is not None else None}


def save_state(path, streaks, last_run):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump({"streaks": streaks, "last_run": last_run}, fh, indent=2)
    os.replace(tmp, path)


def main(argv=None):
    ap = argparse.ArgumentParser(description="CMS machinery-integration eval canary")
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    ap.add_argument("--state", default=default_state_path(),
                    help="debounce/cadence state file (default: XDG_STATE_HOME/cms-canary/state.json)")
    ap.add_argument("--only", help="comma-separated subset of tasks to run")
    ap.add_argument("--if-due", type=float, metavar="DAYS", default=None,
                    help="self-gate: run only if >= DAYS since the last run, else a silent "
                         "no-op (exit 0, no output). For cadence callers like /housekeep.")
    args = ap.parse_args(argv)

    selected = list(TASKS)
    if args.only:
        selected = [t.strip() for t in args.only.split(",") if t.strip()]
        unknown = [t for t in selected if t not in TASKS]
        if unknown:
            ap.error("unknown task(s): {} (known: {})".format(
                ", ".join(unknown), ", ".join(TASKS)))

    state = load_state(args.state)
    now = time.time()
    if args.if_due is not None and not is_due(state["last_run"], args.if_due, now):
        if args.json:
            print(json.dumps({"skipped": "not_due", "last_run": state["last_run"]}))
        return 0  # not due — stay silent; the cadence caller surfaces nothing

    results = [TASKS[name]() for name in selected]
    prev = state["streaks"]
    new_state, alerts = debounce(prev, results)
    # Preserve streaks for tasks not run this pass; stamp the run time for the cadence gate.
    merged = dict(prev)
    merged.update(new_state)
    save_state(args.state, merged, last_run=now)

    if args.json:
        print(json.dumps({
            "results": [r.as_dict() for r in results],
            "streaks": {r.name: merged.get(r.name, 0) for r in results},
            "alerts": alerts,
        }, indent=2))
    else:
        print("CMS machinery-integration eval canary\n")
        for r in results:
            streak = merged.get(r.name, 0)
            tag = ""
            if r.status == FAIL:
                tag = "  ALERT (2+ consecutive)" if r.name in alerts else \
                      "  (1st failure — debounced)"
            print("  {:<5} {:<15} {}{}".format(r.status, r.name, r.detail, tag))
        print()
        if alerts:
            print("  ALERT: {} — a human should look now.".format(", ".join(alerts)))
        else:
            print("  no alert ({} task(s) run)".format(len(results)))

    return 1 if alerts else 0


if __name__ == "__main__":
    sys.exit(main())
