/**
 * LIVE PythonAnywhere end-to-end test (patient portal).
 * Reading save karta hai aur turant DELETE kar deta hai -> production me kuch nahi bachta.
 */
const { chromium } = require('playwright');
const fs = require('fs');
const { execSync } = require('child_process');

const B = 'https://gillhopitalsoftware1.pythonanywhere.com';
const PIN = '5554';
let pass = 0, fail = 0;
const log = (s) => { try { fs.appendFileSync('scratch/preview/pa-e2e.log', s + '\n'); } catch (e) {} process.stdout.write(s + '\n'); };
const check = (n, ok, d) => { if (ok) { pass++; log('  OK   ' + n); } else { fail++; log('  FAIL ' + n + (d ? ' -- ' + d : '')); } };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function waitText(page, needle, timeout = 40000) {
  const t0 = Date.now();
  let last = '';
  while (Date.now() - t0 < timeout) {
    try { last = await page.evaluate(() => (document.body ? document.body.textContent : '') || ''); } catch (e) { last = ''; }
    if (last.includes(needle)) return true;
    await sleep(400);
  }
  return false;
}

(async () => {
  try { fs.writeFileSync('scratch/preview/pa-e2e.log', ''); } catch (e) {}

  // live DB se ek patient (naam + mobile) - print nahi karenge
  const info = JSON.parse(execSync('python scripts/pa_patient_info.py', { encoding: 'utf8' }).trim());
  if (!info.ok) { log('patient info nahi mila: ' + info.msg); process.exit(1); }
  log('1) live patient mila (naam chhupa raha hoon), readings abhi: ' + info.readings);

  const browser = await chromium.launch();
  const errors = [];
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const p = await ctx.newPage();
  p.setDefaultTimeout(30000);
  p.on('pageerror', (e) => errors.push(String(e.message)));

  await p.goto(B + '/opd/login', { waitUntil: 'domcontentloaded' });
  await p.locator('input[name="pin"]').fill(PIN);
  await p.locator('button[type="submit"]').first().click();
  check('doctor login (live)', await waitText(p, 'New Prescription'));

  log('2) patient select + link');
  await p.locator('button:has-text("Search Old")').click();
  await p.locator('#patient-search').fill(info.search);
  await sleep(5000);
  let items = await p.locator('.autocomplete-item').count();
  if (items === 0) { // queue path (CQ) bhi try karo
    await p.locator('#patient-search').fill('CQ');
    await sleep(5000);
    items = await p.locator('.autocomplete-item').count();
  }
  log('   search results: ' + items);
  check('patient search live', items >= 1);
  if (items === 0) { await browser.close(); log('\n' + pass + ' passed, ' + fail + ' failed'); process.exit(1); }

  await p.locator('.autocomplete-item').first().click();
  await sleep(2000);
  await p.locator('#patient-link-btn').click();
  const got = await p.waitForFunction(() => {
    const el = document.getElementById('pl-url');
    return el && el.value.includes('/my/');
  }, null, { timeout: 40000 }).then(() => true).catch(() => false);
  check('patient portal link bana (live)', got);
  if (!got) { await browser.close(); log('\n' + pass + ' passed, ' + fail + ' failed'); process.exit(1); }
  const portalUrl = await p.locator('#pl-url').inputValue();
  const token = portalUrl.split('/my/')[1];
  log('   link: ' + B + '/my/' + token.slice(0, 8) + '...');
  check('link PA domain par', portalUrl.startsWith(B + '/my/'));

  log('3) patient side (naya browser, koi login nahi)');
  const ctx2 = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });
  const pp = await ctx2.newPage();
  pp.setDefaultTimeout(30000);
  pp.on('pageerror', (e) => errors.push('patient: ' + e.message));
  await pp.goto(portalUrl, { waitUntil: 'domcontentloaded' });
  check('portal verify screen', await waitText(pp, 'Suraksha Satyapan'));

  log('4) mobile verify (registered number se)');
  await pp.locator('#pp-phone').fill(info.phone);
  await pp.locator('#pp-verify-btn').click();
  const unlocked = await waitText(pp, 'Aaj ki readings', 40000);
  check('verify hokar portal khula (live)', unlocked);
  if (unlocked) {
    const rows = await pp.locator('#pp-rows .pp-row').count();
    check('entry form ke metrics', rows >= 6, String(rows));
    check('download buttons', (await pp.locator('a[href$="fmt=pdf"]').count()) >= 1);
    check('"Doctor ko bhejo" card', await waitText(pp, 'Kisi bhi doctor ko record bhejein', 15000));

    log('5) reading save (test) + turant delete');
    const r0 = pp.locator('#pp-rows .pp-row');
    await r0.nth(0).locator('input[type="number"]').fill('138');
    await r0.nth(1).locator('input[type="number"]').fill('88');
    await pp.locator('#pp-save').click();
    const saved = await waitText(pp, 'save ho gayi', 40000);
    check('reading save hui (live write)', saved);
    check('Excel table me value aayi', await pp.evaluate(() => (document.getElementById('pp-table') || {}).textContent.includes('138/88')));

    // reading id nikaalo aur delete karo
    const data = await pp.evaluate(async (t) => (await fetch('/my/' + t + '/data')).json(), token);
    const justSaved = (data.readings || []).filter((r) => r.code === 'bp-systolic' && r.value === 138);
    check('naya reading DB me mila', justSaved.length >= 1, 'count=' + justSaved.length);
    for (const r of justSaved) {
      const okDel = await pp.evaluate(async ({ t, id }) => {
        const res = await fetch('/my/' + t + '/readings/' + id, { method: 'DELETE' });
        return res.ok;
      }, { t: token, id: r.reading_id });
      log('   delete ' + r.reading_id.slice(0, 8) + ' -> ' + okDel);
    }
    await sleep(1500);
    const after = await pp.evaluate(async (t) => (await fetch('/my/' + t + '/data')).json(), token);
    check('test reading delete ho gayi (production saaf)', (after.readings || []).length === info.readings, 'baaki=' + (after.readings || []).length);

    // share link (read-only) bhi live test
    log('6) "Doctor ko bhejo" read-only link');
    await pp.locator('#pp-share-btn').click();
    const shareOk = await pp.waitForFunction(() => {
      const el = document.getElementById('pp-share-url');
      return el && el.value.includes('/s/');
    }, null, { timeout: 40000 }).then(() => true).catch(() => false);
    check('share link bana (live)', shareOk);
    if (shareOk) {
      const shareUrl = await pp.locator('#pp-share-url').inputValue();
      const ctx3 = await browser.newContext({ viewport: { width: 390, height: 844 } });
      const sp = await ctx3.newPage();
      await sp.goto(shareUrl, { waitUntil: 'domcontentloaded' });
      check('doctor read-only view khula (bina login)', await waitText(sp, 'read-only', 30000));
      check('read-only me save button nahi', await sp.evaluate(() => !/Save readings/i.test(document.body.textContent || '')));
      await sp.screenshot({ path: 'scratch/preview/pa-shared-view.png', fullPage: true });
      await ctx3.close();
    }
    await pp.screenshot({ path: 'scratch/preview/pa-patient-portal-unlocked.png', fullPage: true });
  }

  check('koi uncaught JS error nahi', errors.length === 0, errors.slice(0, 2).join(' | '));
  log('\n' + pass + ' passed, ' + fail + ' failed');
  await browser.close();
  process.exitCode = fail > 0 ? 1 : 0;
})().catch((e) => { log('FATAL: ' + e.message); process.exit(1); });
