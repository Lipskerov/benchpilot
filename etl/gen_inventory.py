#!/usr/bin/env python3
"""
Generate a realistic SYNTHETIC lab inventory for a TNBC research lab and load it
into benchpilot.db (table: inventory) + data/snapshot/inventory.jsonl.

Three categories: chemical, biological, plastic (consumables/labware).
Some items are intentionally below reorder threshold or expired so the
"what do we need to order?" flagging can be demoed.

Deterministic (seeded) so the demo reproduces.
"""

import json
import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

random.seed(42)
TODAY = date(2026, 7, 1)  # fixed for reproducibility

# Molecular weights (g/mol) for known chemicals; "" for the rest
MW = {
    "Olaparib": 435.4, "Talazoparib": 380.4, "Cisplatin": 300.05, "Carboplatin": 371.25,
    "Paclitaxel": 853.9, "Doxorubicin HCl": 579.98, "DMSO": 78.13, "Tris base": 121.14,
    "EDTA disodium": 372.24, "SDS": 288.38, "Glycine": 75.07, "Methanol": 32.04,
    "Ethanol absolute": 46.07, "Crystal Violet": 407.99, "MTT reagent": 414.32,
    "Propidium Iodide": 668.4, "DAPI": 350.25, "2-Mercaptoethanol": 78.13,
    "Triton X-100": 647.0, "Tween-20": 1227.5, "Acrylamide/Bis 30%": 71.08,
    "APS (ammonium persulfate)": 228.18, "TEMED": 116.21, "Hydrocortisone": 362.46,
}

# --- Curated, realistic item catalogs -------------------------------------------------
# (name, subtype, vendor, catalog_number, cas, unit, hazard, storage_temp)
CHEMICALS = [
    ("Olaparib", "PARP inhibitor", "Selleck", "S1060", "763113-22-0", "mg", "Irritant", "-20C"),
    ("Talazoparib", "PARP inhibitor", "MedChemExpress", "HY-16106", "1207456-01-6", "mg", "Irritant", "-20C"),
    ("Cisplatin", "Chemotherapy", "Sigma-Aldrich", "P4394", "15663-27-1", "mg", "Toxic", "RT"),
    ("Carboplatin", "Chemotherapy", "Sigma-Aldrich", "C2538", "41575-94-4", "mg", "Toxic", "RT"),
    ("Paclitaxel", "Chemotherapy", "Sigma-Aldrich", "T7402", "33069-62-4", "mg", "Toxic", "-20C"),
    ("Doxorubicin HCl", "Chemotherapy", "Sigma-Aldrich", "D1515", "25316-40-9", "mg", "Toxic", "-20C"),
    ("DMSO", "Solvent", "Sigma-Aldrich", "D2650", "67-68-5", "mL", "Irritant", "RT"),
    ("RPMI-1640 medium", "Cell culture media", "Gibco", "11875093", "N/A", "mL", "None", "4C"),
    ("DMEM high glucose", "Cell culture media", "Gibco", "11965092", "N/A", "mL", "None", "4C"),
    ("Fetal Bovine Serum (FBS)", "Media supplement", "Gibco", "16000044", "N/A", "mL", "None", "-20C"),
    ("Penicillin-Streptomycin", "Antibiotic", "Gibco", "15140122", "N/A", "mL", "Irritant", "-20C"),
    ("Trypsin-EDTA 0.25%", "Dissociation", "Gibco", "25200056", "N/A", "mL", "Irritant", "-20C"),
    ("DPBS 1x", "Buffer", "Gibco", "14190144", "N/A", "mL", "None", "RT"),
    ("Tris base", "Buffer", "Sigma-Aldrich", "T1503", "77-86-1", "g", "Irritant", "RT"),
    ("EDTA disodium", "Buffer", "Sigma-Aldrich", "E5134", "6381-92-6", "g", "Irritant", "RT"),
    ("SDS", "Detergent", "Sigma-Aldrich", "L3771", "151-21-3", "g", "Irritant", "RT"),
    ("Glycine", "Buffer", "Sigma-Aldrich", "G7126", "56-40-6", "g", "None", "RT"),
    ("Methanol", "Solvent", "Sigma-Aldrich", "179337", "67-56-1", "mL", "Flammable/Toxic", "Flammables"),
    ("Ethanol absolute", "Solvent", "Sigma-Aldrich", "459836", "64-17-5", "mL", "Flammable", "Flammables"),
    ("Paraformaldehyde 16%", "Fixative", "Thermo", "28908", "50-00-0", "mL", "Toxic/Carcinogen", "4C"),
    ("Crystal Violet", "Stain", "Sigma-Aldrich", "C0775", "548-62-9", "g", "Irritant", "RT"),
    ("MTT reagent", "Viability assay", "Sigma-Aldrich", "M5655", "298-93-1", "mg", "Irritant", "-20C"),
    ("Propidium Iodide", "Viability stain", "Sigma-Aldrich", "P4170", "25535-16-4", "mg", "Toxic", "4C"),
    ("DAPI", "Nuclear stain", "Thermo", "62248", "28718-90-3", "mg", "Irritant", "-20C"),
    ("2-Mercaptoethanol", "Reducing agent", "Sigma-Aldrich", "M3148", "60-24-2", "mL", "Toxic", "4C"),
    ("Agarose", "Electrophoresis", "Sigma-Aldrich", "A9539", "9012-36-6", "g", "None", "RT"),
    ("Bovine Serum Albumin (BSA)", "Blocking", "Sigma-Aldrich", "A7906", "9048-46-8", "g", "None", "4C"),
    ("Triton X-100", "Detergent", "Sigma-Aldrich", "X100", "9002-93-1", "mL", "Irritant", "RT"),
    ("Tween-20", "Detergent", "Sigma-Aldrich", "P9416", "9005-64-5", "mL", "None", "RT"),
    ("Acrylamide/Bis 30%", "Electrophoresis", "Bio-Rad", "1610158", "79-06-1", "mL", "Neurotoxin/Carcinogen", "4C"),
    ("APS (ammonium persulfate)", "Electrophoresis", "Sigma-Aldrich", "A3678", "7727-54-0", "g", "Oxidizer", "4C"),
    ("TEMED", "Electrophoresis", "Sigma-Aldrich", "T9281", "110-18-9", "mL", "Flammable/Toxic", "RT"),
]

BIOLOGICALS = [
    ("Anti-PARP1 antibody", "Primary antibody", "Cell Signaling", "9532", "N/A", "uL", "None", "-20C"),
    ("Anti-cleaved Caspase-3", "Primary antibody", "Cell Signaling", "9664", "N/A", "uL", "None", "-20C"),
    ("Anti-gamma-H2AX", "Primary antibody", "Millipore", "05-636", "N/A", "uL", "None", "-20C"),
    ("Anti-BRCA1 antibody", "Primary antibody", "Santa Cruz", "sc-6954", "N/A", "uL", "None", "-20C"),
    ("Anti-Ki67 antibody", "Primary antibody", "Abcam", "ab15580", "N/A", "uL", "None", "4C"),
    ("Anti-PD-L1 antibody", "Primary antibody", "Cell Signaling", "13684", "N/A", "uL", "None", "-20C"),
    ("Anti-E-cadherin", "Primary antibody", "BD Biosciences", "610181", "N/A", "uL", "None", "4C"),
    ("Anti-Vimentin", "Primary antibody", "Cell Signaling", "5741", "N/A", "uL", "None", "-20C"),
    ("Anti-GAPDH (loading control)", "Primary antibody", "Cell Signaling", "2118", "N/A", "uL", "None", "-20C"),
    ("Goat anti-Rabbit HRP", "Secondary antibody", "Cell Signaling", "7074", "N/A", "uL", "None", "-20C"),
    ("Goat anti-Mouse HRP", "Secondary antibody", "Cell Signaling", "7076", "N/A", "uL", "None", "-20C"),
    ("Taq DNA Polymerase", "Enzyme", "NEB", "M0273", "N/A", "units", "None", "-20C"),
    ("Q5 High-Fidelity Polymerase", "Enzyme", "NEB", "M0491", "N/A", "units", "None", "-20C"),
    ("T4 DNA Ligase", "Enzyme", "NEB", "M0202", "N/A", "units", "None", "-20C"),
    ("DNase I, RNase-free", "Enzyme", "NEB", "M0303", "N/A", "units", "None", "-20C"),
    ("Proteinase K", "Enzyme", "Thermo", "EO0491", "N/A", "mL", "Irritant", "-20C"),
    ("RNase A", "Enzyme", "Thermo", "EN0531", "N/A", "mL", "Irritant", "4C"),
    ("RNeasy Mini Kit", "Kit", "Qiagen", "74104", "N/A", "preps", "None", "RT"),
    ("High-Capacity cDNA RT Kit", "Kit", "Applied Biosystems", "4368814", "N/A", "rxns", "None", "-20C"),
    ("PowerUp SYBR Green Master Mix", "qPCR reagent", "Applied Biosystems", "A25742", "N/A", "rxns", "None", "-20C"),
    ("Pierce BCA Protein Assay Kit", "Kit", "Thermo", "23225", "N/A", "assays", "Irritant", "RT"),
    ("SuperSignal West Pico ECL", "Detection", "Thermo", "34580", "N/A", "mL", "None", "4C"),
    ("Annexin V-FITC Apoptosis Kit", "Kit", "BD Biosciences", "556547", "N/A", "tests", "None", "4C"),
    ("Lipofectamine 3000", "Transfection", "Thermo", "L3000015", "N/A", "mL", "Irritant", "4C"),
    ("MDA-MB-231 cell line", "Cell line", "ATCC", "HTB-26", "N/A", "vials", "Biohazard", "LN2"),
    ("MDA-MB-468 cell line", "Cell line", "ATCC", "HTB-132", "N/A", "vials", "Biohazard", "LN2"),
    ("BT-549 cell line", "Cell line", "ATCC", "HTB-122", "N/A", "vials", "Biohazard", "LN2"),
    ("HCC1937 cell line (BRCA1-mut)", "Cell line", "ATCC", "CRL-2336", "N/A", "vials", "Biohazard", "LN2"),
    ("MCF-10A cell line (normal)", "Cell line", "ATCC", "CRL-10317", "N/A", "vials", "Biohazard", "LN2"),
    ("BRCA1 qPCR primers (F/R)", "Primer", "IDT", "custom-BRCA1", "N/A", "nmol", "None", "-20C"),
    ("GAPDH qPCR primers (F/R)", "Primer", "IDT", "custom-GAPDH", "N/A", "nmol", "None", "-20C"),
    ("PARP1 qPCR primers (F/R)", "Primer", "IDT", "custom-PARP1", "N/A", "nmol", "None", "-20C"),
    ("Recombinant human EGF", "Growth factor", "PeproTech", "AF-100-15", "N/A", "ug", "None", "-20C"),
    ("Hydrocortisone", "Media supplement", "Sigma-Aldrich", "H0888", "50-23-7", "mg", "Irritant", "4C"),
    ("Insulin (human)", "Media supplement", "Sigma-Aldrich", "I9278", "11061-68-0", "mL", "None", "4C"),
]

PLASTICS = [
    ("Filter tips 10 uL", "Pipette tips", "Rainin", "30389226", "rack", "None", "RT"),
    ("Filter tips 200 uL", "Pipette tips", "Rainin", "30389228", "rack", "None", "RT"),
    ("Filter tips 1000 uL", "Pipette tips", "Rainin", "30389230", "rack", "None", "RT"),
    ("96-well plate, clear flat", "Microplate", "Corning", "3599", "case", "None", "RT"),
    ("96-well plate, black", "Microplate", "Corning", "3603", "case", "None", "RT"),
    ("96-well qPCR plate", "Microplate", "Applied Biosystems", "4346906", "case", "None", "RT"),
    ("6-well plate, TC-treated", "Microplate", "Corning", "3516", "case", "None", "RT"),
    ("12-well plate, TC-treated", "Microplate", "Corning", "3513", "case", "None", "RT"),
    ("24-well plate, TC-treated", "Microplate", "Corning", "3526", "case", "None", "RT"),
    ("T25 flask, TC-treated", "Flask", "Corning", "430639", "case", "None", "RT"),
    ("T75 flask, TC-treated", "Flask", "Corning", "430641U", "case", "None", "RT"),
    ("T175 flask, TC-treated", "Flask", "Corning", "431080", "case", "None", "RT"),
    ("15 mL conical tube", "Tube", "Falcon", "352096", "case", "None", "RT"),
    ("50 mL conical tube", "Tube", "Falcon", "352070", "case", "None", "RT"),
    ("1.5 mL microcentrifuge tube", "Tube", "Eppendorf", "022363204", "case", "None", "RT"),
    ("2.0 mL microcentrifuge tube", "Tube", "Eppendorf", "022363352", "case", "None", "RT"),
    ("0.2 mL PCR 8-tube strips", "Tube", "Thermo", "AB2000", "pack", "None", "RT"),
    ("Serological pipette 5 mL", "Serological pipette", "Falcon", "357543", "case", "None", "RT"),
    ("Serological pipette 10 mL", "Serological pipette", "Falcon", "357551", "case", "None", "RT"),
    ("Serological pipette 25 mL", "Serological pipette", "Falcon", "357525", "case", "None", "RT"),
    ("Cryovial 2 mL", "Cryovial", "Thermo", "5000-0020", "pack", "None", "RT"),
    ("Cell scraper 25 cm", "Cell scraper", "Corning", "3010", "pack", "None", "RT"),
    ("Nitrile gloves M", "Gloves", "Kimberly-Clark", "55082", "box", "None", "RT"),
    ("Nitrile gloves L", "Gloves", "Kimberly-Clark", "55083", "box", "None", "RT"),
    ("0.22 um filter unit", "Filter", "Millipore", "SLGP033RS", "pack", "None", "RT"),
    ("10 cm cell culture dish", "Dish", "Corning", "430167", "case", "None", "RT"),
    ("Parafilm M roll", "Sealing film", "Bemis", "PM996", "roll", "None", "RT"),
    ("Reagent reservoir 25 mL", "Reservoir", "Corning", "4870", "case", "None", "RT"),
    ("Cell strainer 40 um", "Strainer", "Falcon", "352340", "pack", "None", "RT"),
]

# base "full" quantities per unit type (rough, realistic)
FULL_QTY = {
    "mg": (100, 1000), "mL": (100, 500), "g": (25, 500), "uL": (100, 1000),
    "units": (500, 5000), "preps": (50, 250), "rxns": (200, 1000), "assays": (200, 500),
    "tests": (50, 100), "nmol": (10, 50), "ug": (100, 500), "vials": (3, 12),
    "rack": (5, 40), "case": (2, 12), "pack": (2, 20), "box": (2, 20), "roll": (2, 8),
}


def _row(name, category, subtype, vendor, cat_no, cas, unit, hazard, temp, idx):
    lo, hi = FULL_QTY.get(unit, (5, 50))
    reorder = round(random.uniform(0.15, 0.30) * hi, 1)
    # ~18% of items are low stock, a few are zero
    roll = random.random()
    if roll < 0.06:
        qty = 0
    elif roll < 0.18:
        qty = round(random.uniform(0.2, 0.9) * reorder, 1)     # below threshold
    else:
        qty = round(random.uniform(reorder * 1.5, hi), 1)      # healthy
    # expiration: biologicals/chemicals get dates; a few already expired
    exp = ""
    if category in ("biological", "chemical"):
        days = random.randint(-90, 900)      # some in the past
        exp = (TODAY + timedelta(days=days)).isoformat()
    loc_map = {"chemical": ["Chem shelf A", "Chem shelf B", "Flammables cabinet", "Fridge 1", "Freezer -20 #2"],
               "biological": ["Freezer -20 #1", "Freezer -80 #1", "Fridge 2", "LN2 tank"],
               "plastic": ["Consumables rack 1", "Consumables rack 2", "Cold room", "Bench cabinet"]}

    # ---- enrichment fields (concentration / purity / MW / form) ----
    mw = MW.get(name, "")
    purity, concentration, form = "", "", ""
    if category == "chemical":
        purity = random.choice(["≥95%", "≥98%", "≥99%", "≥99.5%"])
        if unit in ("mg", "g"):
            form = "Powder"
            concentration = ""
        else:  # liquids
            form = "Solution"
            if "medium" in name.lower() or "DPBS" in name or "Trypsin" in name:
                concentration = "1×"
            elif "FBS" in name:
                concentration = "100% (heat-inactivated)"
            else:
                concentration = random.choice(["100%", "10 mM stock", "1 M stock", "0.5 M"])
    elif category == "biological":
        sl = subtype.lower()
        if "antibody" in sl:
            form = "Liquid"; concentration = random.choice(["1 mg/mL", "0.5 mg/mL", "200 µg/mL"])
        elif "enzyme" in sl:
            form = "Liquid (glycerol)"; concentration = random.choice(["5,000 U/mL", "20,000 U/mL", "2 U/µL"])
        elif "primer" in sl:
            form = "Lyophilized"; concentration = "100 µM (resuspended)"
        elif "cell line" in sl:
            form = "Cryopreserved"; concentration = "~1×10⁶ cells/vial"
        elif "kit" in sl:
            form = "Kit"; concentration = ""
        else:
            form = "Liquid"; concentration = random.choice(["1 mg/mL", "10 µg/mL", "100×"])
    else:  # plastic
        form = random.choice(["Sterile", "Sterile, individually wrapped", "Non-sterile"])

    return {
        "id": f"{category[:4].upper()}-{idx:04d}",
        "name": name,
        "category": category,
        "subtype": subtype,
        "vendor": vendor,
        "catalog_number": cat_no,
        "cas": cas,
        "molecular_weight": mw,
        "concentration": concentration,
        "purity": purity,
        "form": form,
        "quantity": qty,
        "unit": unit,
        "reorder_threshold": reorder,
        "storage_location": random.choice(loc_map[category]),
        "storage_temp": temp,
        "lot": f"LOT{random.randint(100000, 999999)}",
        "expiration": exp,
        "hazard": hazard,
        "notes": "",
        "last_updated": (TODAY - timedelta(days=random.randint(0, 120))).isoformat(),
    }


def build_items():
    items, i = [], 1
    for (name, sub, ven, cat, cas, unit, haz, temp) in CHEMICALS:
        items.append(_row(name, "chemical", sub, ven, cat, cas, unit, haz, temp, i)); i += 1
    j = 1
    for (name, sub, ven, cat, cas, unit, haz, temp) in BIOLOGICALS:
        items.append(_row(name, "biological", sub, ven, cat, cas, unit, haz, temp, j)); j += 1
    k = 1
    for (name, sub, ven, cat, unit, haz, temp) in PLASTICS:
        items.append(_row(name, "plastic", sub, ven, cat, "N/A", unit, haz, temp, k)); k += 1
    return items


DDL = """
CREATE TABLE IF NOT EXISTS inventory (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,           -- chemical | biological | plastic
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


def main():
    root = Path(__file__).resolve().parent.parent
    db_path = root / "benchpilot.db"
    out = root / "data" / "snapshot" / "inventory.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)

    items = build_items()

    with open(out, "w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")

    conn = sqlite3.connect(str(db_path))
    conn.execute("DROP TABLE IF EXISTS inventory")
    conn.execute(DDL)
    cols = list(items[0].keys())
    conn.executemany(
        f"INSERT INTO inventory ({','.join(cols)}) VALUES ({','.join('?' for _ in cols)})",
        [tuple(it[c] for c in cols) for it in items],
    )
    conn.commit()

    low = [it for it in items if it["quantity"] <= it["reorder_threshold"]]
    expired = [it for it in items if it["expiration"] and it["expiration"] < TODAY.isoformat()]
    by_cat = {}
    for it in items:
        by_cat[it["category"]] = by_cat.get(it["category"], 0) + 1

    print(f"✓ Generated {len(items)} inventory items -> {out}")
    print(f"  by category: {by_cat}")
    print(f"  low/out of stock (<= reorder): {len(low)}")
    print(f"  expired: {len(expired)}")
    conn.close()


if __name__ == "__main__":
    main()
