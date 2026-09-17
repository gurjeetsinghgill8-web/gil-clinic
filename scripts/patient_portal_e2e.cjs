/**
 * TEMP real-browser check (Patient Portal UI, Smart OPD).
 * Doctor login (PIN) → patient select → 📱 Patient link → modal se link →
 * patient portal (verify → readings → graphs) → 🩺 "Doctor ko bhejo" →
 * read-only /s/ page ek SAFA browser me (koi cookie nahi).
 *
 * Run: node scratch/portal_ui_test.cjs   (server on :8099 hona chahiye)
 */
const { chromium } = require('playwright');
const fs = require('fs');

const LOG_FILE = 'scratch/preview/ui-test.log';
try { fs.writeFileSync(LOG_FILE, ''); } catch (e) { /* ignore */ }
function log(s) {
  try { fs.appendFileSync(LOG_FILE, s + '\n'); } catch (e) { /* ignore */ }
  process.stdout.write(s + '\n');
}

const BASE = 'http://127.0.0.1:8099';
const PIN = '5554';
const PHONE = '9876543210';
let pass = 0;
let fail = 0;

// watchdog — koi step atak jaye to 3 minute me band (warna infinite hang)
const watchdog = setTimeout(() => {
  log('WATCHDOG: test atak gaya — 180s se zyada');
  process.exit(2);
}, 180000);

function check(name, ok, detail) {
  if (ok) { pass++; log('  ✓ ' + name); }
  else { fail++; log('  ✗ ' + name + (detail ? ' — ' + detail : '')); }
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function waitText(page, needle, label, timeout = 15000) {
  const start = Date.now();
  let last = '';
  while (Date.now() - start < timeout) {
    try {
      last = await page.evaluate(() => (document.body ? document.body.textContent : '') || '');
    } catch (e) {
      last = ''; // navigation ke dauraan context destroy ho jata hai — retry
    }
    if (last.includes(needle)) return true;
    await sleep(150);
  }
  throw new Error(`Timeout (${label}): "${needle}" not found. Body: ${last.slice(0, 400)}`);
}

(async () => {
  log('0) browser launch…');
  const browser = await chromium.launch();
  const errors = [];
  log('0) browser ready');

  // ── 1) DOCTOR: login → patient select → patient link modal ───────────────
  const doctor = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const dp = await doctor.newPage();
  dp.setDefaultTimeout(15000);
  dp.on('pageerror', (e) => errors.push('doctor: ' + e.message));

  await dp.goto(BASE + '/opd/login');
  await waitText(dp, 'Enter your PIN', 'opd login page');
  log('1) login page khula');
  await dp.locator('input[name="pin"]').fill(PIN);
  await dp.locator('button[type="submit"]').first().click();
  await waitText(dp, 'New Prescription', 'opd dashboard');
  check('doctor login (PIN) → dashboard', true);

  await dp.locator('button:has-text("Search Old")').click();
  await dp.locator('#patient-search').fill('Raj Kumar');
  await waitText(dp, 'Raj Kumar', 'search result');
  check('patient search finds the seeded patient', true);

  await dp.locator('.autocomplete-item:has-text("Raj Kumar")').first().click();
  await waitText(dp, 'Raj Kumar', 'patient selected');
  const linkBtn = dp.locator('#patient-link-btn');
  check('📱 Patient link button visible after selecting patient', await linkBtn.isVisible());
  await linkBtn.click();
  await dp.waitForFunction(
    () => {
      const el = document.getElementById('pl-url');
      return el && el.value.includes('/my/');
    },
    null,
    { timeout: 20000 }
  );
  const portalUrl = await dp.locator('#pl-url').inputValue();
  const token = portalUrl.split('/my/')[1];
  const localPortalUrl = BASE + '/my/' + token; // .env ka APP_BASE_URL purana tunnel ho sakta hai — local test usi path par
  const waHref = await dp.locator('#pl-wa').getAttribute('href');
  check('doctor ko patient portal link mila (/my/<token>)', /\/my\/[A-Za-z0-9_-]{20,}/.test(portalUrl), portalUrl);
  check('WhatsApp button ka link bana (patient ke number ke saath)', (waHref || '').includes('wa.me/91' + PHONE), waHref);
  const msg = await dp.locator('#pl-msg').inputValue();
  check('patient ko bhejne wala message Hinglish me taiyaar', msg.includes('BP') && msg.includes(portalUrl));
  await dp.screenshot({ path: 'scratch/preview/opd-patient-link.png', fullPage: false });

  // ── 2) PATIENT: link kholo → mobile verify → readings → graphs ───────────
  const patient = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });
  const pp = await patient.newPage();
  pp.on('pageerror', (e) => errors.push('patient: ' + e.message));
  await pp.goto(localPortalUrl);
  await waitText(pp, 'Suraksha Satyapan', 'phone verify screen');
  check('portal pehle phone verify maangta hai (security)', true);

  await pp.locator('#pp-phone').fill('9999999999');
  await pp.locator('#pp-verify-btn').click();
  await waitText(pp, 'match nahi hua', 'wrong number error');
  check('galat number reject hota hai', true);

  await pp.locator('#pp-phone').fill(PHONE);
  await pp.locator('#pp-verify-btn').click();
  await waitText(pp, 'Aaj ki readings', 'portal after verify');
  check('sahi number → portal khul gaya', true);
  const nameShown = await pp.evaluate(() => document.body.textContent.includes('Raj Kumar'));
  check('portal par patient ka naam dikhta hai', nameShown);

  const entryRows = await pp.locator('#pp-rows .pp-row').count();
  check('entry form me metrics listed hain (BP/Pulse/SpO2/…)', entryRows >= 6, String(entryRows));

  // reading #1
  async function saveReading(sys, dia, pulse, dayOffsetLabel) {
    const rows = pp.locator('#pp-rows .pp-row');
    await rows.nth(0).locator('input[type="number"]').fill(String(sys));
    await rows.nth(1).locator('input[type="number"]').fill(String(dia));
    await rows.nth(2).locator('input[type="number"]').fill(String(pulse));
    await pp.locator('#pp-save').click();
    await pp.waitForFunction(() => {
      const m = document.getElementById('pp-save-msg');
      return m && m.style.display !== 'none' && /save ho gayi/.test(m.textContent);
    }, null, { timeout: 20000 });
  }
  await saveReading(138, 88, 82);
  await pp.waitForTimeout(500);
  const afterFirst = await pp.locator('#pp-trends svg.trend-chart, #pp-trends svg').count();
  check('pehli reading save hui (table me dikh rahi hai)',
    (await pp.evaluate(() => document.getElementById('pp-table').textContent.includes('138/88'))));

  await saveReading(152, 96, 88);
  await pp.waitForTimeout(800);
  const charts = await pp.locator('#pp-trends svg').count();
  check('doosri reading ke baad trend graph ban gaya', charts >= 1, 'charts=' + charts);
  check('normal range band graph me hai', await pp.evaluate(() =>
    !!document.querySelector('#pp-trends svg rect[fill="#10b981"]')));
  const chartBox = await pp.locator('#pp-trends svg').first().boundingBox();
  check('graph phone par bada render hota hai', chartBox && chartBox.width >= 250,
    JSON.stringify(chartBox));
  check('high value par red-flag guidance dikhi', await pp.evaluate(() =>
    /doctor se consult|badha hua|Khatarnak/i.test(document.body.textContent)));
  const dl = await pp.evaluate(() => ({
    pdf: !!document.querySelector('a[href$="fmt=pdf"]'),
    html: !!document.querySelector('a[href$="fmt=html"]'),
    csv: !!document.querySelector('a[href$="fmt=csv"]')
  }));
  check('PDF / HTML / CSV download buttons maujood', dl.pdf && dl.html && dl.csv, JSON.stringify(dl));
  await pp.screenshot({ path: 'scratch/preview/patient-portal-phone.png', fullPage: true });

  // ── 3) "Doctor ko bhejo" — read-only share link ──────────────────────────
  await pp.locator('#pp-share-note').fill('BP 3 din se high aa raha hai');
  await pp.locator('#pp-share-btn').click();
  await pp.waitForFunction(() => {
    const el = document.getElementById('pp-share-url');
    return el && el.value.includes('/s/');
  }, null, { timeout: 20000 });
  const shareUrl = await pp.locator('#pp-share-url').inputValue();
  const localShareUrl = BASE + '/s/' + shareUrl.split('/s/')[1];
  check('patient ne "Doctor ko bhejo" link banaya (/s/<token>)', /\/s\/[A-Za-z0-9_-]{20,}/.test(shareUrl), shareUrl);
  const shareWa = await pp.locator('#pp-share-wa').getAttribute('href');
  check('share link WhatsApp par bhejne ka button bana', (shareWa || '').includes('wa.me/?text='));
  check('patient ko link ki validity dikhti hai',
    await pp.evaluate(() => /valid till/i.test(document.body.textContent)));

  // ── 4) DOCTOR (no login, fresh browser) → /s/<token> read-only ───────────
  const stranger = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });
  const sp = await stranger.newPage();
  sp.on('pageerror', (e) => errors.push('shared: ' + e.message));
  await sp.goto(localShareUrl);
  await waitText(sp, 'read-only', 'shared record page');
  check('koi bhi (bina login) share link khol sakta hai', true);
  const sharedSvgs = await sp.locator('svg.trend-chart').count();
  check('shared page par graphs dikhte hain', sharedSvgs >= 1, 'charts=' + sharedSvgs);
  check('shared page par patient ka message dikhta hai',
    await sp.evaluate(() => document.body.textContent.includes('BP 3 din se high')));
  check('shared page par Print/Save-as-PDF button hai',
    await sp.evaluate(() => !!Array.from(document.querySelectorAll('button')).find(b => /Print/i.test(b.textContent))));
  check('shared page READ-ONLY hai (koi save/edit button nahi)',
    await sp.evaluate(() => !/Save readings/i.test(document.body.textContent)));
  const spdf = await sp.request.get(localShareUrl + '/export?fmt=pdf');
  check('shared page se PDF download milta hai', spdf.ok() && (await spdf.body()).slice(0, 5).toString() === '%PDF-');
  await sp.screenshot({ path: 'scratch/preview/patient-shared-phone.png', fullPage: true });

  // ── 5) DOCTOR: Patient Monitor tab ──
  await dp.evaluate(() => { if (typeof closePatientLink === 'function') closePatientLink(); });
  await dp.waitForSelector('#patient-link-modal', { state: 'hidden', timeout: 5000 }).catch(() => {});
  await dp.locator('.nav-item[data-tab="patient-monitor"]').click();
  await waitText(dp, 'Patient Monitor', 'patient monitor tab');
  await dp.waitForSelector('#pm-list table', { timeout: 20000 });
  check('Patient Monitor tab me patient list aayi',
    await dp.evaluate(() => document.getElementById('pm-list').textContent.includes('Raj Kumar')));
  await dp.locator('#pm-list button:has-text("Dekho")').first().click();
  await dp.waitForSelector('#pm-detail svg', { timeout: 20000 });
  check('doctor ko patient ke graphs dikhte hain (server-side SVG)',
    (await dp.locator('#pm-detail svg').count()) >= 1);
  check('doctor ko Excel-style table bhi dikhti hai',
    await dp.evaluate(() => /Date & time|138\/88/.test(document.getElementById('pm-detail').textContent)));
  await dp.screenshot({ path: 'scratch/preview/opd-patient-monitor.png', fullPage: true });

  check('koi uncaught page error nahi', errors.length === 0, errors.slice(0, 3).join(' | '));

  await browser.close();
  clearTimeout(watchdog);
  log(`\n${pass} passed, ${fail} failed`);
  process.exitCode = fail > 0 ? 1 : 0;
})().catch(async (e) => {
  log('FATAL: ' + e.message);
  process.exit(1);
});
