# Session-archive semantic recall — runbook

Semantic (embedding) recall over the **summary corpus** of the global session
archive (`~/.claude/logs/sessions/*.md`). The cheap grep path is `archive/recall.py`;
this is the fuzzy-memory path. Both write the same retrievals log
(`~/.claude/logs/retrievals.jsonl`, schema owned by Monition —
`~/projects/monition/docs/contracts/retrievals-log.md`).

## Layout

- `index.py` — builds/updates the ChromaDB; one document per session summary;
  incremental by mtime. Data lives **user-level** at `~/.claude/logs/sessions-index/`
  (the archive is global, not per-project).
- `server.py` — MCP stdio server exposing `search_sessions(query, n_results)`.
- Corpus is summaries **only** — raw transcripts are never embedded (noise-dominated).

## Setup (one-time)

```bash
cd ~/projects/CMS/archive/semantic
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 index.py --force                 # first full build (~minutes on CPU)
# register the MCP server at user scope, pointed at the venv interpreter:
claude mcp add --transport stdio --scope user session-archive -- \
    "$PWD/.venv/bin/python" "$PWD/server.py"
# restart Claude Code to pick up the server
```

The `.venv/` and `~/.claude/logs/sessions-index/` are machine-local data, not
committed. Any venv that satisfies `requirements.txt` works — if one already
exists (e.g. another local-RAG project), point the registration at its python
instead of building a second 2GB venv.

## Re-index after new sessions

```bash
python3 index.py            # incremental: re-embeds only changed summaries
python3 index.py --force    # full wipe-and-rebuild
```

Capture (`/wrap-session`, `backfill.py`) keeps the summary corpus current; the
index is rebuilt separately. `server.py` prints a staleness warning when
summaries postdate the last index build, so a missed re-index is visible, not
silent.

## Which retrieval fires (routing, v1)

There is **no learned router yet** — that is an evals question gated on
retrievals-log volume (same philosophy as Monition's firing engine; decision 4).
The v1 rule of thumb:

| Query shape | Use |
|---|---|
| Exact keyword / known term / a *what* lookup | `recall.py "<terms>"` (grep, cheapest) |
| Fuzzy / conceptual / "I remember *something about*…" | `search_sessions` (semantic) |

Both log to `retrievals.jsonl`; that log is what a future router trains on. Rate a
lookup post-hoc with `recall.py --rate <id> helpful|noise` to seed that signal.

## Debugging

```bash
# raw semantic query with scores, no MCP:
python3 -c "
import chromadb; from chromadb.utils import embedding_functions
from index import DB_PATH, COLLECTION, MODEL
ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=MODEL)
col = chromadb.PersistentClient(str(DB_PATH)).get_collection(COLLECTION, embedding_function=ef)
r = col.query(query_texts=['YOUR QUERY'], n_results=5)
for d, m, dist in zip(r['documents'][0], r['metadatas'][0], r['distances'][0]):
    print(round(1-dist,3), m['file']); print(d[:200], '\n')
"
claude mcp list                       # verify session-archive is registered
```
