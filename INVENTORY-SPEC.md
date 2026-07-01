# BenchPilot — Inventory & Protocols feature (SPEC + Bob build prompts)
### New tab: hypothesis → experiment → **protocol → live-inventory check → order list**

> Status: **synthetic inventory DB already built** by `etl/gen_inventory.py` (96 items: 32 chemical / 35 biological / 29 plastic; 9 low-stock, 7 expired) → loaded into `benchpilot.db` table `inventory` + `data/snapshot/inventory.jsonl`.
> The **app + protocol code below should be authored by Bob** (commit trail). I created only the synthetic seed data, per your request — Bob can regenerate it too if you want a 100% Bob trail.

---

## Why this is a big deal (judging)
Turns BenchPilot from "answers questions" into an **operational co-worker**: it proposes a protocol, reconciles it against *your real stock*, and hands you a shopping list. That's exactly the Wildcard "Future of Work" thesis — AI that helps *plan, coordinate, and execute*, not just inform. Strong, on-camera, and unique.

---

## 1. Data model (built — table `inventory`)
Fields: `id, name, category(chemical|biological|plastic), subtype, vendor, catalog_number, cas, quantity, unit, reorder_threshold, storage_location, storage_temp, lot, expiration, hazard, notes, last_updated`.
- **Low stock** = `quantity <= reorder_threshold` (or 0 = out).
- **Expired** = `expiration < today`.

## 2. New modules (Bob to build)

### `src/inventory/store.py` — CRUD + status
- `list_items(category=None, search=None) -> list[dict]`
- `add_item(item)`, `update_item(id, fields)`, `delete_item(id)` (catalogue new items on the UI)
- `low_stock() -> list`, `expired() -> list`, `categories() -> list`
- Writes go to `benchpilot.db` `inventory`.

### `src/protocols/generate.py` — protocol + materials (Granite, mock fallback)
- `suggest_protocol(experiment_or_hypothesis: str) -> dict`
- Output JSON:
```jsonc
{ "title": "PARP-inhibitor viability assay in BRCA-wildtype TNBC",
  "objective": "...",
  "steps": ["Seed 5,000 MDA-MB-231 cells/well in 96-well plate", "..."],
  "materials": [
    {"name":"Olaparib","category":"chemical","quantity":10,"unit":"mg","purpose":"PARP inhibition"},
    {"name":"MDA-MB-231 cell line","category":"biological","quantity":1,"unit":"vials"},
    {"name":"96-well plate, clear flat","category":"plastic","quantity":2,"unit":"case"},
    {"name":"MTT reagent","category":"chemical","quantity":50,"unit":"mg"}
  ],
  "estimated_duration":"5 days" }
```
- **MOCK_LLM=true** → return a canned protocol keyed by keywords (PARP/viability, qPCR, western blot, Annexin V apoptosis, immunofluorescence). Must always return a valid materials list so the match demo works offline.

### `src/inventory/match.py` — reconcile materials vs stock (deterministic, the core)
- `check_protocol(materials: list) -> list[dict]` where each row:
```jsonc
{ "required":{"name":"Olaparib","quantity":10,"unit":"mg"},
  "matched_id":"CHEM-0001", "in_stock":0, "unit":"mg",
  "status":"MISSING",            // AVAILABLE | LOW | MISSING | EXPIRED
  "vendor":"Selleck","catalog_number":"S1060","suggested_order_qty": ... }
```
- **Matching:** normalize name (lowercase, strip punctuation); match on `name` (exact → contains → fuzzy), fall back to `cas`/`catalog_number`. Keep it simple + explainable (difflib is fine — no extra deps).
- **Status logic:** no match or `in_stock<=0` → **MISSING**; matched but `in_stock<=reorder_threshold` (or `< required qty` when units match) → **LOW**; `expiration<today` → **EXPIRED**; else **AVAILABLE**.
- `order_list(rows) -> list` = all MISSING/LOW/EXPIRED with vendor + catalog + suggested qty (for the "need to order" panel; exportable as CSV/markdown).

## 3. UI (Bob to build) — same app, second tab
Restructure `src/app/app.py` to top-level tabs:
```python
tab_research, tab_inv = st.tabs(["🔬 Research", "🧪 Inventory & Protocols"])
```
- **Research tab:** existing Q&A (unchanged).
- **Inventory & Protocols tab** — a radio/segmented control with two views:
  1. **📦 Catalogue** — filter by category (chemical/biological/plastic) + search box; table with **low-stock rows in red** and an **⚠️ expired** badge; an **"➕ Add / edit item"** form (all fields) writing via `store.add_item/update_item`; delete button.
  2. **🧫 Protocol → Inventory check** — a text box (prefill with the last Research question if present) → **"Generate protocol"** → show protocol steps + a **materials table color-coded by status** (🟢 available / 🟠 low / 🔴 missing / ⏳ expired) → a **"🛒 Need to order"** panel listing MISSING/LOW/EXPIRED with vendor + catalog + suggested qty, and a **download button** (CSV).
- Sidebar: add an **"Inventory: 96 items · N low · M expired"** metric.

## 4. Acceptance criteria
- Catalogue lists 96 items; filtering by category works; adding a new item persists and reappears after rerun.
- Entering "PARP inhibitor viability assay in BRCA-wildtype TNBC" generates a protocol whose materials include Olaparib → inventory check marks **Olaparib = MISSING** (qty 0) → it appears in the order list with vendor Selleck / S1060.
- Runs fully with `MOCK_LLM=true` (no watsonx needed).

---

## 5. Bob build prompts (paste in order — Bob authors & commits each)
1. 🤖 **Inventory store + matcher** · 🪙~6
   > "Create `src/inventory/store.py` (CRUD over the existing `inventory` table in benchpilot.db: list/add/update/delete, low_stock, expired, categories) and `src/inventory/match.py` (`check_protocol(materials)` + `order_list(rows)` per INVENTORY-SPEC.md §2, using difflib for fuzzy name matching — no new deps). Add a `__main__` self-test. Commit 'feat(inventory): store CRUD + protocol-material matcher'."
2. 🤖 **Protocol generator** · 🪙~5
   > "Create `src/protocols/generate.py` with `suggest_protocol(text)` returning the JSON in INVENTORY-SPEC §2, Granite via watsonx with a `MOCK_LLM=true` canned-protocol fallback keyed by assay keywords (PARP/viability, qPCR, western blot, Annexin V, IF). Commit 'feat(protocols): experiment→protocol with materials (mock fallback)'."
3. 🤖 **UI second tab** · 🪙~7
   > "Refactor `src/app/app.py` into two top-level tabs '🔬 Research' (existing Q&A) and '🧪 Inventory & Protocols' per INVENTORY-SPEC §3: a Catalogue view (category filter, search, low-stock in red, expired badge, add/edit/delete form) and a Protocol→Inventory-check view (generate protocol, color-coded materials table by status, '🛒 Need to order' panel with CSV download). Add inventory metrics to the sidebar. Commit 'feat(app): inventory & protocols tab'."

**Feature coin cost: ~🪙18.**

---

## 6. ⚠️ Budget reality check
- Original cap is **40 Bobcoins**. V1 build already consumed part of it; V1 fix-pass (~🪙8) + this inventory feature (~🪙18) will likely push you **over 40**.
- **Options:** (a) make **Inventory & Protocols the flagship** and defer the separate "evidence-gap engine" from PROJECT-MAP §2 (they overlap in spirit); (b) do the inventory feature with real Granite and keep the Research tab in mock; (c) request/allocate more Bobcoins if the plan allows.
- My recommendation: **(a)** — inventory + protocol + order-list is a sharper, more original demo than the gap engine, so lead with it and drop gap-engine to "future work."
