# BenchPilot V2

**Evidence-grounded AI co-worker for TNBC bench-to-decision workflow**

*Built with IBM Bob*

---

## Problem

Every "AI co-worker" targets the office inbox. **None target the science bench.**

A triple-negative breast cancer (TNBC) research lab drowns in evidence — thousands of PubMed papers and hundreds of clinical trials — yet the highest-value decision, *"what should we study next, and hasn't it already been done?"*, stays slow and tacit. Beyond literature search, researchers must:

1. **Design experiments** based on evidence
2. **Draft detailed protocols** with precise methods
3. **Check reagent inventory** and order missing items

This manual workflow is time-consuming, error-prone, and disconnected. BenchPilot V2 closes the loop.

## Solution

**BenchPilot V2** is a FastAPI web application that guides researchers through the complete bench-to-decision workflow:

1. **Ask a scientific question** → Search 785 PubMed papers + 1,468 clinical trials
2. **Find real targets** → Grounded evidence synthesis with citations (PMIDs, NCT IDs)
3. **Design an experiment** → AI-suggested experimental design based on evidence
4. **Draft a protocol** → Detailed step-by-step protocol with methods and materials
5. **Check inventory** → Reconcile protocol against live reagent inventory, flag what to order

The reasoning layer runs on **IBM Granite (watsonx)** with a grounded offline fallback using BM25 retrieval. Every recommendation is defensible, not guessed.

## AI Approach & Architecture

```mermaid
flowchart TD
    subgraph Sources["Real public data (TNBC)"]
        P[PubMed E-utilities<br/>785 papers, 2019-2026]
        A[ClinicalTrials.gov v2<br/>1,468 trials]
        I[Lab Inventory<br/>Reagents & consumables]
    end
    P --> ETL[ETL & Normalization]
    A --> ETL
    ETL --> DB[(SQLite + BM25 Index)]
    I --> INV[(Inventory Store)]
    
    Q[Scientific Question] --> RET[BM25 Retrieval]
    DB --> RET
    RET --> GRAN[IBM Granite Reasoning<br/>watsonx.ai]
    GRAN --> SYNTH[Evidence Synthesis]
    SYNTH --> EXP[Experiment Design]
    EXP --> PROT[Protocol Generation]
    PROT --> MATCH[Inventory Matcher]
    INV --> MATCH
    MATCH --> ORDER[Order List]
    
    SYNTH --> UI[FastAPI + Web UI]
    EXP --> UI
    PROT --> UI
    ORDER --> UI
```

**Core Components:**

| Module | Technology | Purpose |
|--------|-----------|---------|
| **Data Ingestion** | PubMed E-utilities, ClinicalTrials.gov API v2 | Fetch TNBC papers and trials |
| **Knowledge Base** | SQLite + BM25 (rank_bm25) | Store structured data + fast retrieval |
| **Reasoning** | IBM Granite via watsonx.ai (+ offline fallback) | Evidence synthesis, experiment design, protocol generation |
| **Inventory** | SQLite + fuzzy matching | Track reagents, match protocol requirements |
| **Backend** | FastAPI | REST API endpoints |
| **Frontend** | Vanilla JS + HTML/CSS | Interactive workflow UI |

**Key Innovation:** Unlike generic LLM chatbots, BenchPilot V2:
- Grounds every answer in a real, curated TNBC corpus
- Uses BM25 retrieval (not just embeddings) for precise evidence matching
- Generates actionable protocols with inventory reconciliation
- Provides transparent citations for every claim

## Selected Theme

**Wildcard Track: "Build Intelligent Systems for the Future of Work"**

BenchPilot V2 demonstrates AI as a co-worker for scientific research — a domain where decision support must be evidence-based, transparent, and actionable. By automating the bench-to-decision workflow (literature → design → protocol → inventory), it accelerates the research cycle and helps scientists make better-informed decisions about what to study next.

## Current Features (V2)

✅ **Real TNBC Knowledge Base**
- 785 PubMed papers (2019-2026)
- 1,468 clinical trials from ClinicalTrials.gov
- BM25 retrieval for fast, precise evidence matching

✅ **Complete Workflow**
- Scientific question → Evidence synthesis with citations
- Experiment design suggestions based on evidence
- Detailed protocol generation with methods and materials
- Live reagent inventory with order list

✅ **IBM Granite Integration**
- Reasoning via watsonx.ai (when configured)
- Offline fallback mode for demo (no API keys required)
- Grounded synthesis with mandatory citations

✅ **FastAPI Backend + Web UI**
- REST API endpoints for all workflow steps
- Clean, responsive web interface
- Real-time inventory checking

## How IBM Bob Was Used

IBM Bob was the primary development tool for BenchPilot V2, authoring the majority of the codebase through spec-driven development:

**Bob-authored commits:**
- ✅ `chore: project scaffolding and specs` - Initial repo setup with PROJECT-MAP.md and SPEC.md
- ✅ `feat(etl): PubMed + ClinicalTrials.gov TNBC fetchers` - Data ingestion scripts with rate limiting
- ✅ `feat(data): add TNBC corpus snapshot` - Real dataset (785 papers, 1468 trials)
- ✅ `feat(db): normalize + vector index with mock-embeddings fallback` - Database build
- ✅ `feat(app): grounded TNBC Q&A with citations (mock-LLM)` - Initial Streamlit UI (V1)
- ✅ `feat(inventory): protocols + live-inventory check with order list` - Inventory system
- ✅ `feat: BenchPilot V2 — FastAPI app, grounded BM25 retrieval, Granite reasoning, experiment design + protocol drafting, live reagent inventory with order flagging` - Complete V2 rewrite

**Development approach:**
1. Wrote detailed SPEC.md with acceptance criteria for each feature
2. Used Bob in code mode to implement features one at a time
3. Bob generated production-ready code following the spec
4. Manual testing and refinement between Bob sessions
5. All Bob-generated code committed with descriptive messages

**Bobcoin budget:** ~15 credits spent on high-leverage tasks (ETL, database, reasoning, UI), conserving credits by doing manual testing and configuration.

## Quick Start

### Prerequisites
- Python 3.11+
- pip

### Installation

```bash
# Clone the repository
git clone https://github.com/Lipskerov/benchpilot.git
cd benchpilot

# Install dependencies
pip install -r requirements.txt
```

### Configuration (Optional - for real LLM)

To use IBM Granite via watsonx.ai instead of the offline fallback:

```bash
# Copy environment template
cp .env.example .env

# Edit .env and fill in:
# WATSONX_API_KEY=your_api_key_here
# WATSONX_PROJECT_ID=your_project_id_here
# WATSONX_URL=https://us-south.ml.cloud.ibm.com
# GRANITE_MODEL_ID=ibm/granite-3-8b-instruct
```

### Run the App

```bash
# Start the FastAPI server
python -m uvicorn api.main:app --reload

# Open in browser
# http://127.0.0.1:8000
```

The app will automatically use the offline fallback if no watsonx credentials are configured.

### Rebuild Data (Optional)

If you want to rebuild the database from scratch:

```bash
# Fetch latest data
python etl/fetch_pubmed.py
python etl/fetch_trials.py

# Build database and BM25 index
python etl/build_db.py

# Generate inventory
python etl/gen_inventory.py
```

## Example Workflow

1. **Ask a question:** "What is the state of PARP inhibitors in BRCA-wildtype TNBC?"
2. **Review evidence:** See synthesized answer with citations (PMIDs, NCT IDs)
3. **Design experiment:** Get AI-suggested experimental design
4. **Generate protocol:** Receive detailed step-by-step protocol
5. **Check inventory:** View required reagents and what needs to be ordered

## Project Structure

```
benchpilot/
├── README.md                 # This file
├── PROJECT-MAP.md            # Detailed project plan
├── SPEC.md                   # Technical specification
├── INVENTORY-SPEC.md         # Inventory system spec
├── .bob/                     # Bob configuration (proof of usage)
│   └── mcp.json
├── api/                      # FastAPI backend
│   └── main.py               # REST API endpoints
├── web/                      # Frontend
│   ├── index.html            # Main UI
│   ├── styles.css            # Styling
│   └── app.js                # Client-side logic
├── etl/                      # Data ingestion
│   ├── fetch_pubmed.py       # PubMed fetcher
│   ├── fetch_trials.py       # ClinicalTrials.gov fetcher
│   ├── build_db.py           # Database builder
│   └── gen_inventory.py      # Inventory generator
├── data/
│   └── snapshot/             # TNBC corpus (785 papers, 1468 trials, inventory)
│       ├── papers.jsonl
│       ├── trials.jsonl
│       └── inventory.jsonl
├── src/
│   ├── llm/                  # LLM clients
│   │   ├── granite.py        # Granite client (watsonx)
│   │   └── reasoning.py      # Reasoning logic
│   ├── memory/               # Knowledge base
│   │   └── retrieval.py      # BM25 retrieval
│   ├── protocols/            # Protocol generation
│   │   └── generate.py
│   └── inventory/            # Inventory system
│       ├── store.py          # CRUD operations
│       └── match.py          # Fuzzy matching
├── benchpilot.db             # SQLite database (gitignored)
└── requirements.txt
```

## Technology Stack

- **Language:** Python 3.11
- **Backend:** FastAPI
- **Frontend:** Vanilla JavaScript + HTML/CSS
- **Data Sources:** PubMed E-utilities, ClinicalTrials.gov API v2
- **Database:** SQLite
- **Retrieval:** BM25 (rank_bm25)
- **LLM:** IBM Granite via watsonx.ai (+ offline fallback)
- **Development:** IBM Bob (spec-driven development)

## Roadmap

### Phase 1 (Current - V2)
- ✅ Real TNBC knowledge base (785 papers, 1468 trials)
- ✅ BM25 retrieval for precise evidence matching
- ✅ IBM Granite reasoning (with offline fallback)
- ✅ Complete workflow: question → evidence → design → protocol → inventory
- ✅ FastAPI backend + web UI

### Phase 2 (Next)
- 🔄 Evidence gap scoring engine
- 🔄 Redundancy detection for planned experiments
- 🔄 Ranked next-experiment suggestions
- 🔄 Decision ledger (accept/modify/reject)

### Phase 3 (Future)
- ⏳ Knowledge graph visualization
- ⏳ Multi-user support with authentication
- ⏳ Integration with lab management systems (LIMS)
- ⏳ Real-time collaboration features

## License

MIT License - See LICENSE file for details

## Acknowledgments

- Built for the **IBM AI Builders Challenge** (Wildcard Track)
- Developed with **IBM Bob** as the primary coding assistant
- Data from **PubMed** (NCBI) and **ClinicalTrials.gov**
- Powered by **IBM Granite** via watsonx.ai

---

**Repository:** https://github.com/Lipskerov/benchpilot

**Contact:** Fedor Lipskerov