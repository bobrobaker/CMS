#!/usr/bin/env python3
"""Index the session-archive SUMMARY corpus into a local ChromaDB for semantic
recall. One document per session summary (the files are already atomic recall
units — a query should return whole sessions, not fragments).

Corpus is the summary files ONLY (`~/.claude/logs/sessions/*.md`) — never raw
transcripts (decision 5: raw is noise-dominated and never embedded). Index data
lives user-level (the archive is global, not per-project); the model is MiniLM,
matching the rest of the local-RAG machinery.

    python3 index.py            # incremental (re-embed only changed files)
    python3 index.py --force    # full wipe-and-rebuild

Incremental keys on file mtime: unchanged summaries are skipped (an all-skip run
never pays the model-load cost), changed ones are delete+re-added, and summaries
that vanished are dropped. Stdlib for parsing; chromadb/sentence-transformers are
the only heavy deps (see requirements.txt).
"""

import re
import sys
from pathlib import Path

LOG_DIR = Path.home() / '.claude' / 'logs'
SUMMARY_DIR = LOG_DIR / 'sessions'
DB_PATH = LOG_DIR / 'sessions-index'      # user-level, machine-local (gitignored by living outside any repo)
COLLECTION = 'session_archive'
MODEL = 'all-MiniLM-L6-v2'
EMBED_CAP = 2500  # chars of (title + abstract + body) embedded per session


def parse_frontmatter(text: str) -> tuple[dict, str]:
  """Split a summary into (frontmatter dict, body). Handles both plain
  `key: value` and folded block scalars (`key: >-` + indented continuation) —
  the form BOTH writers (backfill.py and the wrap-session skill) emit for the
  free-text title/abstract."""
  match = re.match(r'^---\n(.*?)\n---\n?', text, re.DOTALL)
  if not match:
    return {}, text
  block, body = match.group(1), text[match.end():]
  lines = block.split('\n')
  meta: dict[str, str] = {}
  i = 0
  while i < len(lines):
    keyval = re.match(r'^(\w[\w-]*):\s*(.*)$', lines[i])
    if not keyval:
      i += 1
      continue
    key, value = keyval.group(1), keyval.group(2).strip()
    if value in ('>-', '>', '|', '|-'):
      # folded/literal block scalar: the content is the indented continuation.
      i += 1
      collected = []
      while i < len(lines) and lines[i][:1] in (' ', '\t'):
        collected.append(lines[i].strip())
        i += 1
      meta[key] = ' '.join(c for c in collected if c)
      continue
    meta[key] = value
    i += 1
  return meta, body


def build_record(fpath: Path) -> tuple[str, str, dict, str] | None:
  """Return (id, document, metadata, mtime) for one summary file, or None."""
  try:
    text = fpath.read_text(encoding='utf-8', errors='ignore')
  except OSError:
    return None
  meta, body = parse_frontmatter(text)
  rel = str(fpath.relative_to(LOG_DIR))
  mtime = str(fpath.stat().st_mtime)
  title = meta.get('title', '')
  abstract = meta.get('abstract', '')
  document = f'{title}\n{abstract}\n{body}'.strip()[:EMBED_CAP]
  if not document:
    return None
  metadata = {
    'file': rel,
    'date': meta.get('date', ''),
    'project': meta.get('project', ''),
    'session': meta.get('session', ''),
    'source': meta.get('source', ''),
    'title': title or rel,
    'file_mtime': mtime,
  }
  return rel, document, metadata, mtime


def _make_ef():
  from chromadb.utils import embedding_functions
  return embedding_functions.SentenceTransformerEmbeddingFunction(model_name=MODEL)


def _summaries() -> list[Path]:
  if not SUMMARY_DIR.exists():
    return []
  return sorted(p for p in SUMMARY_DIR.glob('*.md') if p.name != 'sessions.md')


def build_index(force: bool = False, quiet: bool = False) -> None:
  import chromadb

  client = chromadb.PersistentClient(path=str(DB_PATH))
  if force:
    try:
      client.delete_collection(COLLECTION)
    except Exception:
      pass
    col = client.create_collection(COLLECTION, embedding_function=_make_ef())
    added = 0
    for fpath in _summaries():
      rec = build_record(fpath)
      if rec is None:
        continue
      rid, doc, meta, _ = rec
      col.add(ids=[rid], documents=[doc], metadatas=[meta])
      added += 1
    print(f'full build: {added} sessions indexed -> {DB_PATH}')
    return

  # Incremental. A plain handle (no embedding fn) serves get/delete so an
  # all-skip run never loads the model.
  try:
    scan = client.get_collection(COLLECTION)
  except Exception:
    scan = client.get_or_create_collection(COLLECTION, embedding_function=_make_ef())
  ef_col = {'c': None}

  def embed_col():
    if ef_col['c'] is None:
      ef_col['c'] = client.get_or_create_collection(
        COLLECTION, embedding_function=_make_ef())
    return ef_col['c']

  present, reindexed, skipped = set(), 0, 0
  for fpath in _summaries():
    rec = build_record(fpath)
    if rec is None:
      continue
    rid, doc, meta, mtime = rec
    present.add(rid)
    existing = scan.get(ids=[rid], include=['metadatas'])
    if existing['metadatas'] and existing['metadatas'][0].get('file_mtime') == mtime:
      skipped += 1
      continue
    scan.delete(ids=[rid])
    embed_col().add(ids=[rid], documents=[doc], metadatas=[meta])
    reindexed += 1
    if not quiet:
      print(f'  reindexed {rid}', file=sys.stderr)

  all_meta = scan.get(include=['metadatas'])['metadatas']
  indexed = {m['file'] for m in all_meta if m.get('file')}
  orphans = indexed - present
  for orphan in orphans:
    scan.delete(ids=[orphan])
    if not quiet:
      print(f'  removed orphan {orphan}', file=sys.stderr)
  print(f'incremental: {reindexed} reindexed, {skipped} skipped, '
        f'{len(orphans)} orphaned removed -> {DB_PATH}')


if __name__ == '__main__':
  import argparse
  parser = argparse.ArgumentParser(description=__doc__,
                                   formatter_class=argparse.RawDescriptionHelpFormatter)
  parser.add_argument('--force', action='store_true', help='full wipe-and-rebuild')
  parser.add_argument('-q', '--quiet', action='store_true')
  args = parser.parse_args()
  build_index(force=args.force, quiet=args.quiet)
