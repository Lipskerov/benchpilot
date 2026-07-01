#!/usr/bin/env python3
"""
BenchPilot API — FastAPI backend.

Serves the static frontend and a JSON API for the end-to-end workflow:
  ask question -> find targets in papers/trials -> design experiment ->
  draft protocol -> reconcile against live reagent inventory -> flag missing.

Reasoning runs on IBM Granite (watsonx) when configured, with a grounded
offline fallback so the app always works.
"""

import sys
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.memory.retrieval import get_index
from src.llm import reasoning, granite
from src.protocols.generate import suggest_protocol
from src.inventory.store import InventoryStore
from src.inventory.match import check_protocol, order_list
from src.team.store import TeamStore
from src.team import digest

app = FastAPI(title="BenchPilot API", version="2.0")
WEB = ROOT / "web"


# ---------- models ----------
class AskReq(BaseModel):
    question: str
    k: int = 8


class DesignReq(BaseModel):
    target: str
    question: str = ""


class ProtocolReq(BaseModel):
    experiment: str


class InvItem(BaseModel):
    name: str
    category: str
    subtype: str = ""
    vendor: str = ""
    catalog_number: str = ""
    cas: str = ""
    molecular_weight: str = ""
    concentration: str = ""
    purity: str = ""
    form: str = ""
    quantity: float = 0
    unit: str = ""
    reorder_threshold: float = 0
    storage_location: str = ""
    storage_temp: str = ""
    expiration: str = ""
    hazard: str = ""
    notes: str = ""


# ---------- meta ----------
@app.get("/api/stats")
def stats():
    idx = get_index()
    papers = sum(1 for d in idx.docs if d["kind"] == "paper")
    trials = sum(1 for d in idx.docs if d["kind"] == "trial")
    inv = InventoryStore(); s = inv.stats(); inv.close()
    return {"papers": papers, "trials": trials, "inventory": s,
            "engine": "granite" if granite.is_configured() else "offline"}


# ---------- 1. discover ----------
@app.post("/api/ask")
def ask(req: AskReq):
    idx = get_index()
    papers = idx.search(req.question, k=max(req.k, 20), kind="paper")
    trials = idx.search(req.question, k=max(req.k, 20), kind="trial")
    syn = reasoning.synthesize_evidence(req.question, papers, trials)
    targets = reasoning.extract_targets(req.question, papers, trials)
    return {
        "synthesis": syn["synthesis"],
        "engine": syn.get("engine"),
        "targets": targets,
        "papers": papers[:req.k],
        "trials": trials[:req.k],
    }


# ---------- 2. design ----------
@app.post("/api/design")
def design(req: DesignReq):
    return reasoning.design_experiment(req.target, req.question)


# ---------- 3. protocol + inventory check ----------
@app.post("/api/protocol")
def protocol(req: ProtocolReq):
    proto = suggest_protocol(req.experiment)
    inv = InventoryStore()
    rows = check_protocol(proto["materials"], store=inv)
    inv.close()
    return {"protocol": proto, "check": rows, "order_list": order_list(rows)}


# ---------- inventory CRUD ----------
@app.get("/api/inventory")
def inventory(category: Optional[str] = None, search: Optional[str] = None):
    inv = InventoryStore()
    items = inv.list_items(category=category, search=search)
    stats = inv.stats()
    inv.close()
    return {"items": items, "stats": stats}


@app.get("/api/inventory/{item_id}")
def inventory_item(item_id: str):
    inv = InventoryStore(); it = inv.get_item(item_id); inv.close()
    if not it:
        raise HTTPException(404, "not found")
    return it


@app.post("/api/inventory")
def inventory_add(item: InvItem):
    inv = InventoryStore(); new_id = inv.add_item(item.model_dump()); inv.close()
    return {"id": new_id}


@app.put("/api/inventory/{item_id}")
def inventory_update(item_id: str, item: InvItem):
    inv = InventoryStore(); inv.update_item(item_id, item.model_dump()); inv.close()
    return {"ok": True}


@app.delete("/api/inventory/{item_id}")
def inventory_delete(item_id: str):
    inv = InventoryStore(); inv.delete_item(item_id); inv.close()
    return {"ok": True}


# ---------- team / projects / tasks (V3) ----------
class TaskReq(BaseModel):
    project_id: str
    title: str
    stage: str = "experiment"
    target: str = ""
    assignee: Optional[str] = None
    status: str = "todo"
    priority: str = "medium"
    due: str = ""
    reagents: List[str] = []
    notes: str = ""


class TaskPatch(BaseModel):
    status: Optional[str] = None
    assignee: Optional[str] = None
    priority: Optional[str] = None
    title: Optional[str] = None


@app.get("/api/team")
def team():
    ts = TeamStore()
    out = {"members": ts.workload(), "projects": ts.projects(),
           "tasks": ts.tasks(), "duplicates": ts.duplicates()}
    ts.close()
    return out


@app.get("/api/projects")
def projects():
    ts = TeamStore(); out = ts.projects(); ts.close()
    return out


class ProjectReq(BaseModel):
    name: str
    goal: str = ""
    lead: Optional[str] = None


@app.post("/api/projects")
def project_create(p: ProjectReq):
    ts = TeamStore(); pid = ts.add_project(p.name, p.goal, p.lead); ts.close()
    return {"id": pid}


class SpinupReq(BaseModel):
    question: str
    target: str = ""
    experiment: str = ""
    assay: str = "experiment"
    reagents: List[str] = []
    lead: Optional[str] = None
    auto_assign: bool = True


@app.post("/api/spinup")
def spinup(req: SpinupReq):
    """Turn a discovery into a staffed project: create project + stage tasks, auto-assign."""
    ts = TeamStore()
    name = req.target or (req.question[:60] + ("…" if len(req.question) > 60 else ""))
    pid = ts.add_project(name=f"{name} — TNBC", goal=req.question, lead=req.lead)
    tgt = req.target or "TNBC"
    exp_short = (req.experiment or req.question)[:70]
    plan = [
        ("discover", f"Literature & trial scan: {tgt}", "done", "medium", 7, []),
        ("design", f"Design experiment: {exp_short}", "todo", "high", 5, []),
        ("protocol", f"Draft & source protocol: {tgt}", "todo", "high", 8, req.reagents),
        ("experiment", f"Run {req.assay} assay: {tgt}", "todo", "high", 14, req.reagents),
        ("analysis", f"Analyze results: {tgt}", "todo", "medium", 21, []),
    ]
    from datetime import date, timedelta
    today = date.today()
    for stage, title, status, prio, due_off, reagents in plan:
        ts.add_task({"project_id": pid, "title": title, "stage": stage, "target": tgt,
                     "status": status, "priority": prio,
                     "due": (today + timedelta(days=due_off)).isoformat(), "reagents": reagents})
    ts.close()
    if req.auto_assign:
        for s in digest.suggest_assignments(pid):
            t2 = TeamStore(); t2.update_task(s["task_id"], {"assignee": s["suggest_id"]}); t2.close()
    return {"project_id": pid}


@app.get("/api/project/{pid}")
def project(pid: str):
    ts = TeamStore()
    p = ts.project(pid)
    if not p:
        ts.close(); raise HTTPException(404, "not found")
    out = {"project": p, "board": ts.board(pid), "pipeline": ts.pipeline(pid),
           "members": ts.members()}
    ts.close()
    return out


@app.post("/api/tasks")
def task_add(t: TaskReq):
    ts = TeamStore(); tid = ts.add_task(t.model_dump()); ts.close()
    return {"id": tid}


@app.patch("/api/tasks/{tid}")
def task_patch(tid: str, patch: TaskPatch):
    fields = {k: v for k, v in patch.model_dump().items() if v is not None}
    ts = TeamStore(); ts.update_task(tid, fields); ts.close()
    return {"ok": True}


@app.delete("/api/tasks/{tid}")
def task_delete(tid: str):
    ts = TeamStore(); ts.delete_task(tid); ts.close()
    return {"ok": True}


@app.get("/api/standup")
def standup(project: Optional[str] = None):
    return digest.standup(project)


@app.get("/api/suggest")
def suggest(project: Optional[str] = None):
    return digest.suggest_assignments(project)


# ---------- static frontend ----------
@app.get("/")
def index():
    return FileResponse(WEB / "index.html")


app.mount("/", StaticFiles(directory=str(WEB)), name="web")
