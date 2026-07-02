#!/usr/bin/env python3
"""
Build a fully static BenchPilot site (for GitHub Pages) into ./site/.
- Exports the corpus + inventory + team data to site/data/*.json
- Copies app.js, styles.css, static-backend.js, and the uploads images
- Rewrites index.html to use relative paths and load static-backend.js before app.js
No server needed at runtime: static-backend.js reimplements /api/* in the browser.
"""
import json
import shutil
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
SITE = ROOT / "site"
DB = ROOT / "benchpilot.db"


def export_data(dst: Path):
    conn = sqlite3.connect(str(DB)); conn.row_factory = sqlite3.Row
    papers = [{"id": r["pmid"], "title": r["title"], "abstract": r["abstract"],
               "year": r["year"], "journal": r["journal"]} for r in conn.execute("SELECT * FROM papers")]
    trials = []
    for r in conn.execute("SELECT * FROM trials"):
        iv = [x.get("name", "") for x in json.loads(r["interventions"] or "[]")]
        trials.append({"id": r["nct_id"], "title": r["brief_title"], "phase": r["phase"],
                       "status": r["status"], "sponsor": r["sponsor"], "interventions": " ".join(iv),
                       "primary_outcomes": json.loads(r["primary_outcomes"] or "[]"),
                       "conditions": " ".join(json.loads(r["conditions"] or "[]"))})
    inv = [dict(r) for r in conn.execute("SELECT * FROM inventory")]
    members = [dict(r) for r in conn.execute("SELECT * FROM members")]
    projects = []
    for r in conn.execute("SELECT * FROM projects"):
        p = dict(r); p["members"] = json.loads(p.get("members") or "[]"); projects.append(p)
    tasks = []
    for r in conn.execute("SELECT * FROM tasks"):
        t = dict(r)
        t["reagents"] = json.loads(t.get("reagents") or "[]")
        t["attachments"] = [a.lstrip("/") for a in json.loads(t.get("attachments") or "[]")]  # relative paths
        d = t.get("design"); t["design"] = json.loads(d) if d and d not in ("null", "") else None
        tasks.append(t)
    conn.close()
    (dst / "papers.json").write_text(json.dumps(papers))
    (dst / "trials.json").write_text(json.dumps(trials))
    (dst / "inventory.json").write_text(json.dumps(inv))
    (dst / "team.json").write_text(json.dumps({"members": members, "projects": projects, "tasks": tasks}))
    return len(papers), len(trials), len(inv), len(tasks)


def main():
    if SITE.exists():
        shutil.rmtree(SITE)
    (SITE / "data").mkdir(parents=True)
    for f in ["app.js", "styles.css", "static-backend.js"]:
        shutil.copy(WEB / f, SITE / f)
    shutil.copytree(WEB / "uploads", SITE / "uploads")
    n = export_data(SITE / "data")

    html = (WEB / "index.html").read_text()
    html = html.replace('href="/styles.css"', 'href="styles.css"')
    # load static backend before the app, and make app.js relative
    html = html.replace('<script src="/app.js"></script>',
                        '<script src="static-backend.js"></script>\n<script src="app.js"></script>')
    (SITE / "index.html").write_text(html)
    # add a .nojekyll so GitHub Pages serves files as-is
    (SITE / ".nojekyll").write_text("")
    print(f"✓ built {SITE} — {n[0]} papers, {n[1]} trials, {n[2]} inventory, {n[3]} tasks")
    print("  serve locally:  python3 -m http.server -d site 8700   → http://localhost:8700")


if __name__ == "__main__":
    main()
