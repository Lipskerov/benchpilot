#!/usr/bin/env python3
"""
AI orchestration for the lab team: a "standup" digest + assignment suggestions.

Decision intelligence over the project's real state (statuses, blockers,
reagent-readiness, workload, duplicated effort). Uses IBM Granite (watsonx) to
write the narrative when configured; otherwise a grounded rule-based summary.
"""

from typing import Dict, List, Optional

from src.llm import granite
from src.team.store import TeamStore
from src.inventory.store import InventoryStore


def _facts(store: TeamStore, project_id: Optional[str]) -> Dict:
    inv = InventoryStore()
    tasks = store.tasks(project_id=project_id)
    for t in tasks:
        t["readiness"] = store.readiness(t, inv)
    inv.close()

    active = [t for t in tasks if t["status"] != "done"]
    blocked = [t for t in tasks if t["status"] == "blocked" or not t["readiness"]["ready"]]
    unassigned = [t for t in active if not t["assignee"]]
    ready_high = [t for t in active if t["priority"] == "high" and t["readiness"]["ready"]
                  and t["status"] != "blocked"]
    dups = store.duplicates(project_id)
    counts = {s: sum(1 for t in tasks if t["status"] == s) for s in ["todo", "in_progress", "blocked", "done"]}
    return {"tasks": tasks, "active": active, "blocked": blocked, "unassigned": unassigned,
            "ready_high": ready_high, "duplicates": dups, "counts": counts}


def standup(project_id: Optional[str] = None) -> Dict:
    store = TeamStore()
    f = _facts(store, project_id)

    # structured blockers with reasons
    blockers = []
    for t in f["blocked"]:
        miss = t["readiness"]["missing"]
        reason = ("out of stock: " + ", ".join(miss)) if miss else "flagged blocked"
        blockers.append({"id": t["id"], "title": t["title"],
                         "assignee": t["assignee_name"], "reason": reason})

    priorities = [{"id": t["id"], "title": t["title"], "assignee": t["assignee_name"]} for t in f["ready_high"]]
    unassigned = [{"id": t["id"], "title": t["title"], "priority": t["priority"]} for t in f["unassigned"]]
    duplicates = [{"target": g["target"], "who": [x["assignee_name"] for x in g["tasks"]],
                   "tasks": [x["id"] for x in g["tasks"]]} for g in f["duplicates"]]

    narrative = _narrative(f, project_id)
    store.close()
    return {"narrative": narrative, "counts": f["counts"], "blockers": blockers,
            "priorities": priorities, "unassigned": unassigned, "duplicates": duplicates}


def _narrative(f: Dict, project_id) -> str:
    if granite.is_configured():
        try:
            lines = []
            for t in f["tasks"]:
                r = "READY" if t["readiness"]["ready"] else "BLOCKED(" + ",".join(t["readiness"]["missing"]) + ")"
                lines.append(f"- [{t['status']}/{t['priority']}] {t['title']} · {t['assignee_name']} · {r}")
            prompt = (
                "You are a lab research manager. Write a concise 4-6 sentence stand-up summary of the "
                "project below: progress, the most urgent blockers (and why), what to prioritize next, "
                "and any duplicated effort. Be specific and actionable.\n\nTASKS:\n" + "\n".join(lines))
            txt = granite.generate(prompt, max_new_tokens=350, temperature=0.3)
            if txt:
                return txt
        except Exception:
            pass

    c = f["counts"]
    parts = [f"{c['done']} done, {c['in_progress']} in progress, {c['todo']} to do, {c['blocked']} blocked."]
    if f["blocked"]:
        b = f["blocked"][0]
        miss = b["readiness"]["missing"]
        parts.append(f"Top blocker: '{b['title']}' ({b['assignee_name']})"
                     + (f" — waiting on {', '.join(miss)}." if miss else "."))
    if f["ready_high"]:
        parts.append(f"Prioritize '{f['ready_high'][0]['title']}' — high priority and all reagents in stock.")
    if f["unassigned"]:
        parts.append(f"{len(f['unassigned'])} task(s) still unassigned.")
    return " ".join(parts)


def suggest_assignments(project_id: Optional[str] = None) -> List[Dict]:

# ============ FUTURE: IBM Bob API Integration ============
# TODO: Replace rule-based assignment with IBM Bob API
# Placeholder for Bob API call:
#   - POST to Bob API endpoint with unassigned tasks, member profiles, workload
#   - Bob analyzes task requirements, member expertise, and current capacity
#   - Returns intelligent assignment suggestions with reasoning
# Example:
#   response = bob_api.suggest_task_assignments(tasks=tasks, members=members, workload=workload)
#   return response.suggestions
# =========================================================


    """Suggest an owner for each unassigned task: least-loaded member whose focus fits the target."""
    store = TeamStore()
    workload = {w["id"]: w for w in store.workload()}
    tasks = [t for t in store.tasks(project_id=project_id) if not t["assignee"] and t["status"] != "done"]
    members = store.members()
    out = []
    for t in tasks:
        # score members: focus keyword overlap with target, then lowest active load
        def score(m):
            focus = (m["focus"] or "").lower()
            tgt = (t["target"] or "").lower()
            fit = sum(1 for w in tgt.replace("/", " ").split() if len(w) > 3 and w in focus)
            return (-fit, workload[m["id"]]["active"])
        best = sorted([m for m in members if m["role"] != "Principal Investigator"], key=score)[0]
        out.append({"task_id": t["id"], "title": t["title"], "target": t["target"],
                    "suggest": best["name"], "suggest_id": best["id"],
                    "why": f"{best['focus']} · {workload[best['id']]['active']} active tasks"})
    store.close()
    return out


if __name__ == "__main__":
    import json
    print(json.dumps(standup("PRJ-01"), indent=1)[:900])
    print("\nSUGGEST:", suggest_assignments())
