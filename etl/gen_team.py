#!/usr/bin/env python3
"""
Generate a synthetic lab team, projects, and tasks for BenchPilot V3
(collaboration layer) and load them into benchpilot.db + data/snapshot/*.jsonl.

Deterministic. Some tasks are deliberately blocked on out-of-stock reagents,
and two tasks share a target (duplicated effort) so the AI standup can flag them.
"""

import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path

TODAY = date(2026, 7, 1)


def d(offset):  # due date helper
    return (TODAY + timedelta(days=offset)).isoformat()


MEMBERS = [
    ("MEM-00", "Fedor Lipskerov", "Lead Researcher (PI)", "FL", "Lead researcher · TNBC program"),
    ("MEM-01", "Dr. Elena Rossi", "Principal Investigator", "ER", "Co-investigator · TNBC therapeutics"),
    ("MEM-02", "Dr. Sam Okafor", "Postdoc", "SO", "DNA-damage response · PARP"),
    ("MEM-03", "Maya Chen", "PhD student", "MC", "Immuno-oncology · PD-L1"),
    ("MEM-04", "Liam Novak", "PhD student", "LN", "ADCs · TROP2"),
    ("MEM-05", "Priya Nair", "MSc student", "PN", "Cell-based assays"),
    ("MEM-06", "Tom Becker", "Research intern", "TB", "Molecular biology · qPCR"),
]

PROJECTS = [
    ("PRJ-01", "PARP synthetic lethality in BRCA-wildtype TNBC",
     "Test whether ATR/PARP combinations restore synthetic lethality in HR-proficient TNBC.", "active", "MEM-00"),
    ("PRJ-02", "TROP2 ADC response biomarkers",
     "Identify determinants of response to TROP2-directed ADCs across TNBC lines.", "active", "MEM-00"),
    ("PRJ-03", "Checkpoint blockade & PD-L1 dynamics",
     "Characterize PD-L1 regulation and immunotherapy response in TNBC models.", "active", "MEM-00"),
]

# (id, project, title, stage, target, assignee, status, priority, due, reagents)
TASKS = [
    ("TSK-01", "PRJ-01", "Literature scan: ATR+PARP combinations", "discover",
     "PARP/BRCA (HR deficiency)", "MEM-02", "done", "medium", d(-14), []),
    ("TSK-02", "PRJ-01", "Design PARP viability assay (BRCA-wt)", "design",
     "PARP/BRCA (HR deficiency)", "MEM-02", "done", "high", d(-7), []),
    ("TSK-03", "PRJ-01", "PARP inhibitor viability assay in MDA-MB-231", "experiment",
     "PARP/BRCA (HR deficiency)", "MEM-05", "blocked", "high", d(2),
     ["Olaparib", "MTT reagent", "MDA-MB-231 cell line", "96-well plate, clear flat"]),
    ("TSK-04", "PRJ-01", "γH2AX immunofluorescence after olaparib", "experiment",
     "ATR / CHK1 / WEE1 (DDR)", "MEM-06", "todo", "medium", d(9),
     ["Olaparib", "Anti-gamma-H2AX", "Paraformaldehyde 16%", "DAPI"]),
    ("TSK-05", "PRJ-01", "Analyze IC50 dose-response", "analysis",
     "PARP/BRCA (HR deficiency)", None, "todo", "medium", d(16), []),

    ("TSK-06", "PRJ-02", "Scan ADC / TROP2 evidence", "discover",
     "TROP2 (ADC target)", "MEM-04", "done", "medium", d(-10), []),
    ("TSK-07", "PRJ-02", "Quantify TROP2 by western across lines", "experiment",
     "TROP2 (ADC target)", "MEM-04", "in_progress", "high", d(4),
     ["Anti-PARP1 antibody", "Pierce BCA Protein Assay Kit", "Acrylamide/Bis 30%", "SuperSignal West Pico ECL"]),
    ("TSK-08", "PRJ-02", "Sacituzumab govitecan dose-response", "experiment",
     "TROP2 (ADC target)", "MEM-05", "blocked", "high", d(6),
     ["Sacituzumab govitecan", "MDA-MB-468 cell line", "96-well plate, clear flat"]),
    ("TSK-09", "PRJ-02", "Correlate TROP2 level with ADC IC50", "analysis",
     "TROP2 (ADC target)", None, "todo", "low", d(20), []),

    ("TSK-10", "PRJ-03", "Review PD-L1 regulation in TNBC", "discover",
     "PD-L1 / PD-1 (immune checkpoint)", "MEM-03", "done", "medium", d(-8), []),
    ("TSK-11", "PRJ-03", "PD-L1 expression panel by flow", "experiment",
     "PD-L1 / PD-1 (immune checkpoint)", "MEM-03", "in_progress", "high", d(3),
     ["Anti-PD-L1 antibody", "MDA-MB-231 cell line", "6-well plate, TC-treated"]),
    # duplicate effort: same target as TSK-11, different student
    ("TSK-12", "PRJ-03", "Screen PD-L1 inducers (IFN-γ)", "experiment",
     "PD-L1 / PD-1 (immune checkpoint)", "MEM-05", "todo", "medium", d(11),
     ["Anti-PD-L1 antibody", "MDA-MB-468 cell line"]),
    ("TSK-13", "PRJ-03", "Annexin V apoptosis under co-culture", "experiment",
     "PD-L1 / PD-1 (immune checkpoint)", "MEM-06", "todo", "medium", d(13),
     ["Annexin V-FITC Apoptosis Kit", "Propidium Iodide", "6-well plate, TC-treated"]),
    ("TSK-14", "PRJ-03", "Draft immunotherapy-resistance hypothesis", "discover",
     "PD-L1 / PD-1 (immune checkpoint)", None, "todo", "low", d(18), []),
    ("TSK-15", "PRJ-03", "Western blot — PD-L1 expression across TNBC lines", "experiment",
     "PD-L1 / PD-1 (immune checkpoint)", "MEM-06", "done", "high", d(-2),
     ["Pierce BCA Protein Assay Kit", "Acrylamide/Bis 30%", "Anti-PD-L1 antibody",
      "Goat anti-Rabbit HRP", "SuperSignal West Pico ECL", "Anti-GAPDH (loading control)"]),
    ("TSK-16", "PRJ-03", "IF microscopy — PD-L1 localization (green) / DAPI", "experiment",
     "PD-L1 / PD-1 (immune checkpoint)", "MEM-03", "in_progress", "high", d(4),
     ["Paraformaldehyde 16%", "Triton X-100", "Anti-PD-L1 antibody", "DAPI", "24-well plate, TC-treated"]),
    ("TSK-17", "PRJ-03", "Set up 96-well treatment plate (groups + dose series)", "experiment",
     "PD-L1 / PD-1 (immune checkpoint)", "MEM-05", "done", "medium", d(-5),
     ["Paclitaxel", "Anti-PD-L1 antibody", "96-well plate, clear flat", "MDA-MB-468 cell line", "DMSO"]),
]

# experimental design + attached photos for select tasks (how the protocol was run)
EXTRA = {
    "TSK-15": {
        "design": {
            "cell_lines": ["MCF-10A (normal control)", "MDA-MB-231 (basal-like)", "MDA-MB-468 (PD-L1-high)"],
            "groups": ["Baseline (untreated)"], "replicates": 3,
            "controls": ["GAPDH loading control", "MCF-10A normal line"],
            "readout": "PD-L1 band intensity normalised to GAPDH"},
        "attachments": ["/uploads/western_pdl1.png"]},
    "TSK-16": {
        "design": {
            "cell_lines": ["MDA-MB-468 (PD-L1-high)", "MDA-MB-231"],
            "groups": ["Vehicle", "IFN-γ stimulated"], "replicates": 3,
            "controls": ["Secondary-antibody only (no primary)", "DAPI only"],
            "readout": "PD-L1 membrane localisation (green) vs nuclei (DAPI, blue)"},
        "attachments": ["/uploads/if_pdl1.png"]},
    "TSK-17": {
        "design": {
            "cell_lines": ["MDA-MB-468 (PD-L1-high)", "MDA-MB-231", "MCF-10A (normal)"],
            "groups": ["Vehicle (DMSO)", "Chemotherapy (paclitaxel)", "Immunotherapy (anti-PD-L1)", "Chemo + Immuno"],
            "replicates": 3, "controls": ["Untreated", "Vehicle (DMSO)"],
            "readout": "5-point dose series per group"},
        "attachments": ["/uploads/plate_map.svg"]},
}

DDL_M = "CREATE TABLE IF NOT EXISTS members (id TEXT PRIMARY KEY, name TEXT, role TEXT, initials TEXT, focus TEXT)"
DDL_P = "CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, name TEXT, goal TEXT, status TEXT, lead TEXT, members TEXT, created TEXT)"


def _project_members(pid, lead):
    ppl = {lead} if lead else set()
    for t in TASKS:
        if t[1] == pid and t[5]:
            ppl.add(t[5])
    return sorted(ppl)
DDL_T = ("CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, project_id TEXT, title TEXT, stage TEXT, "
         "target TEXT, assignee TEXT, status TEXT, priority TEXT, due TEXT, reagents TEXT, notes TEXT, "
         "created TEXT, design TEXT, attachments TEXT)")


def main():
    root = Path(__file__).resolve().parent.parent
    db = root / "benchpilot.db"
    snap = root / "data" / "snapshot"
    snap.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db))
    for ddl, tbl in [(DDL_M, "members"), (DDL_P, "projects"), (DDL_T, "tasks")]:
        conn.execute(f"DROP TABLE IF EXISTS {tbl}")
        conn.execute(ddl)

    conn.executemany("INSERT INTO members VALUES (?,?,?,?,?)", MEMBERS)
    conn.executemany("INSERT INTO projects VALUES (?,?,?,?,?,?,?)",
                     [(p[0], p[1], p[2], p[3], p[4], json.dumps(_project_members(p[0], p[4])), d(-30))
                      for p in PROJECTS])
    conn.executemany(
        "INSERT INTO tasks (id,project_id,title,stage,target,assignee,status,priority,due,reagents,notes,"
        "created,design,attachments) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [(i, pj, ti, st, tg, asg, stat, pr, du, json.dumps(rg), "", d(-20),
          json.dumps(EXTRA.get(i, {}).get("design")), json.dumps(EXTRA.get(i, {}).get("attachments", [])))
         for (i, pj, ti, st, tg, asg, stat, pr, du, rg) in TASKS])
    conn.commit()

    # snapshots
    for name, rows in [("members", MEMBERS), ("projects", [(*p, d(-30)) for p in PROJECTS])]:
        pass
    with open(snap / "team.jsonl", "w", encoding="utf-8") as f:
        for m in MEMBERS:
            f.write(json.dumps({"kind": "member", "id": m[0], "name": m[1], "role": m[2],
                                "initials": m[3], "focus": m[4]}) + "\n")
        for p in PROJECTS:
            f.write(json.dumps({"kind": "project", "id": p[0], "name": p[1], "goal": p[2],
                                "status": p[3], "lead": p[4], "members": _project_members(p[0], p[4])}) + "\n")
        for t in TASKS:
            f.write(json.dumps({"kind": "task", "id": t[0], "project_id": t[1], "title": t[2],
                                "stage": t[3], "target": t[4], "assignee": t[5], "status": t[6],
                                "priority": t[7], "due": t[8], "reagents": t[9]}) + "\n")

    conn.close()
    print(f"✓ team: {len(MEMBERS)} members, {len(PROJECTS)} projects, {len(TASKS)} tasks")
    print(f"  blocked tasks: {sum(1 for t in TASKS if t[6]=='blocked')} · unassigned: {sum(1 for t in TASKS if t[5] is None)}")


if __name__ == "__main__":
    main()
