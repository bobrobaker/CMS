---
name: mirror-back
description: Drain the upstream-candidates queue — propose each open teaching-surface candidate through the consent gate, apply accepted ones to the canonical corpus, and strike landed lines as dated provenance. Use when the user invokes /mirror-back, says "run the mirror-back sweep" / "drain the upstream candidates" / "resolve the queued candidates", or after /housekeep §E reports open candidates. NOT for queueing a new candidate (that's /codify, or a fork's /mine-session step 6) and NOT the report-only count (that's /housekeep §E).
---

# mirror-back

You are resolving queued teaching-surface proposals into the canonical corpus. Detection
is automatic cadence — `/housekeep` §E counts open candidates and points here — but
**resolution stays manual + consent-gated**
(`docs/decisions/2026-07-05-mirror-back-queue-canonical-location.md`): this skill removes
the toil and the "remember to run it", never the per-candidate judgment. Pulling a lesson
into canonical is a judgment call — does it survive the domain-and-environment strip? —
so **never auto-apply**, even a candidate that looks obviously good.

**Gate first.** Applying a candidate edits the reference implementation's teaching
surfaces (`method/`, `.claude/skills/`, `starter/`, the linter). If the cwd repo doesn't
carry them (`method/` and `starter/` both present), stop with one line: run
`/mirror-back` from the canonical CMS clone.

1. **Resolve the canonical queue** exactly as `/housekeep` §E does — every producer and
   consumer resolves it this way, so a candidate can't be written to one place and swept
   from another:

   ```bash
   q="${CMS_LANDING_ZONE:+$CMS_LANDING_ZONE/handoffs/upstream-candidates.md}"
   [ -n "$q" ] || q="$(git rev-parse --show-toplevel)/handoffs/upstream-candidates.md"
   # open = pipe line | `## ` block heading | unchecked `- [ ]`, MINUS anything marked
   # landed: struck `~~…~~` or tagged `[landed …]`/`[declined …]`/`[resolved …]`.
   grep -nE '^([0-9]{4}-[0-9]{2}-[0-9]{2} \||## |- \[ \] )' "$q" \
     | grep -vE '~~|\[(landed|declined|resolved)'
   ```

   Open candidates come in three shapes — a dated `YYYY-MM-DD | rule | origin` line, a
   `## ` block entry (heading plus its body until the next entry), or an unchecked
   `- [ ]` line; a pipe-only match reads a queue of block entries as empty (2026-08-20).
   Struck-provenance blockquotes are history, not work; the header/format prose is
   neither. Queue absent or zero open candidates → print `✓ mirror-back: queue empty`
   and stop.

2. **Walk each open candidate, oldest first.** Per candidate:
   - Show the line verbatim (date, rule, origin).
   - Locate the teaching surface it targets — a `method/` doc, a skill, a `starter/`
     template, or a linter check. Before editing a skill or `starter/` template, read
     the `method/` doc that governs it (CLAUDE.md rule — e.g. `method/tooling.md` for
     skills). Respect `forkgen` markers: a fork-variant region is edited at the source
     the marker's note names, never at the regenerated copy.
   - Sanity-check routing: a *row-shaped* candidate (trigger + lesson, no teaching-surface
     target) is misrouted — the queue carries teaching-surface proposals only. Propose
     inserting it into the Monition hub (`reach: general`) instead of applying, and
     strike it as `misrouted → monition` once moved.
   - Propose the **concrete edit** — target file plus the actual wording, not a
     paraphrase — with a one-line strip judgment: would another fork be wrong to
     inherit this?
   - **Consent-gate per candidate**: accept / decline / defer.

3. **On accept:** apply the edit, then strike the queue line — move it out of the open
   set into a dated provenance blockquote (strike, never silently delete — the record of
   what landed and where is the queue's audit trail):

   ```
   > **Resolved in the mirror-back sweep YYYY-MM-DD** (removed from queue):
   > - *short handle* — landed in `<target file>` (<what changed>). Origin: <origin>.
   ```

   Extend the same day's existing block rather than opening a second one. For a long
   `## ` block entry, the equivalent in-place strike is allowed instead of relocating the
   whole body: strike the heading (`## ~~…~~`) or tag it `[landed YYYY-MM-DD]` — the
   detection rule in step 1 stops counting it either way.

4. **On decline or defer:** leave the line open, untouched. If a candidate is declined
   *for good* (judged not to survive the strip), offer to strike it with a `declined:`
   verdict in the provenance block instead — consent-gated like an accept — so §E stops
   counting a candidate nobody intends to land.

5. **Close:** one line per outcome — N landed (files touched), N declined, N left open.
   Landed skill edits reach forks on their next `bootstrap --update` / `monition sync`
   (the down direction — `/housekeep` §L watches for forks that lag).

Anti-goals: never auto-apply; never edit the origin fork (the sweep writes to canonical
only — forks receive the change via the down path); never renumber or rewrite open lines
you didn't resolve.
