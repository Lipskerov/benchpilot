#!/usr/bin/env python3
"""
Scientific reasoning over the TNBC corpus:
  - extract_targets:   surface real molecular targets from retrieved evidence
  - synthesize_evidence: grounded, cited answer to a question
  - design_experiment: turn a target into a concrete experiment design

Uses IBM Granite (watsonx) when configured; otherwise a grounded offline path
(counts over real retrieved abstracts/trials + curated TNBC target knowledge).
No fabricated citations — every PMID/NCT comes from the retrieved corpus.
"""

import re
from typing import Dict, List

from src.llm import granite

# ---- curated TNBC target knowledge (name -> type + alias tokens) ---------------------
TARGETS = {
    "PARP/BRCA (HR deficiency)": {
        "type": "DNA-repair / synthetic lethality",
        "aliases": ["parp", "parp1", "brca", "brca1", "brca2", "olaparib", "talazoparib",
                    "niraparib", "rucaparib", "veliparib", "homologous recombination", "hrd", "brcaness"],
        "assay": "parp",
    },
    "TROP2 (ADC target)": {
        "type": "Antibody-drug conjugate target",
        "aliases": ["trop2", "trop-2", "sacituzumab", "govitecan", "datopotamab", "dato-dxd", "adc"],
        "assay": "viability",
    },
    "PD-L1 / PD-1 (immune checkpoint)": {
        "type": "Immune checkpoint",
        "aliases": ["pd-l1", "pdl1", "pd-1", "pd1", "pembrolizumab", "atezolizumab",
                    "durvalumab", "nivolumab", "checkpoint", "immunotherapy"],
        "assay": "apoptosis",
    },
    "PI3K / AKT / PTEN": {
        "type": "PI3K signaling",
        "aliases": ["pi3k", "akt", "pten", "pik3ca", "ipatasertib", "capivasertib", "alpelisib"],
        "assay": "western",
    },
    "ATR / CHK1 / WEE1 (DDR)": {
        "type": "DNA-damage response / cell cycle",
        "aliases": ["atr", "chk1", "wee1", "ceralasertib", "adavosertib", "replication stress"],
        "assay": "if",
    },
    "AR (androgen receptor)": {
        "type": "Nuclear receptor (LAR subtype)",
        "aliases": ["androgen receptor", "ar-positive", "enzalutamide", "bicalutamide", "lar subtype"],
        "assay": "qpcr",
    },
    "EGFR": {
        "type": "Receptor tyrosine kinase",
        "aliases": ["egfr", "cetuximab", "erlotinib", "gefitinib"],
        "assay": "western",
    },
    "CDK4/6": {
        "type": "Cell-cycle kinase",
        "aliases": ["cdk4", "cdk6", "cdk4/6", "palbociclib", "ribociclib", "abemaciclib"],
        "assay": "viability",
    },
    "VEGF / angiogenesis": {
        "type": "Angiogenesis",
        "aliases": ["vegf", "angiogenesis", "bevacizumab"],
        "assay": "viability",
    },
}


def _text_of(doc: Dict) -> str:
    if doc.get("kind") == "trial" or "interventions" in doc:
        return f"{doc.get('title','')} {doc.get('interventions','')}".lower()
    return f"{doc.get('title','')} {doc.get('abstract','')}".lower()


def extract_targets(question: str, papers: List[Dict], trials: List[Dict], top: int = 6) -> List[Dict]:
    """Rank molecular targets by real evidence in the retrieved papers + trials."""
    results = []
    for name, meta in TARGETS.items():
        pat = re.compile(r"\b(" + "|".join(re.escape(a) for a in meta["aliases"]) + r")\b")
        p_hits = [p for p in papers if pat.search(_text_of(p))]
        t_hits = [t for t in trials if pat.search(_text_of(t))]
        n = len(p_hits) + len(t_hits)
        if n == 0:
            continue
        # also weight if the target appears in the question itself
        q_hit = bool(pat.search((question or "").lower()))
        results.append({
            "target": name,
            "type": meta["type"],
            "assay": meta["assay"],
            "paper_count": len(p_hits),
            "trial_count": len(t_hits),
            "score": n + (5 if q_hit else 0),
            "example_pmids": [p["id"] for p in p_hits[:3]],
            "example_ncts": [t["id"] for t in t_hits[:3]],
        })
    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:top]


def synthesize_evidence(question: str, papers: List[Dict], trials: List[Dict]) -> Dict:
    """Grounded, cited synthesis. Granite when available; extractive fallback otherwise."""
    sources = ([{"type": "paper", "id": p["id"], "title": p.get("title", "")} for p in papers[:5]] +
               [{"type": "trial", "id": t["id"], "title": t.get("title", "")} for t in trials[:5]])

    if granite.is_configured():
        try:
            ev = "\n".join(
                [f"PMID {p['id']}: {p.get('title','')} — {str(p.get('abstract',''))[:400]}" for p in papers[:5]] +
                [f"{t['id']} ({t.get('phase','')}, {t.get('status','')}): {t.get('title','')}" for t in trials[:5]]
            )
            prompt = (
                "You are a molecular biologist. Using ONLY the evidence below, write a concise "
                "(4-6 sentence) grounded synthesis answering the question. Cite sources inline as "
                "(PMID xx…) or (NCTxx…). Do not invent citations.\n\n"
                f"QUESTION: {question}\n\nEVIDENCE:\n{ev}\n\nSYNTHESIS:"
            )
            text = granite.generate(prompt, max_new_tokens=400, temperature=0.2)
            if text:
                return {"synthesis": text, "sources": sources, "engine": "granite"}
        except Exception:
            pass

    # grounded extractive fallback (real titles + real PMIDs/NCTs)
    parts = []
    if papers:
        parts.append(f"The retrieved literature centers on {papers[0].get('title','').rstrip('.')} "
                     f"(PMID {papers[0]['id']})")
        if len(papers) > 1:
            parts.append(f"and related work such as {papers[1].get('title','').rstrip('.')} (PMID {papers[1]['id']})")
    if trials:
        phases = sorted({t.get("phase", "") for t in trials if t.get("phase")})
        parts.append(f". In the clinic, {len(trials)} matching trials (e.g., {trials[0]['id']}, "
                     f"{trials[0].get('phase','')}) are evaluating related interventions"
                     f"{' across ' + ', '.join(phases) if phases else ''}")
    synthesis = " ".join(parts).replace(" .", ".") + "." if parts else \
        "No strongly matching evidence was retrieved for this question."
    return {"synthesis": synthesis, "sources": sources, "engine": "offline"}


def design_experiment(target: str, question: str = "", papers: List[Dict] = None) -> Dict:
    """Design an experiment for a target. Granite when available; template fallback."""
    meta = TARGETS.get(target, {})
    assay = meta.get("assay", "viability")

    if granite.is_configured():
        try:
            prompt = (
                "You are a TNBC lab scientist. Design a concise experiment to interrogate the target "
                f"'{target}' ({meta.get('type','')}) in triple-negative breast cancer. "
                "Return JSON with keys: hypothesis, rationale, model_systems (list of TNBC cell lines), "
                "approach, readouts (list), controls (list), assay_type (one of: viability, qpcr, western, "
                "apoptosis, if).\n"
                f"Context question: {question}"
            )
            j = granite.generate_json(prompt, max_new_tokens=700)
            if j and "hypothesis" in j:
                j["engine"] = "granite"
                j.setdefault("assay_type", assay)
                return j
        except Exception:
            pass

    return _template_experiment(target, meta, assay)


def _template_experiment(target: str, meta: Dict, assay: str) -> Dict:
    lines = {
        "PARP/BRCA (HR deficiency)": dict(
            hypothesis="PARP inhibition is synthetically lethal in HR-deficient TNBC cells and enhanced by DNA-damaging agents.",
            model_systems=["HCC1937 (BRCA1-mutant)", "MDA-MB-231 (BRCA-wildtype)", "MCF-10A (control)"],
            approach="Dose-response of a PARP inhibitor +/- platinum; measure viability and DNA-damage foci.",
            readouts=["Cell viability / IC50", "γH2AX foci", "Cleaved PARP / caspase-3"],
            controls=["Vehicle (DMSO)", "BRCA-wildtype line", "Untreated"]),
        "TROP2 (ADC target)": dict(
            hypothesis="TROP2-directed ADC payload delivery reduces TNBC viability proportional to TROP2 expression.",
            model_systems=["MDA-MB-468 (TROP2-high)", "MDA-MB-231", "MCF-10A (control)"],
            approach="Quantify TROP2 by western/flow, then ADC dose-response viability across lines.",
            readouts=["TROP2 expression", "Cell viability / IC50", "Apoptosis"],
            controls=["Isotype ADC", "TROP2-low line", "Vehicle"]),
        "PD-L1 / PD-1 (immune checkpoint)": dict(
            hypothesis="PD-L1 expression in TNBC modulates T-cell-mediated cytotoxicity under checkpoint blockade.",
            model_systems=["MDA-MB-231", "MDA-MB-468", "PBMC co-culture"],
            approach="Co-culture TNBC + activated PBMCs +/- anti-PD-L1; measure tumor-cell apoptosis.",
            readouts=["PD-L1 expression", "Apoptosis (Annexin V)", "IFN-γ release"],
            controls=["Isotype antibody", "Tumor-only", "PBMC-only"]),
    }
    base = lines.get(target, dict(
        hypothesis=f"Modulating {target} alters TNBC cell survival/phenotype.",
        model_systems=["MDA-MB-231", "MDA-MB-468", "MCF-10A (control)"],
        approach=f"Perturb {target} (inhibitor/knockdown) and measure phenotypic response vs controls.",
        readouts=["Cell viability", "Target pathway markers (western)", "Apoptosis"],
        controls=["Vehicle / scramble", "Normal epithelial line", "Untreated"]))
    return {
        "target": target,
        "rationale": f"{meta.get('type','Target')} is implicated in TNBC based on the retrieved evidence.",
        "assay_type": assay,
        "engine": "offline",
        **base,
    }


if __name__ == "__main__":
    from src.memory.retrieval import get_index
    idx = get_index()
    q = "PARP inhibitor combination strategies in BRCA-wildtype TNBC"
    papers = idx.search(q, k=25, kind="paper")
    trials = idx.search(q, k=25, kind="trial")
    print("TARGETS:")
    for t in extract_targets(q, papers, trials):
        print(f"  {t['target']:34} papers={t['paper_count']} trials={t['trial_count']} score={t['score']}")
    print("\nSYNTHESIS:", synthesize_evidence(q, papers, trials)["synthesis"][:300])
    print("\nEXPERIMENT:", design_experiment("PARP/BRCA (HR deficiency)")["hypothesis"])


# ============ V4: richer hypotheses + experiment plan (work packages) ============
TARGET_DETAIL = {
    "PARP/BRCA (HR deficiency)": {
        "drug": "Olaparib", "combo": "Cisplatin", "marker": "γH2AX foci", "marker_ab": "Anti-gamma-H2AX",
        "cells": ["HCC1937 (BRCA1-mutant)", "MDA-MB-231 (BRCA-wt)", "MCF-10A (normal)"],
        "assay": "viability", "mechanism": "PARP trapping at DNA lesions and replication-fork collapse"},
    "TROP2 (ADC target)": {
        "drug": "Sacituzumab govitecan", "combo": None, "marker": "TROP2 surface expression", "marker_ab": "Anti-PARP1 antibody",
        "cells": ["MDA-MB-468 (TROP2-high)", "MDA-MB-231", "MCF-10A (normal)"],
        "assay": "viability", "mechanism": "TROP2-directed payload delivery and topoisomerase-I inhibition"},
    "PD-L1 / PD-1 (immune checkpoint)": {
        "drug": "Anti-PD-L1 antibody", "combo": "Paclitaxel", "marker": "PD-L1 expression", "marker_ab": "Anti-PD-L1 antibody",
        "cells": ["MDA-MB-231", "MDA-MB-468", "MCF-10A (normal)"],
        "assay": "apoptosis", "mechanism": "relief of PD-1/PD-L1-mediated T-cell suppression"},
    "ATR / CHK1 / WEE1 (DDR)": {
        "drug": "Olaparib", "combo": "Cisplatin", "marker": "γH2AX / replication stress", "marker_ab": "Anti-gamma-H2AX",
        "cells": ["MDA-MB-231", "MDA-MB-468", "MCF-10A (normal)"],
        "assay": "if", "mechanism": "abrogation of the S/G2 checkpoint under replication stress"},
}
_GENERIC_DETAIL = {"drug": "a targeted inhibitor", "combo": None, "marker": "pathway markers",
                   "marker_ab": "Anti-GAPDH (loading control)",
                   "cells": ["MDA-MB-231", "MDA-MB-468", "MCF-10A (normal)"],
                   "assay": "viability", "mechanism": "modulation of the target pathway"}

_REAGENTS = {
    "viability": ["RPMI-1640 medium", "Fetal Bovine Serum (FBS)", "96-well plate, clear flat", "MTT reagent", "DMSO", "Filter tips 200 uL"],
    "western": ["Pierce BCA Protein Assay Kit", "Acrylamide/Bis 30%", "Goat anti-Rabbit HRP", "SuperSignal West Pico ECL", "Anti-GAPDH (loading control)"],
    "if": ["Paraformaldehyde 16%", "Triton X-100", "DAPI", "24-well plate, TC-treated", "Bovine Serum Albumin (BSA)"],
    "apoptosis": ["Annexin V-FITC Apoptosis Kit", "Propidium Iodide", "6-well plate, TC-treated"],
    "qpcr": ["RNeasy Mini Kit", "High-Capacity cDNA RT Kit", "PowerUp SYBR Green Master Mix", "96-well qPCR plate"],
    "analysis": [],
}


def _ev_note(papers, trials):
    p = f"PMID {papers[0]['id']}" if papers else "the literature"
    return (f"Grounded in {p} and {len(papers)} related papers; "
            f"{len(trials)} matching trials indicate clinical momentum, motivating mechanistic follow-up.")


def generate_hypotheses(target, question="", papers=None, trials=None):

# ============ FUTURE: IBM Bob API Integration ============
# TODO: Replace offline hypothesis generation with IBM Bob API
# Placeholder for Bob API call:
#   - POST to Bob API endpoint with target, question, evidence
#   - Bob generates 3 distinct, testable hypotheses grounded in evidence
#   - Returns structured JSON with statement, mechanism, prediction, etc.
# Example:
#   response = bob_api.generate_hypotheses(target=target, question=question, evidence=papers+trials)
#   return response.hypotheses
# =========================================================


    papers, trials = papers or [], trials or []
    if granite.is_configured():
        try:
            ev = "\n".join([f"PMID {p['id']}: {p.get('title','')}" for p in papers[:6]] +
                           [f"{t['id']} ({t.get('phase','')}): {t.get('title','')}" for t in trials[:6]])
            prompt = (
                f"You are a TNBC PI. Propose 3 DISTINCT, specific, testable hypotheses about '{target}' "
                f"for the question: {question}. Ground them in the evidence. Return a JSON array; each item has: "
                "id (H1..), statement (directional, mechanistic 'if/then/because'), mechanism, prediction "
                "(quantitative expected result), falsification (result that would refute it), novelty, "
                "confidence (low|medium|high), key_readouts (list), model_systems (list of TNBC lines).\n\n"
                f"EVIDENCE:\n{ev}")
            j = granite.generate_json(prompt, max_new_tokens=1100)
            if isinstance(j, list) and j and "statement" in j[0]:
                for i, h in enumerate(j, 1):
                    h.setdefault("id", f"H{i}"); h["engine"] = "granite"
                return j[:3]
        except Exception:
            pass
    return _hyp_templates(target, question, papers, trials)


def _pdl1_hypotheses(note, cells):
    """Judge-friendly, plain-language hypotheses for the immunotherapy demo."""
    return [{
        "id": "H1", "engine": "offline", "confidence": "medium",
        "plain": "Chemo + immunotherapy together should help more patients respond than chemo alone.",
        "statement": "Adding immunotherapy (a PD-L1 checkpoint blocker) to standard chemotherapy improves "
                     "treatment response in triple-negative breast cancer by helping the immune system attack "
                     "tumor cells that chemotherapy has exposed.",
        "mechanism": "Chemotherapy stresses tumor cells and exposes them to the immune system; blocking the PD-L1 "
                     "'brake' then lets immune cells recognise and kill the cancer.",
        "prediction": "The chemo + immunotherapy combination kills notably more tumor cells (≥30% greater response) "
                      "than either treatment alone, and the benefit is largest in PD-L1-high tumors.",
        "rationale": note,
        "falsification": "If the combination works no better than chemotherapy alone, the hypothesis is wrong.",
        "novelty": "Which patients benefit most — and how PD-L1 level predicts it — is still unclear.",
        "key_readouts": ["Tumor-cell killing", "PD-L1 level", "Immune activation"], "model_systems": cells,
    }, {
        "id": "H2", "engine": "offline", "confidence": "medium",
        "plain": "Tumors with more of the PD-L1 'brake' should respond better to immunotherapy.",
        "statement": "PD-L1 level on tumor cells predicts which triple-negative breast cancers respond to immunotherapy, "
                     "and can be used to select patients most likely to benefit.",
        "mechanism": "Higher PD-L1 means the tumor is relying more on the immune 'brake', so releasing it helps more.",
        "prediction": "PD-L1-high tumor models show a clearly stronger response to the PD-L1 blocker (correlation |r| ≥ 0.6).",
        "rationale": note,
        "falsification": "If response is unrelated to PD-L1 level, PD-L1 is not a useful selection marker.",
        "novelty": "A simple, measurable marker to pick the right patients would change practice.",
        "key_readouts": ["PD-L1 level", "Tumor-cell killing"], "model_systems": cells,
    }, {
        "id": "H3", "engine": "offline", "confidence": "low",
        "plain": "Immunotherapy on its own may only help a subset of tumors.",
        "statement": "Immunotherapy alone (PD-L1 blockade without chemotherapy) reduces tumor-cell survival only in a "
                     "subset of triple-negative breast cancers.",
        "mechanism": "Without chemotherapy to expose the tumor, the immune system may not recognise most tumors.",
        "prediction": "PD-L1 blocker alone reduces survival in ≤1 of 3 models, fewer than the combination.",
        "rationale": note,
        "falsification": "Broad single-agent activity across all models would refute the 'subset-only' claim.",
        "novelty": "Clarifies when immunotherapy needs a chemotherapy partner.",
        "key_readouts": ["Tumor-cell killing"], "model_systems": cells,
    }]


def _hyp_templates(target, question, papers, trials):
    det = TARGET_DETAIL.get(target, _GENERIC_DETAIL)
    drug, combo, cells, mech = det["drug"], det["combo"], det["cells"], det["mechanism"]
    note = _ev_note(papers, trials)
    if target.startswith("PD-L1"):
        return _pdl1_hypotheses(note, cells)
    H = [{
        "id": "H1", "engine": "offline",
        "statement": f"Pharmacological inhibition of {target} with {drug} reduces TNBC cell viability in a "
                     f"dose-dependent manner, with greatest sensitivity in {cells[0]}.",
        "mechanism": f"{drug} acts through {mech}.",
        "prediction": f"{drug} lowers viability ≥30% at clinically relevant doses in sensitive lines, "
                      f"with a ≥3-fold IC50 shift versus {cells[-1]}.",
        "rationale": note,
        "falsification": "A flat dose–response (no IC50 reached, <10% viability change) would refute it.",
        "novelty": "Direct, quantitative sensitivity comparison across defined TNBC backgrounds is under-reported.",
        "confidence": "medium", "key_readouts": ["Cell viability / IC50", "Apoptosis"], "model_systems": cells,
    }, {
        "id": "H2", "engine": "offline",
        "statement": (f"Combining {drug} with {combo} produces synthetic-lethal synergy in TNBC beyond either agent alone."
                      if combo else
                      f"Acquired resistance to {drug} in TNBC is driven by adaptive rewiring of the {target} pathway."),
        "mechanism": (f"{combo} increases the DNA-damage burden that {drug} converts into lethal lesions."
                      if combo else f"Compensatory signaling restores survival despite {target} inhibition."),
        "prediction": ("Combination index <0.7 (Chou–Talalay) with ≥2-fold IC50 reduction versus monotherapy."
                       if combo else "Resistant sub-lines show ≥2-fold higher IC50 and altered pathway-marker levels."),
        "rationale": note,
        "falsification": ("An additive/antagonistic index (CI ≥1) would refute synergy."
                          if combo else "No IC50 shift in derived sub-lines would refute the resistance model."),
        "novelty": "Mechanistic dissection in the BRCA-wildtype / HR-proficient setting remains a gap.",
        "confidence": "medium", "key_readouts": ["Combination index", "Cell viability", det["marker"]], "model_systems": cells[:2],
    }, {
        "id": "H3", "engine": "offline",
        "statement": f"{det['marker']} is a predictive biomarker of {drug} response and stratifies TNBC lines by sensitivity.",
        "mechanism": f"Baseline {det['marker']} reflects dependence on the {target} axis.",
        "prediction": f"Baseline {det['marker']} correlates with {drug} IC50 across lines (|r| ≥ 0.6).",
        "rationale": note,
        "falsification": "No correlation between marker level and IC50 would refute the biomarker claim.",
        "novelty": "Links a measurable baseline marker to a functional drug-response readout.",
        "confidence": "low", "key_readouts": [det["marker"], "IC50"], "model_systems": cells,
    }]
    H[0]["plain"] = f"In plain terms: blocking {target.split(' ')[0]} with {drug} should slow tumor growth."
    H[1]["plain"] = ("In plain terms: two drugs together may work better than one." if combo
                     else "In plain terms: tumors may adapt and resist the drug over time.")
    H[2]["plain"] = f"In plain terms: measuring {det['marker']} up front may predict who responds."
    return H


def _wp(i, title, aim, stage, assay, cells, readouts, reagents, dur, deps, design=None):
    w = {"id": f"WP{i}", "title": title, "aim": aim, "stage": stage, "assay_type": assay,
         "model_systems": cells, "readouts": readouts, "reagents": reagents,
         "duration_weeks": dur, "depends_on": deps}
    if design:
        w["design"] = design
    return w


def _design(cells, groups, controls, readout, reps=3):
    return {"cell_lines": cells, "groups": groups, "replicates": reps,
            "controls": controls, "readout": readout}


def _schedule(wps):
    by = {w["id"]: w for w in wps}
    for _ in range(len(wps) + 1):
        for w in wps:
            start = 0
            for d in (w.get("depends_on") or []):
                if d in by and "end_week" in by[d]:
                    start = max(start, by[d]["end_week"])
            w["start_week"] = start
            w["end_week"] = start + max(1, int(w.get("duration_weeks", 2)))
    total = max((w["end_week"] for w in wps), default=0)
    return wps, total


def generate_plan(hypothesis, target, question=""):
    stmt = (hypothesis.get("statement", "") if isinstance(hypothesis, dict) else str(hypothesis)).lower()
    det = TARGET_DETAIL.get(target, _GENERIC_DETAIL)
    drug, combo, cells, ab, assay = det["drug"], det["combo"], det["cells"], det["marker_ab"], det["assay"]

    if granite.is_configured():
        try:
            prompt = (
                f"You are a TNBC PI planning experiments to test this hypothesis: "
                f"{hypothesis.get('statement') if isinstance(hypothesis, dict) else hypothesis}\n"
                f"Target: {target}. Return JSON {{'work_packages': [...]}} where each WP has: id (WP1..), title, aim, "
                "stage (experiment|analysis), assay_type (viability|western|if|apoptosis|qpcr|analysis), "
                "model_systems (list), readouts (list), reagents (list of reagent names), duration_weeks (int), "
                "depends_on (list of WP ids). Order them so some run in parallel (shared dependencies) and some sequentially. "
                "Simple/descriptive hypotheses may need only 1-2 WPs.")
            j = granite.generate_json(prompt, max_new_tokens=1200)
            wps = j.get("work_packages") if isinstance(j, dict) else (j if isinstance(j, list) else None)
            if wps and "title" in wps[0]:
                for i, w in enumerate(wps, 1):
                    w.setdefault("id", f"WP{i}")
                wps, total = _schedule(wps)
                return {"work_packages": wps, "total_weeks": total, "engine": "granite"}
        except Exception:
            pass

    # descriptive/expression-only hypothesis -> single experiment
    descriptive = ("express" in stmt or "biomarker" in stmt or "predict" in stmt) and \
        not any(k in stmt for k in ["inhibit", "reduce", "synerg", "resist", "lethal"])
    if descriptive:
        wps = [
            _wp(1, f"Characterize {det['marker']} across TNBC lines",
                f"Measure baseline {det['marker']} and correlate with {drug} response.",
                "experiment", "western", cells, [det["marker"], "IC50"], _REAGENTS["western"] + [ab], 3, []),
            _wp(2, "Analysis & correlation", "Correlate marker with response; evaluate the hypothesis.",
                "analysis", "analysis", [], ["Correlation (r)", "Figures"], [], 1, ["WP1"]),
        ]
    else:
        norm = cells[-1]
        dose_groups = ["Vehicle (DMSO)", f"{drug} low", f"{drug} mid", f"{drug} high"]
        wps = [
            _wp(1, f"Western blot — baseline {det['marker'].split()[0]} / target expression",
                f"Quantify {target} / marker protein levels across TNBC lines by Western blot to stratify models.",
                "experiment", "western", cells, ["Target/marker band intensity", "GAPDH loading control"],
                _REAGENTS["western"] + [ab], 2, [],
                _design(cells, ["Baseline (untreated)"], ["GAPDH loading control", f"{norm} normal line"],
                        "Band intensity normalised to GAPDH")),
            _wp(2, f"{drug} dose-response ({assay})",
                f"Primary test: establish {drug} sensitivity / IC50 across lines with a dose series.",
                "experiment", assay, cells, ["Cell viability / IC50"], _REAGENTS[assay] + [drug], 3, ["WP1"],
                _design(cells, dose_groups, ["Vehicle (DMSO)", f"{norm} normal line", "Untreated"],
                        "IC50 per line (5-point dose series)")),
            _wp(3, f"IF microscopy — {det['marker']} localisation",
                f"Confirm on-pathway effect by immunofluorescence ({det['marker']}, green) vs DAPI (blue).",
                "experiment", "if", cells[:2], [det["marker"], "Apoptosis"], _REAGENTS["if"] + [ab], 3, ["WP1"],
                _design(cells[:2], ["Vehicle", f"{drug}-treated"],
                        ["Secondary-antibody only (no primary)", "DAPI only"],
                        "Marker localisation per nucleus")),
        ]
        if combo:
            wps.append(_wp(4, f"{drug} + {combo} combination",
                       f"Test whether {combo} potentiates {drug} (synergy / combination index).",
                       "experiment", "viability", cells[:2], ["Combination index", "Viability"],
                       _REAGENTS["viability"] + [drug, combo], 3, ["WP2"],
                       _design(cells[:2], ["Vehicle (DMSO)", drug, combo, f"{drug} + {combo}"],
                               ["Vehicle (DMSO)", "Single agents"], "Combination index (Chou–Talalay)")))
        final_deps = ["WP2", "WP3"] + (["WP4"] if combo else [])
        wps.append(_wp(len(wps) + 1, "Analysis & synthesis",
                   "Integrate results, run statistics, and evaluate the hypothesis.",
                   "analysis", "analysis", [], ["Statistics", "Figures", "Go/no-go"], [], 1, final_deps))

    wps, total = _schedule(wps)
    return {"work_packages": wps, "total_weeks": total, "engine": "offline"}
