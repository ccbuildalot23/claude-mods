# hybrid-search

One search tool for the whole harness (plan G2C-2026-10-24-004, Chris's yes Oct 24 2026).
Keywords (BM25) find exact codes, vectors find meaning, Reciprocal Rank Fusion
(1/(60+rank)) merges them, and a cross-encoder reranker picks the winner.
Free, local, offline after install, no API keys, no telemetry.

Lives on the Mac at `~/Developer/grok-bridge/tools/hybrid-search/`. Source of truth is
this folder in claude-mods.

## What it reads
grok-bridge `.md/.csv/.json/.jsonl` files plus the Skills Catalog
(`labeau-ops/data/harness_map.csv`). Never: `journal/`, `archive/`, `research/freestyles/`,
`poems/`, `line-bank/`, `public-copy/`, legal material, any file whose name mentions a
transcript/freestyle/therapy/bankruptcy, and any file whose first lines say PRIVATE.
`./hs files` lists exactly what is indexed. It only writes `.index/` and, with
`scoreboard --publish`, one table in `grok-bridge/research/`.

## Pins
- Python packages: `requirements.lock` (uv compile, macOS arm64, Python 3.13, nothing
  published after 2026-10-10, sha256 hashes). Top level: chromadb 1.5.9, rank-bm25 0.2.2,
  sentence-transformers 6.1.0 (torch 2.11.0, transformers 5.19.0).
- Models: `models.lock.json`, exact Hugging Face revisions. all-MiniLM-L6-v2 (Apache-2.0)
  and BAAI/bge-reranker-base (MIT), about 1.3 GB in `~/.cache/huggingface`.

## Use
    ./install.sh                      # disk check, venv, models, index, scoreboard
    ./hs search "G2C-2026-10-19-002"
    ./hs search "where did we decide Gist rules" -k 3
    ./hs index                        # rebuild after new bridge files
    ./hs scoreboard --publish         # 20 questions, 4 modes

Pass rule: hybrid+rerank gets at least 10/12 exact questions first and 16/20 in the top
five. Nobody else uses the tool until the scoreboard passes.

## Undo
    rm -rf ~/Developer/grok-bridge/tools/hybrid-search/.venv ~/Developer/grok-bridge/tools/hybrid-search/.index
    rm -rf ~/.cache/huggingface/hub/models--sentence-transformers--all-MiniLM-L6-v2 ~/.cache/huggingface/hub/models--BAAI--bge-reranker-base

Tests (stand-in models, no downloads): `HS_BRIDGE=... HS_CATALOG=... python -m unittest tests/test_hs.py`
