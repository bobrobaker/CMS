---
status: decided
---
# 2026-06-20 · Self-improving lexical layer for the autoflagger's tier 2

**Decision.** Tier 2 of the autoflagger (`tools/autoflag.py`, the Stop-hook backstop from
`2026-06-18-two-tier-autoflagger.md`) gains a second LLM-free layer beside the existing
admitted-error **regex floor**: a **self-improving lexical matcher** (`tools/flag_corpus.py`)
that scores each response sentence against a corpus of known flag-worthy phrasings
(IDF-weighted whole-sentence Jaccard) and writes a flag when the best match clears a
conservative threshold. The corpus is **data** — seeded from the regex patterns
(`tools/flag_corpus_seed.json`), accumulated live at `~/.claude/flag-corpus.json`, and
grown at mine-time (`/mine-session` step 0d) from the manual flags the matcher missed,
with mis-firing entries demerited until they drop below a firing floor. The two layers run
together and dedup on a shared matched snippet.

**Why this shape.**

- **Why a backstop at all, over the agent (tier 1).** The agent is the stronger *judge*
  but is not *reliable* — under crowded context it forgets to self-flag. For a net, the
  property that matters is "always runs," not "judges best." A deterministic layer that
  always fires beats a smarter one that sometimes doesn't. (This is the same reason the
  regex floor exists; the lexical layer widens its recall without giving up determinism.)
- **Why lexical, not embeddings.** Embeddings earn their keep when the target class is
  semantically diverse with low vocabulary overlap (Monition's `on_demand` rows span every
  topic). The flag class is the opposite — a small, recurring, vocabulary-clustered set
  (`wrong / mistake / should-have / overlooked / assumed`). Surface-form matching captures
  most of the available signal there. The non-negotiable cost of embeddings sealed it: the
  Stop hook runs under the system `python3`, which has no `fastembed`; adding it pulls
  onnxruntime + model weights (~185MB) into a currently pure-stdlib hook, and with no warm
  daemon every Stop would pay a ~1–2s cold model load. Lexical is stdlib, instant, zero new
  dependency. (Monition's embedding layer was considered as a shared backend via a CLI seam;
  rejected for v1 as more coupling and surface than the gain warrants — revisit only if the
  lexical layer's recall proves insufficient in practice.)
- **Why the corpus is data grown at mine-time.** Static patterns can't learn the author's
  own phrasings. Routing growth through `/mine-session` puts the *expensive, high-quality*
  judgment (extracting the generalizable trigger from a miss) where the LLM already is and
  is free, while the *runtime* stays dumb and cheap. Misses raise recall; demerits raise
  precision — the same fire/rate/suppress shape Monition uses, re-derived for flags.
- **Why the hook is read-only on the corpus.** The corpus is one machine-global file. If
  the Stop hook wrote it, concurrent sessions would clobber each other on the hot path
  (the per-session-keying rule, applied to a shared resource). All mutation is therefore a
  mine-time act — single-session, atomic write — never the hook.
- **Why it stays in CMS, not Monition.** Flags are a CMS concept; the corpus, the matcher,
  the flag-file format all stay CMS-local. Monition never learns what a flag is. No
  cross-repo dependency, and the flag-file contract is **unchanged** — so the other
  consumers of `~/.claude/session-flags/` (`postmortem`, `housekeep`) are unaffected.

**Calibration note.** Threshold is 0.4 (conservative — bias to precision; recall ramps as
the corpus grows). A correction surfaced while building: IDF-weighting **narrows** the gap
between a true admitted-error and a stopword-sharing decoy but does **not** reliably
re-rank them on a small corpus — on the seed a benign decoy ("I was on the call about
that", 0.32) out-scores a true novel miss ("I was wrong on the threshold", 0.28). It is the
**threshold**, not IDF, that suppresses the decoy (both sit below 0.4). The one-occurrence
learning lag (a novel phrasing is missed once, then learned) is by design.

**Validation (real-data, 250 sessions / 27k sentences).** Confirmed: (1) the metric is
sound, not length-broken — when corpus entries are realistic full-length phrasings,
similar real sentences clear 0.4 (0.45–0.79) and benign ones stay low (0.10); the early
"median 0.00 on real admitted-errors" was a **seed-quality** artifact (short synthetic
phrasings barely overlap long real sentences), not a metric defect. (2) Threshold 0.4 is
well-placed. (3) The original regex-transcribed seed left the layer near-dormant at
cold-start. So the seed was **enriched** with eight generic full-length conversational
admissions; measured against the real corpus this caught four genuine "you're right, my X
was wrong" concessions **the regex floor cannot match**, with total fires staying at
21/27,495 (0.076% — no bar-lowering) and the decoy still suppressed. Net-new precision
~75% (two weak bare-"you're right" fires self-correct via demerit).

**Forkability.** The seed and matcher are stdlib and ship in `tools/`; a fork inherits the
regex floor + lexical layer with zero extra dependency. The live corpus is personal and
machine-local (never committed), mirroring `session-flags/`.
