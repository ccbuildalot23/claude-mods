#!/usr/bin/env python3
"""Hybrid search over the grok-bridge (BM25 + vectors + RRF + cross-encoder rerank).

Plan: grok-bridge/to-claude/G2C-2026-10-24-004-hybrid-search-plan.md (Chris's yes, Oct 24 2026).
Read-only over what it indexes. Writes only inside its own folder (.index/) and,
for `scoreboard --publish`, one table under grok-bridge/research/.

  hs.py index                      build the index
  hs.py search "query" [-k 5] [--mode hybrid+rerank|hybrid|bm25|vector]
  hs.py scoreboard [--publish]     run the 20 test questions in all four modes
"""
import argparse
import csv
import datetime as dt
import io
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BRIDGE = Path(os.environ.get("HS_BRIDGE", HERE.parent.parent)).resolve()
CATALOG = Path(os.environ.get("HS_CATALOG", BRIDGE.parent / "labeau-ops/data/harness_map.csv"))
INDEX_DIR = Path(os.environ.get("HS_INDEX", HERE / ".index"))
MODELS_LOCK = HERE / "models.lock.json"
QUESTIONS = HERE / "questions.json"

# Never indexed. Chris's plan: not poems/, line-bank/, public-copy/, journal or legal
# material unless he says so separately. Private transcripts stay out too.
SKIP_DIRS = {"journal", "archive", "freestyles", "tools", "poems", "line-bank",
             "public-copy", "legal", ".git", ".index"}
SKIP_NAME = re.compile(r"chelsea|freestyle|therapy|bankrupt|transcript|legal", re.I)
PRIVATE_MARK = re.compile(r"\bPRIVATE\b|NEVER put this on the bridge")
EXTS = {".md", ".csv", ".json", ".jsonl"}

RRF_K = 60
CANDIDATES = 30   # per retriever, before fusion
RERANK_TOP = 20   # fused candidates the cross-encoder looks at
CHUNK_CHARS = 1200


# ---------- files and chunks ----------

def eligible(path: Path) -> bool:
    rel = path.relative_to(BRIDGE)
    if path.suffix.lower() not in EXTS or any(p in SKIP_DIRS for p in rel.parts):
        return False
    if SKIP_NAME.search(path.name):
        return False
    try:
        head = path.read_text(errors="replace")[:800]
    except OSError:
        return False
    return not PRIVATE_MARK.search(head)


def source_files():
    files = sorted(p for p in BRIDGE.rglob("*") if p.is_file() and eligible(p))
    if CATALOG.is_file():
        files.append(CATALOG)
    return files


def label(path: Path) -> str:
    try:
        return "grok-bridge/" + str(path.relative_to(BRIDGE))
    except ValueError:
        return "labeau-ops/data/" + path.name if path == CATALOG else str(path)


def split_text(text: str):
    """Markdown: split on headings, then pack paragraphs up to CHUNK_CHARS."""
    parts = re.split(r"\n(?=#{1,4} )", text)
    out = []
    for part in parts:
        buf = ""
        for para in re.split(r"\n\s*\n", part):
            if buf and len(buf) + len(para) > CHUNK_CHARS:
                out.append(buf)
                buf = ""
            buf = (buf + "\n\n" + para).strip() if buf else para.strip()
        if buf:
            out.append(buf)
    return [c for c in out if c.strip()]


MSG_ID = re.compile(r"[A-Z0-9]{2,4}-\d{4}-\d{2}-\d{2}(?:-\d{3})?")


def chunks_for(path: Path):
    text = path.read_text(errors="replace")
    name = label(path)
    m = MSG_ID.search(path.name)
    if m:  # the message's own id, so a lookup by id lands on its home file
        name_line = f"{name} {m.group(0)} {m.group(0)}"
    else:
        name_line = name
    if path.suffix == ".csv":
        rows = list(csv.reader(io.StringIO(text)))
        if not rows:
            return []
        header = rows[0]
        return [(name, f"{name_line}\n" + "; ".join(f"{h}: {v}" for h, v in zip(header, r) if v))
                for r in rows[1:] if any(r)]
    if path.suffix == ".jsonl":
        return [(name, f"{name_line}\n{line}") for line in text.splitlines() if line.strip()]
    return [(name, f"{name_line}\n{c}") for c in split_text(text)]


def all_chunks():
    out = []
    for f in source_files():
        out.extend(chunks_for(f))
    return out


# ---------- keyword side ----------

TOKEN = re.compile(r"[A-Za-z0-9$]+(?:[-_.:][A-Za-z0-9]+)*")


def tokenize(text: str):
    """Keep exact codes whole (G2C-2026-10-19-002, rec..., 1.5.9) and also their parts."""
    toks = []
    for t in TOKEN.findall(text.lower()):
        toks.append(t)
        sub = re.split(r"[-_.:]", t)
        if len(sub) > 1:
            toks.extend(s for s in sub if s)
    return toks


# ---------- models (pinned revisions, offline after install) ----------

def model_pins():
    if not MODELS_LOCK.is_file():
        sys.exit("models.lock.json is missing. Run ./install.sh first.")
    return json.loads(MODELS_LOCK.read_text())


def load_embedder():
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    from sentence_transformers import SentenceTransformer
    pin = model_pins()["embedder"]
    return SentenceTransformer(pin["id"], revision=pin["revision"], device="cpu")


def load_reranker():
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    from sentence_transformers import CrossEncoder
    pin = model_pins()["reranker"]
    return CrossEncoder(pin["id"], revision=pin["revision"], device="cpu")


def chroma_collection(create=False):
    import chromadb
    from chromadb.config import Settings
    client = chromadb.PersistentClient(path=str(INDEX_DIR),
                                       settings=Settings(anonymized_telemetry=False))
    if create:
        try:
            client.delete_collection("bridge")
        except Exception:
            pass
        return client.create_collection("bridge", embedding_function=None,
                                        metadata={"hnsw:space": "cosine"})
    return client.get_collection("bridge", embedding_function=None)


# ---------- index ----------

def cmd_index(_args):
    chunks = all_chunks()
    INDEX_DIR.mkdir(exist_ok=True)
    (INDEX_DIR / "chunks.json").write_text(json.dumps(chunks))
    emb = load_embedder()
    vecs = emb.encode([c[1] for c in chunks], batch_size=32, show_progress_bar=False,
                      normalize_embeddings=True)
    col = chroma_collection(create=True)
    for i in range(0, len(chunks), 1000):
        part = chunks[i:i + 1000]
        col.add(ids=[str(j) for j in range(i, i + len(part))],
                embeddings=[v.tolist() for v in vecs[i:i + len(part)]],
                documents=[c[1] for c in part],
                metadatas=[{"file": c[0]} for c in part])
    files = len({c[0] for c in chunks})
    print(f"Indexed {len(chunks)} chunks from {files} files into {INDEX_DIR}")


# ---------- search ----------

class Searcher:
    def __init__(self, need_models=True):
        path = INDEX_DIR / "chunks.json"
        if not path.is_file():
            sys.exit("No index yet. Run: ./hs index")
        self.chunks = json.loads(path.read_text())
        from rank_bm25 import BM25Okapi
        self.bm25 = BM25Okapi([tokenize(c[1]) for c in self.chunks])
        self._emb = self._rr = self._col = None
        self.need_models = need_models

    def bm25_rank(self, q, n=CANDIDATES):
        scores = self.bm25.get_scores(tokenize(q))
        order = sorted(range(len(scores)), key=lambda i: -scores[i])
        return [i for i in order[:n] if scores[i] > 0]

    def vector_rank(self, q, n=CANDIDATES):
        if self._emb is None:
            self._emb = load_embedder()
            self._col = chroma_collection()
        v = self._emb.encode([q], normalize_embeddings=True)[0].tolist()
        res = self._col.query(query_embeddings=[v], n_results=n)
        return [int(i) for i in res["ids"][0]]

    def rerank(self, q, ids):
        if self._rr is None:
            self._rr = load_reranker()
        scores = self._rr.predict([(q, self.chunks[i][1]) for i in ids])
        return [i for _, i in sorted(zip(scores, ids), key=lambda t: -t[0])]

    def search(self, q, mode="hybrid+rerank"):
        if mode == "bm25":
            return self.bm25_rank(q)
        if mode == "vector":
            return self.vector_rank(q)
        fused = {}
        for ranked in (self.bm25_rank(q), self.vector_rank(q)):
            for r, i in enumerate(ranked):
                fused[i] = fused.get(i, 0.0) + 1.0 / (RRF_K + r + 1)
        ids = sorted(fused, key=lambda i: -fused[i])
        if mode == "hybrid":
            return ids
        return self.rerank(q, ids[:RERANK_TOP]) + ids[RERANK_TOP:]

    def files(self, ids, k):
        seen = []
        for i in ids:
            f = self.chunks[i][0]
            if f not in seen:
                seen.append(f)
            if len(seen) == k:
                break
        return seen


def cmd_search(args):
    s = Searcher()
    ids = s.search(args.query, args.mode)
    shown = set()
    for i in ids:
        f, text = s.chunks[i]
        if f in shown:
            continue
        shown.add(f)
        snippet = " ".join(text.split("\n", 1)[-1].split())[:220]
        print(f"{len(shown)}. {f}\n   {snippet}\n")
        if len(shown) == args.k:
            break


# ---------- scoreboard ----------

MODES = ["vector", "bm25", "hybrid", "hybrid+rerank"]


def cmd_scoreboard(args):
    qs = json.loads(QUESTIONS.read_text())
    s = Searcher()
    tally = {m: {"exact": [0, 0], "meaning": [0, 0]} for m in MODES}  # [hit@1, hit@5]
    rows = []
    for q in qs:
        gold = set(q["gold"])
        line = {"id": q["id"], "kind": q["kind"], "q": q["q"]}
        for m in MODES:
            top = s.files(s.search(q["q"], m), 5)
            h1 = bool(top) and top[0] in gold
            h5 = any(f in gold for f in top)
            tally[m][q["kind"]][0] += h1
            tally[m][q["kind"]][1] += h5
            line[m] = ("1" if h1 else "5" if h5 else "-")
        rows.append(line)

    n_exact = sum(q["kind"] == "exact" for q in qs)
    n_mean = len(qs) - n_exact
    out = io.StringIO()
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    out.write(f"# Hybrid search scoreboard ({now} local)\n\n")
    out.write(f"Index: {len(s.chunks)} chunks. Questions: {n_exact} exact, {n_mean} meaning. "
              "Hit@1 = right file first; Hit@5 = right file in the top five.\n\n")
    out.write("| Mode | Exact hit@1 | Exact hit@5 | Meaning hit@1 | Meaning hit@5 | Total hit@1 |\n")
    out.write("|---|---|---|---|---|---|\n")
    for m in MODES:
        e, me = tally[m]["exact"], tally[m]["meaning"]
        out.write(f"| {m} | {e[0]}/{n_exact} | {e[1]}/{n_exact} | {me[0]}/{n_mean} | "
                  f"{me[1]}/{n_mean} | {e[0] + me[0]}/{len(qs)} |\n")
    hr = tally["hybrid+rerank"]
    passed = hr["exact"][0] >= 10 and (hr["exact"][1] + hr["meaning"][1]) >= 16
    out.write(f"\nPass rule: hybrid+rerank exact hit@1 at least 10/12 and total hit@5 at least 16/20. "
              f"Result: **{'PASS' if passed else 'NOT YET'}**.\n\n")
    out.write("Per question (1 = first, 5 = in top five, - = missed):\n\n")
    out.write("| # | Kind | Question | vector | bm25 | hybrid | hybrid+rerank |\n|---|---|---|---|---|---|---|\n")
    for r in rows:
        qtext = r["q"].replace("|", "/")
        out.write(f"| {r['id']} | {r['kind']} | {qtext} | " + " | ".join(r[m] for m in MODES) + " |\n")
    text = out.getvalue()
    print(text)
    if args.publish:
        dest = BRIDGE / "research" / f"hybrid-search-scoreboard-{dt.date.today()}.md"
        dest.write_text(text)
        print(f"Published to {dest}")
    sys.exit(0 if passed else 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("index")
    sp = sub.add_parser("search")
    sp.add_argument("query")
    sp.add_argument("-k", type=int, default=5)
    sp.add_argument("--mode", choices=MODES, default="hybrid+rerank")
    sb = sub.add_parser("scoreboard")
    sb.add_argument("--publish", action="store_true")
    sub.add_parser("files", help="list what would be indexed")
    args = ap.parse_args()
    if args.cmd == "files":
        for f in source_files():
            print(label(f))
        return
    {"index": cmd_index, "search": cmd_search, "scoreboard": cmd_scoreboard}[args.cmd](args)


if __name__ == "__main__":
    main()
