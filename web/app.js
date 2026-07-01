// BenchPilot frontend — end-to-end TNBC bench-to-decision workflow.
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const api = (p, o) => fetch(p, o).then(r => r.json());
const esc = s => (s ?? "").toString().replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

const state = { question: "", target: null, experiment: "", inventory: [], cat: "all" };

const EXAMPLES = [
  "PARP inhibitor combination strategies in BRCA-wildtype TNBC",
  "TROP2 antibody-drug conjugates in metastatic TNBC",
  "Immune checkpoint blockade and PD-L1 in TNBC",
  "ATR inhibition to exploit replication stress in TNBC",
];

// ---------- navigation ----------
function show(view) {
  $$(".view").forEach(v => v.classList.remove("active"));
  $("#view-" + view).classList.add("active");
  $$(".navitem").forEach(n => n.classList.toggle("active", n.dataset.view === view));
  window.scrollTo(0, 0);
}
$$(".navitem").forEach(n => n.onclick = () => show(n.dataset.view));
document.addEventListener("click", e => {
  const g = e.target.closest("[data-goto]");
  if (g) { e.preventDefault(); show(g.dataset.goto); }
});

// ---------- boot ----------
(async function init() {
  const s = await api("/api/stats");
  $("#kbStats").textContent = `${s.papers} papers · ${s.trials} trials · ${s.inventory.total} reagents`;
  const eng = $("#engineBadge");
  eng.textContent = s.engine === "granite" ? "IBM Granite" : "Offline engine";
  eng.classList.toggle("offline", s.engine !== "granite");
  $("#examples").innerHTML = EXAMPLES.map(e => `<span class="ex">${esc(e)}</span>`).join("");
  $$(".ex").forEach(x => x.onclick = () => { $("#q").value = x.textContent; ask(); });
  loadInventory();
})();

// ---------- 01 discover ----------
$("#askBtn").onclick = ask;
$("#q").addEventListener("keydown", e => { if (e.key === "Enter") ask(); });

async function ask() {
  const q = $("#q").value.trim();
  if (!q) return;
  state.question = q;
  const box = $("#discoverResults");
  box.innerHTML = `<div class="card"><span class="spinner"></span> Searching corpus and extracting targets…</div>`;
  const r = await api("/api/ask", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question: q, k: 6 }) });
  box.innerHTML = renderDiscover(r);
  $$("#discoverResults [data-target]").forEach(b => b.onclick = () => goDesign(b.dataset.target, b.dataset.assay));
}

function renderDiscover(r) {
  const engine = r.engine === "granite" ? "IBM Granite" : "grounded";
  let h = `<div class="card"><h3>Evidence synthesis · ${engine}</h3><div class="synthesis">${esc(r.synthesis)}</div></div>`;

  h += `<div class="section-label">Targets found in the evidence</div>`;
  if (r.targets.length) {
    h += `<div class="targets">` + r.targets.map(t => `
      <div class="target">
        <div class="tname">${esc(t.target)}</div>
        <div class="ttype">${esc(t.type)}</div>
        <div class="counts"><span><b>${t.paper_count}</b> papers</span><span><b>${t.trial_count}</b> trials</span></div>
        <button data-target="${esc(t.target)}" data-assay="${esc(t.assay)}">Design experiment →</button>
      </div>`).join("") + `</div>`;
  } else { h += `<div class="empty">No curated targets matched — try a more specific query.</div>`; }

  h += `<div class="section-label">Supporting evidence</div><div class="evidence">
    <div class="evcol"><h4>Papers</h4>${r.papers.map(p => `
      <div class="ev"><div class="evtitle">${esc(p.title)}</div>
      <div class="evmeta"><a href="https://pubmed.ncbi.nlm.nih.gov/${esc(p.id)}/" target="_blank">PMID ${esc(p.id)}</a>
      <span>${esc(p.year || "")}</span><span class="pill">score ${p.score}</span></div></div>`).join("")}</div>
    <div class="evcol"><h4>Clinical trials</h4>${r.trials.map(t => `
      <div class="ev"><div class="evtitle">${esc(t.title)}</div>
      <div class="evmeta"><a href="https://clinicaltrials.gov/study/${esc(t.id)}" target="_blank">${esc(t.id)}</a>
      <span class="pill">${esc(t.phase || "—")}</span><span>${esc(t.status || "")}</span></div></div>`).join("")}</div>
  </div>`;
  return h;
}

// ---------- 02 design ----------
async function goDesign(target, assay) {
  state.target = target;
  show("design");
  const body = $("#designBody");
  body.className = "";
  body.innerHTML = `<div class="card"><span class="spinner"></span> Designing experiment for <b>${esc(target)}</b>…</div>`;
  const d = await api("/api/design", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ target, question: state.question }) });
  body.innerHTML = renderDesign(target, d);
  $("#toProtocol").onclick = () => {
    state.experiment = `${d.assay_type || assay} assay for ${target} in TNBC — ${d.hypothesis}`;
    show("protocol");
    $("#protoInput").value = state.experiment;
    runProtocol();
  };
}

function renderDesign(target, d) {
  const eng = d.engine === "granite" ? "IBM Granite" : "template";
  const list = a => (a && a.length) ? `<ul class="clean">${a.map(x => `<li>${esc(x)}</li>`).join("")}</ul>` : "—";
  const chips = a => (a && a.length) ? `<div class="chips">${a.map(x => `<span class="chip">${esc(x)}</span>`).join("")}</div>` : "—";
  return `
    <div class="card">
      <h3>Target · ${eng}</h3>
      <div style="font-size:16px;font-weight:600;margin-bottom:4px">${esc(target)}</div>
      <div class="synthesis">${esc(d.hypothesis || "")}</div>
    </div>
    <div class="card">
      <div class="kv">
        <div class="k">Rationale</div><div>${esc(d.rationale || "")}</div>
        <div class="k">Assay type</div><div><span class="chip n">${esc(d.assay_type || "")}</span></div>
        <div class="k">Model systems</div><div>${chips(d.model_systems)}</div>
        <div class="k">Approach</div><div>${esc(d.approach || "")}</div>
        <div class="k">Readouts</div><div>${list(d.readouts)}</div>
        <div class="k">Controls</div><div>${list(d.controls)}</div>
      </div>
    </div>
    <button class="primary" id="toProtocol">Draft protocol &amp; check stock →</button>`;
}

// ---------- 03 protocol ----------
$("#protoBtn").onclick = runProtocol;
$("#protoInput").addEventListener("keydown", e => { if (e.key === "Enter") runProtocol(); });

async function runProtocol() {
  const exp = $("#protoInput").value.trim();
  if (!exp) return;
  const body = $("#protocolBody");
  body.innerHTML = `<div class="card"><span class="spinner"></span> Drafting protocol and reconciling against live stock…</div>`;
  const r = await api("/api/protocol", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ experiment: exp }) });
  body.innerHTML = renderProtocol(r);
  const btn = $("#dlOrder");
  if (btn) btn.onclick = () => downloadCSV(r.order_list);
}

function renderProtocol(r) {
  const p = r.protocol, eng = p.engine === "granite" ? "IBM Granite" : "template";
  let h = `<div class="card"><h3>Protocol · ${eng}</h3>
    <div style="font-size:16px;font-weight:600">${esc(p.title)}</div>
    <div class="ttype" style="margin:4px 0 10px">⏱ ${esc(p.estimated_duration || "")} · ${esc(p.objective || "")}</div>
    <ol class="steps">${(p.steps || []).map(s => `<li>${esc(s)}</li>`).join("")}</ol></div>`;

  h += `<div class="section-label">Materials vs live inventory</div>
    <div class="table-wrap"><table><thead><tr>
    <th>Status</th><th>Material</th><th>Need</th><th>In stock</th><th>Matched</th><th>Vendor</th></tr></thead><tbody>` +
    r.check.map(c => `<tr>
      <td><span class="status s-${c.status}"><span class="dot"></span>${c.status}</span></td>
      <td>${esc(c.required_name)}</td>
      <td class="mono-cell">${esc(c.required_qty)} ${esc(c.required_unit)}</td>
      <td class="mono-cell">${esc(c.in_stock)} ${esc(c.unit)}</td>
      <td class="mono-cell">${esc(c.matched_id || "—")}</td>
      <td>${esc(c.vendor || "—")}</td></tr>`).join("") + `</tbody></table></div>`;

  const o = r.order_list;
  if (o.length) {
    h += `<div class="section-label">Need to order (${o.length})</div><div class="order">` +
      o.map(x => `<div class="oitem"><span><span class="status s-${x.status}"><span class="dot"></span>${x.status}</span> &nbsp;${esc(x.required_name)}</span>
        <span class="mono-cell">~${esc(x.suggested_order_qty)} ${esc(x.required_unit)} · ${esc(x.vendor || "vendor TBD")} ${esc(x.catalog_number || "")}</span></div>`).join("") +
      `<div style="margin-top:14px"><button class="ghost" id="dlOrder">⬇ Download order list (CSV)</button></div></div>`;
  } else {
    h += `<div class="order ok" style="margin-top:16px">✓ All materials in stock — ready to run.</div>`;
  }
  return h;
}

function downloadCSV(rows) {
  const head = ["status", "material", "suggested_qty", "unit", "vendor", "catalog_number"];
  const lines = [head.join(",")].concat(rows.map(r =>
    [r.status, `"${r.required_name}"`, r.suggested_order_qty, r.required_unit, `"${r.vendor || ""}"`, r.catalog_number || ""].join(",")));
  const blob = new Blob([lines.join("\n")], { type: "text/csv" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob); a.download = "benchpilot_order_list.csv"; a.click();
}

// ---------- inventory ----------
async function loadInventory() {
  const r = await api("/api/inventory");
  state.inventory = r.items;
  renderCats();
  renderInventory();
  $("#invSummary").innerHTML =
    `<span><b>${r.stats.total}</b> items</span><span style="color:var(--miss)"><b>${r.stats.low}</b> low / out</span><span style="color:var(--exp)"><b>${r.stats.expired}</b> expired</span>`;
}
function renderCats() {
  const cats = ["all", ...new Set(state.inventory.map(i => i.category))];
  $("#catChips").innerHTML = cats.map(c =>
    `<span class="catchip ${c === state.cat ? "active" : ""}" data-cat="${c}">${c[0].toUpperCase() + c.slice(1)}</span>`).join("");
  $$(".catchip").forEach(ch => ch.onclick = () => { state.cat = ch.dataset.cat; renderCats(); renderInventory(); });
}
function today() { return new Date().toISOString().slice(0, 10); }
function statusOf(it) {
  if ((it.quantity || 0) <= (it.reorder_threshold || 0)) return "MISSING";
  if (it.expiration && it.expiration < today()) return "EXPIRED";
  return "AVAILABLE";
}
function renderInventory() {
  const q = $("#invSearch").value.trim().toLowerCase();
  let rows = state.inventory;
  if (state.cat !== "all") rows = rows.filter(i => i.category === state.cat);
  if (q) rows = rows.filter(i => (i.name + i.vendor + i.catalog_number + i.cas + i.subtype).toLowerCase().includes(q));
  $("#invBody").innerHTML = rows.map(it => {
    const st = statusOf(it);
    return `<tr data-id="${esc(it.id)}">
      <td><span class="dot" style="background:var(--${st === "MISSING" ? "miss" : st === "EXPIRED" ? "exp" : "ok"})"></span></td>
      <td class="mono-cell">${esc(it.id)}</td>
      <td>${esc(it.name)}</td>
      <td><span class="cat-tag">${esc(it.category)}</span></td>
      <td class="mono-cell">${esc(it.quantity)} ${esc(it.unit)}</td>
      <td class="mono-cell">${esc(it.concentration || "—")}</td>
      <td>${esc(it.vendor || "—")}</td>
      <td class="mono-cell">${esc(it.catalog_number || "—")}</td>
      <td class="mono-cell">${esc(it.storage_location || "—")}</td></tr>`;
  }).join("") || `<tr><td colspan="9" class="empty">No items match.</td></tr>`;
  $$("#invBody tr[data-id]").forEach(tr => tr.onclick = () => openDrawer(tr.dataset.id));
}
$("#invSearch").addEventListener("input", renderInventory);

// drawer detail
async function openDrawer(id) {
  const it = await api("/api/inventory/" + id);
  const st = statusOf(it);
  const row = (k, v) => v ? `<div class="drow"><span class="dk">${k}</span><span>${esc(v)}</span></div>` : "";
  $("#drawer").innerHTML = `<button class="close" id="dClose">×</button>
    <h2>${esc(it.name)}</h2>
    <div class="dsub">${esc(it.id)} · <span class="status s-${st}"><span class="dot"></span>${st}</span></div>
    ${row("Category", it.category)}${row("Subtype", it.subtype)}
    ${row("Quantity", `${it.quantity} ${it.unit}  (reorder ≤ ${it.reorder_threshold})`)}
    ${row("Concentration", it.concentration)}${row("Purity", it.purity)}
    ${row("Molecular weight", it.molecular_weight && it.molecular_weight + " g/mol")}${row("Form", it.form)}
    ${row("Vendor", it.vendor)}${row("Catalog #", it.catalog_number)}${row("CAS", it.cas)}
    ${row("Storage", `${it.storage_location || ""} · ${it.storage_temp || ""}`)}
    ${row("Lot", it.lot)}${row("Expiration", it.expiration)}${row("Hazard", it.hazard)}${row("Notes", it.notes)}
    <button class="danger" id="dDelete">Delete item</button>`;
  openPanel();
  $("#dClose").onclick = closePanel;
  $("#dDelete").onclick = async () => {
    if (!confirm(`Delete ${it.name}?`)) return;
    await api("/api/inventory/" + id, { method: "DELETE" });
    closePanel(); loadInventory();
  };
}
function openPanel() { $("#drawer").classList.add("show"); $("#scrim").classList.add("show"); }
function closePanel() { $("#drawer").classList.remove("show"); $("#scrim").classList.remove("show"); }
$("#scrim").onclick = () => { closePanel(); $("#modal").classList.remove("show"); };

// add item modal
$("#addBtn").onclick = () => {
  const f = (k, ph, val = "") => `<label>${k}<input name="${k}" placeholder="${ph}" value="${val}"></label>`;
  $("#modalCard").innerHTML = `<h2>Catalogue a new reagent</h2>
    <div class="formgrid">
      <label class="full">Name<input name="name" placeholder="e.g. Niraparib"></label>
      <label>Category<select name="category"><option>chemical</option><option>biological</option><option>plastic</option></select></label>
      ${f("subtype", "PARP inhibitor")}
      ${f("vendor", "Selleck")}${f("catalog_number", "S-1234")}
      ${f("cas", "1038915-60-4")}${f("molecular_weight", "320.4")}
      ${f("concentration", "10 mM stock")}${f("purity", "≥98%")}
      ${f("form", "Powder")}
      <label>Quantity<input name="quantity" type="number" value="100"></label>
      ${f("unit", "mg")}
      <label>Reorder ≤<input name="reorder_threshold" type="number" value="20"></label>
      ${f("storage_location", "Freezer -20 #1")}${f("storage_temp", "-20C")}
      ${f("expiration", "2027-01-01")}${f("hazard", "Irritant")}
      <label class="full">Notes<input name="notes" placeholder="optional"></label>
    </div>
    <div class="modal-actions"><button class="ghost" id="mCancel">Cancel</button><button class="primary" id="mSave">Add to inventory</button></div>`;
  $("#modal").classList.add("show");
  $("#mCancel").onclick = () => $("#modal").classList.remove("show");
  $("#mSave").onclick = async () => {
    const data = {};
    $$("#modalCard [name]").forEach(i => data[i.name] = i.type === "number" ? parseFloat(i.value || 0) : i.value);
    if (!data.name) { alert("Name is required"); return; }
    await api("/api/inventory", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });
    $("#modal").classList.remove("show");
    loadInventory();
  };
};

// ================= V3: Projects & Team =================
const LOADERS = { projects: loadProjects, team: loadTeam };
$$(".navitem").forEach(n => n.onclick = () => { show(n.dataset.view); (LOADERS[n.dataset.view] || (() => {}))(); });

const STATUS_LABEL = { todo: "To do", in_progress: "In progress", blocked: "Blocked", done: "Done" };
const avatar = (ini, name) => `<span class="avatar ${!name || name === "Unassigned" ? "none" : ""}" title="${esc(name || "Unassigned")}">${esc(ini || "—")}</span>`;

// ---- Projects ----
async function loadProjects() {
  const projs = await api("/api/projects");
  state.projects = projs;
  $("#projectPicker").innerHTML = projs.map((p, i) => `
    <div class="proj-card ${i === 0 ? "active" : ""}" data-pid="${esc(p.id)}">
      <div class="pname">${esc(p.name)}</div>
      <div class="pgoal">${esc(p.goal)}</div>
      <div class="progress"><span style="width:${p.progress}%"></span></div>
      <div class="pmeta"><span>${p.done_count}/${p.task_count} done</span><span>${esc(p.lead_name)}</span></div>
    </div>`).join("");
  $$("#projectPicker .proj-card").forEach(c => c.onclick = () => {
    $$("#projectPicker .proj-card").forEach(x => x.classList.remove("active"));
    c.classList.add("active"); openProject(c.dataset.pid);
  });
  if (projs.length) openProject(projs[0].id);
}

async function openProject(pid) {
  const body = $("#projectBody");
  body.innerHTML = `<div class="card"><span class="spinner"></span> Loading board and running stand-up…</div>`;
  const [pr, su] = await Promise.all([api("/api/project/" + pid), api("/api/standup?project=" + pid)]);
  body.innerHTML = renderStandup(su) + renderPipeline(pr.pipeline) + renderBoard(pr.board);
}

function renderStandup(s) {
  const c = s.counts;
  let flags = "";
  if (s.blockers.length) flags += `<div class="flag"><b>Blockers:</b> ` +
    s.blockers.map(b => `${esc(b.title)} — ${esc(b.reason)}`).join(" · ") + `</div>`;
  if (s.duplicates.length) flags += `<div class="flag dup"><b>Duplicated effort:</b> ` +
    s.duplicates.map(d => `${esc(d.target)} (${d.who.map(esc).join(", ")})`).join(" · ") + `</div>`;
  if (s.unassigned.length) flags += `<div class="flag">${s.unassigned.length} unassigned task(s) — see Team &amp; tasks.</div>`;
  return `<div class="standup"><h3>✦ AI stand-up</h3>
    <div class="snarr">${esc(s.narrative)}</div>
    <div class="schips"><span>✅ ${c.done} done</span><span>🔵 ${c.in_progress} in progress</span><span>⚪ ${c.todo} to do</span><span style="color:var(--miss)">⛔ ${c.blocked} blocked</span></div>
    ${flags}</div>`;
}

function renderPipeline(pipe) {
  return `<div class="pipeline">` + pipe.map((s, i) =>
    `<div class="stage"><div class="sn">${esc(s.stage)}</div><div class="sc">${s.count}</div></div>` +
    (i < pipe.length - 1 ? "" : "")).join("") + `</div>`;
}

function renderBoard(board) {
  return `<div class="board">` + ["todo", "in_progress", "blocked", "done"].map(st => `
    <div class="col"><h4>${STATUS_LABEL[st]} <span>${board[st].length}</span></h4>
      ${board[st].map(t => taskCard(t)).join("")}
    </div>`).join("") + `</div>`;
}

function taskCard(t) {
  const rd = t.readiness || { ready: true, missing: [] };
  const badge = t.reagents && t.reagents.length
    ? (rd.ready ? `<span class="ready">reagents ok</span>` : `<span class="ready block">need ${esc(rd.missing.join(", "))}</span>`)
    : "";
  return `<div class="taskcard"><div class="tt">${esc(t.title)}</div>
    <div class="trow"><span>${avatar(t.assignee_initials, t.assignee_name)}</span>
    <span class="prio ${t.priority}">${t.priority}</span></div>
    ${badge ? `<div class="trow" style="margin-top:7px">${badge}</div>` : ""}</div>`;
}

// ---- Team & tasks ----
async function loadTeam() {
  const data = await api("/api/team");
  state.members = data.members;
  const projName = {}; (state.projects || await api("/api/projects")).forEach(p => projName[p.id] = p.name);

  $("#rosterBody").innerHTML = data.members.map(m => `
    <div class="mcard">${avatar(m.initials, m.name)}
      <div><div class="mname">${esc(m.name)}</div><div class="mrole">${esc(m.role)}</div>
      <div class="mload">${m.active} active${m.blocked ? ` · <span class="b">${m.blocked} blocked</span>` : ""}</div></div>
    </div>`).join("");

  $("#dupBody").innerHTML = data.duplicates.length ? data.duplicates.map(d =>
    `<div class="dup-warn">⚠️ <b>Duplicated effort</b> on <b>${esc(d.target)}</b>: ` +
    d.tasks.map(t => `${esc(t.title)} (${esc(t.assignee_name)})`).join(" · ") + `</div>`).join("") : "";

  const opts = a => data.members.map(m => `<option value="${m.id}" ${a === m.id ? "selected" : ""}>${esc(m.initials)} · ${esc(m.name)}</option>`).join("");
  $("#taskBody").innerHTML = data.tasks.map(t => `
    <tr>
      <td class="mono-cell">${esc(t.id)}</td>
      <td>${esc(t.title)}</td>
      <td class="mono-cell">${esc(t.project_id)}</td>
      <td>${esc(t.target)}</td>
      <td><select class="mini" data-task="${t.id}" data-f="assignee"><option value="">— Unassigned</option>${opts(t.assignee)}</select></td>
      <td><select class="mini" data-task="${t.id}" data-f="status">${["todo", "in_progress", "blocked", "done"].map(s => `<option value="${s}" ${t.status === s ? "selected" : ""}>${STATUS_LABEL[s]}</option>`).join("")}</select></td>
      <td><span class="prio ${t.priority}">${t.priority}</span></td>
      <td class="mono-cell">${esc(t.due || "")}</td>
    </tr>`).join("");

  $$('#taskBody select').forEach(sel => sel.onchange = async () => {
    await api("/api/tasks/" + sel.dataset.task, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ [sel.dataset.f]: sel.value || null }) });
    loadTeam();
  });
}

$("#suggestBtn").onclick = async () => {
  const s = await api("/api/suggest");
  if (!s.length) { alert("No unassigned tasks — the board is fully staffed."); return; }
  const rows = s.map(x => `<div class="oitem"><span>${esc(x.title)} <span class="mono-cell">→ ${esc(x.target)}</span></span>
    <span><b>${esc(x.suggest)}</b> <span class="mono-cell">(${esc(x.why)})</span> &nbsp;
    <button class="ghost" style="padding:3px 10px" data-t="${x.task_id}" data-m="${x.suggest_id}">Assign</button></span></div>`).join("");
  $("#modalCard").innerHTML = `<h2>✦ Suggested assignments</h2><div class="order" style="background:#f6fbfb;border-color:#cfe6e6">${rows}</div>
    <div class="modal-actions"><button class="ghost" id="mClose">Close</button></div>`;
  $("#modal").classList.add("show");
  $("#mClose").onclick = () => $("#modal").classList.remove("show");
  $$("#modalCard [data-t]").forEach(b => b.onclick = async () => {
    await api("/api/tasks/" + b.dataset.t, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ assignee: b.dataset.m }) });
    b.textContent = "✓ Assigned"; b.disabled = true; loadTeam();
  });
};
