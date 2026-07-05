# Structured brainstorming vs. a strong single-agent baseline — research + experiments (2026-07-04)

**Question.** For LLM candidate generation, does *structured multi-strategy brainstorming* (a
runbook of ideation strategies chosen by task type, fanned out and converged) beat a plain
single-agent baseline — "generate N deliberately-diverse candidates and pick the best against a
checker" — on either **solution quality (reward)** or **set diversity**?

**Answer (one paragraph).** No, on any task we could measure objectively — and the reason turned
out to be more interesting than "the strategies are weak." Internal *reasoning-style* strategies
(inversion, decomposition, analogy, morphological, even 12 enforced-orthogonal mechanism families)
stay on the model's high-probability **mode** and collapse to near-identical behavior, so they add
nothing over the baseline. The diversity that *does* help comes from moving **off-mode** — either by
reshaping the sampling distribution (verbalized sampling, ordinary personas) or by injecting
**distant/structured/planned external knowledge** (retrieval/deep-research). But the objective-checker
tasks needed to *measure* a win have small formal solution spaces, so the baseline saturates them on
both reward and diversity; the tasks where off-mode methods demonstrably win are *open* and
large-space, which have no clean checker. **The measurable regime and the value regime are disjoint.**
The literature confirms this with ablation-strength evidence on open tasks; our experiments confirm the
null on formal ones. The two are consistent.

This document records the full literature review, the experiments, the reconciled finding, and the
resulting architecture.

---

## 1. Method

- **Literature:** eight parallel web-research passes over (a) human ideation methods, (b) non-AI
  search/optimization algorithms, (c) LLM ideation methods, (d) TRIZ (deep + applied), (e) current
  2024–2026 tools/practice, (f) the 2024–2026 paper frontier on diverse/novel LLM generation.
  Primary/arXiv sources preferred; secondary and single-voice claims labeled as such.
- **Experiments:** blind subagent arms (a capable frontier mid-tier model, Claude Sonnet class),
  objective judgment-free checkers, equal generation budgets, held-out scoring where applicable.
  Four studies: (1) task-fingerprint reliability, (2) structured-vs-baseline A/B on reward,
  (3) a Phase-0 task-admissibility gate, (4) a behavioral-diversity A/B including the literature's
  "off-mode" methods.

All numbers are point-in-time and model-specific; re-run rather than trusting them later.

---

## 2. Literature review

### 2.1 Human ideation methods

- **The one robust empirical result** is *production blocking* (Diehl & Stroebe 1987, JPSP; meta-
  analysed by Mullen, Johnson & Salas 1991): nominal groups (people ideating in isolation, pooled
  later) reliably beat interacting groups, because ideas that see each other during generation
  anchor. Design implication that ports to LLMs: **diverge in isolation, converge later.**
- **Techniques with built-in pruning** (rare): *morphological analysis* (Zwicky box + cross-
  consistency assessment collapses the combinatorial grid) and *TRIZ contradiction matrix*. Most
  other techniques (SCAMPER, synectics, six-hats, brainwriting/6-3-5, NGT) are pure divergence
  generators needing an external convergence stage.
- **Meta-selection.** Structure should match problem *definedness* (fNIRS/ICED13 work): well-specified
  problems with a checkable target favor systematic methods. The most defensible task discriminator is
  Shah's (1998/2000) *germinal vs. transformational* (start cold vs. improve a seed). The single axis
  every taxonomy (Osborn-Parnes CPS, VanGundy, Shah, SessionLab, geniusrevive) agrees on is
  **divergent/convergent, temporally separated.**
- **The four "unconventional" moves** a "generate more ideas" default never makes: **inversion**
  (anti-problem, worst-possible-idea), **subtraction** (SIT — remove an essential component),
  **random insertion** (Oblique Strategies), **forced analogy** (Synectics, biomimicry).
- **Efficacy caveat:** SCAMPER, synectics, six-hats have canonical definitions but near-zero
  controlled efficacy evidence; ubiquity ≠ validation.

### 2.2 Non-AI search/optimization algorithms (formal analogues of "brainstorm then select")

- **Quality-Diversity / MAP-Elites** (Mouret & Clune 2015; Pugh, Soros & Stanley 2016) and **Novelty
  Search** (Lehman & Stanley 2011): *illuminate* a space by keeping the best candidate **per niche**
  (a filled grid), not a ranked top-k — preserving stepping-stones a global objective would prune.
- **Multi-armed bandits** (UCB1, Auer et al. 2002; Thompson sampling) and **MCTS** (Browne et al.
  2012, incl. progressive widening): allocate effort across options by realized payoff; contextual
  bandits for problem-type dependence; never hard-prune an under-explored arm.
- **Multi-objective** (NSGA-II, Deb et al. 2002): keep a **Pareto front**, don't collapse
  novelty×quality into one score before selecting.
- **Cross-cutting lesson:** every rugged-landscape method **prunes redundancy first, quality last**,
  and defers objective-based pruning.

### 2.3 LLM ideation methods

- **Reasoning-search:** Chain-of-Thought (Wei et al. 2201.11903) + Self-Consistency (Wang et al.
  2203.11171); Tree-of-Thoughts (Yao et al. 2305.10601, value-function-as-pruner); Graph-of-Thoughts
  (Besta et al. 2308.09687, *aggregate* operator = merge candidates); Least-to-Most (Zhou et al.
  2205.10625).
- **Critique-refine:** Self-Refine (Madaan et al. 2303.17651); Reflexion (Shinn et al. 2303.11366,
  verbal episodic memory).
- **Evolutionary-LLM (the core family):** FunSearch (Romera-Paredes et al., *Nature* 2023); AlphaEvolve
  (2506.13131); Eureka (2310.12931, reward-function search); OPRO (2309.03409, LLM-as-optimizer with a
  sorted score trajectory); Promptbreeder (2309.16797); Language-Model-Crossover (2302.12170).
- **Diversity + the two killer caveats (Stanford, Si et al. 2409.04109):** AI research ideas rated
  *more novel but slightly less feasible* than humans'; **diversity plateaus hard** (~4000 ideas →
  only ~5% non-duplicate, rate falls as you sample more); **LLM self-ranking ≈ chance** (Claude-3.5
  pairwise 53.3% vs. human inter-rater 56.1%). DPP-based semantic diversity (2509.04784) is the
  rigorous "keep a set spanning distinct modes" selector.
- **Existing brainstorm tools** (claude-brainstorm; superpowers; diverge-converge libraries) each *are*
  a single strategy; none fan out over multiple strategies, select by task type, take a pass-condition,
  or learn across runs.

### 2.4 TRIZ — deep, then applied

**What it is** (primary: MATRIZ knowledge base; honest validation labels): 40 inventive principles +
a 39×39 contradiction matrix (the *weakest-validated* tool — Mann's ~2002 patent study found ~50%
compliance, no evidence it beats random principle selection); the **separation principles** (space,
time, parts/whole, condition) for *physical* contradictions; Ideal Final Result / ideality; Su-Field
analysis + 76 standard inventive solutions; 8 (heuristic, patent-derived) laws of engineering-system
evolution.

**Applied to LLM idea generation.** Frame diversity-vs-relevance as a **physical contradiction** —
generation must be *wide and narrow at the same moment* (high-entropy to escape the mode, low-entropy
to stay on-target). TRIZ's answer to physical contradictions is *don't compromise on temperature —
separate along a dimension*:

- **Separation in space ≡ MAP-Elites illumination** — partition into behavioral cells
  (who-it's-for × mechanism × constraint); generate the best candidate *per cell*; keep the filled
  grid. Makes "diverse AND relevant" non-contradictory (locally on-target, globally spread).
- **Separation on condition ≡ assumption-negation** — enumerate the model's *silent* assumptions
  ("assumes real-time / one user / must be software / budget matters"), negate each, generate under
  the relaxed world. The most reliable *non-obvious* generator; attacks the priors that produce the
  obvious answers.
- **Separation in time ≡ diverge-then-converge** — with an **external** selector, never LLM self-rank.
- The 39×39 matrix does *not* transfer to an information-generation task; the separation principles and
  ~12 of the 40 principles reinterpreted as generation operators (the SCAMPER/SIT lineage) do the work.

### 2.5 Current frontier (2024–2026) — the decisive stream

- **Verbalized Sampling** (2510.01171): locates single-model low diversity in **RLHF typicality bias**
  — preference data favors typical/fluent text, giving effective reward `r + α·log π_ref` with
  α̂=0.57±0.07, so alignment sharpens the policy by γ=1+α/β>1 (temperature-scaling toward the mode).
  Direct prompting retains only **23.8%** of base diversity. *Training-free fix:* ask for a
  **distribution with explicit probabilities** ("k responses + their probabilities") → **66.8%**
  recovered, **1.6–2.1×** creative-writing diversity, quality flat; larger models gain *more*.
- **Barriers to Diversity in LLM-Generated Ideas** (2602.20408): the culprit is **knowledge
  aggregation** (pretraining fuses all worldviews into one distribution), *not* fixation (which affects
  humans and LLMs equally). Humans 26.29 unique idea-categories vs. LLM 18.45. Critically, **feeding
  the LLM diverse human seed-ideas failed to improve diversity** — different starting points don't
  restore partitioning. *Ordinary* personas (physicist, accountant) reach ≈ human diversity and beat
  "creative entrepreneur" personas — because the value is the **partition**, not the creativity.
- **DeepEvolve** (2510.06056): AlphaEvolve + a deep-research (web/paper retrieval) loop before each
  mutation. **The ablation is the load-bearing datum:** remove retrieval and a frontier evolutionary
  system reverts to marginal single-generation gains — pure AlphaEvolve +0.6% (evolution added
  *nothing*) vs. **+2.96%** with sustained multi-generation jumps when retrieval is on.
- **Nova** (2410.14255): planning + retrieval that enriches context each round → **3.4× more unique
  novel ideas** vs. a no-retrieval baseline; frames pure LLMs as "simplistic and repetitive from
  limited internal knowledge." Plateaus after ~3 iterations.
- **ShinkaEvolve** (2509.19349): an explicit **novelty filter** (embedding + LLM-judge rejection
  sampling) over a population buys sample-efficiency (SOTA circle-packing in ~150 samples vs.
  thousands).
- **Self-MoA / Rethinking Mixture-of-Agents** (2502.00674): repeatedly sampling **one** strong model
  *beat* mixing different models (+6.6pt AlpacaEval2); a quality-diversity regression found the quality
  coefficient **1.4–2.5×** the diversity coefficient — homogeneous multi-agent systems *amplify shared
  bias, not variety.* A caution: more agents ≠ better.
- **Similarity-RAG backfires** (creativity survey 2511.07448): "higher retrieval quality often
  *reduces* output diversity as models overfit to retrieved passages." **Relational/knowledge-graph
  retrieval and planning-search** help; nearest-neighbor RAG re-anchors to the mode.
- **QD applied to LLM outputs:** In-context QD (2404.15794, LLM as a MAP-Elites mutation operator);
  Rainbow Teaming (2402.16822) / QD Red-Teaming (2506.07121) — MAP-Elites over an output archive
  yields a diverse grid *by construction.*
- **Framing-only** (no original diversity measurement; cite as lenses): homogenization papers
  2601.06116, 2604.01504. **Complementary, not a clean win either way:** RAG-vs-CoT for engineering
  ideation (doi 10.1080/09544828.2025.2574209) — RAG wins comprehensiveness, CoT wins elaboration.

---

## 3. Experiments

### 3.1 Task-fingerprint reliability

We tested whether an LLM can reliably classify a task on axes that would drive strategy selection.
Three independent fresh-context classifiers over 10–14 task specs, 3 reps.

- A first 5-axis scheme was noisy/redundant: `germinal|transformational` reached only **50%** unanimous
  agreement (coin-flip); `combinatorial|conceptual` and `incremental|breakthrough` co-fired on the same
  single spec (redundant).
- **Correction:** the useful axis is not "does solved literature exist" (an LLM reads almost everything
  as solved) but **"is the *fit* of known approaches to *this* constrained problem non-obvious?"** Under
  this definition, a trimmed 3-axis fingerprint — **fit** (obvious|non-obvious), **eval**
  (programmatic|soft), **shape** (single|stack) — reached **79%** unanimous agreement, splitting cleanly
  rather than collapsing. `fit` is a reliable **gate** but a **weak strategy selector** (the
  `non-obvious/programmatic/single` cell holds tasks wanting very different strategies).

### 3.2 Structured-vs-baseline A/B on reward

Arm A = baseline ("generate 12 diverse, pick best"). Arm B = 12 candidates via structured strategies
(inversion/decomposition/analogy/systematic). Equal 12-candidate budget, blind agents, 3 tasks × 3 reps,
objective checkers.

| Task | Baseline | Structured | Result |
|---|---|---|---|
| Binary-code min-Hamming-distance construction (ceiling 4) | 4,4,4 | 4,4,4 | tie at optimum |
| Reverse-engineer a hidden scoring rule (max corr 1.0) | ~1.0 | ~1.0 | tie (structured overengineered) |
| Adversarial test inputs, distinct bug-classes (/5) | **4.0** | 2.67 | **baseline wins** |

**Structured won 0/3**, and cost more (11–17 tool calls per structured arm on the construction task).
Mechanism, from the transcripts: five of six "distinct" strategies independently chose the *same*
features because those are the only signal in the data — different narratives, same behavior.

### 3.3 Phase-0 task-admissibility gate (the key negative)

Before an A/B can mean anything, the baseline must leave *headroom* (not saturate). We ran baseline-only
pilots (tools allowed) on three *harder* tasks with verified ceilings, admitting a task only if baseline
best ≤ 75% of ceiling with inter-rep variance.

| Task | Ceiling | Baseline best | How baseline solved it | Verdict |
|---|---|---|---|---|
| LABS (low-autocorrelation sequence, L=20) | merit ~7.69 | 7.69, 7.69, 7.69 | simulated annealing to the optimum | **reject** |
| MAX-SAT (planted-satisfiable, 20 var / 91 clause) | 1.0 | 1.0, 1.0, 1.0 | brute-forced all 2²⁰ | **reject** |
| Rule-induction v2 (multi-term rule) | 1.0 | 0.79, 0.90 | least-squares regression | **reject** |

**0 of 3 admissible.** The finding is structural: **a problem specified tightly enough for an objective
checker is specified tightly enough for the model to *write a solver* (search / brute-force / regression)
and saturate it** — available to any arm, so all arms tie at the ceiling. Objective checkers select for
solver-dominated tasks, which are the *wrong population* for testing ideation.

### 3.4 Behavioral-diversity A/B (including the off-mode methods)

Reframing to the measurable claim "does structure produce a more *diverse* candidate set?" Metric
(objective, judgment-free): run each candidate function on a fixed 40-string probe, take its output
vector; **distinct behaviors** = clusters at output-correlation > 0.95; **mean pairwise distance** =
mean (1 − |corr|). Task = rule-induction (functions).

| Method | distinct / 12 | mean pairwise distance | best reward |
|---|---|---|---|
| **Baseline (undirected)** | 11–12 | **0.56–0.72** | **0.79–0.90** |
| Structured-6 (task-selected strategies) | 11 | 0.51 | 0.82 |
| Enforced-orthogonal-12 (disjoint mechanism families) | 12 | 0.55 | 0.75 |
| Persona-partitioned (12 worldviews) | 11 | 0.49 | 0.76 |
| Verbalized-sampling (distribution + tail) | 10 | 0.48 | 0.78 |

**Every method — including the two literature-backed off-mode levers — scored at or below baseline on
both diversity and reward.** Cause: this task's solution space is tiny (a handful of features), so
anything genuinely fitting the data converges; the baseline's spontaneous 0.56–0.72 is already near the
task's diversity **ceiling**. The literature's diversity wins (verbalized sampling 2×, personas ≈ human,
Nova 3.4×) were on *open* tasks (story-writing, research ideation) with huge spaces — which an
objective-checker task structurally cannot represent.

---

## 4. The reconciled finding

### 4.1 The one variable: on-mode vs. off-mode

An LLM is a probability distribution over responses; the **mode** is the high-probability default. The
real determinant of diversity is **whether an intervention moves sampling off the RLHF mode**, not
"internal vs. external."

| Intervention | Off-mode? | Evidence |
|---|---|---|
| Reasoning-style variation (inversion/decomposition/analogy/orthogonal families) | **No** — same distribution | §3.2–3.4; Barriers; Self-MoA |
| **Distribution-reshape** (verbalized sampling; *ordinary* personas) | **Yes** — internal, cheap | VS 23.8%→66.8%; personas ≈ human |
| **External knowledge** — *only if distant / structured / planned* | **Yes** | DeepEvolve ablation; Nova 3.4× |
| Naive similarity-RAG | **No** — re-anchors to mode | survey 2511.07448 |
| Homogeneous multi-model mixing | **No** — amplifies shared bias | Self-MoA |
| Evolution + **external** evaluator | **Yes** — novelty rewarded externally | FunSearch / AlphaEvolve / QD |

### 4.2 Root cause

Two compounding sources: **RLHF mode-sharpening** (γ=1+α/β>1; Verbalized Sampling) and **pretraining
knowledge aggregation** (all worldviews fused into one distribution, whereas human collective diversity
comes from knowledge *partitioned across minds*; Barriers to Diversity). This is why reasoning-style
prompts collapse (same distribution) and why *partitioning* (personas) or *re-widening* (verbalized
sampling) or *injecting non-weight content* (retrieval) are the interventions that move the needle.

### 4.3 The disjoint-regimes conclusion

- **Measurable regime** (objective checker) ⟹ small formal solution space ⟹ baseline saturates on
  reward *and* diversity ⟹ nothing beats it.
- **Value regime** (open, large-space, "I don't know how to build this") ⟹ off-mode methods
  demonstrably win (ablation-strength evidence) ⟹ but no clean checker exists, and LLM self-ranking is
  ≈ chance, so measurement is intrinsically noisy.
- These sets are **disjoint**. The value is real and unprovable on toy tasks simultaneously; both
  observations are correct.

---

## 5. The resulting architecture

A structured-fan-out system worth building, per the evidence:

1. **Gate** on `fit` — short-circuit to a single strong generation when the approach is obvious; only
   fan out when the fit to *this* problem is non-obvious. (Fan-out rarely helps; the gate's value is
   knowing *when not to*.)
2. **Default generator (off-mode, evidence-backed):** *verbalized sampling* (ask for candidates as a
   distribution with probabilities, tail included) + *ordinary personas* (re-partition the generator).
3. **The big lever — external-knowledge injection** for open/soft problems: *plan → retrieve
   distant/structured knowledge (papers, web, KG hops) → propose*, and prototype-and-measure. **Not**
   naive similarity-RAG.
4. **Playbook library, opt-in, top-N only:** assumption-negation, MAP-Elites cells, inversion,
   subtraction, analogy, morphological, evolve-generator. Kept available for judgment calls, **not
   auto-run** (auto-running all of them is the inert part).
5. **Convergence is external** — a programmatic checker, a QD/MAP-Elites grid, or a human. **Never** the
   model ranking its own fan-out.
6. **Diverge in isolation** (production-blocking); **any learning layer is write-only** until enough
   externally-scored runs accumulate (a contextual bandit cannot converge at low run frequency).

---

## 6. Lessons worth keeping (codify candidates)

1. **On a frontier model, internal structured multi-strategy fan-out is inert vs. a strong single agent
   told to diversify** — the strategies stay on the RLHF mode and collapse. Prove a fan-out beats its
   single-agent baseline *before* building the machinery.
2. **A judgment-free checker silently selects for solver-dominated tasks** — the population your ideation
   claim isn't about. Add a **saturation gate** (baseline pilot must leave verified headroom) before any
   A/B on generative structure.
3. **The diversity lever is "off-mode," not "more strategies":** distribution-reshape (verbalized
   sampling, ordinary personas) and distant/structured external knowledge. Reasoning-style variation and
   naive similarity-RAG do *not* move off-mode.
4. **Converge externally, diverge in isolation.** LLM self-ranking ≈ chance; never let the generator
   grade its own fan-out.
5. **Contamination hygiene for multi-arm eval:** one private working dir per agent-rep; hash final
   outputs across arms to detect cross-reads; keep the loop on a dev split and score once on held-out.

---

## 7. Limitations

- Single model class tested (Claude Sonnet class); larger models benefit *more* from verbalized sampling
  per the literature, so the off-mode gap may widen on frontier tiers — untested here.
- Experiment sample sizes are small (n=3 reps, few tasks) and the diversity A/B's decisive arms are
  n=1 rep; directional, corroborated by literature, not definitive.
- The core claim's *value regime* (open, large-space tasks) was **not** directly measured — by
  construction it resists objective measurement; we rely on the external ablation literature
  (DeepEvolve, Nova) for the positive evidence.
- Several 2025–2026 papers are recent; claims are labeled by source strength but re-verify against
  primaries before load-bearing use.

---

## 8. Bibliography

**Human ideation:** Diehl & Stroebe 1987 (JPSP 53:497); Mullen, Johnson & Salas 1991 (BASP 12:3);
Delbecq et al. 1975 (NGT); Rohrbach 1968 (6-3-5); Zwicky/Ritchey (morphological analysis, swemorph.com);
Eberle 1971 (SCAMPER) / Osborn 1953; Gordon & Prince 1961 (Synectics); de Bono (Six Hats / lateral
thinking); Osborn-Parnes CPS; Shah 1998/2000 (idea-generation taxonomy, *Research in Engineering
Design*); SIT (drewboyd.com); Liberating Structures; Gamestorming; Oblique Strategies.

**Non-AI algorithms:** Lehman & Stanley 2011 (Novelty Search, *Evol. Comp.* 19:2); Mouret & Clune 2015
(MAP-Elites, arXiv:1504.04909); Pugh/Soros/Stanley 2016 (Quality-Diversity, *Frontiers Robotics AI* 3:40);
Auer et al. 2002 (UCB1); Browne et al. 2012 (MCTS survey); Deb et al. 2002 (NSGA-II); Kirkpatrick et al.
1983 (SA); Glover 1989 (tabu); Kennedy & Eberhart 1995 (PSO).

**LLM ideation:** CoT [2201.11903]; Self-Consistency [2203.11171]; Tree-of-Thoughts [2305.10601];
Graph-of-Thoughts [2308.09687]; Least-to-Most [2205.10625]; Self-Refine [2303.17651]; Reflexion
[2303.11366]; Multi-Agent Debate [2305.14325]; FunSearch (*Nature* s41586-023-06924-6); AlphaEvolve
[2506.13131]; Eureka [2310.12931]; OPRO [2309.03409]; Promptbreeder [2309.16797]; LMX [2302.12170]; DPP
diversity [2509.04784]; Stanford "Can LLMs Generate Novel Research Ideas?" [2409.04109].

**TRIZ:** MATRIZ knowledge base (wiki.matriz.org); Altshuller 40 principles + contradiction matrix; Mann
2002/2003 (matrix validation critique, TRIZCON); separation principles (leanmethods.com,
innovation-triz.com); Su-Field (the-trizjournal.com); Laws of technical-systems evolution (Wikipedia;
aitriz.org TRIZCON2019 "productive tautologies").

**Current frontier (2024–2026):** Verbalized Sampling [2510.01171]; Barriers to Diversity [2602.20408];
DeepEvolve [2510.06056]; Nova [2410.14255]; ShinkaEvolve [2509.19349]; Self-MoA [2502.00674]; In-context
QD [2404.15794]; Rainbow Teaming [2402.16822]; QD Red-Teaming [2506.07121]; creativity survey
[2511.07448]; homogenization [2601.06116, 2604.01504]; RAG-vs-CoT (doi 10.1080/09544828.2025.2574209);
Price of Format / diversity collapse [2505.18949]; homogeneity-bias robustness [2501.02211].

_arXiv IDs are `YYMM.NNNNN`; fetch `/abs/` or `/html/`, never `/pdf/`. Several 2025–2026 IDs postdate
common training cutoffs and are real — verify against primaries rather than dismissing._
