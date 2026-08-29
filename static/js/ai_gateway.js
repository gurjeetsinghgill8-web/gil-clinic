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

  var HOP_LIMIT = 4;

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
    var payload = body;
    var hops = 0;
    var usedPuter = false;
    var lastError = '';
    while (hops < HOP_LIMIT) {
      var res;
      try { res = await rawFetch(path, payload, opts); }
      catch (e) { return { ok: false, error: 'Network error: ' + e }; }

      if (!res || res.ok || !res.code) {
        if (usedPuter) logUsage(path, opts.feature, !!(res && res.ok), lastError);
        return res;
      }

      var code = res.code;
      if (code === 'PUTER_NEED_SIGNIN') {
        try { await signIn(); } catch (e) {
          return { ok: false, error: 'Puter sign-in cancelled or unavailable: ' + e };
        }
        hops++;
        continue;
      }

      if (!puterAvailable()) {
        return {
          ok: false,
          error: 'This clinic uses the free Puter AI mode, but the Puter script could not load. Check internet, or switch OPD → Settings → AI Provider → mode "Own API keys".',
        };
      }

      try {
        usedPuter = true;
        if (code === 'PUTER_CHAT') {
          var text = await doChat(res.prompt, res.model);
          if (!text) { lastError = 'Puter returned empty response'; return { ok: false, error: lastError }; }
          payload = mergeBody(body, {
            puter_result: text,
            stage: res.stage,
            puter_specialty: res.puter_specialty,
            _structured: res._structured,
            _raw_ocr: res._raw_ocr,
          });
        } else if (code === 'PUTER_OCR') {
          var ocrText = await doOcr(body);
          if (!ocrText) { lastError = 'Puter OCR returned empty text'; return { ok: false, error: lastError }; }
          payload = mergeBody(body, { puter_ocr_result: ocrText });
        } else if (code === 'PUTER_TRANSCRIBE') {
          var trText = await doTranscribe(body);
          if (!trText) { lastError = 'Puter transcription returned empty text'; return { ok: false, error: lastError }; }
          payload = mergeBody(body, { puter_result: trText });
        } else {
          return res;
        }
      } catch (e) {
        lastError = 'Puter AI error: ' + e;
        return { ok: false, error: lastError };
      }
      hops++;
    }
    return { ok: false, error: 'AI gateway: too many steps. Please try again.' };
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
