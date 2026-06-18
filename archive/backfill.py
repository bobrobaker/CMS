#!/usr/bin/env python3
"""Backfill the session archive: summarise recent transcripts into the corpus.

For each session JSONL touched in the last ~N days, extract the user+assistant
trace (via the shared extractor), summarise it with a headless model call, and
land two artifacts the retrieval ladder reads — a rung-2 summary file in
`~/.claude/logs/sessions/` and a rung-1 index entry in `sessions.md`. This is
the one-time seeding of the corpus that live `/wrap-session` keeps current from
here on; it covers exactly the recent history a fuzzy memory is likely to reach
for.

Idempotent (re-runnable): a session whose summary file already exists is
skipped, so an interrupted run resumes cheaply. Fail-soft per session: an empty
transcript, an extractor error, or a model timeout skips that one and the batch
continues.

Usage:
    backfill.py [--days 14] [--limit N] [--model haiku] [--cap 50000] [--dry-run]

Stdlib only. Shells out to the extractor and the `claude` CLI, so it summarises
through exactly the tools a human would.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EXTRACTOR = REPO_ROOT / 'tools' / 'extract_session.py'
PROJECTS_DIR = Path.home() / '.claude' / 'projects'
LOG_DIR = Path.home() / '.claude' / 'logs'
SESSIONS_MD = LOG_DIR / 'sessions.md'
SUMMARY_DIR = LOG_DIR / 'sessions'
# A transcript touched this recently is plausibly a live (or just-ended) session.
# Backfill seeds un-wrapped *gaps*, not live sessions, so it leaves these for
# /wrap-session — which supersedes a backfill stub anyway, but at higher quality.
LIVE_WINDOW_SECONDS = 15 * 60

# The format spec lives in the SYSTEM prompt (instructions), and the user turn
# is purely the transcript (content). Keeping the two separate is what stops the
# model mistaking the format template for an example and asking "where is the
# transcript?" — and replacing the heavy default agent prompt is the token win.
SUMMARY_SYSTEM = (
  'You summarise a past coding session for a searchable archive, so someone who '
  'half-remembers it can find it again. The user message is the session '
  'transcript — user and assistant turns, a long middle possibly elided.\n'
  'Your entire reply MUST begin with the literal token "TITLE:" — no preamble, '
  'greeting, or sign-off. The transcript may itself be a handoff, summary, or '
  'Q&A: ignore its formatting and address-the-reader voice, and re-express it in '
  'the shape below. Use these section headers verbatim and no others: **Did:**, '
  '**Decisions:**, **Artifacts:**, **Open / next:**.\n'
  'Output EXACTLY this shape and nothing else:\n'
  'TITLE: <one specific line, <=80 chars, naming what the session was about>\n'
  'ABSTRACT: 2-3 flowing sentences on ONE line — a dense natural-language gloss '
  'naming the concepts, tools, files, and the problem and outcome, written so a '
  'semantic search over a fuzzy memory ("that thing about X") lands on it. Prose, '
  'not fragments; self-contained (do not start with "this session"). This line is '
  'the embedding target, so make it information-dense and specific.\n'
  '**Did:** 2-5 bullets — what was built, changed, decided, or figured out.\n'
  '**Decisions:** the load-bearing calls, each with a one-clause why (omit the '
  'line if none).\n'
  '**Artifacts:** files, paths, commands, PRs touched (omit if none).\n'
  '**Open / next:** unfinished threads, or "none".\n'
  'Be concrete — name real files, decisions, and terms from the transcript. Do '
  'not invent detail that is not present. Use no tools.'
)

# The user turn: a one-line lead, with the transcript piped in on stdin after it.
SUMMARY_PROMPT = 'Summarise the session transcript in this message.'


# A transcript whose first user turn is one of these is itself a headless tool
# call (our own summariser, an echo test, an agent sub-call) — machinery, not a
# work session worth archiving. Skip it even if it landed a transcript on disk.
MACHINE_PREFIXES = (
  'Summarise the session transcript',
  'You are summarising a past coding session',
  'Reply with exactly',
)


def is_machine_session(trace: str) -> bool:
  """True if the trace's first user turn is a headless/tool prompt, not real work."""
  marker = '[user]\n'
  index = trace.find(marker)
  if index == -1:
    return False
  first_turn = trace[index + len(marker) :].lstrip()
  return first_turn.startswith(MACHINE_PREFIXES)


# A user turn carrying only one of these is session-control, not work.
RESUME_MARKERS = {'resume', 'continue'}


def _user_turns(trace: str) -> list[str]:
  """The text of each [user] turn in an extracted trace."""
  return [m.group(1).strip()
          for m in re.finditer(r'\[user\]\n(.*?)(?=\n\n\[|\Z)', trace, re.S)]


def is_empty_session(trace: str) -> bool:
  """True if no user turn carries substantive prose — only slash-command echoes
  (e.g. /clear) or a bare resume/continue. These are session-control artifacts,
  not work worth archiving."""
  for turn in _user_turns(trace):
    if not turn:
      continue
    if turn.startswith(('<command-', '<local-command')):
      continue  # a slash-command echo
    if turn.lower() in RESUME_MARKERS:
      continue  # a bare resume/continue
    return False  # found real prose
  return True


@dataclass(frozen=True)
class SessionMeta:
  session_id: str
  project: str
  day: str  # YYYY-MM-DD


def _slug_safe(value: str) -> str:
  return '-'.join(value.replace(os.sep, '-').split()) or 'unknown'


def session_meta(jsonl_path: Path) -> SessionMeta:
  """Project + date from the transcript's own records, falling back to mtime.

  The `cwd` and `timestamp` fields on the first records that carry them are the
  ground truth; the directory slug is lossy (project names may contain dashes)
  and file mtime is only a fallback.
  """
  project = None
  day = None
  try:
    with jsonl_path.open(encoding='utf-8', errors='replace') as handle:
      for line in handle:
        try:
          record = json.loads(line)
        except json.JSONDecodeError:
          continue
        if not isinstance(record, dict):
          continue
        if project is None and isinstance(record.get('cwd'), str):
          project = Path(record['cwd']).name
        if day is None and isinstance(record.get('timestamp'), str):
          day = record['timestamp'][:10]
        if project and day:
          break
  except OSError:
    pass
  if not day:
    day = datetime.fromtimestamp(jsonl_path.stat().st_mtime).date().isoformat()
  return SessionMeta(jsonl_path.stem, _slug_safe(project or 'unknown'), day)


def recent_transcripts(days: int) -> list[Path]:
  """Every session JSONL touched within `days`, oldest first."""
  cutoff = time.time() - days * 86400
  found = [
    path
    for path in PROJECTS_DIR.glob('*/*.jsonl')
    if path.stat().st_mtime >= cutoff
  ]
  return sorted(found, key=lambda p: p.stat().st_mtime)


def summary_path(meta: SessionMeta) -> Path:
  return SUMMARY_DIR / f'{meta.day}-{meta.project}-{meta.session_id}.md'


def extract_trace(jsonl_path: Path, cap: int) -> str | None:
  """The capped user+assistant trace, or None when there is nothing to summarise."""
  result = subprocess.run(
    [sys.executable, str(EXTRACTOR), str(jsonl_path), '--cap', str(cap)],
    capture_output=True,
    text=True,
  )
  if result.returncode != 0 or not result.stdout.strip():
    return None
  return result.stdout


# Appended to the system prompt on a retry when the first attempt drifted out of
# format (advisory/handoff transcripts make the model echo their conversational
# voice instead of the required shape). (--json-schema would force structure but
# hangs the call to timeout in this setup, so a stricter re-ask is the fix.)
STRICT_RETRY = (
  '\n\nYour previous attempt drifted out of format. Output ONLY the required '
  'shape, starting with the literal token "TITLE:". No preamble, no commentary, '
  'no alternate headers, no addressing the reader.'
)


def _call_model(
  trace: str, model: str, system: str, timeout: int
) -> tuple[str, dict[str, float]] | None:
  """One headless summariser call → (result_text, usage), or None on failure."""
  try:
    result = subprocess.run(
      # --setting-sources '' loads NO settings, so no hooks fire — without it the
      #   project's monition hooks log every summariser call into the firings eval
      #   table (~2-3 junk rows per session). Auth still loads from credentials, so
      #   this keeps working where --bare ("skip hooks") breaks to "Not logged in".
      # --strict-mcp-config ignores the project .mcp.json (belt-and-braces: with no
      #   settings there is no MCP config to load anyway, but the first call could
      #   otherwise spawn the cwd's MCP servers for a health check and stall).
      # --system-prompt replaces the heavy default agent prompt with `system`.
      # --output-format json returns the call's usage + total_cost_usd.
      # --no-session-persistence stops THIS call from writing its own transcript
      #   into ~/.claude/projects — without it the summariser litters the corpus
      #   with sessions titled "Summarise the session transcript ..." that a later
      #   backfill then discovers and summarises (the archive eating its own tail).
      ['claude', '-p', SUMMARY_PROMPT, '--model', model,
       '--setting-sources', '', '--strict-mcp-config', '--no-session-persistence',
       '--system-prompt', system, '--output-format', 'json'],
      input=trace,
      capture_output=True,
      text=True,
      timeout=timeout,
    )
  except (subprocess.TimeoutExpired, OSError):
    return None
  if result.returncode != 0:
    return None
  try:
    payload = json.loads(result.stdout)
  except json.JSONDecodeError:
    return None
  if not isinstance(payload, dict) or payload.get('is_error'):
    return None
  return (str(payload.get('result', '')), extract_usage(payload))


def _has_title(text: str) -> bool:
  """True if the output opens with a real TITLE: line (i.e. kept format)."""
  return any(line.strip().upper().startswith('TITLE:')
             for line in text.splitlines()[:3])


def summarise(
  trace: str, model: str, timeout: int = 180
) -> tuple[str, str, str, dict[str, float]] | None:
  """(title, abstract, body, usage) from the summariser, or None on failure.

  Retries once with a stricter prompt if the first attempt drifted out of format;
  `usage` sums both calls so cost accounting stays honest.
  """
  first = _call_model(trace, model, SUMMARY_SYSTEM, timeout)
  if first is None:
    return None
  text, usage = first
  if not _has_title(text):
    retry = _call_model(trace, model, SUMMARY_SYSTEM + STRICT_RETRY, timeout)
    if retry is not None:
      retry_text, retry_usage = retry
      for key in usage:
        usage[key] += retry_usage.get(key, 0.0)
      if _has_title(retry_text):
        text = retry_text
  parsed = parse_summary(text)
  if parsed is None:
    return None
  title, abstract, body = parsed
  return (title, abstract, body, usage)


def extract_usage(payload: dict) -> dict[str, float]:
  """Token counts + cost from a --output-format json result, zero-filled."""
  raw = payload.get('usage') if isinstance(payload.get('usage'), dict) else {}
  fields = (
    'input_tokens', 'output_tokens',
    'cache_creation_input_tokens', 'cache_read_input_tokens',
  )
  usage: dict[str, float] = {key: float(raw.get(key, 0) or 0) for key in fields}
  usage['cost_usd'] = float(payload.get('total_cost_usd', 0) or 0)
  return usage


def parse_summary(text: str) -> tuple[str, str, str] | None:
  """Split the model output into (title, abstract, body); None if no content.

  The abstract is the embed-text — every line between TITLE and the first `**`
  bullet, collapsed to one line. The body is the readable bullets from `**` on.
  """
  lines = text.strip().splitlines()
  title = ''
  cursor = 0
  for i, line in enumerate(lines):
    if line.strip().upper().startswith('TITLE:'):
      title = line.split(':', 1)[1].strip()
      cursor = i + 1
      break
  abstract_parts: list[str] = []
  while cursor < len(lines) and not lines[cursor].strip().startswith('**'):
    chunk = lines[cursor].strip()
    if chunk.upper().startswith('ABSTRACT:'):
      chunk = chunk.split(':', 1)[1].strip()
    if chunk:
      abstract_parts.append(chunk)
    cursor += 1
  abstract = ' '.join(' '.join(abstract_parts).split())
  body = '\n'.join(lines[cursor:]).strip()
  if not title and not body:
    return None
  if not title:
    # Model skipped TITLE (e.g. echoed a handoff's voice) — derive one from the
    # first sentence of the abstract, else the first body line, before falling
    # all the way back to a generic label.
    source = abstract or body.lstrip('*').strip()
    first = re.split(r'(?<=[.!?])\s', source.strip(), maxsplit=1)[0]
    title = first[:80].strip() or 'untitled session'
  return (title, abstract, body)


def write_summary(
  meta: SessionMeta, title: str, abstract: str, body: str
) -> Path:
  SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
  path = summary_path(meta)
  # title/abstract are free text (colons, quotes, emoji) — folded block scalars
  # (`>-`) keep the frontmatter valid YAML without escaping. abstract is the
  # embed-text the retrieval layer vectorises alongside the title.
  front = (
    f'---\n'
    f'date: {meta.day}\n'
    f'project: {meta.project}\n'
    f'session: {meta.session_id}\n'
    f'source: backfill\n'
    f'title: >-\n  {title}\n'
    f'abstract: >-\n  {abstract or title}\n'
    f'---\n\n'
  )
  path.write_text(front + body + '\n', encoding='utf-8')
  return path


def update_index(meta: SessionMeta, title: str) -> None:
  """Add a rung-1 entry, or link an existing entry to its new summary file.

  If `sessions.md` already carries this session's marker (its SessionEnd hook
  ran), insert a `summary:` pointer beneath the marker rather than duplicating
  the entry. Otherwise append a fresh backfill entry.
  """
  marker = f'<!-- session: {meta.session_id} -->'
  pointer = f'summary: sessions/{summary_path(meta).name}'
  text = SESSIONS_MD.read_text() if SESSIONS_MD.exists() else ''
  lines = text.splitlines()
  if marker in lines:
    index = lines.index(marker)
    following = lines[index + 1 : index + 3]
    if not any(line.startswith('summary:') for line in following):
      lines.insert(index + 1, pointer)
      text = '\n'.join(lines) + '\n'
      _atomic_write(SESSIONS_MD, text)
    return
  entry = f'\n## {meta.day} · {meta.project} · {title}\n\n{marker}\n{pointer}\n'
  _atomic_write(SESSIONS_MD, text + entry)


def _atomic_write(path: Path, text: str) -> None:
  path.parent.mkdir(parents=True, exist_ok=True)
  tmp = path.parent / (path.name + '.tmp')
  tmp.write_text(text, encoding='utf-8')
  os.replace(tmp, path)


def _transcript_for(session_id: str) -> Path | None:
  hits = list(PROJECTS_DIR.glob(f'*/{session_id}.jsonl'))
  return hits[0] if hits else None


def prune_corpus(cap: int, dry_run: bool) -> int:
  """Drop machine/empty entries from the index + delete their summary files.

  Re-validates every index entry against the same filters the backfill applies
  on the way in (is_machine_session / is_empty_session), so the corpus self-cleans
  of machinery and session-control noise. Entries whose transcript is gone are
  kept (no positive evidence to remove them). Conservative and idempotent.
  """
  if not SESSIONS_MD.exists():
    print('no sessions.md to prune', file=sys.stderr)
    return 0
  text = SESSIONS_MD.read_text()
  blocks = [b for b in re.split(r'(?=^## )', text, flags=re.M) if b.strip()]
  kept: list[str] = []
  removed: list[tuple[str, str]] = []
  for block in blocks:
    sid_match = re.search(r'<!-- session: (\S+) -->', block)
    title_match = re.search(r'^## \S+ · \S+ · (.*)$', block, re.M)
    sid = sid_match.group(1) if sid_match else None
    title = (title_match.group(1) if title_match else '')[:60]
    transcript = _transcript_for(sid) if sid else None
    trace = extract_trace(transcript, cap) if transcript else None
    reason = None
    if trace is not None and is_machine_session(trace):
      reason = 'machine'
    elif trace is not None and is_empty_session(trace):
      reason = 'empty'
    if reason:
      removed.append((f'{reason:8} {sid[:8] if sid else "????????"}', title))
      if not dry_run and sid:
        for summary in SUMMARY_DIR.glob(f'*-{sid}.md'):
          summary.unlink()
    else:
      kept.append(block)

  verb = 'would remove' if dry_run else 'removed'
  for tag, title in removed:
    print(f'  {verb}: {tag}  {title}', file=sys.stderr)
  print(
    f'prune: {len(removed)} {verb}, {len(kept)} kept', file=sys.stderr
  )
  if removed and not dry_run:
    _atomic_write(SESSIONS_MD.with_suffix('.md.bak'), text)  # reversible
    _atomic_write(SESSIONS_MD, ''.join(kept))
    print(f'  (backup: {SESSIONS_MD.with_suffix(".md.bak")})', file=sys.stderr)
  return 0


def main() -> int:
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('--days', type=int, default=14)
  parser.add_argument('--limit', type=int, default=0, help='cap sessions processed (0 = all)')
  parser.add_argument('--model', default='haiku')
  parser.add_argument('--cap', type=int, default=50000, help='per-session char cap')
  parser.add_argument('--dry-run', action='store_true', help='list what would run; call no model')
  parser.add_argument('--prune', action='store_true',
                      help='remove machine/empty entries from the index (no model calls)')
  parser.add_argument('--refresh', action='store_true',
                      help='re-summarise even if a summary file already exists')
  arguments = parser.parse_args()

  if arguments.prune:
    return prune_corpus(arguments.cap, arguments.dry_run)

  transcripts = recent_transcripts(arguments.days)
  full_window = len(transcripts)
  if arguments.limit:
    transcripts = transcripts[-arguments.limit :]
  print(
    f'{len(transcripts)} of {full_window} transcript(s) in the last '
    f'{arguments.days} days',
    file=sys.stderr,
  )

  done = skipped = failed = 0
  totals: dict[str, float] = {
    'input_tokens': 0.0, 'output_tokens': 0.0,
    'cache_creation_input_tokens': 0.0, 'cache_read_input_tokens': 0.0,
    'cost_usd': 0.0,
  }
  for path in transcripts:
    meta = session_meta(path)
    tag = f'{meta.day} {meta.project} {meta.session_id[:8]}'
    if summary_path(meta).exists() and not arguments.refresh:
      skipped += 1
      continue
    if path.stat().st_mtime >= time.time() - LIVE_WINDOW_SECONDS:
      # Leave plausibly-live sessions for /wrap-session; a stub written here would
      # race the live wrap and could win the file with the lower-quality summary.
      print(f'  skip (live session): {tag}', file=sys.stderr)
      skipped += 1
      continue
    if arguments.dry_run:
      print(f'  would summarise: {tag}', file=sys.stderr)
      continue
    trace = extract_trace(path, arguments.cap)
    if trace is None:
      print(f'  skip (no trace): {tag}', file=sys.stderr)
      skipped += 1
      continue
    if is_machine_session(trace):
      print(f'  skip (machine session): {tag}', file=sys.stderr)
      skipped += 1
      continue
    result = summarise(trace, arguments.model)
    if result is None:
      print(f'  FAIL (model): {tag}', file=sys.stderr)
      failed += 1
      continue
    title, abstract, body, usage = result
    for key in totals:
      totals[key] += usage.get(key, 0.0)
    write_summary(meta, title, abstract, body)
    update_index(meta, title)
    done += 1
    print(f'  summarised: {tag} — {title[:60]}', file=sys.stderr)

  print(
    f'backfill: {done} summarised, {skipped} skipped, {failed} failed',
    file=sys.stderr,
  )
  if done:
    avg_cost = totals['cost_usd'] / done
    avg_in = (
      totals['input_tokens'] + totals['cache_creation_input_tokens']
      + totals['cache_read_input_tokens']
    ) / done
    print(
      f"  tokens (sample): in {totals['input_tokens']:.0f} · "
      f"out {totals['output_tokens']:.0f} · "
      f"cache-write {totals['cache_creation_input_tokens']:.0f} · "
      f"cache-read {totals['cache_read_input_tokens']:.0f}",
      file=sys.stderr,
    )
    print(
      f"  cost (sample): ${totals['cost_usd']:.4f}  |  per session "
      f"~${avg_cost:.4f}, ~{avg_in:.0f} input tok",
      file=sys.stderr,
    )
    print(
      f'  projection: full window = {full_window} sessions -> '
      f'~${avg_cost * full_window:.2f} gross '
      f'(already-summarised are skipped, so actual <= this)',
      file=sys.stderr,
    )
  return 0


if __name__ == '__main__':
  sys.exit(main())
