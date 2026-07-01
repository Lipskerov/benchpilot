#!/usr/bin/env python3
"""
Reconcile a protocol's required materials against live inventory.

Given a materials list (from src/protocols/generate.py), produce per-material
status (AVAILABLE / LOW / MISSING / EXPIRED) and an order list of what to buy.
Matching is deterministic and explainable (difflib fuzzy on normalized names,
plus CAS / catalog-number exact match). No external deps.
"""

import re
import difflib
from datetime import date
from typing import List, Dict, Optional

from src.inventory.store import InventoryStore

_PUNCT = re.compile(r"[^a-z0-9 ]+")
_WS = re.compile(r"\s+")


def _norm(s: str) -> str:
    s = (s or "").lower()
    s = _PUNCT.sub(" ", s)
    return _WS.sub(" ", s).strip()


def _best_match(req: Dict, items: List[Dict], norm_names: List[str]) -> Optional[Dict]:
    """Find the best inventory item for a required material."""
    # 1) exact CAS / catalog match
    for key in ("cas", "catalog_number"):
        val = str(req.get(key, "") or "").strip().lower()
        if val and val not in ("", "n/a", "none"):
            for it in items:
                if str(it.get(key, "") or "").strip().lower() == val:
                    return it
    rname = _norm(req.get("name", ""))
    if not rname:
        return None
    # 2) exact normalized name
    for it, nn in zip(items, norm_names):
        if nn == rname:
            return it
    # 3) containment either direction
    for it, nn in zip(items, norm_names):
        if rname in nn or nn in rname:
            return it
    # 4) fuzzy closest (token-aware)
    matches = difflib.get_close_matches(rname, norm_names, n=1, cutoff=0.6)
    if matches:
        return items[norm_names.index(matches[0])]
    return None


def check_protocol(materials: List[Dict], store: Optional[InventoryStore] = None) -> List[Dict]:
    own = store is None
    store = store or InventoryStore()
    items = store.list_items()
    norm_names = [_norm(it["name"]) for it in items]
    today = date.today().isoformat()

    rows: List[Dict] = []
    for req in materials:
        match = _best_match(req, items, norm_names)
        req_qty = req.get("quantity")
        req_unit = req.get("unit", "")

        if match is None:
            status = "MISSING"
            in_stock, unit = 0, req_unit
            row = {"matched_id": None, "matched_name": None,
                   "vendor": None, "catalog_number": None}
        else:
            in_stock = match.get("quantity") or 0
            unit = match.get("unit", req_unit)
            reorder = match.get("reorder_threshold") or 0
            exp = match.get("expiration") or ""
            same_unit = (str(req_unit).lower() == str(unit).lower()) and req_qty is not None
            if in_stock <= 0:
                status = "MISSING"
            elif exp and exp < today:
                status = "EXPIRED"
            elif in_stock <= reorder or (same_unit and in_stock < req_qty):
                status = "LOW"
            else:
                status = "AVAILABLE"
            row = {"matched_id": match["id"], "matched_name": match["name"],
                   "vendor": match.get("vendor"), "catalog_number": match.get("catalog_number")}

        # suggested reorder amount
        suggested = None
        if status in ("MISSING", "LOW", "EXPIRED"):
            reorder = (match.get("reorder_threshold") if match else None) or 0
            base = max(req_qty or 0, reorder * 2)
            suggested = round(max(base - (in_stock if status == "LOW" else 0), req_qty or reorder or 1), 1)

        row.update({
            "required_name": req.get("name"),
            "required_qty": req_qty,
            "required_unit": req_unit,
            "category": req.get("category"),
            "in_stock": in_stock,
            "unit": unit,
            "status": status,
            "suggested_order_qty": suggested,
        })
        rows.append(row)

    if own:
        store.close()
    return rows


def order_list(rows: List[Dict]) -> List[Dict]:
    """Filter the check rows down to items that need ordering."""
    need = [r for r in rows if r["status"] in ("MISSING", "LOW", "EXPIRED")]
    # MISSING first, then LOW, then EXPIRED
    order = {"MISSING": 0, "LOW": 1, "EXPIRED": 2}
    return sorted(need, key=lambda r: order.get(r["status"], 9))


if __name__ == "__main__":
    demo = [
        {"name": "Olaparib", "category": "chemical", "quantity": 10, "unit": "mg"},
        {"name": "MDA-MB-231 cell line", "category": "biological", "quantity": 1, "unit": "vials"},
        {"name": "96-well plate, clear flat", "category": "plastic", "quantity": 2, "unit": "case"},
        {"name": "Unobtainium reagent X", "category": "chemical", "quantity": 5, "unit": "mg"},
    ]
    rows = check_protocol(demo)
    for r in rows:
        print(f"  {r['status']:9} {r['required_name'][:30]:30} stock={r['in_stock']}{r['unit']} "
              f"match={r['matched_id']}")
    print("\nORDER LIST:")
    for r in order_list(rows):
        print(f"  {r['status']:9} {r['required_name'][:28]:28} qty~{r['suggested_order_qty']} "
              f"[{r['vendor']} {r['catalog_number']}]")
