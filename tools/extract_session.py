#!/usr/bin/env python3
"""Extract user+assistant text from a Claude Code session JSONL.

Produces a compact, role-labelled conversational trace — the shared foundation
two things consume: the session archive (backfill summarisation, which caps the
trace and feeds it to a model) and tier-3 evaluation (per-project trace input
for failure-mode scoring). Tool calls, tool results and raw JSONL are
deliberately left out: they are noise-dominated and never summarised.

The harness JSONL schema is an external contract that shifts between harness
versions. Rather than silently dropping content when a new record or block type
appears, this tool knows the schema surface it depends on and acts as a DRIFT
CANARY: anything outside the known surface is reported (to stderr and a
diagnostic log) so the archive notices the format moved instead of quietly
losing turns. `--canary` runs that detection alone over one or more transcripts
and exits non-zero on drift, so it can stand watch over the whole corpus.

Usage:
    extract_session.py <session.jsonl> [--out PATH] [--cap N] [--include-thinking]
    extract_session.py --canary <session.jsonl> [<session.jsonl> ...]

Stdlib only, fail-soft: a malformed line never sinks the whole transcript.
"""

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

DIAGNOSTIC_LOG_PATH = Path.home() / '.claude' / 'logs' / 'session-archive.log'

# The schema surface the extractor depends on, current as of harness 2.1.x.
# A record `type` or content-block `type` outside these sets means the format
# drifted under us — noticing that is the canary's whole job. Extend these
# deliberately when a new type is confirmed conversational; never to silence an
# alarm without first checking what the new type actually carries.
KNOWN_RECORD_TYPES = frozenset({
  'user', 'assistant', 'system', 'summary', 'attachment', 'mode',
  'ai-title', 'last-prompt', 'file-history-snapshot', 'queue-operation',
  'bridge-session', 'permission-mode',
})
KNOWN_BLOCK_TYPES = frozenset({
  'text', 'thinking', 'tool_use', 'tool_result', 'image',
})
# Of the known blocks, the ones whose text is lifted into the trace. `thinking`
# joins only under --include-thinking (reasoning traces, for tier-3); tool_use,
# tool_result and image are machine payload and stay out.
PROSE_BLOCK_TYPES = frozenset({'text'})
CONVERSATIONAL_ROLES = frozenset({'user', 'assistant'})
# Tool-use names that write a file — the staleness-capture signal (`--files`).
# Read/Grep/Bash also carry a file_path but only consult; they are excluded.
EDIT_TOOLS = frozenset({'Edit', 'Write', 'MultiEdit', 'NotebookEdit'})


def log_diagnostic(message: str) -> None:
  """Report a schema problem to stderr and the diagnostic log.

  stderr can be swallowed — the extractor often runs inside a backfill loop or
  behind a hook — so drift is also appended to a durable log a human can sweep.
  A read-only log must never sink an extraction, so logging itself fails open.
  """
  print(f'extract-session: {message}', file=sys.stderr)
  try:
    DIAGNOSTIC_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().isoformat(timespec='seconds')
    with DIAGNOSTIC_LOG_PATH.open('a') as log_file:
      log_file.write(f'{timestamp} {message}\n')
  except OSError:
    pass


@dataclass(frozen=True)
class Turn:
  """One conversational turn lifted from the transcript."""

  role: str
  text: str


@dataclass
class DriftReport:
  """What the sweep saw that the known schema surface does not cover.

  Oddities are deduplicated: a drifted schema would otherwise repeat the same
  line per record. `malformed_lines` counts unparseable JSON — usually a single
  crash-truncated final line, so it is reported but not on its own treated as
  drift; an unknown record or block type is.
  """

  source: str
  total_records: int = 0
  malformed_lines: int = 0
  oddities: set[str] = field(default_factory=set)

  @property
  def has_drift(self) -> bool:
    return bool(self.oddities)

  def render(self) -> str:
    lines = [f'{self.source}: {self.total_records} records']
    if self.malformed_lines:
      lines.append(f'  {self.malformed_lines} malformed line(s)')
    for oddity in sorted(self.oddities):
      lines.append(f'  DRIFT: {oddity}')
    if not self.has_drift and not self.malformed_lines:
      lines.append('  clean')
    return '\n'.join(lines)


def _prose_from_content(
  content: object, role: str, report: DriftReport, include_thinking: bool
) -> list[str]:
  """Prose strings lifted from one record's content; records drift in report."""
  if isinstance(content, str):
    text = content.strip()
    return [text] if text else []
  if content is None:
    return []
  if not isinstance(content, list):
    report.oddities.add(
      f'unexpected {role} content type: {type(content).__name__}'
    )
    return []
  wanted = PROSE_BLOCK_TYPES | ({'thinking'} if include_thinking else set())
  prose = []
  for item in content:
    if not isinstance(item, Mapping):
      report.oddities.add(
        f'non-object block in {role} content: {type(item).__name__}'
      )
      continue
    block_type = item.get('type')
    if block_type not in KNOWN_BLOCK_TYPES:
      report.oddities.add(f'unknown content block type: {block_type!r}')
    if block_type in wanted:
      text = item.get('text')
      if isinstance(text, str) and text.strip():
        prose.append(text.strip())
  return prose


def extract(
  jsonl_path: Path, include_thinking: bool = False
) -> tuple[list[Turn], DriftReport]:
  """Sweep one transcript into role-labelled turns plus a drift report."""
  report = DriftReport(source=jsonl_path.name)
  turns: list[Turn] = []
  with jsonl_path.open(encoding='utf-8', errors='replace') as handle:
    for line in handle:
      line = line.strip()
      if not line:
        continue
      try:
        record: object = json.loads(line)
      except json.JSONDecodeError:
        # A crash mid-write can truncate the final line; count and continue
        # rather than losing the rest of the transcript.
        report.malformed_lines += 1
        continue
      if not isinstance(record, Mapping):
        report.oddities.add(f'non-object record: {type(record).__name__}')
        continue
      report.total_records += 1
      record_type = record.get('type')
      if record_type not in KNOWN_RECORD_TYPES:
        report.oddities.add(f'unknown record type: {record_type!r}')
      if record_type not in CONVERSATIONAL_ROLES:
        continue
      if record.get('isMeta'):
        # Injected harness context (system reminders, hook output, command
        # echoes) — not the user's or the model's own prose.
        continue
      message = record.get('message')
      content = message.get('content') if isinstance(message, Mapping) else None
      prose = _prose_from_content(content, record_type, report, include_thinking)
      if prose:
        turns.append(Turn(role=record_type, text='\n\n'.join(prose)))
  return turns, report


def extract_files(jsonl_path: Path) -> list[str]:
  """Distinct file paths the session edited, in first-touch order.

  The archive's staleness check needs to know what a session actually changed.
  That signal lives in the transcript's Edit/Write/MultiEdit tool calls and is
  lifted here deterministically (no model). The prose trace drops tool_use blocks
  as noise; for this purpose they are the whole point. Fail-soft — an unreadable
  or malformed transcript yields [].
  """
  seen: dict[str, None] = {}  # dict preserves first-seen order while deduping
  try:
    handle = jsonl_path.open(encoding='utf-8', errors='replace')
  except OSError:
    return []
  with handle:
    for line in handle:
      line = line.strip()
      if not line:
        continue
      try:
        record = json.loads(line)
      except json.JSONDecodeError:
        continue
      if not isinstance(record, Mapping) or record.get('type') != 'assistant':
        continue
      message = record.get('message')
      content = message.get('content') if isinstance(message, Mapping) else None
      if not isinstance(content, list):
        continue
      for item in content:
        if not isinstance(item, Mapping) or item.get('type') != 'tool_use':
          continue
        # Only edit-class tools change a file. Read/Grep/Bash also carry a
        # file_path but are context, not work products — counting them would
        # make every file the session glanced at look stale-checkable.
        if item.get('name') not in EDIT_TOOLS:
          continue
        tool_input = item.get('input')
        if not isinstance(tool_input, Mapping):
          continue
        path = tool_input.get('file_path') or tool_input.get('notebook_path')
        if isinstance(path, str) and path:
          seen[path] = None
  return list(seen)


def render_trace(session_id: str, turns: Sequence[Turn]) -> str:
  """A role-labelled trace: a header, then `[role]` / text blocks per turn."""
  parts = [f'# Session trace — {session_id}', f'# {len(turns)} turns', '']
  for turn in turns:
    parts.append(f'[{turn.role}]')
    parts.append(turn.text)
    parts.append('')
  return '\n'.join(parts).rstrip() + '\n'


def cap_head_tail(text: str, cap: int) -> str:
  """Keep the first and last cap//2 chars, eliding the middle.

  Backfill summarisation needs the shape of a long session — its open and its
  close — not every middle turn. Splitting head+tail preserves both ends.
  """
  if cap <= 0 or len(text) <= cap:
    return text
  half = cap // 2
  elided = len(text) - 2 * half
  return f'{text[:half]}\n\n[... {elided} chars elided ...]\n\n{text[-half:]}'


def run_extract(
  jsonl_path: Path, include_thinking: bool, cap: int, out: Path | None
) -> int:
  """Extract one transcript; emit the trace; report drift fail-open."""
  if not jsonl_path.exists():
    print(f'ERROR: session file not found: {jsonl_path}', file=sys.stderr)
    print(
      'Expected ~/.claude/projects/<project-slug>/<session-id>.jsonl',
      file=sys.stderr,
    )
    return 1
  turns, report = extract(jsonl_path, include_thinking)
  if report.has_drift:
    log_diagnostic(f'{report.source}: ' + '; '.join(sorted(report.oddities)))
  if not turns:
    log_diagnostic(f'no user/assistant text extracted from {report.source}')
    return 2
  trace = render_trace(jsonl_path.stem, turns)
  if cap:
    trace = cap_head_tail(trace, cap)
  if out is not None:
    out.write_text(trace, encoding='utf-8')
    print(
      f'wrote {len(turns)} turns ({len(trace)} chars) → {out}', file=sys.stderr
    )
  else:
    sys.stdout.write(trace)
  return 0


def run_canary(paths: Sequence[Path]) -> int:
  """Report schema drift over each transcript; exit non-zero if any drifted."""
  drifted = False
  for path in paths:
    if not path.exists():
      print(f'{path.name}: MISSING')
      drifted = True
      continue
    _, report = extract(path)
    print(report.render())
    if report.has_drift:
      drifted = True
  return 1 if drifted else 0


def main() -> int:
  parser = argparse.ArgumentParser(
    description=(
      'Extract user+assistant text from a session JSONL; '
      'carries a schema drift canary.'
    )
  )
  parser.add_argument('paths', nargs='+', type=Path, help='session JSONL file(s)')
  parser.add_argument(
    '--canary',
    action='store_true',
    help='report schema drift over the transcript(s); write no trace; '
    'exit non-zero on drift',
  )
  parser.add_argument(
    '--out',
    type=Path,
    help='write the trace to this file instead of stdout (single input only)',
  )
  parser.add_argument(
    '--cap',
    type=int,
    default=0,
    help='cap the trace to ~N chars, head+tail split (for backfill); 0 = no cap',
  )
  parser.add_argument(
    '--include-thinking',
    action='store_true',
    help="also lift assistant 'thinking' blocks (reasoning traces, for tier-3)",
  )
  parser.add_argument(
    '--files',
    action='store_true',
    help='emit the distinct file paths the session edited '
    '(Edit/Write/MultiEdit), one per line; the staleness-capture source, '
    'no trace written',
  )
  arguments = parser.parse_args()

  if arguments.canary:
    return run_canary(arguments.paths)
  if arguments.files:
    if len(arguments.paths) != 1:
      print('ERROR: --files takes exactly one transcript', file=sys.stderr)
      return 1
    for path in extract_files(arguments.paths[0]):
      print(path)
    return 0
  if len(arguments.paths) != 1:
    print(
      'ERROR: extract mode takes exactly one transcript '
      '(use --canary for many)',
      file=sys.stderr,
    )
    return 1
  return run_extract(
    arguments.paths[0], arguments.include_thinking, arguments.cap, arguments.out
  )


if __name__ == '__main__':
  sys.exit(main())
