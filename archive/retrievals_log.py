"""Retrievals log writer — one row per recall lookup against the session-archive
disclosure ladder (index -> summary -> transcript -> raw).

The SCHEMA is owned by Monition, not here:
`~/projects/monition/docs/contracts/retrievals-log.md` (v1). This module is only
the CMS-side *writer*; it cites that contract and must not duplicate the schema's
prose. Two load-bearing properties carried over from the contract:

  - **Fail-open.** Instrumentation must never break retrieval, and must work with
    Monition absent — there is no Monition runtime dependency in this path. Every
    write is wrapped; a failure drops the row and returns, never raises.
  - **`hit` vs `outcome` are independent.** `hit` is mechanical (did the ladder
    return a candidate), written here at lookup time. `outcome` is the post-hoc
    rating (helpful|noise), left NULL = unrated; it is never derived from `hit`
    and NULL is never coerced to "noise".

Physical encoding is CMS's choice (the contract leaves it open): one JSON object
per line in `~/.claude/logs/retrievals.jsonl`. The explicit `schema_version`
field is the per-row version stamp the contract requires — Monition does not read
this log, so a column fingerprint is unavailable.
"""

import json
import os
import uuid
from datetime import datetime
from pathlib import Path

# Bump only on a removed/renamed field or an enum-domain change; additive columns
# are compatible without a bump (retrievals-log.md, "Versioning and rejection").
SCHEMA_VERSION = 1

LOG_PATH = Path.home() / '.claude' / 'logs' / 'retrievals.jsonl'

# The ascending-cost rungs, per the contract's `rungs_climbed` vocabulary.
RUNGS = ('index', 'summary', 'transcript', 'raw')


def log_retrieval(
  query: str,
  rungs_climbed: list[str],
  hit: bool,
  result_ref: str | None,
  tokens: int,
  session_id: str | None = None,
) -> None:
  """Append one retrievals row. Never raises (fail-open).

  `rungs_climbed` is the ordered set actually touched; it is stored comma-joined
  in ascending-cost order. `session_id` defaults to the issuing harness session
  if the env exposes it, else the literal "unknown" anonymous bucket (contract
  semantics, joinable to `firings.session_id`).
  """
  try:
    ordered = [r for r in RUNGS if r in set(rungs_climbed)]
    row = {
      'id': str(uuid.uuid4()),
      'schema_version': SCHEMA_VERSION,
      'queried_at': datetime.now().isoformat(timespec='seconds'),
      'session_id': session_id or os.environ.get('CLAUDE_CODE_SESSION_ID') or 'unknown',
      'query': query,
      'rungs_climbed': ','.join(ordered),
      'hit': 1 if hit else 0,
      'result_ref': result_ref,
      'tokens': int(tokens),
      'outcome': None,  # unrated; rated later via `rate` below. NULL != noise.
    }
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open('a', encoding='utf-8') as handle:
      handle.write(json.dumps(row, ensure_ascii=False) + '\n')
  except Exception:
    return  # fail-open: a broken log must not break recall


def rate(retrieval_id: str, outcome: str) -> bool:
  """Set the post-hoc `outcome` (helpful|noise) on a logged row, in place.

  Returns True if a row was updated. Fail-open: returns False on any error or an
  unknown id rather than raising. `outcome` must be 'helpful' or 'noise' — the
  contract's enum; NULL stays the writer's job (unrated), never set here.
  """
  if outcome not in ('helpful', 'noise'):
    return False
  try:
    if not LOG_PATH.exists():
      return False
    lines = LOG_PATH.read_text(encoding='utf-8').splitlines()
    changed = False
    for i, line in enumerate(lines):
      if not line.strip():
        continue
      row = json.loads(line)
      if row.get('id') == retrieval_id:
        row['outcome'] = outcome
        lines[i] = json.dumps(row, ensure_ascii=False)
        changed = True
        break
    if not changed:
      return False
    tmp = LOG_PATH.with_suffix('.jsonl.tmp')
    tmp.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    os.replace(tmp, LOG_PATH)
    return True
  except Exception:
    return False
