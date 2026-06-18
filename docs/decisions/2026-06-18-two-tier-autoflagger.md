# 2026-06-18 · Two-tier autoflagger — agent-as-judge, hook-as-backstop

**Decision.** Auto-capture flag-worthy moments into `~/.claude/session-flags.md` (the
file `/flag` writes and `/mine-session` drains) via two tiers:

- **Tier 1 — judge = the agent, via CLAUDE.md.** A standing rule has the agent self-flag
  inline when a response hits a flag-worthy moment (admitted error, recurring gotcha,
  "make this a rule"). The semantic judgment runs in the model already in the loop.
- **Tier 2 — backstop = `tools/autoflag.py`, a Stop hook.** Regex-only (no LLM call),
  fail-open, dedup-per-snippet. Catches the one keyword-detectable class — admitted-error
  phrasing (`mine-session` 0b's pattern) — that tier 1 might skip. Wired live in this
  repo's `.claude/settings.json`; added to `bootstrap.sh`'s portable-tools copy list so
  forks inherit it (wiring stays per-environment, exactly like `craft_reminder.py`).

**Why not the originally-requested "in-hook LLM RAG on every response."** That spins up a
*separate* model call per turn to score flaggability — constant cost + latency, and a
worse judgment (it reads a transcript snippet; the agent has full context). It duplicates,
at a price, a judgment tier 1 makes for free. This mirrors the repo's existing split
(`craft_reminder.py`: "the harness guarantees firing, the agent supplies the judgment").
The Haiku-in-hook judge remains a documented upgrade *only* if flagging independent of
agent compliance is later wanted.

**Why a hook can't "run the skill."** Hooks are shell commands outside the model loop;
there's no primitive to make the agent invoke `/flag`. It isn't needed — `/flag`'s entire
effect is one append to `session-flags.md`, which the hook does directly. The only
model-re-entry lever (`Stop` → `{"decision":"block"}`) was rejected: it forces an extra
round-trip every flaggable turn.

**Tier-2 routing.** Admitted error → `GOVERNANCE` (matches `mine-session` 0b, which treats
admitted mistakes as governance-change candidates).

**How forks get both tiers.** By forking. The tier-1 rule lives in this repo's own
`CLAUDE.md` and the tier-2 script in `tools/` — a fork inherits both unchanged by forking
(§No profiles, §What CMS is). This is the right channel *for forks*: a fork keeps CMS's
own `CLAUDE.md`, not the starter template.

**Open (separate channel, not done).** `starter/CLAUDE.md.template` is the baseline
`CLAUDE.md` a *template-scaffolded* project starts from — and it legitimately carries
baseline behavioral rules (Context hygiene, Execution discipline, etc.), not just identity
placeholders. So seeding the tier-1 judge rule there is a real option *if* we want
projects scaffolded from the template to get autoflagging by default — it is **not** the
retired payload pattern (that retired the generator copying single-sourced *machinery*
into N projects; `CLAUDE.md` rules are per-project-owned by design). It simply doesn't
affect forks. Deferred as an explicit choice, not a forbidden one.

**Not done (optional, gated).** A `method/` note documenting the flag pipeline end-to-end
— cold context loaded on demand, not a payload — if the pipeline warrants it. Goes through
the "never codify silently" gate before writing.
