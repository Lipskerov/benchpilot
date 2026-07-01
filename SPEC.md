# BenchPilot — SPEC.md
### Spec-driven development brief for IBM Bob
> Feed this to Bob one section at a time. Precise specs = fewer re-prompts = fewer Bobcoins.
> Target: MVP defined in PROJECT-MAP.md §2. Stack in §5. Every feature below has **acceptance criteria** — Bob is done when they pass.

---

## Global conventions
- **Language:** Python 3.11+. UI: Streamlit (fast path).
- **LLM:** all model calls go through one thin client `src/llm/watsonx_client.py` wrapping **watsonx.ai + IBM Granite**. Must support a `MOCK_LLM=true` env flag that returns canned JSON (so the UI never blocks on API issues during the demo).
- **All LLM outputs are JSON, schema-validated** (pydantic). Reject/repair non-JSON. Temperature 0.2.
- **Config** via `.env` (see `.env.example`): `WATSONX_API_KEY`, `WATSONX_PROJECT_ID`, `WATSONX_URL`, `GRANITE_MODEL_ID`, `MOCK_LLM`.
- **Storage:** SQLite (`benchpilot.db`) + Chroma for vectors. No auth, single local user.
- **Determinism:** fixed random seed everywhere so demos reproduce.

---

## Feature 1 — Synthetic assay simulator  `data/simulator.py`
**Purpose:** a hidden ground-truth response surface so recommendations visibly improve on camera.
- Function `true_response(factors: dict) -> dict` maps `{annealing_temp_c, primer_nM, cycles}` → `{amplification_efficiency, ct_mean, ct_sd}`.
- Surface: single smooth optimum (e.g., efficiency peaks near temp≈62°C, primer≈250nM) + gaussian noise on readouts.
- Function `run_round(factors, replicates=3, seed=…)` returns a realistic ExperimentRecord (adds controls, replicate SD).
- CLI: `python data/simulator.py --seed 7 --out data/round1.csv`.

**Acceptance:** running 3 rounds toward the optimum yields monotonically-ish improving efficiency; output CSV matches Experiment Record fields.

---

## Feature 2 — Ingestion & normalization  `src/ingest/`
- Accept: results **CSV** (conditions + readouts) and free-text **notes** (string/`.md`).
- Produce a validated **`ExperimentRecord`** (schema in PROJECT-MAP.md §4) via pydantic.
- Use Granite to extract structured hints from notes (e.g., "primer-dimer at 58°C" → `{observation:"primer_dimer", at:{temp:58}}`), but **never block** ingestion if extraction fails.

**Acceptance:** given `round1.csv` + a note string, returns a valid `ExperimentRecord`; bad rows raise clear errors; note extraction returns JSON or `[]`.

---

## Feature 3 — Lab Memory  `src/memory/`
- Store each `ExperimentRecord` (SQLite) and embed a text summary (Granite embeddings → Chroma).
- API: `add_record(rec)`, `get_project(project_id) -> list[rec]`, `search(query, k) -> list[chunk]`.

**Acceptance:** after adding 3 rounds, `get_project` returns 3 ordered records; `search("primer dimer")` returns the relevant round.

---

## Feature 4 — QC & anomaly module  `src/reasoning/qc.py`
- **Rule checks:** NTC (no-template control) should be empty → flag if `ntc_ct` not null; replicate `ct_sd` > threshold → "high variance"; efficiency outside 0.9–1.1 → flag.
- **Granite explanation:** for each flag, produce a one-sentence plain-language cause + suggested fix. JSON: `[{flag, severity, explanation, suggested_fix}]`.

**Acceptance:** a round with NTC contamination and SD=1.2 returns ≥2 flags with explanations; a clean round returns `[]`.

---

## Feature 5 — Reasoning / Decision Engine  `src/reasoning/graph.py` (LangGraph)
Stateful graph over one "decide next" request:
```
ingest_ready → qc → interpret → recommend(call Feature 6) → critique → assemble_output
```
- **interpret:** Granite summarizes trajectory across prior rounds (improving? plateau? which factor drives readout?). JSON `{trend, key_driver, summary}`.
- **critique (the innovation):** pass the optimizer's proposed point + priors to Granite; it must **justify or challenge** it (e.g., "62°C risks dropout on GC-rich amplicons") and may veto with reason. JSON `{verdict: accept|adjust|reject, reason, adjusted_factors?}`.
- Assemble final **`Recommendation`** (schema §4) combining optimizer + critique.

**Acceptance:** given 3 prior rounds, returns a `Recommendation` with proposed_factors, rationale, expected_gain, qc_flags, confidence; MOCK_LLM path returns canned but schema-valid output.

---

## Feature 6 — Active-learning recommender  `src/recommender/`
- Fit a **Gaussian-Process** surrogate on prior (factors → objective) using scikit-optimize (or simple GP).
- Objective = maximize efficiency, penalize ct_sd (`obj = efficiency - 0.5*ct_sd`).
- Return next point via **Expected Improvement** acquisition, within factor bounds.
- Output `{proposed_factors, expected_gain, method:"GP-EI"}`.

**Acceptance:** with ≥3 points, proposes an unseen in-bounds point whose EI > 0; over successive rounds (using the simulator) the objective trends upward.

---

## Feature 7 — Decision Ledger  `src/ledger/`
- Append-only table: recommendation shown → human action (`accept|modify|reject`) + `final_factors` + `reason` + timestamp.
- API: `log_decision(...)`, `history(project_id)`. Feeds back into Lab Memory as a decision note.

**Acceptance:** logging a "modify" persists final_factors + reason; `history` returns chronological entries; entry is searchable in memory.

---

## Feature 8 — Web UI  `src/app/` (Streamlit)
Single page, 4 zones:
1. **Upload** round (CSV + notes) → shows normalized record.
2. **Timeline** of rounds with a small objective-vs-round line chart (the "climb").
3. **Next Best Experiment card:** proposed conditions · expected gain · rationale · QC flags · confidence · buttons **Accept / Modify / Reject** (Modify opens editable factors + reason).
4. **Ask the lab** box: NL question → grounded answer from Lab Memory (RAG via Granite).

**Acceptance:** full loop works in-app — upload → recommendation → accept → run simulated next round → chart updates upward; Q&A returns a cited answer.

---

## Feature 9 — README + Bob-proof artifacts (submission)
- `README.md` with: Problem · Solution · AI approach & architecture (diagram) · Selected theme (**Wildcard – Future of Work**) · **How IBM Bob was used** (+ screenshots).
- Commit `.bob/`, `implementation-plan.md`. Ensure repo + video are **public**.

**Acceptance:** a stranger can clone, `pip install -r requirements.txt`, set `MOCK_LLM=true`, run the app, and reproduce the demo.

---

## Build order for Bob (matches the coin budget in PROJECT-MAP §9)
1. Ask-mode: review this SPEC + propose file scaffold. *(cheap)*
2. Plan-mode: Features 1–3 (data + ingest + memory) in one plan. *(~6 coins)*
3. Implement Feature 5 + LLM client (the core). *(~12 coins — the priority spend)*
4. Implement Features 6 + 7 (recommender + ledger). *(~8 coins)*
5. Implement Feature 8 UI + Q&A. *(~6 coins)*
6. `grill-me` review of plan/code before submission. *(~3 coins)*

> Do Features 1–2 glue, config, `.env`, styling, and all testing **by hand** to conserve coins. Reserve the buffer for one reasoning-engine rework.
