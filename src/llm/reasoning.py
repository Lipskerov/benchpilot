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
