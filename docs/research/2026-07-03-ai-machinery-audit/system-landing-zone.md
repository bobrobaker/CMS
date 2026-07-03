# System lens — landing-zone vault machinery

The cross-project landing zone (`$CMS_LANDING_ZONE`) is a private knowledge vault; this
public copy reports machinery health only, not vault content. Snapshot: 2026-07-02.

## Operator context (one line, kept abstract here)

The machinery ecosystem serves a portfolio strategy whose lead signal is *designed
evaluations* — rigor, deterministic gates, traceability, regression evidence. That
raises the priority of synthesis Gap 5 (the harness's own missing behavioral eval): the
governance showcase should carry the discipline it advertises.

## Machinery health — measured, not aspirational

- **decisions/** — 6 cross-project decision docs, all June 2026, all referenced from
  project roadmaps (identity-slug canonicalization, replay-runner seam ownership,
  recurrence logging, decision-lifecycle enforcement, fleet propagation of shared
  standards, gating global firing behind the SQL server). Load-bearing, not shelf-ware.
- **handoffs/** — 69 files: 4 open (all dated within days of snapshot), 65 archived.
  Confer threads resolve and archive within ~3 days; no rot in the root. This is the
  strongest hygiene signal in the whole audit.
- **method/** — 1 doc: lesson-routing (v4 at vault, v5 canonical in Monition), the
  routing spec for where mined lessons land, with a `ROUTING_VERSION` parity contract.
  Live (referenced by the mine-session template).
- **tools/** — 8 files, minimal and live: a 26K vault linter wired to pre-commit
  (mechanical invariants: wikilink hygiene, frontmatter, zone consistency; last run at
  snapshot day), inbox sweep/fanout automation, prompts for inbox digestion, transcript
  fetcher.
- **Directives** — 24 scoped governance docs, all recent; the two large `.feedback.md`
  files (18K codify, 76K inbox-digestion) are working notes of real explanation gaps
  being caught and folded back — continuous improvement instrumented, not archives.
- **Monition integration** — hub store config + 11M dump checkpoint; hooks wired at the
  vault level (PreToolUse fire-hook, SessionStart session-brief, UserPromptSubmit
  prompt-hook), logging to a state-dir error log.

## Vault zone health

| Zone | Files | State |
|------|------:|-------|
| Inbox | 0 | clean — actively drained |
| Knowledge | 88 | distilled concept nodes + glossary |
| Active | 23 | living working docs |
| Sources | 42 | curated external references |
| Archive | 76 | dated, tagged session/intake logs |
| Learning | 11 | spaced-repetition mastery cards |

Activity: 13 commits/7 days, 46/30 days at snapshot; pre-commit linter firing on every
commit.

## Assessment

The landing zone is the healthiest component audited: consent-gated writes, prompt
archival, zero inbox backlog, and feedback loops that demonstrably close (logged
explanation gaps → directive updates). Its discipline is the standard the Monition
rating loop (synthesis Gap 1) currently fails to meet — worth noting that the same
operator sustains both, so the difference is structural (per-item cost and volume), not
motivational: vault items arrive at human pace; firings arrive at machine pace. Any fix
for Gap 1 has to respect that asymmetry.
