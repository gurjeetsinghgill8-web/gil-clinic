/* ═══════════════════════════════════════════════════════════════════════════
   ai_gateway.js — GIL CLINIC browser AI gateway.

   Every AI feature calls aiFetch('/opd/api/...', body) instead of fetch().
   The backend answers either:
     { ok: true, ... }                 → done (clinic BYOK keys or system)
     { ok:false, code:'PUTER_CHAT'|'PUTER_OCR'|'PUTER_TRANSCRIBE', prompt/model }
                                       → this gateway runs the Puter AI hop in
                                         the browser (USER PAYS — clinic's Puter
                                         account) and re-posts the result.
   Puter usage is metered via /opd/api/ai-usage or /staff/api/ai-usage.
   ═══════════════════════════════════════════════════════════════════════════ */
(function () {
  'use strict';

  var HOP_LIMIT = 8;  // multi-specialty upgrades need several Puter hops

  function puterAvailable() {
    return typeof window.puter !== 'undefined' && window.puter && window.puter.ai;
  }

  function isSignedIn() {
    if (!puterAvailable()) return Promise.resolve(false);
    try { return Promise.resolve(window.puter.auth.isSignedIn()); }
    catch (e) { return Promise.resolve(false); }
  }

  async function signIn() {
    if (!puterAvailable()) throw new Error('Puter SDK not loaded (internet required)');
    if (await isSignedIn()) return true;
    await window.puter.auth.signIn();
    return await isSignedIn();
  }

  function extractText(res) {
    if (!res) return '';
    if (typeof res === 'string') return res;
    if (res.message && res.message.content) return res.message.content;
    if (res.text) return res.text;
    if (res.content) return typeof res.content === 'string' ? res.content : JSON.stringify(res.content);
    try { return JSON.stringify(res); } catch (e) { return ''; }
  }

  function b64ToFile(b64, name) {
    var mime = 'image/jpeg';
    var raw = b64;
    if (raw.indexOf(',') !== -1) {
      var head = raw.slice(0, raw.indexOf(','));
      var mm = head.match(/data:([a-zA-Z0-9\/.+-]+)/);
      if (mm) mime = mm[1];
      raw = raw.slice(raw.indexOf(',') + 1);
    }
    var bin = atob(raw);
    var arr = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
    return new File([arr], name, { type: mime });
  }

  function mergeBody(original, extra) {
    if (typeof FormData !== 'undefined' && original instanceof FormData) {
      var fd = new FormData();
      original.forEach(function (v, k) { if (k !== 'puter_result' && k !== 'puter_ocr_result') fd.append(k, v); });
      Object.keys(extra).forEach(function (k) {
        if (extra[k] !== undefined && extra[k] !== null) fd.append(k, extra[k]);
      });
      return fd;
    }
    var obj = {};
    if (original && typeof original === 'object') {
      for (var k in original) { if (Object.prototype.hasOwnProperty.call(original, k)) obj[k] = original[k]; }
    }
    for (var ek in extra) { if (Object.prototype.hasOwnProperty.call(extra, ek)) obj[ek] = extra[ek]; }
    return obj;
  }

  function getAudioFile(body) {
    if (typeof FormData !== 'undefined' && body instanceof FormData) {
      var f = body.get('audio');
      if (f) return f;
    }
    return (body && body.audioFile) || null;
  }

  async function rawFetch(path, body, opts) {
    var init = { method: (opts && opts.method) || 'POST', credentials: 'same-origin' };
    if (typeof FormData !== 'undefined' && body instanceof FormData) {
      init.body = body;
    } else {
      init.headers = { 'Content-Type': 'application/json' };
      init.body = JSON.stringify(body || {});
    }
    var resp = await fetch(path, init);
    // E2.4: Puter credits khatam (402 insufficient_funds) -> clear message
    if (resp.status === 402) {
      return {
        ok: false,
        code: 'PUTER_402',
        error: 'Puter credits khatam ho gaye — "💳 Recharge" button dabao (top-right chip ya Settings) ya puter.com par sign-in karke Billing → upgrade karo.',
      };
    }
    var ct = resp.headers.get('content-type') || '';
    if (ct.indexOf('application/json') !== -1) {
      try { return await resp.json(); } catch (e) { return { ok: false, error: 'Bad JSON response' }; }
    }
    return { ok: resp.ok, status: resp.status };
  }

  function usagePathFor(path) {
    if (String(path).indexOf('/staff/') === 0) return '/staff/api/ai-usage';
    return '/opd/api/ai-usage';
  }

  function logUsage(path, feature, success, error) {
    try {
      var f = feature || String(path).split('/api/')[1] || 'browser-ai';
      fetch(usagePathFor(path), {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ feature: f, provider: 'puter', success: !!success, error: error || '' }),
      }).catch(function () {});
    } catch (e) {}
  }

  async function doChat(prompt, model) {
    var res = await window.puter.ai.chat(prompt, { model: model || 'gpt-4o-mini' });
    return extractText(res);
  }

  async function doOcr(body) {
    var b64 = body && (body.image || body.image_b64 || body.imageData);
    if (!b64) throw new Error('No image in request for Puter OCR');
    var file = b64ToFile(b64, 'scan.jpg');
    var res = await window.puter.ai.img2txt(file);
    return extractText(res);
  }

  async function doTranscribe(body) {
    var f = getAudioFile(body);
    if (!f) throw new Error('No audio file for Puter transcription');
    var res = await window.puter.ai.speech2txt(f);
    return extractText(res);
  }

  async function aiFetch(path, body, opts) {
    opts = opts || {};
    // Accept BOTH calling conventions used across the app:
    //   1. aiFetch(path, payload)                    -> legacy style (FormData etc.)
    //   2. aiFetch(path, {method, headers, body})    -> fetch-style init object
    var payload;
    var isForm = (typeof FormData !== 'undefined' && body instanceof FormData);
    var looksLikeInit = !isForm && body && typeof body === 'object' &&
        (body.method || body.headers || body.body !== undefined || body.credentials);
    if (looksLikeInit && !opts.body) {
      opts = body;
      if (typeof opts.body === 'string') {
        try { payload = JSON.parse(opts.body) || {}; } catch (e) { payload = opts.body; }
      } else if (typeof FormData !== 'undefined' && opts.body instanceof FormData) {
        payload = opts.body;
      } else {
        payload = opts.body;
      }
    } else {
      payload = body;
    }
    // The re-post payload must be the ACTUAL request data (parsed above),
    // never the opts wrapper.
    var basePayload = payload;
    var hops = 0;
    var usedPuter = false;
    var lastError = '';
    var final = null;
    while (hops < HOP_LIMIT) {
      var res;
      try { res = await rawFetch(path, payload, opts); }
      catch (e) { final = { ok: false, error: 'Network error: ' + e }; break; }

      if (!res || res.ok || !res.code) {
        if (usedPuter) logUsage(path, opts.feature, !!(res && res.ok), lastError);
        final = res;
        break;
      }

      var code = res.code;
      if (code === 'PUTER_NEED_SIGNIN') {
        try { await signIn(); } catch (e) {
          final = { ok: false, error: 'Puter sign-in cancelled or unavailable: ' + e };
          break;
        }
        hops++;
        continue;
      }

      if (!puterAvailable()) {
        final = {
          ok: false,
          error: 'This clinic uses the free Puter AI mode, but the Puter script could not load. Check internet, or switch OPD → Settings → AI Provider → mode "Own API keys".',
        };
        break;
      }

      try {
        usedPuter = true;
        // Puter AI needs a signed-in user. Try the popup, but do NOT hang
        // forever — 20s timeout ke baad clear message (banner button se sign-in).
        var signedInNow = await isSignedIn();
        if (!signedInNow) {
          try {
            await Promise.race([
              signIn(),
              new Promise(function (_, rej) {
                setTimeout(function () { rej(new Error('timeout')); }, 20000);
              }),
            ]);
          } catch (e) {
            final = { ok: false, error: 'Puter sign-in popup nahi khula ya timeout ho gaya. Top-right "Sign in to Puter" button dabao, phir dobara Generate dabao.' };
            break;
          }
          signedInNow = await isSignedIn();
          if (!signedInNow) {
            final = { ok: false, error: 'Puter sign-in complete nahi hua. Top-right "Sign in to Puter" button se sign-in karo, phir dobara Generate dabao.' };
            break;
          }
        }
        if (code === 'PUTER_CHAT') {
          var text = await doChat(res.prompt, res.model);
          if (!text) { lastError = 'Puter returned empty response'; final = { ok: false, error: lastError }; break; }
          payload = mergeBody(basePayload, {
            puter_result: text,
            stage: res.stage,
            puter_specialty: res.puter_specialty,
            _structured: res._structured,
            _raw_ocr: res._raw_ocr,
          });
        } else if (code === 'PUTER_OCR') {
          var ocrText = await doOcr(basePayload);
          if (!ocrText) { lastError = 'Puter OCR returned empty text'; final = { ok: false, error: lastError }; break; }
          payload = mergeBody(basePayload, { puter_ocr_result: ocrText });
        } else if (code === 'PUTER_TRANSCRIBE') {
          var trText = await doTranscribe(basePayload);
          if (!trText) { lastError = 'Puter transcription returned empty text'; final = { ok: false, error: lastError }; break; }
          payload = mergeBody(basePayload, { puter_result: trText });
        } else {
          final = res;
          break;
        }
      } catch (e) {
        lastError = 'Puter AI error: ' + e;
        final = { ok: false, error: lastError };
        break;
      }
      hops++;
    }
    if (final === null) final = { ok: false, error: 'AI gateway: too many steps. Please try again.' };

    // IMPORTANT: return a REAL Response object so every caller (legacy code
    // does .then(r => r.json()) while newer code reads the object directly)
    // works the same way. Status mirrors the logical ok flag.
    var status = (final && final.ok === false) ? 502 : 200;
    return new Response(JSON.stringify(final), {
      status: status,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  async function puterStatus() {
    try {
      if (!puterAvailable()) return null;
      if (!(await isSignedIn())) return null;
      var u = await window.puter.auth.getUser();
      return { username: u && u.username, email: u && u.email };
    } catch (e) { return null; }
  }

  window.aiFetch = aiFetch;
  window.puterConnect = signIn;
  window.puterIsSignedIn = isSignedIn;
  window.puterStatus = puterStatus;
  window.puterAvailable = puterAvailable;
})();
