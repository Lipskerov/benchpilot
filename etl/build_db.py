#!/usr/bin/env python3
"""
Build BenchPilot's SQLite database from the JSONL snapshots.
Loads papers and trials into benchpilot.db. Retrieval is handled at runtime by
src/memory/retrieval.py (BM25), so no vector store is built here.
"""

import json
import sqlite3
from pathlib import Path


def create_tables(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS papers (
            pmid TEXT PRIMARY KEY, title TEXT NOT NULL, abstract TEXT NOT NULL,
            journal TEXT, year INTEGER, mesh TEXT)""")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS trials (
            nct_id TEXT PRIMARY KEY, brief_title TEXT NOT NULL, phase TEXT, status TEXT,
            conditions TEXT, interventions TEXT, primary_outcomes TEXT, sponsor TEXT,
            start_date TEXT, enrollment INTEGER)""")
    conn.commit()


def load_papers(conn, path: Path) -> int:
    n = 0
    with open(path, encoding="utf-8") as f:
        for line in f:
            p = json.loads(line)
            conn.execute(
                "INSERT OR REPLACE INTO papers (pmid,title,abstract,journal,year,mesh) VALUES (?,?,?,?,?,?)",
                (p["pmid"], p["title"], p["abstract"], p.get("journal", ""),
                 p.get("year"), json.dumps(p.get("mesh", []))))
            n += 1
    conn.commit()
    return n


def load_trials(conn, path: Path) -> int:
    n = 0
    with open(path, encoding="utf-8") as f:
        for line in f:
            t = json.loads(line)
            conn.execute(
                "INSERT OR REPLACE INTO trials (nct_id,brief_title,phase,status,conditions,"
                "interventions,primary_outcomes,sponsor,start_date,enrollment) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (t["nct_id"], t["brief_title"], t.get("phase", ""), t.get("status", ""),
                 json.dumps(t.get("conditions", [])), json.dumps(t.get("interventions", [])),
                 json.dumps(t.get("primary_outcomes", [])), t.get("sponsor", ""),
                 t.get("start_date", ""), t.get("enrollment")))
            n += 1
    conn.commit()
    return n


def main():
    root = Path(__file__).resolve().parent.parent
    db = root / "benchpilot.db"
    snap = root / "data" / "snapshot"
    if not (snap / "papers.jsonl").exists():
        print("Run fetch_pubmed.py and fetch_trials.py first."); return
    conn = sqlite3.connect(str(db))
    create_tables(conn)
    p = load_papers(conn, snap / "papers.jsonl")
    t = load_trials(conn, snap / "trials.jsonl")
    conn.close()
    print(f"✓ Built {db.name}: {p} papers, {t} trials. Run gen_inventory.py for reagent stock.")


if __name__ == "__main__":
    main()
