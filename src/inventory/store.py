#!/usr/bin/env python3
"""
Inventory store: CRUD over the `inventory` table in benchpilot.db.
Tracks chemical / biological / plastic (consumable) stock, flags low stock and
expired items. Used by the "Inventory & Protocols" tab.
"""

import sqlite3
from datetime import date
from typing import List, Dict, Optional

DB_PATH = "benchpilot.db"

FIELDS = [
    "id", "name", "category", "subtype", "vendor", "catalog_number", "cas",
    "molecular_weight", "concentration", "purity", "form",
    "quantity", "unit", "reorder_threshold", "storage_location", "storage_temp",
    "lot", "expiration", "hazard", "notes", "last_updated",
]

_PREFIX = {"chemical": "CHEM", "biological": "BIOL", "plastic": "PLAS"}

DDL = """
CREATE TABLE IF NOT EXISTS inventory (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    subtype TEXT,
    vendor TEXT,
    catalog_number TEXT,
    cas TEXT,
    molecular_weight TEXT,
    concentration TEXT,
    purity TEXT,
    form TEXT,
    quantity REAL,
    unit TEXT,
    reorder_threshold REAL,
    storage_location TEXT,
    storage_temp TEXT,
    lot TEXT,
    expiration TEXT,
    hazard TEXT,
    notes TEXT,
    last_updated TEXT
)
"""


class InventoryStore:
    def __init__(self, db_path: str = DB_PATH):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute(DDL)
        self.conn.commit()

    # ---------- reads ----------
    def list_items(self, category: Optional[str] = None, search: Optional[str] = None) -> List[Dict]:
        q = "SELECT * FROM inventory WHERE 1=1"
        params: list = []
        if category and category != "all":
            q += " AND category = ?"
            params.append(category)
        if search:
            like = f"%{search.lower()}%"
            q += (" AND (LOWER(name) LIKE ? OR LOWER(IFNULL(vendor,'')) LIKE ?"
                  " OR LOWER(IFNULL(catalog_number,'')) LIKE ? OR LOWER(IFNULL(subtype,'')) LIKE ?)")
            params += [like, like, like, like]
        q += " ORDER BY category, name"
        return [dict(r) for r in self.conn.execute(q, params)]

    def get_item(self, item_id: str) -> Optional[Dict]:
        r = self.conn.execute("SELECT * FROM inventory WHERE id = ?", (item_id,)).fetchone()
        return dict(r) if r else None

    def categories(self) -> List[str]:
        return [r[0] for r in self.conn.execute(
            "SELECT DISTINCT category FROM inventory ORDER BY category")]

    def low_stock(self) -> List[Dict]:
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM inventory WHERE quantity <= reorder_threshold ORDER BY category, name")]

    def expired(self) -> List[Dict]:
        today = date.today().isoformat()
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM inventory WHERE IFNULL(expiration,'') != '' AND expiration < ? "
            "ORDER BY expiration", (today,))]

    def stats(self) -> Dict:
        total = self.conn.execute("SELECT COUNT(*) FROM inventory").fetchone()[0]
        return {"total": total, "low": len(self.low_stock()), "expired": len(self.expired())}

    # ---------- writes ----------
    def _next_id(self, category: str) -> str:
        prefix = _PREFIX.get(category, "ITEM")
        rows = self.conn.execute(
            "SELECT id FROM inventory WHERE id LIKE ?", (f"{prefix}-%",)).fetchall()
        nums = []
        for (rid,) in rows:
            try:
                nums.append(int(rid.split("-")[-1]))
            except (ValueError, IndexError):
                pass
        return f"{prefix}-{(max(nums) + 1) if nums else 1:04d}"

    def add_item(self, item: Dict) -> str:
        item = dict(item)
        if not item.get("id"):
            item["id"] = self._next_id(item.get("category", "chemical"))
        if not item.get("last_updated"):
            item["last_updated"] = date.today().isoformat()
        cols = [f for f in FIELDS if f in item]
        self.conn.execute(
            f"INSERT OR REPLACE INTO inventory ({','.join(cols)}) "
            f"VALUES ({','.join('?' for _ in cols)})",
            tuple(item[c] for c in cols),
        )
        self.conn.commit()
        return item["id"]

    def update_item(self, item_id: str, fields: Dict) -> None:
        fields = {k: v for k, v in fields.items() if k in FIELDS and k != "id"}
        fields["last_updated"] = date.today().isoformat()
        sets = ", ".join(f"{k} = ?" for k in fields)
        self.conn.execute(f"UPDATE inventory SET {sets} WHERE id = ?",
                          (*fields.values(), item_id))
        self.conn.commit()

    def delete_item(self, item_id: str) -> None:
        self.conn.execute("DELETE FROM inventory WHERE id = ?", (item_id,))
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()


if __name__ == "__main__":
    s = InventoryStore()
    print("stats:", s.stats())
    print("categories:", s.categories())
    print("first 3:", [i["name"] for i in s.list_items()[:3]])
    print("low stock:", [i["name"] for i in s.low_stock()][:5])
    s.close()
