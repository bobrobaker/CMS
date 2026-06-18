#!/usr/bin/env python3
# Copyright 2026 Ilya Sherman (ishermandom@)
# SPDX-License-Identifier: MIT
"""Record per-session token counts in the global session log.

As a SessionEnd hook (JSON payload on stdin), sums the four API usage
counters across the session's transcript and subagent transcripts, then
writes a `tokens:` line into the session log: into the entry whose
session-id marker matches (the wrap-session skill stamps the marker),
or as a new counts-only "stats-only" entry when no marker exists.

With `--print`, reports the live session's marker line and provisional
counts without writing — reflection input for the wrap-session skill;
the SessionEnd hook writes the final, complete line.
"""

import argparse
import json
import os
import re
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

DEFAULT_LOG_PATH = Path.home() / '.claude' / 'logs' / 'sessions.md'
DIAGNOSTIC_LOG_PATH = Path.home() / '.claude' / 'logs' / 'session-tokens.log'

# Sessions whose cwd contains any of these fragments are skipped — they are
# subagent spawns, worktrees, or temp dirs that don't produce session-level
# knowledge worth indexing. Override by setting CMS_SKIP_CWD (colon-separated).
_DEFAULT_SKIP_CWD_FRAGMENTS = (
  '/tmp/', '/-tmp-', '/cache/agent-spawn', '/cache/agent-workstream',
  'superset-worktrees', 'agent-spawn-worktrees',
)
SKIP_CWD_FRAGMENTS: tuple[str, ...] = tuple(
  f for f in os.environ.get('CMS_SKIP_CWD', '').split(':') if f
) or _DEFAULT_SKIP_CWD_FRAGMENTS

# Sessions with fewer real user turns than this are drive-bys and skipped.
MIN_USER_TURNS = 2

# Counter fields summed into the log, plus the non-counter fields
# current transcript records carry. A field outside this set means the
# usage schema changed and the counters may be silently wrong.
EXPECTED_USAGE_FIELD_NAMES = frozenset(
  {
    'input_tokens',
    'output_tokens',
    'cache_creation_input_tokens',
    'cache_read_input_tokens',
    'cache_creation',
    'inference_geo',
    'iterations',
    'output_tokens_details',
    'server_tool_use',
    'service_tier',
    'speed',
  }
)


def log_diagnostic(message: str) -> None:
  """Report a problem to stderr and the diagnostic log file.

  stderr alone would vanish: SessionEnd hook output is shown only in
  debug mode, and the session is already over when this hook runs.
  """
  print(f'session-tokens: {message}', file=sys.stderr)
  DIAGNOSTIC_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
  timestamp = datetime.now().isoformat(timespec='seconds')
  with DIAGNOSTIC_LOG_PATH.open('a') as log_file:
    log_file.write(f'{timestamp} {message}\n')


@dataclass(frozen=True)
class UsageTotals:
  """Summed API usage counters for one session's transcripts."""

  input_tokens: int
  output_tokens: int
  cache_creation_input_tokens: int
  cache_read_input_tokens: int


def _usage_of(record: object) -> Mapping[str, object] | None:
  """The usage mapping on one transcript record; None when absent."""
  if not isinstance(record, Mapping):
    return None
  message = record.get('message')
  if not isinstance(message, Mapping):
    return None
  usage = message.get('usage')
  return usage if isinstance(usage, Mapping) else None


def summed_usage(transcript_paths: Iterable[Path]) -> UsageTotals:
  """Sum the usage counters across all records in the transcripts."""
  totals = {
    'input_tokens': 0,
    'output_tokens': 0,
    'cache_creation_input_tokens': 0,
    'cache_read_input_tokens': 0,
  }
  malformed_line_count = 0
  # Each distinct schema oddity is logged once after the sweep, not per
  # record — a drifted schema would otherwise flood the diagnostic log.
  oddities: set[str] = set()
  for path in transcript_paths:
    for line in path.read_text().splitlines():
      try:
        record: object = json.loads(line)
      except json.JSONDecodeError:
        # A crash mid-write can truncate the final line; count and
        # continue rather than losing the whole transcript's totals.
        malformed_line_count += 1
        continue
      usage = _usage_of(record)
      if usage is None:
        continue
      for name in usage.keys() - EXPECTED_USAGE_FIELD_NAMES:
        oddities.add(f'unexpected usage field: {name}')
      for name in totals:
        value = usage.get(name)
        if isinstance(value, int):
          totals[name] += value
        elif value is not None:
          oddities.add(f'non-integer counter {name}: {value!r}')
  if malformed_line_count:
    log_diagnostic(
      f'skipped {malformed_line_count} malformed transcript line(s)'
    )
  for oddity in sorted(oddities):
    log_diagnostic(oddity)
  return UsageTotals(
    input_tokens=totals['input_tokens'],
    output_tokens=totals['output_tokens'],
    cache_creation_input_tokens=totals['cache_creation_input_tokens'],
    cache_read_input_tokens=totals['cache_read_input_tokens'],
  )


def session_transcript_paths(transcript_path: Path) -> Sequence[Path]:
  """The main transcript plus the session's subagent transcripts.

  Subagent transcripts live in a `<session-id>/subagents/` directory
  alongside the main `<session-id>.jsonl` file.
  """
  subagent_directory = (
    transcript_path.parent / transcript_path.stem / 'subagents'
  )
  return [transcript_path, *sorted(subagent_directory.glob('*.jsonl'))]


def formatted_count(count: int) -> str:
  """A compact form: 873 → '873', 51049 → '51.0k', 10703404 → '10.7M'."""
  for threshold, suffix in ((1_000_000, 'M'), (1_000, 'k')):
    if count >= threshold:
      scaled = count / threshold
      digits = 0 if scaled >= 100 else 1
      return f'{scaled:.{digits}f}{suffix}'
  return str(count)


def tokens_line(totals: UsageTotals) -> str:
  """The log line summarizing one session's token counts."""
  return (
    f'tokens: input {formatted_count(totals.input_tokens)}'
    f' · output {formatted_count(totals.output_tokens)}'
    f' · cache-write {formatted_count(totals.cache_creation_input_tokens)}'
    f' · cache-read {formatted_count(totals.cache_read_input_tokens)}'
  )


def marker_line(session_id: str) -> str:
  """The marker comment that ties a log entry to its session."""
  return f'<!-- session: {session_id} -->'


def updated_log_text(
  log_text: str, session_id: str, new_line: str
) -> str | None:
  """log_text with new_line inserted after the session's marker.

  Returns None when the marker is absent. When several entries carry
  the marker (wrap-session ran more than once), the last one wins.
  Returns the text unchanged when a tokens line already follows the
  marker, so a duplicate hook firing is a no-op.
  """
  marker = marker_line(session_id)
  lines = log_text.splitlines()
  if marker not in lines:
    return None
  index = len(lines) - 1 - lines[::-1].index(marker)
  follower = lines[index + 1] if index + 1 < len(lines) else ''
  if follower.startswith('tokens:'):
    return log_text
  lines.insert(index + 1, new_line)
  return '\n'.join(lines) + '\n'


def first_user_message(transcript_path: Path, limit: int = 80) -> str | None:
  """The session's first real user prompt — one line, truncated — or None.

  Skips injected context (isMeta records: reminders, hook output) and bare
  slash-command echoes, reading the first user record that carries prose. This
  is what titles an unwrapped session's log entry, so the entry is rung 1 of the
  archive's disclosure ladder — findable by what the user actually asked, not a
  generic 'stats-only'. Fail-soft: an absent or malformed transcript yields
  None, never an error.
  """
  try:
    lines = transcript_path.read_text().splitlines()
  except OSError:
    return None
  for line in lines:
    try:
      record: object = json.loads(line)
    except json.JSONDecodeError:
      continue
    if not isinstance(record, Mapping):
      continue
    if record.get('type') != 'user' or record.get('isMeta'):
      continue
    message = record.get('message')
    content = message.get('content') if isinstance(message, Mapping) else None
    text: str | None = None
    if isinstance(content, str):
      text = content
    elif isinstance(content, list):
      for item in content:
        if isinstance(item, Mapping) and item.get('type') == 'text':
          candidate = item.get('text')
          if isinstance(candidate, str) and candidate.strip():
            text = candidate
            break
    if not text or not text.strip():
      continue
    stripped = text.strip()
    if stripped.startswith(('<command-', '<local-command')):
      continue  # a slash-command echo, not a typed prompt
    collapsed = ' '.join(stripped.split())
    suffix = '…' if len(collapsed) > limit else ''
    return collapsed[:limit].rstrip() + suffix
  return None


def count_user_turns(transcript_path: Path) -> int:
  """Real user turns in the transcript — injected meta records excluded."""
  count = 0
  try:
    for line in transcript_path.read_text().splitlines():
      try:
        record: object = json.loads(line)
      except json.JSONDecodeError:
        continue
      if isinstance(record, Mapping) and record.get('type') == 'user' and not record.get('isMeta'):
        count += 1
  except OSError:
    pass
  return count


def unwrapped_entry(
  project: str, session_id: str, new_line: str, entry_date: str, descriptor: str
) -> str:
  """A log entry for a session with no wrap entry.

  `descriptor` titles it — the first user message when one is recoverable, so an
  unwrapped session is still findable by topic; 'stats-only' when no prose was
  found. The marker + counts line follow, matching a wrapped entry's shape.
  """
  return (
    f'\n## {entry_date} · {project} · {descriptor}\n'
    f'\n'
    f'{marker_line(session_id)}\n'
    f'{new_line}\n'
  )


def write_log(log_path: Path, text: str) -> None:
  """Replace the log atomically so a failure can't truncate it."""
  log_path.parent.mkdir(parents=True, exist_ok=True)
  temporary_path = log_path.parent / (log_path.name + '.tmp')
  temporary_path.write_text(text)
  os.replace(temporary_path, log_path)


def record_session_end(payload: Mapping[str, object], log_path: Path) -> None:
  """Count the ended session's tokens and record them in the log."""
  cwd = payload.get('cwd', '')
  if isinstance(cwd, str) and any(frag in cwd for frag in SKIP_CWD_FRAGMENTS):
    return

  transcript_value = payload.get('transcript_path')
  if not isinstance(transcript_value, str):
    raise ValueError(f'payload has no transcript_path: {dict(payload)}')
  transcript_path = Path(transcript_value)
  session_value = payload.get('session_id')
  session_id = (
    session_value if isinstance(session_value, str) else transcript_path.stem
  )

  if count_user_turns(transcript_path) < MIN_USER_TURNS:
    return

  totals = summed_usage(session_transcript_paths(transcript_path))
  new_line = tokens_line(totals)
  log_text = log_path.read_text() if log_path.exists() else ''

  updated_text = updated_log_text(log_text, session_id, new_line)
  if updated_text is None:
    cwd_value = payload.get('cwd')
    project = Path(cwd_value).name if isinstance(cwd_value, str) else 'unknown'
    descriptor = first_user_message(transcript_path) or 'stats-only'
    entry = unwrapped_entry(
      project, session_id, new_line, date.today().isoformat(), descriptor
    )
    updated_text = log_text + entry
  write_log(log_path, updated_text)


def live_transcript_path(cwd: Path) -> Path:
  """This session's transcript in cwd's project directory.

  Prefer the authoritative harness session id (`$CLAUDE_CODE_SESSION_ID`); fall
  back to newest-by-mtime only when it is unset — newest mtime misidentifies the
  session when another runs in the same cwd concurrently.
  """
  slug = re.sub(r'[^A-Za-z0-9-]', '-', str(cwd))
  project_directory = Path.home() / '.claude' / 'projects' / slug
  session_id = os.environ.get('CLAUDE_CODE_SESSION_ID')
  if session_id:
    candidate = project_directory / f'{session_id}.jsonl'
    if candidate.exists():
      return candidate
  transcript_paths = sorted(
    project_directory.glob('*.jsonl'),
    key=lambda path: path.stat().st_mtime,
    reverse=True,
  )
  if not transcript_paths:
    raise FileNotFoundError(f'no transcripts under {project_directory}')
  return transcript_paths[0]


def print_live_counts() -> None:
  """Print the live session's marker line and provisional tokens line."""
  transcript_path = live_transcript_path(Path.cwd())
  totals = summed_usage(session_transcript_paths(transcript_path))
  print(marker_line(transcript_path.stem))
  print(tokens_line(totals))


def main() -> int:
  """Dispatch between hook mode (stdin payload) and `--print`."""
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument(
    '--print',
    dest='print_only',
    action='store_true',
    help='print the live session marker and counts; write nothing',
  )
  parser.add_argument(
    '--log',
    type=Path,
    default=DEFAULT_LOG_PATH,
    help='session log to update (for tests)',
  )
  arguments = parser.parse_args()

  try:
    if arguments.print_only:
      print_live_counts()
    else:
      payload: object = json.loads(sys.stdin.read())
      if not isinstance(payload, Mapping):
        raise ValueError(f'hook payload is not a JSON object: {payload!r}')
      record_session_end(payload, arguments.log)
  except (OSError, ValueError, json.JSONDecodeError) as error:
    log_diagnostic(str(error))
    return 1
  return 0


if __name__ == '__main__':
  sys.exit(main())
