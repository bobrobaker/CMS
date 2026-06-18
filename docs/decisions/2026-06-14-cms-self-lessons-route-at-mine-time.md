# 2026-06-14 · CMS routes its own lessons at mine-time — no candidate queue

**Decision.** For the incubator's *own* mined lessons, drop the `mirror=candidate`
queue. Route a domain-free lesson when it's mined: helps a generated project →
propose into `payload/lessons.md.template` now; incubator/module-meta → local row
(`mirror none`). `--mirror candidate` is reserved for instantiated downstream projects.

**Why.** `candidate` is a queue for an actor that can't edit the upstream directly and
whose run is real evidence. CMS is neither: a session here can edit `payload/`
directly, and CMS firings are incubator-dev signal that doesn't represent a generated
project — so the "let it prove itself first" evidence gate is illusory. Early-phase CMS
favors responsiveness/adaptability over a buffer (user call, 2026-06-14). Building a
forward-promotion pipeline for cargo that isn't coming would be the apparatus this repo
is built to avoid.

**Triage of the existing candidates.** Promoted to payload: t16 (git --since), t5
($CLAUDE_PROJECT_DIR hooks), t7 (handoff staleness). Kept CMS-local (meta): t4, t9,
t17. Held local as workload-conditional (would be tier-0 noise for most projects):
t8, t11, t12, t13, t14.

**Follow-on (not now).** The workload-conditional bucket hints the payload may eventually
want **workload-tagged starter lessons** — `/instantiate` selecting a lesson subset by
project type — rather than one flat tier-0 file. Shelved in the roadmap, not built; it
earns its place only once there are generated projects of those types to serve.

**Limitations.** No `monition` verb sets `mirror` post-hoc, so the promoted rows keep a
stale `candidate` flag — harmless, since nothing reads CMS-store mirror flags (the
sweep scans file queues only). Cleanup waits on a Monition affordance, not worth it now.
