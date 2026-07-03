#!/usr/bin/env python3
"""
Build a TNBC knowledge graph from the papers AND trials, then apply basic ML:
  - Nodes: genes/targets, drugs, TNBC subtypes (from a curated lexicon)
  - Edges: co-mention counts across papers + trials
  - Metrics: PageRank (importance), degree, communities, yearly-trend slope (linear regression)
  - Link prediction: scikit-learn LogisticRegression on graph features
      (common-neighbors, Jaccard, Adamic-Adar, resource-allocation, preferential-attachment)
      -> ranks under-studied but structurally-supported connections worth exploring, with a test AUC
  - Layout: networkx spring_layout (precomputed positions)
Output: data/snapshot/graph.json  (rendered client-side; works in server + static build)
"""
import json
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import networkx as nx
from networkx.algorithms import community as nx_comm
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "benchpilot.db"
OUT = ROOT / "data" / "snapshot" / "graph.json"
rng = np.random.RandomState(7)

# ---- curated TNBC lexicon (canonical -> type + aliases) ----
GENES = {
    "BRCA1": ["brca1"], "BRCA2": ["brca2"], "PARP1": ["parp1", "parp-1", "parp inhibitor", "parp"],
    "TP53": ["tp53", "p53"], "PTEN": ["pten"], "PIK3CA": ["pik3ca"], "AKT": ["akt", "akt1"],
    "PI3K": ["pi3k"], "mTOR": ["mtor"], "EGFR": ["egfr"], "TROP2": ["trop2", "trop-2", "tacstd2"],
    "PD-L1": ["pd-l1", "pdl1", "cd274"], "PD-1": ["pd-1", "pd1", "pdcd1"], "CTLA-4": ["ctla-4", "ctla4"],
    "HER2": ["her2", "erbb2"], "AR": ["androgen receptor", "ar-positive"], "RB1": ["rb1", "retinoblastoma"],
    "MYC": ["c-myc", "myc"], "CCND1": ["ccnd1", "cyclin d1"], "CDK4/6": ["cdk4", "cdk6", "cdk4/6"],
    "ATR": ["atr "], "CHK1": ["chk1", "chek1"], "WEE1": ["wee1"], "ATM": ["atm "], "RAD51": ["rad51"],
    "KRAS": ["kras"], "NOTCH": ["notch", "notch1"], "WNT": ["wnt", "beta-catenin"], "VEGF": ["vegf", "vegfa"],
    "STAT3": ["stat3"], "NF-kB": ["nf-kb", "nfkb", "nf-kappab"], "FOXM1": ["foxm1"], "BCL2": ["bcl2", "bcl-2"],
    "Caspase-3": ["caspase-3", "caspase 3"], "Ki67": ["ki67", "ki-67", "mki67"], "E-cadherin": ["e-cadherin", "cdh1"],
    "Vimentin": ["vimentin", "vim "], "SNAIL": ["snail", "snai1"], "ZEB1": ["zeb1"], "TWIST1": ["twist1", "twist"],
    "HIF-1a": ["hif-1", "hif1a", "hypoxia-inducible"], "TGF-beta": ["tgf-beta", "tgfb"], "Wee": [],
    "gamma-H2AX": ["h2ax", "γh2ax", "gamma-h2ax"], "EMT": ["epithelial-mesenchymal", "emt "],
}
DRUGS = {
    "Olaparib": ["olaparib"], "Talazoparib": ["talazoparib"], "Niraparib": ["niraparib"], "Rucaparib": ["rucaparib"],
    "Veliparib": ["veliparib"], "Cisplatin": ["cisplatin"], "Carboplatin": ["carboplatin"],
    "Paclitaxel": ["paclitaxel"], "Docetaxel": ["docetaxel"], "Doxorubicin": ["doxorubicin"],
    "Gemcitabine": ["gemcitabine"], "Capecitabine": ["capecitabine"], "Eribulin": ["eribulin"],
    "Sacituzumab govitecan": ["sacituzumab", "govitecan"], "Datopotamab": ["datopotamab", "dato-dxd"],
    "Trastuzumab deruxtecan": ["trastuzumab deruxtecan", "t-dxd"], "Pembrolizumab": ["pembrolizumab"],
    "Atezolizumab": ["atezolizumab"], "Durvalumab": ["durvalumab"], "Nivolumab": ["nivolumab"],
    "Ipatasertib": ["ipatasertib"], "Capivasertib": ["capivasertib"], "Alpelisib": ["alpelisib"],
    "Everolimus": ["everolimus"], "Palbociclib": ["palbociclib"], "Ribociclib": ["ribociclib"],
    "Abemaciclib": ["abemaciclib"], "Bevacizumab": ["bevacizumab"], "Cetuximab": ["cetuximab"],
    "Enzalutamide": ["enzalutamide"], "Bicalutamide": ["bicalutamide"], "Ceralasertib": ["ceralasertib"],
    "Adavosertib": ["adavosertib"], "Metformin": ["metformin"],
}
SUBTYPES = {
    "Basal-like": ["basal-like", "basal like"], "LAR subtype": ["luminal androgen", "lar subtype", "lar "],
    "Mesenchymal": ["mesenchymal-like", "mesenchymal stem"], "Immunomodulatory": ["immunomodulatory"],
    "Claudin-low": ["claudin-low"], "HR-deficient": ["homologous recombination defic", "hr-deficient", "hrd"],
    "BRCA-mutant": ["brca-mut", "brca mutant", "germline brca"],
}
LEX = {}
for name, al in GENES.items(): LEX[name] = {"type": "gene", "aliases": [name.lower()] + al}
for name, al in DRUGS.items(): LEX[name] = {"type": "drug", "aliases": [name.lower()] + al}
for name, al in SUBTYPES.items(): LEX[name] = {"type": "subtype", "aliases": [name.lower()] + al}
for name in LEX:
    pat = "|".join(re.escape(a.strip()) for a in LEX[name]["aliases"] if a.strip())
    LEX[name]["pat"] = re.compile(r"(?<![a-z0-9])(" + pat + r")(?![a-z0-9])", re.I)


def entities_in(text):
    t = " " + (text or "").lower() + " "
    return {name for name, m in LEX.items() if m["pat"].search(t)}


def main():
    conn = sqlite3.connect(str(DB)); conn.row_factory = sqlite3.Row
    docs = []  # (text, year)
    for r in conn.execute("SELECT title, abstract, year FROM papers"):
        docs.append((f"{r['title']} {r['abstract']}", r["year"]))
    for r in conn.execute("SELECT brief_title, interventions, conditions, start_date FROM trials"):
        iv = " ".join(x.get("name", "") for x in json.loads(r["interventions"] or "[]"))
        yr = None
        if r["start_date"]:
            m = re.search(r"(20\d\d)", r["start_date"]); yr = int(m.group(1)) if m else None
        docs.append((f"{r['brief_title']} {iv} {r['conditions']}", yr))
    conn.close()

    mentions = Counter()
    edges = Counter()
    yearly = defaultdict(Counter)  # entity -> year -> count
    for text, yr in docs:
        ents = sorted(entities_in(text))
        for e in ents:
            mentions[e] += 1
            if yr: yearly[e][yr] += 1
        for i in range(len(ents)):
            for j in range(i + 1, len(ents)):
                edges[(ents[i], ents[j])] += 1

    # keep entities mentioned enough; edges with weight >= 2
    keep = {e for e, c in mentions.items() if c >= 3}
    G = nx.Graph()
    for e in keep:
        G.add_node(e, type=LEX[e]["type"], mentions=mentions[e])
    for (a, b), w in edges.items():
        if a in keep and b in keep and w >= 2:
            G.add_edge(a, b, weight=w)
    G.remove_nodes_from(list(nx.isolates(G)))

    pr = nx.pagerank(G, weight="weight")
    comms = list(nx_comm.greedy_modularity_communities(G, weight="weight"))
    comm_of = {}
    for ci, c in enumerate(comms):
        for n in c: comm_of[n] = ci

    def slope(e):
        ys = sorted(yearly[e]);
        if len(ys) < 3: return 0.0
        xs = np.array(ys, float); vs = np.array([yearly[e][y] for y in ys], float)
        return float(np.polyfit(xs - xs.mean(), vs, 1)[0])
    trend = {e: slope(e) for e in G.nodes()}

    # layout (unweighted + larger k spreads the dense drug hub for readability)
    pos = nx.spring_layout(G, seed=7, k=0.9, iterations=250)

    # ---- link prediction (basic ML) ----
    nodes = list(G.nodes())
    node_idx = {n: i for i, n in enumerate(nodes)}
    existing = set(map(frozenset, G.edges()))
    non_edges = []
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            if frozenset((nodes[i], nodes[j])) not in existing:
                non_edges.append((nodes[i], nodes[j]))
    rng.shuffle(non_edges)

    def feats(u, v):
        cn = len(list(nx.common_neighbors(G, u, v)))
        jc = next(nx.jaccard_coefficient(G, [(u, v)]))[2]
        aa = next(nx.adamic_adar_index(G, [(u, v)]))[2]
        ra = next(nx.resource_allocation_index(G, [(u, v)]))[2]
        pa = G.degree(u) * G.degree(v)
        return [cn, jc, aa, ra, np.log1p(pa)]

    pos_pairs = [tuple(fs) for fs in existing]
    neg_pairs = non_edges[:len(pos_pairs)]
    X = np.array([feats(*p) for p in pos_pairs] + [feats(*p) for p in neg_pairs])
    y = np.array([1] * len(pos_pairs) + [0] * len(neg_pairs))
    idx = rng.permutation(len(y)); X, y = X[idx], y[idx]
    cut = int(0.75 * len(y))
    clf = LogisticRegression(max_iter=1000).fit(X[:cut], y[:cut])
    auc = float(roc_auc_score(y[cut:], clf.predict_proba(X[cut:])[:, 1])) if len(set(y[cut:])) > 1 else None

    # score candidate non-edges (predicted connections to explore)
    cand = non_edges[:4000]
    scores = clf.predict_proba(np.array([feats(*p) for p in cand]))[:, 1]
    ranked = sorted(zip(cand, scores), key=lambda z: -z[1])
    seen, preds = set(), []
    for (a, b), s in ranked:
        # prefer cross-type, structurally supported, reasonably prominent
        if LEX[a]["type"] == LEX[b]["type"] == "subtype": continue
        cn = len(list(nx.common_neighbors(G, a, b)))
        if cn < 2: continue
        key = frozenset((a, b))
        if key in seen: continue
        seen.add(key)
        preds.append({"a": a, "b": b, "score": round(float(s), 3), "shared": cn,
                      "type_a": LEX[a]["type"], "type_b": LEX[b]["type"]})
        if len(preds) >= 14: break

    emerging = sorted([(e, trend[e]) for e in G.nodes()], key=lambda z: -z[1])[:8]

    out = {
        "nodes": [{"id": n, "type": G.nodes[n]["type"], "mentions": G.nodes[n]["mentions"],
                   "degree": G.degree(n), "pagerank": round(pr[n], 5), "community": comm_of.get(n, 0),
                   "trend": round(trend[n], 3), "x": round(float(pos[n][0]), 4), "y": round(float(pos[n][1]), 4)}
                  for n in nodes],
        "edges": [{"source": a, "target": b, "weight": G[a][b]["weight"]} for a, b in G.edges()],
        "predictions": preds,
        "emerging": [{"id": e, "slope": round(s, 3)} for e, s in emerging],
        "model": {"name": "LogisticRegression (link prediction)", "auc": round(auc, 3) if auc else None,
                  "features": ["common_neighbors", "jaccard", "adamic_adar", "resource_allocation", "preferential_attachment"],
                  "train": cut, "test": len(y) - cut},
        "stats": {"nodes": G.number_of_nodes(), "edges": G.number_of_edges(),
                  "communities": len(comms), "docs": len(docs)},
    }
    OUT.write_text(json.dumps(out))
    print(f"✓ graph.json — {out['stats']['nodes']} nodes, {out['stats']['edges']} edges, "
          f"{out['stats']['communities']} communities · link-pred AUC={out['model']['auc']}")
    print("  top predictions:", ", ".join(f"{p['a']}–{p['b']}({p['score']})" for p in preds[:5]))
    print("  emerging:", ", ".join(f"{e['id']}({e['slope']:+})" for e in out["emerging"][:5]))


if __name__ == "__main__":
    main()
