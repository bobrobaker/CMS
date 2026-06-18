#!/usr/bin/env python3
"""MCP server exposing `search_sessions` — semantic recall over the session-archive
summary corpus, backed by the local ChromaDB built by index.py.

This is the SEMANTIC rung of the disclosure ladder's retrieval side; `recall.py`
is the grep rung. Both write to the same retrievals log (schema owned by
Monition), so the two surfaces feed one eval substrate — the data a future
eval-governed router (decision 4) trains on to decide which fires. There is no
learned router in v1; the routing rule is documented in runbook.md.

Register once (point it at a venv that has the deps — see runbook.md):
    claude mcp add --transport stdio --scope user session-archive -- \
        /path/to/venv/bin/python /path/to/CMS/archive/semantic/server.py
Re-index when summaries change:  python3 index.py
"""

import asyncio
import sys
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions
from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types

# retrievals_log lives one level up (archive/), shared with the grep tool.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import retrievals_log  # noqa: E402
from index import DB_PATH, COLLECTION, MODEL, SUMMARY_DIR  # noqa: E402

server = Server('session-archive')
_col = None


def _collection():
  global _col
  if _col is None:
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=MODEL)
    _col = chromadb.PersistentClient(path=str(DB_PATH)).get_collection(
      COLLECTION, embedding_function=ef)
  return _col


def _staleness_note() -> str:
  """Warn if summaries postdate the last index build (recall would miss them)."""
  db_file = DB_PATH / 'chroma.sqlite3'
  try:
    if not SUMMARY_DIR.exists() or not db_file.exists():
      return ''
    summaries = list(SUMMARY_DIR.glob('*.md'))
    if summaries and max(f.stat().st_mtime for f in summaries) > db_file.stat().st_mtime:
      return ('⚠ Index may be stale — summaries exist that postdate the last '
              'rebuild. Run `python3 index.py` to include them.\n\n')
  except Exception:
    pass
  return ''


@server.list_tools()
async def list_tools() -> list[types.Tool]:
  return [types.Tool(
    name='search_sessions',
    description=(
      'Semantic search over the global session archive (summaries of past Claude '
      'Code sessions across every project). Use for fuzzy-memory recall — "I '
      'remember a session where I worked on X" — when keywords are uncertain. For '
      'exact keyword lookup, grep ~/.claude/logs/sessions.md or use recall.py.'),
    inputSchema={
      'type': 'object',
      'properties': {
        'query': {'type': 'string', 'description': 'Natural-language recall query'},
        'n_results': {'type': 'integer',
                      'description': 'Sessions to return (default 5, max 15)',
                      'default': 5},
      },
      'required': ['query'],
    },
  )]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
  if name != 'search_sessions':
    raise ValueError(f'Unknown tool: {name}')
  query = arguments['query']
  n = min(int(arguments.get('n_results', 5)), 15)

  results = _collection().query(query_texts=[query], n_results=n)
  docs = results['documents'][0]
  metas = results['metadatas'][0]
  dists = results['distances'][0]

  hit = bool(docs)
  result_ref = metas[0]['file'] if hit else None
  out_lines: list[str] = []
  note = _staleness_note()
  if note:
    out_lines.append(note)
  for i, (doc, meta, dist) in enumerate(zip(docs, metas, dists), 1):
    out_lines.append(f'### {i}. {meta.get("title") or meta["file"]}  '
                     f'(score {round(1 - dist, 3)})')
    out_lines.append(f'**{meta.get("date","?")} · {meta.get("project","?")}** · '
                     f'`{meta["file"]}` · session `{meta.get("session","?")[:8]}`')
    out_lines.append('')
    out_lines.append(doc[:700])
    out_lines.append('')
  text = '\n'.join(out_lines) if hit else 'No matching sessions.'

  # Semantic search reads the summary corpus → log at the summary rung. session_id
  # comes from the env if the harness exposes it; else the anonymous bucket.
  retrievals_log.log_retrieval(query, ['summary'], hit, result_ref,
                               max(1, len(text) // 4))
  return [types.TextContent(type='text', text=text)]


async def main():
  async with stdio_server() as (read, write):
    await server.run(read, write, server.create_initialization_options())


if __name__ == '__main__':
  asyncio.run(main())
