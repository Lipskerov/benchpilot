# BenchPilot V1 — Build Runbook (Bob-first)
### Real, credit-wise build. YOU prompt Bob · Bob writes the code · Bob does every commit/push.

**V1 = thinnest end-to-end demoable slice** (TNBC):
> Build the real TNBC knowledge base (PubMed + ClinicalTrials.gov) → a minimal RAG query UI that returns cited papers + trials for a question. (Gap engine, redundancy verdict, ledger = V2.)

**Legend:** 🧑 = you do it by hand (save coins) · 🤖 = prompt Bob (spends coins) · 💾 = Bob commits/pushes · 🪙 = est. Bobcoins.

---

## Pre-reqs (🧑, once)
- [ ] Bob logged in; `~/.bob/mcp_settings.json` has a valid GitHub token (done — refresh after the revoke).
- [ ] Confirm the GitHub MCP works in Bob: ask Bob *"list my GitHub repos"* — if it answers, pushes will work.
- [ ] Python 3.11 + `pip` available.
- [ ] watsonx keys **optional for V1** — we run with `MOCK_LLM=true`, so the demo never blocks. (Add real Granite in V2.)

---

## Step 0 — 🤖 Repo + planning artifacts  · 🪙~2
**Paste to Bob (Ask/Build mode):**
> "Create a new public GitHub repo `benchpilot` under my account. Initialize it with these files from my local folder `bench-to-decision/`: `PROJECT-MAP.md`, `SPEC.md`, `.bob/mcp.json`, `.gitignore`, `.env.example`. Add a short `README.md` stub (title + one-line pitch + 'Built with IBM Bob'). Commit as 'chore: project scaffolding and specs' and push."

**Bob outputs:** a public repo with your specs committed. 💾 first commit.
🧑 *You verify:* repo is public, `.bob/` is committed (proof of Bob usage), `.env` is NOT committed.

---

## Step 1 — 🤖 ETL: fetch the real TNBC corpus  · 🪙~5
**Paste to Bob (Plan → Build):**
> "Implement `etl/fetch_pubmed.py` and `etl/fetch_trials.py` per SPEC.md Features 1–2, TNBC scope.
> - `fetch_pubmed.py`: use NCBI E-utilities (esearch+efetch) for query `(\"triple negative breast cancer\"[Title/Abstract] OR TNBC[Title/Abstract]) AND hasabstract AND 2019:2026[dp]`, cap 800 records, save `data/snapshot/papers.jsonl` with fields pmid,title,abstract,journal,year,mesh. Respect rate limits (≤3 req/s, ret/batch=200).
> - `fetch_trials.py`: use ClinicalTrials.gov API v2 `query.cond=\"triple negative breast cancer\"`, page through all, save `data/snapshot/trials.jsonl` with nct_id,brief_title,phase,status,conditions,interventions,primary_outcomes,sponsor,start_date,enrollment.
> Add `requirements.txt`. Do NOT call any LLM here. Commit as 'feat(etl): PubMed + ClinicalTrials.gov TNBC fetchers' and push."

**Bob outputs:** two runnable fetchers + requirements. 💾 commit.
🧑 *You run:* `pip install -r requirements.txt && python etl/fetch_pubmed.py && python etl/fetch_trials.py`. Eyeball the JSONL counts. (Fix trivial parse issues yourself — no coins.)

---

## Step 2 — 🤖 Build the DB (normalize + embed, mock-safe)  · 🪙~5
**Paste to Bob:**
> "Implement `etl/build_db.py` per SPEC Feature 3: load `papers.jsonl`+`trials.jsonl` into SQLite `benchpilot.db` (tables: papers, trials). Build a Chroma vector index over paper+trial text. Embeddings go through `src/llm/embed.py`, which must support `MOCK_LLM=true` (deterministic hash-based fake vectors) so it runs with no watsonx key. Add `src/memory/store.py` with `search(query,k)`. Commit as 'feat(db): normalize + vector index with mock-embeddings fallback' and push."

**Bob outputs:** DB builder + memory store, runs offline. 💾 commit.
🧑 *You run:* `MOCK_LLM=true python etl/build_db.py`; then a quick `search("PARP inhibitor")` sanity check.
🧑 *Commit the snapshot:* ask Bob → *"commit `data/snapshot/*.jsonl` and `benchpilot.db` as 'data: TNBC snapshot' and push"* (so the demo is reproducible). 💾

---

## Step 3 — 🤖 Minimal RAG + UI  · 🪙~5
**Paste to Bob:**
> "Implement `src/llm/watsonx_client.py` (Granite via watsonx, with `MOCK_LLM=true` returning a canned cited synthesis) and `src/app/app.py` (Streamlit): one ask box → retrieve top papers+trials via `src/memory/store.search` → show a synthesis with inline citations (PMIDs + NCT IDs) and an evidence panel listing the sources. Per SPEC Feature 8 (Q&A slice only). Commit as 'feat(app): grounded TNBC Q&A with citations (mock-LLM)' and push."

**Bob outputs:** a running Streamlit app. 💾 commit.
🧑 *You run:* `MOCK_LLM=true streamlit run src/app/app.py` → ask a TNBC question → see cited answer. **This is the V1 demo.**

---

## Step 4 — 🤖 README + wrap  · 🪙~2
**Paste to Bob:**
> "Write `README.md`: Problem · Solution · AI approach & architecture (embed the mermaid from PROJECT-MAP §3) · Selected theme: Wildcard – Future of Work · How IBM Bob was used (bullet the commits Bob authored). Add run instructions (`MOCK_LLM=true`). Commit 'docs: README for submission' and push."

🧑 *You:* screenshot Bob building/committing for the video; confirm repo public.

---

## V1 coin total: ~🪙19 of 40  → leaves ~21 for V2 (gap engine, redundancy verdict, ledger, real Granite) + a late `grill-me`.

## Coin-saving rules (repeat)
1. One Bob prompt per step, full context — don't iterate in Bob for small fixes; fix by hand.
2. All **running/testing = you**, not Bob.
3. Renames, CSS, config, `.env` = you.
4. Keep `MOCK_LLM=true` until V2 so you don't spend watsonx calls (or Bob debugging them) during scaffolding.
5. If Bob drifts, correct with ONE precise message citing the SPEC section + file path.

## What stays honest (why this is the winning path)
- Every commit is **Bob-authored** → real `.bob/` artifacts + real commit trail.
- Bobcoins genuinely spent → matches backend telemetry judges can see.
- You still control architecture via the SPEC → fewer wasted coins, better result.
