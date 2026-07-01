#!/usr/bin/env python3
"""
Turn an experiment idea / hypothesis into a structured protocol with a materials
list. Uses IBM Granite (watsonx) when configured; falls back to canned protocols
keyed by assay keywords when MOCK_LLM=true (or watsonx is unavailable) so the
inventory-matching demo always works offline.

Output schema:
{ "title", "objective", "steps": [...],
  "materials": [ {"name","category","quantity","unit","purpose"} ],
  "estimated_duration" }

The material names are chosen to match names in the synthetic inventory so the
matcher (src/inventory/match.py) can reconcile them.
"""

import os
from typing import Dict

MOCK_LLM = os.getenv("MOCK_LLM", "false").lower() == "true"


# ---- canned protocol library (mock) --------------------------------------------------
_PARP_VIABILITY = {
    "title": "PARP-inhibitor viability assay in TNBC cells",
    "objective": "Determine the dose-response of a PARP inhibitor on TNBC cell viability.",
    "steps": [
        "Seed 5,000 TNBC cells per well in a 96-well plate; incubate 24 h.",
        "Prepare olaparib serial dilutions in DMSO; treat wells in triplicate.",
        "Incubate 72 h at 37 °C, 5% CO2.",
        "Add MTT reagent; incubate 3 h; solubilize formazan in DMSO.",
        "Read absorbance at 570 nm and compute IC50.",
    ],
    "materials": [
        {"name": "Olaparib", "category": "chemical", "quantity": 10, "unit": "mg", "purpose": "PARP inhibition"},
        {"name": "MDA-MB-231 cell line", "category": "biological", "quantity": 1, "unit": "vials", "purpose": "TNBC model"},
        {"name": "RPMI-1640 medium", "category": "chemical", "quantity": 100, "unit": "mL", "purpose": "culture"},
        {"name": "Fetal Bovine Serum (FBS)", "category": "chemical", "quantity": 50, "unit": "mL", "purpose": "supplement"},
        {"name": "96-well plate, clear flat", "category": "plastic", "quantity": 1, "unit": "case", "purpose": "assay plate"},
        {"name": "MTT reagent", "category": "chemical", "quantity": 50, "unit": "mg", "purpose": "viability readout"},
        {"name": "DMSO", "category": "chemical", "quantity": 20, "unit": "mL", "purpose": "solvent"},
        {"name": "Filter tips 200 uL", "category": "plastic", "quantity": 2, "unit": "rack", "purpose": "pipetting"},
    ],
    "estimated_duration": "5 days",
}

_QPCR = {
    "title": "qPCR gene-expression assay in TNBC cells",
    "objective": "Quantify target mRNA expression relative to GAPDH in treated vs control TNBC cells.",
    "steps": [
        "Extract total RNA with the RNeasy Mini Kit.",
        "Reverse-transcribe 1 µg RNA using the cDNA RT kit.",
        "Set up SYBR Green qPCR with target and GAPDH primers in a 96-well qPCR plate.",
        "Run 40 cycles; analyze with the 2^-ddCt method.",
    ],
    "materials": [
        {"name": "RNeasy Mini Kit", "category": "biological", "quantity": 1, "unit": "preps", "purpose": "RNA extraction"},
        {"name": "High-Capacity cDNA RT Kit", "category": "biological", "quantity": 50, "unit": "rxns", "purpose": "reverse transcription"},
        {"name": "PowerUp SYBR Green Master Mix", "category": "biological", "quantity": 200, "unit": "rxns", "purpose": "qPCR"},
        {"name": "PARP1 qPCR primers (F/R)", "category": "biological", "quantity": 5, "unit": "nmol", "purpose": "target amplicon"},
        {"name": "GAPDH qPCR primers (F/R)", "category": "biological", "quantity": 5, "unit": "nmol", "purpose": "reference gene"},
        {"name": "96-well qPCR plate", "category": "plastic", "quantity": 1, "unit": "case", "purpose": "qPCR plate"},
        {"name": "Filter tips 10 uL", "category": "plastic", "quantity": 2, "unit": "rack", "purpose": "pipetting"},
    ],
    "estimated_duration": "2 days",
}

_WESTERN = {
    "title": "Western blot for DNA-damage / apoptosis markers",
    "objective": "Assess PARP and cleaved-caspase-3 protein levels after treatment.",
    "steps": [
        "Lyse cells; quantify protein with the BCA assay.",
        "Run SDS-PAGE (acrylamide gel); transfer to membrane.",
        "Block in BSA; probe with anti-PARP1 and anti-cleaved caspase-3.",
        "Detect with HRP secondary + ECL substrate; normalize to GAPDH.",
    ],
    "materials": [
        {"name": "Pierce BCA Protein Assay Kit", "category": "biological", "quantity": 1, "unit": "assays", "purpose": "protein quant"},
        {"name": "Acrylamide/Bis 30%", "category": "chemical", "quantity": 50, "unit": "mL", "purpose": "gel"},
        {"name": "Anti-PARP1 antibody", "category": "biological", "quantity": 50, "unit": "uL", "purpose": "primary antibody"},
        {"name": "Anti-cleaved Caspase-3", "category": "biological", "quantity": 50, "unit": "uL", "purpose": "primary antibody"},
        {"name": "Goat anti-Rabbit HRP", "category": "biological", "quantity": 20, "unit": "uL", "purpose": "secondary antibody"},
        {"name": "Anti-GAPDH (loading control)", "category": "biological", "quantity": 20, "unit": "uL", "purpose": "loading control"},
        {"name": "SuperSignal West Pico ECL", "category": "biological", "quantity": 10, "unit": "mL", "purpose": "detection"},
        {"name": "Bovine Serum Albumin (BSA)", "category": "chemical", "quantity": 25, "unit": "g", "purpose": "blocking"},
    ],
    "estimated_duration": "2 days",
}

_APOPTOSIS = {
    "title": "Annexin V / PI apoptosis assay by flow cytometry",
    "objective": "Quantify apoptotic and necrotic fractions after drug treatment.",
    "steps": [
        "Treat TNBC cells in 6-well plates for 48 h.",
        "Harvest, wash, and resuspend in binding buffer.",
        "Stain with Annexin V-FITC and propidium iodide.",
        "Acquire on flow cytometer; gate live / early / late apoptotic.",
    ],
    "materials": [
        {"name": "Annexin V-FITC Apoptosis Kit", "category": "biological", "quantity": 20, "unit": "tests", "purpose": "apoptosis stain"},
        {"name": "Propidium Iodide", "category": "chemical", "quantity": 5, "unit": "mg", "purpose": "necrosis stain"},
        {"name": "Cisplatin", "category": "chemical", "quantity": 10, "unit": "mg", "purpose": "positive control"},
        {"name": "6-well plate, TC-treated", "category": "plastic", "quantity": 1, "unit": "case", "purpose": "treatment plate"},
        {"name": "MDA-MB-468 cell line", "category": "biological", "quantity": 1, "unit": "vials", "purpose": "TNBC model"},
    ],
    "estimated_duration": "3 days",
}

_IF = {
    "title": "Immunofluorescence of gamma-H2AX DNA-damage foci",
    "objective": "Visualize DNA double-strand-break foci after PARP-inhibitor treatment.",
    "steps": [
        "Seed cells on coverslips in 24-well plates.",
        "Treat, then fix with paraformaldehyde and permeabilize with Triton X-100.",
        "Block in BSA; stain with anti-gamma-H2AX + fluorescent secondary; counterstain DAPI.",
        "Image by fluorescence microscopy and count foci per nucleus.",
    ],
    "materials": [
        {"name": "Paraformaldehyde 16%", "category": "chemical", "quantity": 20, "unit": "mL", "purpose": "fixation"},
        {"name": "Triton X-100", "category": "chemical", "quantity": 5, "unit": "mL", "purpose": "permeabilization"},
        {"name": "Anti-gamma-H2AX", "category": "biological", "quantity": 50, "unit": "uL", "purpose": "DNA-damage marker"},
        {"name": "DAPI", "category": "chemical", "quantity": 5, "unit": "mg", "purpose": "nuclear counterstain"},
        {"name": "24-well plate, TC-treated", "category": "plastic", "quantity": 1, "unit": "case", "purpose": "coverslip plate"},
        {"name": "Bovine Serum Albumin (BSA)", "category": "chemical", "quantity": 25, "unit": "g", "purpose": "blocking"},
    ],
    "estimated_duration": "2 days",
}


def _pick_mock(text: str) -> Dict:
    t = (text or "").lower()
    if any(k in t for k in ("qpcr", "rt-pcr", "expression", "mrna", "transcript")):
        return _QPCR
    if any(k in t for k in ("western", "protein", "blot", "immunoblot")):
        return _WESTERN
    if any(k in t for k in ("apopto", "annexin", "flow cyto", "cell death")):
        return _APOPTOSIS
    if any(k in t for k in ("immunofluor", "microscop", "foci", "h2ax", "staining", " if ")):
        return _IF
    # default: viability / PARP / drug screen
    return _PARP_VIABILITY


def suggest_protocol(text: str) -> Dict:
    """Generate a protocol + materials list for an experiment idea/hypothesis."""
    if not MOCK_LLM:
        try:
            proto = _granite_protocol(text)
            if proto and proto.get("materials"):
                proto["query"] = text
                proto["engine"] = "granite"
                return proto
        except Exception:
            pass  # fall back to templates so the app never blocks
    proto = dict(_pick_mock(text))
    proto["query"] = text
    proto["engine"] = "offline"
    return proto


def _granite_protocol(text: str) -> Dict:
    """Real watsonx/Granite protocol generation. Raises if not configured."""
    from src.llm import granite
    if not granite.is_configured():
        raise RuntimeError("watsonx not configured")
    prompt = (
        "You are a TNBC lab scientist. Draft a concise, runnable protocol for this experiment. "
        "Return JSON with keys: title, objective, steps (list of strings), estimated_duration, "
        "and materials (list of objects with name, category [chemical|biological|plastic], "
        "quantity [number], unit, purpose). Use standard reagent names.\n\n"
        f"EXPERIMENT: {text}"
    )
    return granite.generate_json(prompt, max_new_tokens=900)


if __name__ == "__main__":
    for q in ["PARP inhibitor viability assay in BRCA-wildtype TNBC",
              "qPCR of PARP1 expression after olaparib",
              "western blot for cleaved caspase-3"]:
        p = suggest_protocol(q)
        print(f"\n### {q}\n -> {p['title']} ({len(p['materials'])} materials, {p['estimated_duration']})")
