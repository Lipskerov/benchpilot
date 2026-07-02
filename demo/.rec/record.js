// BenchPilot ~2.5-min demo recorder (Playwright). Drives the real app + on-screen captions.
// Reuses Playwright installed under the Where2Open demo recorder.
const { chromium } = require('/Users/lipskerov/Desktop/Claude/Where2Open/demo/.rec/node_modules/playwright');

const BASE = process.env.BASE || 'http://localhost:8600';
const W = 1920, H = 1200;
const sleep = ms => new Promise(r => setTimeout(r, ms));

(async () => {
  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: W, height: H }, deviceScaleFactor: 2,
    recordVideo: { dir: __dirname + '/video', size: { width: W, height: H } },
  });
  const page = await context.newPage();
  page.setDefaultTimeout(12000);

  async function initOverlay() {
    await page.addStyleTag({ content: `
      #demoHead{position:fixed;top:18px;left:50%;transform:translateX(-50%);z-index:99999;pointer-events:none;
        background:linear-gradient(135deg,#0d9488,#0891b2);color:#fff;font-family:'IBM Plex Sans',sans-serif;
        font-weight:600;font-size:18px;padding:8px 20px;border-radius:999px;box-shadow:0 8px 30px rgba(0,0,0,.25);
        opacity:0;transition:opacity .4s;letter-spacing:.2px}
      #demoCap{position:fixed;bottom:0;left:0;right:0;z-index:99999;pointer-events:none;background:linear-gradient(0deg,rgba(8,11,16,.94),rgba(8,11,16,.72));
        color:#fff;font-family:'IBM Plex Sans',sans-serif;font-size:27px;line-height:1.45;text-align:center;
        padding:24px 70px 28px;opacity:0;transition:opacity .4s}
      #demoCap b{color:#5fe6d6}`});
    await page.evaluate(() => {
      const h = document.createElement('div'); h.id = 'demoHead'; document.body.appendChild(h);
      const c = document.createElement('div'); c.id = 'demoCap'; document.body.appendChild(c);
      window.__cap = (head, sub) => {
        const H = document.getElementById('demoHead'), C = document.getElementById('demoCap');
        if (head != null) { H.textContent = head; H.style.opacity = head ? 1 : 0; }
        if (sub != null) { C.innerHTML = sub; C.style.opacity = sub ? 1 : 0; }
      };
    });
  }
  const cap = (head, sub) => page.evaluate(([h, s]) => window.__cap(h, s), [head, sub]).catch(() => {});
  const click = async (sel, t = 9000) => { const l = page.locator(sel).first(); await l.waitFor({ state: 'visible', timeout: t }); await sleep(400); await l.click(); };
  const safe = async fn => { try { await fn(); } catch (e) { console.error('  (skipped) ' + e.message.split('\n')[0]); } };
  const killModal = () => page.evaluate(() => { const m = document.getElementById('modal'); if (m) m.classList.remove('show'); }).catch(() => {});

  try {
    // ============ 1. HOOK ============
    await page.goto(BASE, { waitUntil: 'networkidle' });
    await initOverlay(); await sleep(600);
    await cap('BenchPilot', '<b>What if</b> — instead of 20+ hours reading, planning and assigning — you could jump straight from a scientific hypothesis to real work?'); await sleep(7500);
    await cap('The reality today', 'Every project starts the same way: <b>drowning in papers and trials</b> before a single experiment runs.'); await sleep(5500);

    // ============ 2. DISCOVER ============
    await cap('1 · Discover', 'So let\'s just ask — in plain language — and let BenchPilot read the whole field for us.');
    await page.locator('#landingQ').click();
    await page.locator('#landingQ').type('How can immunotherapy help more triple-negative breast cancer patients respond to treatment?', { delay: 38 });
    await sleep(700); await click('#landingBtn');
    await page.locator('#discoverResults .target').first().waitFor({ timeout: 12000 }); await sleep(3000);
    await cap('1 · Discover', 'Grounded in <b>real PubMed papers and clinical trials</b> — with the actual molecular targets pulled out.');
    await page.evaluate(() => window.scrollTo({ top: 360, behavior: 'smooth' })); await sleep(3800);
    await cap('1 · Discover', 'Every paper opens to its <b>full abstract</b>; every trial to its phase, sponsor and outcomes.');
    await safe(async () => { await page.locator('#discoverResults .ev-more summary').first().click(); await sleep(3400); });
    await page.evaluate(() => window.scrollTo({ top: 640, behavior: 'smooth' })); await sleep(1800);
    await safe(async () => { await page.locator('#discoverResults .evcol').nth(1).locator('.ev-more summary').first().click(); await sleep(3200); });
    await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'smooth' })); await sleep(1400);

    // ============ 3. HYPOTHESES ============
    await cap('2 · Hypotheses', 'Pick a target and it proposes <b>competing hypotheses</b> — each in plain English, and testable.');
    const pdl1 = page.locator('.target button[data-target*="PD-L1"]');
    await (await pdl1.count() ? pdl1.first() : page.locator('.target button').first()).click();
    await page.locator('.hyp').first().waitFor({ timeout: 12000 }); await sleep(4200);
    await cap('2 · Hypotheses', 'A <b>plain-terms summary</b>, a number to hit, and the result that would prove it wrong.');
    await page.evaluate(() => window.scrollTo({ top: 420, behavior: 'smooth' })); await sleep(4000);
    await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'smooth' })); await sleep(1000);
    await click('.hbtn[data-hyp="H1"]');

    // ============ 4. PLAN + TIMELINE ============
    await page.locator('.gantt').waitFor({ timeout: 12000 });
    await cap('3 · The plan', 'Choose one — and it designs the <b>experiments to answer it</b>, on a timeline, some running in parallel.');
    await sleep(4800);
    await page.evaluate(() => { const w = document.querySelector('.wps'); if (w) w.scrollIntoView({ behavior: 'smooth', block: 'start' }); });
    await cap('3 · The plan', 'Western blots, imaging, dose-response — with the exact <b>cell lines, test groups and reagents</b>.');
    await sleep(6000);

    // ============ 5. SPIN UP ============
    await cap('4 · Make it real', 'One click turns the plan into a live project — <b>Fedor leads</b>, and the team is staffed automatically.');
    await page.evaluate(() => { const b = document.getElementById('planSpinup'); if (b) b.scrollIntoView({ block: 'center' }); });
    await sleep(900); await click('#planSpinup');
    await page.locator('#pe_save').waitFor({ timeout: 10000 }); await sleep(2000);
    const boxes = await page.$$('#pe_members input[type=checkbox]');
    for (const b of boxes) { await b.check().catch(() => {}); await sleep(180); }
    await sleep(900); await safe(() => click('#pe_auto')); await sleep(2200);
    await click('#pe_save');
    await page.locator('.board').waitFor({ timeout: 10000 }); await sleep(3000);

    // ============ 6. TEAM ============
    await cap('4 · The team', 'Everyone\'s workload in one place…');
    await click('.navitem[data-view="team"]');
    await page.locator('#rosterBody .mcard').first().waitFor({ timeout: 9000 }); await sleep(3800);
    await cap('4 · The team', '…and the AI <b>suggests who should run each task</b>, by expertise and load.');
    await safe(async () => { await click('#suggestBtn'); await sleep(4200); await page.locator('#mClose').click(); await sleep(700); });
    await killModal();
    await cap('4 · Track work', 'Reassign or move work — the board updates live.');
    await safe(async () => { await page.locator('#taskBody select[data-f="status"]').first().selectOption('in_progress'); await sleep(2600); });

    // ============ 7. EXPERIMENTS + PHOTOS ============
    await cap('5 · Run & track', 'Track every experiment on a live board, with a roadmap of what\'s next.');
    await click('.navitem[data-view="projects"]');
    await page.locator('.proj-card[data-pid="PRJ-03"]').waitFor({ timeout: 9000 });
    await click('.proj-card[data-pid="PRJ-03"]');
    await page.locator('.board').waitFor({ timeout: 9000 }); await sleep(3000);
    await safe(async () => { const rm = page.locator('.roadmap-wrap summary').first(); await rm.click(); await sleep(3000); await rm.click(); await sleep(700); });
    await cap('5 · Run & track', 'Open the <b>Western blot</b> — the design, the cell lines, and the real result.');
    await safe(async () => { await page.locator('.taskcard', { hasText: 'Western blot' }).first().click(); await sleep(4800); await click('#dClose'); await sleep(700); });
    await cap('5 · Run & track', '…and the <b>confocal imaging</b>, right next to the protocol.');
    await safe(async () => { await page.locator('.taskcard', { hasText: 'IF microscopy' }).first().click(); await sleep(4800); await click('#dClose'); await sleep(700); });

    // ============ 8. REAGENTS ============
    await cap('6 · Reagents', 'Every reagent is searchable — with concentration and live stock.');
    await click('.navitem[data-view="inventory"]');
    await page.locator('#invBody tr').first().waitFor({ timeout: 9000 }); await sleep(2400);
    await page.locator('#invSearch').type('olaparib', { delay: 70 }); await sleep(2000);
    await safe(async () => { await page.locator('#invBody tr').first().click(); await sleep(4000); await click('#dClose'); await sleep(700); });
    await cap('6 · Reagents', 'And before you run, it checks your stock and tells you <b>exactly what to order</b>.');
    await click('.navitem[data-view="protocol"]');
    await page.locator('#protoInput').fill('Immunotherapy (anti-PD-L1) + paclitaxel viability assay in TNBC');
    await sleep(700); await click('#protoBtn');
    await page.locator('#protocolBody .spinup-cta').waitFor({ timeout: 15000 }); await sleep(2600);
    await page.evaluate(() => window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' })); await sleep(4600);

    // ============ 9. OUTRO ============
    await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'smooth' }));
    await cap('BenchPilot', 'From a question to a <b>staffed, scheduled project</b> — in minutes, not weeks. Built with IBM Bob.'); await sleep(6500);
  } catch (e) { console.error('STEP ERROR:', e.message); }
  finally {
    await context.close(); await browser.close();
    const fs = require('fs');
    const f = fs.readdirSync(__dirname + '/video').find(x => x.endsWith('.webm'));
    if (f) console.log('VIDEO:' + __dirname + '/video/' + f);
  }
})();
