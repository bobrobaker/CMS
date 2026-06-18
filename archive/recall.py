#!/usr/bin/env python3
"""Recall — grep over the session-archive disclosure ladder.

Answers a fuzzy-memory query ("I remember working on X") by climbing the ladder
cheapest-rung-first and stopping at the first rung that returns candidates:

  1. index       — the one-line titles in ~/.claude/logs/sessions.md
  2. summary      — the per-session summary files (title + abstract + body)
  3. transcript   — the raw session JSONL (the expensive fallback)
  4. raw          — same bytes, no filtering (last resort)

Each rung is ~10x the tokens of the last (spec decision 3), so the default ceiling
is `summary`: the embeddable corpus that holds exactly what gets fuzzily
remembered. Climbing to transcript/raw is opt-in (`--max-rung transcript`).

Stdlib only, fail-open: a missing corpus prints a notice and exits 0. Every
lookup writes one row to the retrievals log (schema owned by Monition; see
retrievals_log.py) unless `--no-log` is passed.

    recall.py [--top N] [--max-rung index|summary|transcript|raw]
              [--session-id SID] [--no-log] <query words...>
    recall.py --rate <retrieval-id> helpful|noise
"""

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import retrievals_log

LOG_DIR = Path.home() / '.claude' / 'logs'
SESSIONS_MD = LOG_DIR / 'sessions.md'
SUMMARY_DIR = LOG_DIR / 'sessions'
PROJECTS_DIR = Path.home() / '.claude' / 'projects'

RUNG_ORDER = ('index', 'summary', 'transcript', 'raw')
STOPWORDS = {
  'the', 'a', 'an', 'to', 'of', 'and', 'or', 'in', 'on', 'for', 'with', 'i',
  'was', 'is', 'it', 'that', 'this', 'my', 'me', 'we', 'do', 'did', 'how',
  'what', 'when', 'where', 'about', 'remember', 'working', 'session',
}


@dataclass
class Entry:
  day: str
  project: str
  title: str
  session_id: str | None
  summary_file: str | None  # relative, e.g. "sessions/2026-…md"


def tokenize(query: str) -> list[str]:
  terms = re.findall(r'[a-z0-9][a-z0-9_-]+', query.lower())
  return [t for t in terms if len(t) >= 2 and t not in STOPWORDS]


def score(terms: list[str], text: str) -> int:
  """Distinct query terms present in `text` (case-insensitive substring)."""
  low = text.lower()
  return sum(1 for t in set(terms) if t in low)


def load_index() -> list[Entry]:
  """Parse sessions.md into one Entry per `## …` block. Fail-open to []."""
  if not SESSIONS_MD.exists():
    return []
  text = SESSIONS_MD.read_text(encoding='utf-8')
  entries: list[Entry] = []
  for block in re.split(r'(?=^## )', text, flags=re.M):
    header = re.match(r'## (\S+) · (\S+) · (.*)', block.strip())
    if not header:
      continue
    sid = re.search(r'<!-- session: (\S+) -->', block)
    summ = re.search(r'^summary: (\S+)', block, re.M)
    entries.append(Entry(
      day=header.group(1),
      project=header.group(2),
      title=header.group(3).strip(),
      session_id=sid.group(1) if sid else None,
      summary_file=summ.group(1) if summ else None,
    ))
  return entries


def best_excerpt(terms: list[str], text: str, window: int = 5) -> str:
  """The highest-scoring contiguous line-window — a small, term-dense snippet."""
  lines = [ln for ln in text.splitlines() if ln.strip()]
  if not lines:
    return ''
  best_i, best_s = 0, -1
  for i in range(len(lines)):
    chunk = '\n'.join(lines[i:i + window])
    s = score(terms, chunk)
    if s > best_s:
      best_i, best_s = i, s
  return '\n'.join(lines[best_i:best_i + window])


def summary_text(entry: Entry) -> str:
  if not entry.summary_file:
    return ''
  path = LOG_DIR / entry.summary_file
  try:
    return path.read_text(encoding='utf-8')
  except OSError:
    return ''


def summary_files(text: str) -> list[str]:
  """File paths from a summary's `files:` frontmatter block (a YAML list).

  Hand-parsed — recall.py stays stdlib. The `files:` key followed by `  - <path>`
  lines, ending at the frontmatter close or the next top-level key. Older
  summaries (and backfill stubs) carry no `files:` and yield [], so staleness
  degrades silently to no annotation.
  """
  files: list[str] = []
  in_block = False
  for line in text.splitlines():
    if not in_block:
      if re.match(r'^files:\s*$', line):
        in_block = True
      continue
    if line.strip() == '---':
      break
    item = re.match(r'^\s+-\s+(.+?)\s*$', line)
    if item:
      value = item.group(1)
      if len(value) >= 2 and value[0] == value[-1] and value[0] in '"\'':
        value = value[1:-1]
      files.append(value)
      continue
    if line.strip() and not line.startswith((' ', '\t')):
      break  # a new top-level key ends the list
  return files


def _git_toplevel(path: str) -> str | None:
  """The git repo root containing `path`, or None (path gone, or not a repo)."""
  parent = Path(path).parent
  if not parent.exists():
    return None
  try:
    result = subprocess.run(
      ['git', '-C', str(parent), 'rev-parse', '--show-toplevel'],
      capture_output=True, text=True, timeout=5)
  except (OSError, subprocess.SubprocessError):
    return None
  return result.stdout.strip() if result.returncode == 0 else None


def git_staleness(day: str, files: list[str]) -> str | None:
  """Annotate a surfaced summary with how far its files have moved since.

  A summary is true *as of its date*; this counts commits touching its files
  since, so the reader knows whether to trust it before climbing further. Files
  are grouped by repo (a session can edit more than one). Day granularity — the
  index carries a date, not a timestamp — means same-day commits, including the
  session's own, can count; that errs toward over-warning, the safe direction.
  Fail-open: any git trouble yields no note rather than a wrong one.
  """
  by_repo: dict[str, list[str]] = {}
  for path in files:
    if not path:
      continue
    repo = _git_toplevel(path)
    if repo:
      by_repo.setdefault(repo, []).append(path)
  if not by_repo:
    return None
  # Anchor to the START OF THE DAY AFTER the session, for two reasons. (1) A
  # session commits its own work the same day it is wrapped; counting those would
  # make every summary flag itself stale forever. Excluding the whole session day
  # means "stale" = touched on a *later* day — the session's own commits never
  # count. (2) Must be an explicit datetime: git approxidate fills a bare date's
  # missing time-of-day from the current wall clock, so `--since <day>` silently
  # drifts with the clock. The cost is a slight under-warn (a same-day edit after
  # the wrap is missed); precise wrap-timestamp granularity is the deferred fix.
  try:
    since = (datetime.strptime(day, '%Y-%m-%d') + timedelta(days=1)).strftime(
      '%Y-%m-%d 00:00:00')
  except ValueError:
    return None  # unparseable session date — skip rather than guess a boundary
  total = 0
  for repo, repo_files in by_repo.items():
    try:
      result = subprocess.run(
        ['git', '-C', repo, 'log', '--since', since, '--pretty=format:%h',
         '--', *repo_files],
        capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
      continue
    if result.returncode == 0:
      total += sum(1 for ln in result.stdout.splitlines() if ln.strip())
  if total == 0:
    return f'    ✓ fresh — no commits to these files since {day}'
  return (f'    ⚠ {total} commit(s) touched these files since {day} '
          '— summary may be stale')


def search_transcripts(terms: list[str], top: int) -> list[tuple[int, str, str]]:
  """Rung 3/4: grep raw JSONL for sessions where every term appears. Expensive;
  bounded by short-circuiting per file. Returns (score, session_id, snippet)."""
  hits: list[tuple[int, str, str]] = []
  for path in PROJECTS_DIR.glob('*/*.jsonl'):
    try:
      blob = path.read_text(encoding='utf-8', errors='ignore')
    except OSError:
      continue
    s = score(terms, blob)
    if s < len(set(terms)):  # require all distinct terms present
      continue
    line = next((ln for ln in blob.splitlines() if score(terms, ln) >= 1), '')
    hits.append((s, path.stem, line[:200]))
  hits.sort(key=lambda h: h[0], reverse=True)
  return hits[:top]


def estimate_tokens(text: str) -> int:
  return max(1, len(text) // 4)


def run(query: str, top: int, max_rung: str, session_id: str | None,
        do_log: bool) -> int:
  terms = tokenize(query)
  if not terms:
    print('recall: query has no searchable terms', file=sys.stderr)
    return 2

  ceiling = RUNG_ORDER.index(max_rung)
  index = load_index()
  if not index:
    print('recall: no session archive yet (~/.claude/logs/sessions.md missing)',
          file=sys.stderr)
    if do_log:
      retrievals_log.log_retrieval(query, ['index'], False, None, 1, session_id)
    return 0

  climbed = ['index']
  surfaced: list[str] = []
  result_ref: str | None = None

  # Rung 1 — index titles.
  ranked = sorted(
    ((score(terms, f'{e.day} {e.project} {e.title}'), e) for e in index),
    key=lambda x: x[0], reverse=True,
  )
  rung1 = [(s, e) for s, e in ranked if s > 0][:top]

  matches: list[tuple[int, Entry]] = []
  if rung1:
    matches = rung1
  elif ceiling >= RUNG_ORDER.index('summary'):
    # Rung 2 — full summary bodies (title missed; the detail is in the prose).
    climbed.append('summary')
    scored = []
    for e in index:
      body = summary_text(e)
      if body:
        scored.append((score(terms, body), e))
    matches = [(s, e) for s, e in sorted(scored, key=lambda x: x[0],
                                         reverse=True) if s > 0][:top]

  if matches:
    if 'summary' not in climbed:
      climbed.append('summary')  # we open the top match's summary for an excerpt
    for rank, (s, e) in enumerate(matches):
      sid = (e.session_id or '')[:8]
      line = f'[{s}/{len(set(terms))}] {e.day} · {e.project} · {e.title}'
      ref = e.summary_file or f'(no summary; session {sid})'
      surfaced.append(line)
      surfaced.append(f'        {ref}   session {sid}')
      print(line)
      print(f'        {ref}   session {sid}')
      if rank == 0:
        result_ref = Path(e.summary_file).name if e.summary_file else e.session_id
        body = summary_text(e)
        excerpt = best_excerpt(terms, body)
        if excerpt:
          block = '\n'.join('    ' + ln for ln in excerpt.splitlines())
          surfaced.append(excerpt)
          print(f'\n    — excerpt —\n{block}\n')
        note = git_staleness(e.day, summary_files(body))
        if note:
          surfaced.append(note)
          print(note)
    _finish(query, climbed, True, result_ref, surfaced, session_id, do_log)
    return 0

  # Rung 3/4 — raw transcripts (opt-in).
  if ceiling >= RUNG_ORDER.index('transcript'):
    climbed.append('transcript')
    if ceiling >= RUNG_ORDER.index('raw'):
      climbed.append('raw')
    deep = search_transcripts(terms, top)
    if deep:
      result_ref = deep[0][1]
      for s, sid, snippet in deep:
        line = f'[{s}/{len(set(terms))}] transcript {sid[:8]}: {snippet}'
        surfaced.append(line)
        print(line)
      _finish(query, climbed, True, result_ref, surfaced, session_id, do_log)
      return 0

  reached = climbed[-1]
  print(f'recall: no hit up to rung "{reached}".', file=sys.stderr)
  if reached == 'summary':
    print('       retry with --max-rung transcript to grep raw transcripts.',
          file=sys.stderr)
  _finish(query, climbed, False, None, surfaced, session_id, do_log)
  return 0


def _finish(query, climbed, hit, result_ref, surfaced, session_id, do_log):
  tokens = estimate_tokens('\n'.join(surfaced)) if surfaced else 1
  if do_log:
    retrievals_log.log_retrieval(query, climbed, hit, result_ref, tokens,
                                 session_id)


def main() -> int:
  parser = argparse.ArgumentParser(description=__doc__,
                                   formatter_class=argparse.RawDescriptionHelpFormatter)
  parser.add_argument('query', nargs='*', help='fuzzy-memory query words')
  parser.add_argument('--top', type=int, default=5, help='max matches to show')
  parser.add_argument('--max-rung', default='summary', choices=RUNG_ORDER,
                      help='deepest rung to climb (default: summary)')
  parser.add_argument('--session-id', default=None,
                      help='harness session issuing the query (for the log)')
  parser.add_argument('--no-log', action='store_true',
                      help='do not write a retrievals-log row')
  parser.add_argument('--rate', nargs=2, metavar=('ID', 'OUTCOME'),
                      help='rate a past retrieval: --rate <id> helpful|noise')
  args = parser.parse_args()

  if args.rate:
    ok = retrievals_log.rate(args.rate[0], args.rate[1])
    print('rated' if ok else 'no such retrieval id (or bad outcome)',
          file=sys.stderr)
    return 0 if ok else 1

  if not args.query:
    parser.error('a query is required (or use --rate)')
  return run(' '.join(args.query), args.top, args.max_rung,
             args.session_id, not args.no_log)


if __name__ == '__main__':
  sys.exit(main())
