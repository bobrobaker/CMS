---
name: housekeep
description: Sweep the system's transient stores for orphaned or stale residue (sessions, flag files, handoffs, confer threads, worktrees, upstream-candidates, takeaway rows, skill-farm drift) — auto-reap the mechanical-and-safe class, propose the rest. Use when the user invokes /housekeep, says "do housekeeping", "tidy up", "check for orphaned/stale things", or as a daily cadence pass. Silent when clean. NOT a doc/summary-drift audit (that's the broader Tier-3 pass) and NOT a mining/codify pass.
---

# housekeep

You are running one on-demand sweep over the transient stores this system leaves
behind, reporting what has gone stale or orphaned and reaping only what is safe to reap
without a decision. The design mirrors the Tier-3 audit philosophy in
`method/tooling.md`: **report and propose; auto-apply only the mechanical class** — and
apply that same write-permission split to this skill itself.

Two invariants, both load-bearing:

- **Fail open.** Every probe is independent. A missing directory, an unreadable file, a
  non-git cwd, or a tool that errors → skip that one category silently and continue.
  Never abort the run, never delete on doubt.
- **Silent when clean.** This is meant to run daily. If every category comes back empty,
  print one line (`✓ housekeep: nothing stale`) and stop. No headers, no empty sections.

## The three tiers

Classify every finding into exactly one:

1. **Auto-reap** — mechanical, safe, *cannot lose information*. Do it, then report it as
   done. Only two things qualify (see F and B below). Nothing else is ever auto-applied.
2. **Propose** — a real change that needs a yes: deletion, archival, running a tool. List
   each with the specific action; act only on confirmation.
3. **Report-only** — surfaced for the user's judgment; this skill takes no action.

## The sweep

Run these probes (each guarded; on any error skip that category). Collect findings, then
present them grouped by tier.

### A — Unwrapped sessions → propose backfill

`archive/backfill.py --dry-run` already computes exactly the set of recent sessions with
no archive summary; do not reinvent that selection. The script lives in the system's
source clone but the session archive is machine-global, so when the current repo isn't
that clone, resolve it through the skill-farm symlink instead of silently skipping:

```bash
root=$(git rev-parse --show-toplevel 2>/dev/null)
[ -f "$root/archive/backfill.py" ] || root=$(readlink -f ~/.claude/skills/housekeep 2>/dev/null | sed 's|/\.claude/skills/housekeep$||')
[ -f "$root/archive/backfill.py" ] && python3 "$root/archive/backfill.py" --dry-run 2>/dev/null
```

If it lists N sessions: **propose** `python3 "$root/archive/backfill.py"` (optionally
`--days`, `--limit`). Don't run it unprompted — it makes model calls and costs tokens.

### B — Orphaned flag files

Flag files live in a machine-global dir shared by every concurrent session. A file is an
orphan only if its session is **dead** (its id is absent from the live registry
`~/.claude/sessions/*.json`). Never touch a live session's file.

```bash
d=~/.claude/session-flags; reg=~/.claude/sessions
for f in "$d"/*.md; do
  [ -e "$f" ] || continue
  id=$(basename "$f" .md)
  # live if a registry record names this id; indeterminate registry → treat as live
  if [ -d "$reg" ] && ! grep -rqsF "$id" "$reg"/*.json 2>/dev/null; then
    if [ -s "$f" ]; then echo "ORPHAN-NONEMPTY $f"; else echo "ORPHAN-EMPTY $f"; fi
  fi
done 2>/dev/null
```

- `ORPHAN-EMPTY` (dead session, nothing to mine) → **auto-reap**: `rm` it.
- `ORPHAN-NONEMPTY` (dead session, un-mined lessons) → **propose**: run `/mine-session`,
  which drains dead-session files by design. Never `rm` a non-empty flag file here — that
  would silently destroy the lessons the orphan-safety design exists to preserve.

### C — Over-horizon handoffs

Scan `$CMS_LANDING_ZONE/handoffs/` (if set) and `<repo>/handoffs/`, top level only
(exclude `archive/`). A handoff has `status: open` + a `created:` date. **Exclude confer
threads** (`type: confer` frontmatter — those are category D).

```bash
for base in "${CMS_LANDING_ZONE:+$CMS_LANDING_ZONE/handoffs}" "$(git rev-parse --show-toplevel 2>/dev/null)/handoffs"; do
  [ -d "$base" ] || continue
  for f in "$base"/*.md; do
    [ -e "$f" ] || continue
    grep -qs '^type: confer' "$f" && continue
    grep -qs '^status: open' "$f" || continue
    cr=$(grep -m1 '^created:' "$f" | sed 's/created:[[:space:]]*//')
    echo "OPEN $f created=$cr"
  done
done 2>/dev/null
```

Horizon depends on kind (`handoff/SKILL.md`): a **carry-forward** handoff is stale in
**days**; a **bridge** handoff is patient (~2 weeks). The frontmatter rarely says which,
so use conservative buckets and let the user resolve:

- `created:` > ~3 days → **propose** review ("carry-forward may have missed its pick-up").
- `created:` > ~14 days → **propose** as stale regardless of kind.

Offer the resolutions from `handoff/SKILL.md` §Lifecycle for each, don't pick one —
delete (work died) / promote to durable doc (became a runbook) / route the work into the
target repo's `road.md`/`debt.md` then delete the envelope (real but unstarted — a
handoff is a transfer envelope, not a backlog) / do the pick-up (genuinely imminent).

### D — Stale confer threads

Confer threads (`type: confer`, named `YYYY-MM-DD-confer-<slug>.md`) live in `handoffs/`
and archive to `handoffs/archive/` with an `archived:` stamp. A thread open ≳1 week means
the decision stopped mattering or was made out-of-band.

```bash
for base in "${CMS_LANDING_ZONE:+$CMS_LANDING_ZONE/handoffs}" "$(git rev-parse --show-toplevel 2>/dev/null)/handoffs"; do
  [ -d "$base" ] || continue
  for f in "$base"/*.md; do
    [ -e "$f" ] || continue
    grep -qs '^type: confer' "$f" || continue
    grep -qs '^archived:' "$f" && continue
    age=$(( ( $(date +%s) - $(stat -c %Y "$f") ) / 86400 ))
    [ "$age" -ge 7 ] && echo "STALE-CONFER $f age=${age}d"
  done
done 2>/dev/null
```

**Propose**, per `confer/SKILL.md` close-out: confirm the resolution actually landed in the
owning repo's spec/roadmap/decision shelf, then move the thread to `handoffs/archive/`
(add `archived: YYYY-MM-DD`). Never auto-archive — landing the outcome first is a judgment
call.

### F — Abandoned git worktrees

```bash
git worktree prune --dry-run 2>/dev/null   # admin entries whose dirs are already gone
git worktree list 2>/dev/null              # everything currently registered
```

- Anything `prune --dry-run` reports → **auto-reap**: `git worktree prune` (it only drops
  bookkeeping for directories that no longer exist — no working files are touched).
- A still-present worktree that looks abandoned (old, on a throwaway branch, no uncommitted
  changes — typical `/spawn` or Agent `isolation:worktree` leftovers) → **propose**
  removal. Don't remove a worktree with uncommitted changes without flagging that.

### E — Queued upstream-candidates

Read the **canonical shared queue** (CLAUDE.md's mirror-back rule): the landing-zone hub
when set — every fork appends there, so one read surfaces *all* forks' open candidates —
else this repo's own. Count only **open** candidates (dated `YYYY-MM-DD |` lines), not the
struck-provenance comment blocks a resolved sweep leaves behind:

```bash
q="${CMS_LANDING_ZONE:+$CMS_LANDING_ZONE/handoffs/upstream-candidates.md}"
[ -n "$q" ] || q="$(git rev-parse --show-toplevel 2>/dev/null)/handoffs/upstream-candidates.md"
[ -f "$q" ] && grep -cE '^[0-9]{4}-[0-9]{2}-[0-9]{2} \|' "$q"
```

**Report-only.** A non-zero count means teaching-surface proposals are waiting: surface
"N open upstream-candidate(s) queued — mirror-back due" (on a shared hub these span every
fork, which is the whole point — the cross-fork view a per-repo scan used to miss).
Resolving them — proposing each through the consent gate and striking the landed ones — is
the mirror-back sweep's job, not this skill's.

### G — Monition store: rate the backlog, then audit rows

Three clauses run in order. **G1** supplies retro ratings over the traffic head; **G2**
audits rows on precision (`monition report`); **G3** audits them on measured cost
(`monition ledger`). G2/G3's `noise`/silence signals are starved without a supply of
ratings, so the supply pass comes first. Skip the whole section silently if `monition`
isn't installed or no store is joined.

#### G1 — retro rating supply (weekly)

The retro analog of mine-session's live rating pass (`method/takeaway-store.md` §Rating):
an evidence-gated LLM pass that produces `retro` relevance labels from stored firing
excerpts, feeding G2 and the fire/suppress gate the eval data the live pass alone can't
keep up with. The store owns the sampler, the priority order, and the hardwired `retro`
provenance; this clause owns only **cadence, budget, and consent**.

Self-gate on a weekly cadence — invoke every run, let the stamp decide whether it is due:

```bash
d="${XDG_STATE_HOME:-$HOME/.local/state}/cms"; stamp="$d/monition-retro-rating.last"
out=/tmp/retro-backlog.jsonl; rm -f "$out"                 # never re-rate a stale export
if command -v monition >/dev/null 2>&1 && \
   { [ ! -f "$stamp" ] || [ -z "$(find "$stamp" -mtime -7 2>/dev/null)" ]; }; then
  monition export-firings --rows-by unrated-priority --sample-per-row 8 > "$out" 2>/dev/null
fi
[ -s "$out" ] || :   # empty/absent → not due, or nothing unrated → skip G1 silently
```

When `$out` has rows, run the pass:

- **Budget** — ~30–50 firings across the highest-`rating_priority` rows (the sampler
  orders them head-not-tail; you own only how many). Raise `--sample-per-row` toward 8–10
  for rows near the fire/suppress boundary, where a small sample misjudges a
  borderline-helpful row.
- **Rate — evidence-gated, exactly as the live pass.** For each record decide
  `helpful|noise` from its `situation` excerpt + `one_liner` alone — this is retro, you
  did not live the firing, so judge **relevance**, not utility. Cite the excerpt evidence
  in one line; set `outcome: null` to abstain on anything the excerpt can't support. **No
  evidence → abstain**, and surface the abstention rate — a high one means the excerpts
  are too thin to rate and the store's excerpt capture (not this pass) is what needs
  widening. Rate under the ambient model the sweep already runs; name no model — a
  hardcoded one only rots, and inheriting it keeps retro and live labels one labeler.
- **Consent — one batch, lighter than rows.** Present the proposed labels as a single
  accept with per-line veto — a rating is reversible eval data, not durable governance, so
  it earns the same cheap gate mine-session's rating pass uses.
- **Apply + stamp** — on accept:

  ```bash
  monition rate --from-export "$out"    # provenance auto-retro; already-rated skipped; unknown id fails loud
  monition commit -m "housekeep: retro rating backlog pass [rated_by: <the model id you are running under>]" 2>/dev/null
  mkdir -p "$d" && date -Is > "$stamp"
  ```

  Stamp the **ambient model you ran under** into that commit message (`[rated_by:
  <model-id>]`). The labeler model is recorded nowhere else — not on the firing rows (their
  `model` is the *fire-time* model, not the rater) — so this commit line is the durable
  provenance of *which* model produced these retro labels. It records the runtime model
  without pinning one in this doc, and is the deliberate substitute for a `rated_by_model`
  schema column (`docs/decisions/2026-07-05-housekeep-retro-rating-supply.md`).

**Seam guardrail.** G1 produces `retro` labels and nothing else — it must never touch the
fire/suppress gate or its held-out test set. Retro is asymmetric *training* supervision
(the rater saw only the prompt, so it measures relevance, not lived utility); the
relevance test set stays **live-only**, and retraining the gate on retro is deferred until
volume accrues under an evidenced weighting scheme.

#### G2 — rows due for audit

The audit cadence in `method/takeaway-store.md`: noise-heavy rows want a narrower
trigger or retirement; rows that never fire want a wider spec or folding into a doc.
`monition report` already computes the per-row read (fires / helpful / noise /
precision); do not reinvent that selection.

```bash
monition report 2>/dev/null
```

From its table, surface as **propose** only the clear cases:

- active rows with ≥3 `noise` and 0 `helpful` ratings → propose a narrower
  `trigger_spec` or `monition retire`;
- active rows with 0 firings ever → two-stage: not yet widened → propose widening
  the spec or folding into a doc; widened in a prior pass (`monition show <id>`
  mutation history) and still silent → propose `monition retire`. **Exempt
  rare-hazard rows** (trigger names a rare-but-costly event — force-push,
  destructive migration, credential handling): disuse is not staleness when the
  base rate is low.
- skip rows carrying a `[pinned]` marker in `full_content` (interim convention
  until the store grows a first-class pin), and when the user declines a §G
  proposal, offer to add the marker — re-proposing the same retirement weekly
  trains rubber-stamping, which erodes the consent gate this section runs on.

Every row action is a consented mutation (`monition retire`, `monition set-trigger`,
`monition calibrate --apply`) — propose, never apply. Skip the category silently if
`monition` isn't installed or no store is joined.

#### G3 — value-ledger cost pass (the cost side of the audit)

G2's `monition report` ranks rows by precision; it says nothing about **how much** a
low-precision row costs. `monition ledger --top 5` adds the measured token-cost dimension
and pre-computes the retire/tighten shortlist: its `CANDIDATE` flag fires on
`net ≥ 300 AND prec < 0.50 AND rated ≥ 3` — a row that is both expensive and
low-precision. The ledger is **advisory and read-only** (it feeds no automated decision);
skip silently if `monition` isn't installed or no store is joined.

```bash
monition ledger --top 5 2>/dev/null
```

Surface the flagged rows as **propose** for a human keep / retire / tighten call — never
act; every row mutation is consented (`monition retire`, `monition set-trigger`), exactly
as G2. Two disciplines gate the reading:

- **Batch-noise skepticism.** A high noise% is a retire signal only if the noise is the
  *row's* fault. A row whose noise is mostly batch-borne — one broad session-opening prompt
  firing a whole dump of rows, none of which applied (the batch-noise discount) — earns
  **"leave + note"**, not retirement: that dilution is the batch's, and the row may still be
  precise on its genuine trigger. Discount before you propose.
- **Keep-verdict → signature hook (targeted only).** A **KEEP** on a row despite high
  measured cost is a load-bearing claim — "this row earns its tokens." Make the claim
  monitored rather than merely asserted: **prompt** (never mandate) authoring a violation
  signature for *that* row so the recall sweep can catch the failure it warns about actually
  happening —
  `monition set-signature <id> '{"kind": "transcript_regex", "pattern": "<the failure event>"}'`.
  Same test as a mine-time signature (`method/takeaway-store.md` §Rating): only where the
  failure is a machine-detectable transcript event, and probe the failure itself, never the
  topic (a topic-shaped pattern self-matches). Most keeps won't qualify — under-match or
  skip; it's a targeted prompt on the row you chose to keep, not a blanket sweep.

### H — Global skill-farm drift

`~/.claude/skills/` is a symlink farm: each entry must be a symlink into a source repo
(this clone, or the author's dotfiles). Two drift modes rot silently — a skill authored
as a **real directory** here is tracked by no repo and lost on the next reinstall; a
**dangling symlink** means its source moved or was deleted. Skip the whole category if
the farm doesn't exist (a fork that never ran `bootstrap --link-global`).

```bash
farm=~/.claude/skills
if [ -d "$farm" ]; then
  for e in "$farm"/*; do
    [ -e "$e" ] || [ -L "$e" ] || continue
    if [ ! -L "$e" ]; then echo "LOOSE $e"          # real file/dir — tracked by nothing
    elif [ ! -e "$e" ]; then echo "DANGLING $e -> $(readlink "$e")"  # source gone
    fi
  done 2>/dev/null
fi
```

Both are **propose**, never auto-reap — each needs a judgment call and deleting either
loses information:

- `LOOSE` → propose: give it a tracked home, then symlink back. The home depends on the
  skill — forkable machinery goes in this clone's `.claude/skills/`; a personal or
  adviser-coupled skill goes in the author's dotfiles. Ask which; don't guess and don't
  `rm` it (that destroys the only copy).
- `DANGLING` → propose: repoint the link to the source's new location, or remove it if
  the skill was retired. Never assume "delete" — a moved source wants a repoint.

### I — Unbounded hook sinks

Anything a hook appends per-event grows forever unless the writer bounds it — a
write-only log with no reader is invisible until it's huge. The writer owning its own
rotation/reap is the real fix; this probe is the net that catches sinks wired without
one. Flag, don't delete (the file may be someone's audit trail):

```bash
find ~/.claude -maxdepth 3 \( -name "*.jsonl" -o -name "*.log" \) -size +10M 2>/dev/null
find ~/.local/state -maxdepth 3 \( -name "*.jsonl" -o -name "*.log" \) -size +10M 2>/dev/null
```

Any hit → **propose**: add rotation/TTL in the writer (preferred), or truncate after
confirming nothing reads it.

### J — Aged session transcripts

`~/.claude/projects/` accrues one JSONL per session (subagents included) with no
harness-side retention — the dominant unbounded disk item. A transcript whose session
is already wrapped is prunable after a horizon; the raw JSONL is the archive ladder's
deep-retrieval rung, so propose, never auto-delete.

Age by the transcript's **first recorded timestamp**, never file mtime — background
indexing touches these files, so every mtime reads recent regardless of true age:

```bash
python3 - <<'EOF' 2>/dev/null
import json, os, glob, datetime
cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=60)
old, total = [], 0
for p in glob.glob(os.path.expanduser("~/.claude/projects/*/*.jsonl")):
    total += 1
    try:
        with open(p) as f:
            for _ in range(10):  # first records (mode/permission) carry no timestamp
                d = json.loads(f.readline())
                ts = d.get("timestamp")
                if ts:
                    if datetime.datetime.fromisoformat(ts.replace("Z", "+00:00")) < cutoff:
                        old.append(p)
                    break
    except Exception:
        pass
print(f"{len(old)} of {total} transcripts >60d by first-record timestamp")
EOF
du -sh -- ~/.claude/projects 2>/dev/null | cut -f1
```

A large count → **propose** pruning those transcripts, excluding any session probe
A's `--dry-run` still lists as unwrapped (wrap first, then prune). State in the
proposal that a pruned session keeps its archive summary + index entry but loses the
raw-text retrieval rung.

### K — Machinery-integration eval canary (weekly, CMS repos)

CMS-machinery repos ship `tools/eval_canary.py` — an integration canary asserting the
machinery's cross-surface wiring (bootstrap→`--doctor`, craft-reminder injection,
mine-session routing) is intact. It self-gates on a weekly cadence, so this pass invokes it
every run and lets the harness decide whether it is actually due:

```bash
root="$(git rev-parse --show-toplevel 2>/dev/null)"   # anchor to repo root, not cwd
if [ -n "$root" ] && [ -f "$root/tools/eval_canary.py" ]; then
  out="$(python3 "$root/tools/eval_canary.py" --if-due 7 2>&1)"; rc=$?
  [ "$rc" -ne 0 ] && printf '%s\n' "$out"   # surface ONLY on a non-zero exit
fi
```

- **File absent** (not a CMS-machinery repo) → skip the category silently.
- **Not due** (< 7 days since the last sweep) → the harness prints nothing; surface nothing.
- **Due + every task passes** → clean; stay silent (housekeep's default).
- **Non-zero exit** → **propose**: a task failed twice consecutively (an ALERT — a real
  wiring/config regression) or the harness itself errored. Surface its output verbatim so the
  failing task is named. This is a health check, not a reap — nothing is deleted.

## Output

Group findings under the three tier headings, most actionable first. Auto-reaps are
already done — state what was reaped. Proposes are a numbered list the user can accept
selectively. If nothing fired in any category, the single silent-when-clean line
instead.

Whatever the outcome — findings or clean — stamp the run so `/eos` can surface
staleness (its hygiene glance reads this file's mtime):

```bash
d="${XDG_STATE_HOME:-$HOME/.local/state}/cms"
{ mkdir -p "$d" && date -Is > "$d/housekeep.last"; } 2>/dev/null || true
```

## Anti-goals

- **Not an auto-deleter.** The only unattended actions are the two mechanical reaps (empty
  dead-session flag files; `git worktree prune` of already-gone dirs). Every other change
  is proposed.
- **Doesn't reimplement its dependencies.** It *calls* `backfill.py`, points at
  `/mine-session` and the mirror-back sweep — it never duplicates their logic.
- **Not the Tier-3 doc audit.** This reaps orphan/staleness residue. Drift between
  summaries and their sources, merge candidates, and always-on-layer leanness are the
  broader Tier-3 pass, out of scope here.
- **Not a mining pass.** It never reads orphaned flags into the store or codifies anything
  — that needs the judgment `/mine-session` and `/codify` carry.
