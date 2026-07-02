#!/usr/bin/env python3
"""
Team store: members, projects, tasks — the collaboration layer.
Adds orchestration helpers: task reagent-readiness (vs live inventory),
per-member workload, duplicated-effort detection, board and pipeline views.
"""

import json
import sqlite3
from datetime import date
from typing import Dict, List, Optional

from src.inventory.store import InventoryStore
from src.inventory.match import check_protocol

DB_PATH = "benchpilot.db"
STATUSES = ["todo", "in_progress", "blocked", "done"]
TASK_FIELDS = ["id", "project_id", "title", "stage", "target", "assignee",
               "status", "priority", "due", "reagents", "notes", "created",
               "design", "attachments"]


class TeamStore:
    def __init__(self, db_path: str = DB_PATH):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

    # ---------- members ----------
    def members(self) -> List[Dict]:
        return [dict(r) for r in self.conn.execute("SELECT * FROM members ORDER BY id")]

    def member(self, mid: str) -> Optional[Dict]:
        r = self.conn.execute("SELECT * FROM members WHERE id=?", (mid,)).fetchone()
        return dict(r) if r else None

    def _name(self, mid) -> str:
        m = self.member(mid) if mid else None
        return m["name"] if m else "Unassigned"

    def _initials(self, mid) -> str:
        m = self.member(mid) if mid else None
        return m["initials"] if m else "—"

    # ---------- projects ----------
    def _project_row(self, r) -> Dict:
        p = dict(r)
        p["members"] = json.loads(p.get("members") or "[]")
        p["lead_name"] = self._name(p["lead"])
        p["member_objs"] = [m for m in (self.member(mid) for mid in p["members"]) if m]
        return p

    def projects(self) -> List[Dict]:
        out = []
        for r in self.conn.execute("SELECT * FROM projects ORDER BY id"):
            p = self._project_row(r)
            tasks = self.tasks(project_id=p["id"])
            done = sum(1 for t in tasks if t["status"] == "done")
            p["task_count"] = len(tasks)
            p["done_count"] = done
            p["progress"] = round(100 * done / len(tasks)) if tasks else 0
            out.append(p)
        return out

    def project(self, pid: str) -> Optional[Dict]:
        r = self.conn.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
        return self._project_row(r) if r else None

    def update_project(self, pid: str, fields: Dict) -> None:
        allowed = {}
        for k in ("name", "goal", "lead", "status", "members"):
            if k in fields:
                allowed[k] = json.dumps(fields[k]) if k == "members" and isinstance(fields[k], list) else fields[k]
        if not allowed:
            return
        sets = ", ".join(f"{k}=?" for k in allowed)
        self.conn.execute(f"UPDATE projects SET {sets} WHERE id=?", (*allowed.values(), pid))
        self.conn.commit()

    def _next_project_id(self) -> str:
        rows = self.conn.execute("SELECT id FROM projects").fetchall()
        nums = [int(r[0].split("-")[-1]) for r in rows if r[0].split("-")[-1].isdigit()]
        return f"PRJ-{(max(nums)+1) if nums else 1:02d}"

    def add_project(self, name: str, goal: str = "", lead: Optional[str] = None,
                    members: Optional[List[str]] = None) -> str:
        pid = self._next_project_id()
        mem = json.dumps(members or ([lead] if lead else []))
        self.conn.execute("INSERT INTO projects (id,name,goal,status,lead,members,created) VALUES (?,?,?,?,?,?,?)",
                          (pid, name, goal, "active", lead, mem, date.today().isoformat()))
        self.conn.commit()
        return pid

    # ---------- tasks ----------
    def _row(self, r) -> Dict:
        t = dict(r)
        t["reagents"] = json.loads(t.get("reagents") or "[]")
        t["attachments"] = json.loads(t.get("attachments") or "[]")
        d = t.get("design")
        t["design"] = json.loads(d) if d and d not in ("null", "") else None
        t["assignee_name"] = self._name(t["assignee"])
        t["assignee_initials"] = self._initials(t["assignee"])
        return t

    def tasks(self, project_id=None, assignee=None, status=None) -> List[Dict]:
        q = "SELECT * FROM tasks WHERE 1=1"; p = []
        if project_id: q += " AND project_id=?"; p.append(project_id)
        if assignee: q += " AND assignee=?"; p.append(assignee)
        if status: q += " AND status=?"; p.append(status)
        q += " ORDER BY priority='low', priority='medium', due"
        return [self._row(r) for r in self.conn.execute(q, p)]

    def get_task(self, tid: str) -> Optional[Dict]:
        r = self.conn.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone()
        return self._row(r) if r else None

    def _next_task_id(self) -> str:
        rows = self.conn.execute("SELECT id FROM tasks").fetchall()
        nums = [int(r[0].split("-")[-1]) for r in rows if r[0].split("-")[-1].isdigit()]
        return f"TSK-{(max(nums)+1) if nums else 1:02d}"

    def add_task(self, item: Dict) -> str:
        item = dict(item)
        item.setdefault("id", self._next_task_id())
        item.setdefault("created", date.today().isoformat())
        item.setdefault("status", "todo")
        for k in ("reagents", "attachments"):
            if isinstance(item.get(k), list):
                item[k] = json.dumps(item[k])
        if isinstance(item.get("design"), dict):
            item["design"] = json.dumps(item["design"])
        cols = [c for c in TASK_FIELDS if c in item]
        self.conn.execute(f"INSERT OR REPLACE INTO tasks ({','.join(cols)}) VALUES ({','.join('?' for _ in cols)})",
                          tuple(item[c] for c in cols))
        self.conn.commit(); return item["id"]

    def update_task(self, tid: str, fields: Dict) -> None:
        fields = {k: v for k, v in fields.items() if k in TASK_FIELDS and k != "id"}
        if "reagents" in fields and isinstance(fields["reagents"], list):
            fields["reagents"] = json.dumps(fields["reagents"])
        if not fields: return
        sets = ", ".join(f"{k}=?" for k in fields)
        self.conn.execute(f"UPDATE tasks SET {sets} WHERE id=?", (*fields.values(), tid))
        self.conn.commit()

    def delete_task(self, tid: str) -> None:
        self.conn.execute("DELETE FROM tasks WHERE id=?", (tid,))
        self.conn.commit()

    def add_attachment(self, tid: str, url: str) -> list:
        t = self.get_task(tid)
        if not t:
            return []
        atts = t.get("attachments") or []
        atts.append(url)
        self.conn.execute("UPDATE tasks SET attachments=? WHERE id=?", (json.dumps(atts), tid))
        self.conn.commit()
        return atts

    # ---------- orchestration ----------
    def readiness(self, task: Dict, inv: Optional[InventoryStore] = None) -> Dict:
        reagents = task.get("reagents") or []
        if not reagents:
            return {"ready": True, "missing": []}
        mats = [{"name": r, "quantity": 1, "unit": ""} for r in reagents]
        rows = check_protocol(mats, store=inv)
        missing = [r["required_name"] for r in rows if r["status"] in ("MISSING", "EXPIRED")]
        return {"ready": len(missing) == 0, "missing": missing}

    def workload(self) -> List[Dict]:
        out = []
        for m in self.members():
            ts = self.tasks(assignee=m["id"])
            active = [t for t in ts if t["status"] in ("todo", "in_progress", "blocked")]
            out.append({**m, "active": len(active), "total": len(ts),
                        "blocked": sum(1 for t in ts if t["status"] == "blocked")})
        return out

    def duplicates(self, project_id=None) -> List[Dict]:
        tasks = [t for t in self.tasks(project_id=project_id) if t["status"] != "done"]
        by_target: Dict[str, List[Dict]] = {}
        for t in tasks:
            by_target.setdefault(t["target"], []).append(t)
        groups = []
        for target, ts in by_target.items():
            people = {t["assignee"] for t in ts if t["assignee"]}
            if len(ts) >= 2 and len(people) >= 2:
                groups.append({"target": target,
                               "tasks": [{"id": t["id"], "title": t["title"],
                                          "assignee_name": t["assignee_name"]} for t in ts]})
        return groups

    def board(self, project_id: str) -> Dict[str, List[Dict]]:
        b = {s: [] for s in STATUSES}
        inv = InventoryStore()
        for t in self.tasks(project_id=project_id):
            t["readiness"] = self.readiness(t, inv)
            b[t["status"]].append(t)
        inv.close()
        return b

    def pipeline(self, project_id: str) -> List[Dict]:
        stages = ["discover", "design", "protocol", "experiment", "analysis"]
        counts = {s: 0 for s in stages}
        for t in self.tasks(project_id=project_id):
            counts[t["stage"]] = counts.get(t["stage"], 0) + 1
        return [{"stage": s, "count": counts.get(s, 0)} for s in stages]

    def close(self):
        self.conn.close()


if __name__ == "__main__":
    s = TeamStore()
    print("projects:", [(p["id"], p["progress"], p["task_count"]) for p in s.projects()])
    print("workload:", [(w["initials"], w["active"], w["blocked"]) for w in s.workload()])
    print("duplicates:", [(g["target"], [t["assignee_name"] for t in g["tasks"]]) for g in s.duplicates()])
    inv = InventoryStore()
    for t in s.tasks(project_id="PRJ-01"):
        if t["reagents"]:
            print(t["id"], t["status"], "->", s.readiness(t, inv))
    inv.close(); s.close()
