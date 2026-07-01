#!/usr/bin/env python3
"""
Lexical retrieval over the TNBC corpus (papers + trials) using BM25.

Pure-Python, no external dependencies. Genuinely relevant results offline
(unlike random hash embeddings), so "find the real target" actually works.
The index is built once from benchpilot.db and cached in memory.
"""

import json
import math
import re
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional

DB_PATH = str(Path(__file__).resolve().parent.parent.parent / "benchpilot.db")

_TOKEN = re.compile(r"[a-z0-9\-]+")
_STOP = set("the a an and or of in to for with on is are be as by from that this "
            "we our study results using used effects effect showed shown role".split())


def _tok(text: str) -> List[str]:
    return [t for t in _TOKEN.findall((text or "").lower()) if t not in _STOP and len(t) > 1]


class BM25Index:
    def __init__(self, db_path: str = DB_PATH, k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.docs: List[Dict] = []      # metadata per doc
        self.tokens: List[List[str]] = []
        self.df: Counter = Counter()
        self.idf: Dict[str, float] = {}
        self.avgdl = 0.0
        self._load(db_path)

    def _load(self, db_path: str):
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        for r in conn.execute("SELECT pmid,title,abstract,journal,year FROM papers"):
            text = f"{r['title']} {r['abstract']}"
            self._add({"kind": "paper", "id": r["pmid"], "title": r["title"],
                       "year": r["year"], "journal": r["journal"],
                       "abstract": r["abstract"]}, text)
        for r in conn.execute("SELECT nct_id,brief_title,phase,status,conditions,"
                              "interventions,sponsor,primary_outcomes FROM trials"):
            iv = " ".join(x.get("name", "") for x in json.loads(r["interventions"] or "[]"))
            text = f"{r['brief_title']} {iv} {r['conditions']}"
            self._add({"kind": "trial", "id": r["nct_id"], "title": r["brief_title"],
                       "phase": r["phase"], "status": r["status"], "sponsor": r["sponsor"],
                       "interventions": iv,
                       "primary_outcomes": json.loads(r["primary_outcomes"] or "[]")}, text)
        conn.close()
        n = len(self.docs)
        self.avgdl = sum(len(t) for t in self.tokens) / max(n, 1)
        for term, df in self.df.items():
            self.idf[term] = math.log(1 + (n - df + 0.5) / (df + 0.5))

    def _add(self, meta: Dict, text: str):
        toks = _tok(text)
        self.docs.append(meta)
        self.tokens.append(toks)
        for term in set(toks):
            self.df[term] += 1

    def search(self, query: str, k: int = 8, kind: Optional[str] = None) -> List[Dict]:
        q = _tok(query)
        scored = []
        for i, toks in enumerate(self.tokens):
            if kind and self.docs[i]["kind"] != kind:
                continue
            if not toks:
                continue
            tf = Counter(toks)
            dl = len(toks)
            score = 0.0
            for term in q:
                if term not in tf:
                    continue
                idf = self.idf.get(term, 0.0)
                freq = tf[term]
                score += idf * (freq * (self.k1 + 1)) / (
                    freq + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
            if score > 0:
                scored.append((score, i))
        scored.sort(reverse=True)
        out = []
        for score, i in scored[:k]:
            d = dict(self.docs[i])
            d["score"] = round(score, 3)
            out.append(d)
        return out


_INDEX: Optional[BM25Index] = None


def get_index() -> BM25Index:
    global _INDEX
    if _INDEX is None:
        _INDEX = BM25Index()
    return _INDEX


if __name__ == "__main__":
    idx = get_index()
    print(f"indexed {len(idx.docs)} docs (avgdl={idx.avgdl:.0f})")
    for q in ["PARP inhibitor olaparib BRCA mutation", "sacituzumab govitecan TROP2 ADC",
              "pembrolizumab PD-L1 immunotherapy"]:
        hits = idx.search(q, k=3, kind="paper")
        rel = sum(any(w in (h["title"] + h.get("abstract", "")).lower()
                      for w in q.lower().split()[:2]) for h in hits)
        print(f"\n{q}  -> {rel}/3 clearly on-topic")
        for h in hits:
            print(f"  [{h['score']}] {h['id']} {h['title'][:70]}")
