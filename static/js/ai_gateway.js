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

  // ── Puter sign-in (robust) — blank-popup / guest-account safe.
  //     Ported from the working "nano clinic" reference. ──
  var SIGNIN_TIMEOUT_MS = 25000;
  var TAB_SIGNIN_TIMEOUT_MS = 120000;
  var PUTER_GUI_ORIGIN = 'https://puter.com';
  var PUTER_API_ORIGIN = 'https://api.puter.com';

  function withTimeout(promise, ms, label) {
    return new Promise(function (resolve, reject) {
      var t = setTimeout(function () { reject(new Error((label || 'Request') + ' timed out')); }, ms);
      promise.then(function (v) { clearTimeout(t); resolve(v); }, function (e) { clearTimeout(t); reject(e); });
    });
  }

  function isMobileOrPwa() {
    if (typeof window === 'undefined') return false;
    try {
      var standalone = (window.matchMedia && window.matchMedia('(display-mode: standalone)').matches) ||
        (navigator.standalone === true);
      return standalone || /Android|iPhone|iPad|iPod/i.test(navigator.userAgent);
    } catch (e) { return false; }
  }

  function randomId(prefix) {
    return prefix + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 10);
  }

  function generateUuid() {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID();
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
      var r = Math.random() * 16 | 0;
      var v = c === 'x' ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
  }

  async function puterUser() {
    try {
      if (!puterAvailable()) return undefined;
      var u = await window.puter.auth.getUser();
      return u && (u.email || u.username) ? u : undefined;
    } catch (e) { return undefined; }
  }

  // A signed-in Puter user with NO email = temporary guest account.
  async function isRealPuterAccount() {
    for (var i = 0; i < 4; i++) {
      var u = await puterUser();
      if (u !== undefined) return !!u.email;
      await new Promise(function (r) { setTimeout(r, 500); });
    }
    return true; // can't confirm — never lock a real user out
  }

  function clearPuterSession() {
    try { if (window.puter && window.puter.auth && window.puter.auth.signOut) window.puter.auth.signOut(); } catch (e) {}
    try {
      ['puter.auth.token.v2', 'puter.auth.token.origin.v2', 'puter.auth.token', 'puter.app.id'].forEach(function (k) {
        localStorage.removeItem(k);
      });
    } catch (e) {}
  }

  function savePuterToken(token, appUid) {
    try {
      if (window.puter && window.puter.setAuthToken) {
        window.puter.setAuthToken(token);
        if (appUid && window.puter.setAppID) window.puter.setAppID(appUid);
      } else {
        localStorage.setItem('puter.auth.token.v2', token);
        localStorage.setItem('puter.auth.token.origin.v2', PUTER_API_ORIGIN);
        localStorage.removeItem('puter.auth.token');
        if (appUid) localStorage.setItem('puter.app.id', appUid);
      }
    } catch (e) {}
  }

  async function signIn() {
    if (!puterAvailable()) throw new Error('Puter SDK not loaded (internet required)');
    if (await isSignedIn() && await isRealPuterAccount()) return true;
    if (await isSignedIn()) clearPuterSession();

    // Mobile / standalone PWA: SDK popup renders blank → full-tab login.
    if (isMobileOrPwa()) {
      await signInViaTab();
      return true;
    }

    // Desktop: official SDK first, temp-user creation disabled + hard timeout.
    try {
      await withTimeout(
        window.puter.auth.signIn({ attempt_temp_user_creation: false, request_auth: true }),
        SIGNIN_TIMEOUT_MS,
        'Puter sign-in'
      );
    } catch (e) {
      // blank popup / blocked / timeout → fall through to full-tab login
    }

    if (await isSignedIn() && await isRealPuterAccount()) return true;
    clearPuterSession();
    await signInViaTab();
    return true;
  }

  async function signInViaTab() {
    if (await isSignedIn() && await isRealPuterAccount()) return;

    var msgId = randomId('m');
    var sessionId = generateUuid();
    var isMobile = isMobileOrPwa();
    var popupParam = isMobile ? '' : '&embedded_in_popup=true';
    var url = PUTER_GUI_ORIGIN + '/action/sign-in?msg_id=' + msgId + popupParam +
      '&cross_origin_isolated=true&signin_session=' + sessionId + '&request_auth=true';

    return new Promise(function (resolve, reject) {
      var settled = false;
      var pollTimer = null;
      var timer = null;

      function finish(fn) {
        if (settled) return;
        settled = true;
        window.removeEventListener('message', onMsg);
        window.removeEventListener('focus', onResume);
        document.removeEventListener('visibilitychange', onResume);
        if (pollTimer) clearInterval(pollTimer);
        if (timer) clearTimeout(timer);
        fn();
      }

      function acceptToken(token, appUid) {
        savePuterToken(token, appUid);
        isRealPuterAccount().then(function (real) {
          if (real) resolve();
          else {
            clearPuterSession();
            reject(new Error('Puter guest account bana — puter.com tab me apni email se login karo, phir wapas aao. Ya Settings → AI Mode me Groq key lagao.'));
          }
        });
      }

      function onMsg(e) {
        if (e.origin !== PUTER_GUI_ORIGIN) return;
        var d = e.data || {};
        if (d.msg !== 'puter.token') return;
        if (d.msg_id != null && String(d.msg_id) !== String(msgId)) return;
        if (d.success && d.token) finish(function () { acceptToken(d.token, d.app_uid); });
        else finish(function () { reject(new Error('Puter sign-in complete nahi hua — puter.com tab me login pura karo, tab band mat karo.')); });
      }

      function pollOnce() {
        if (settled) return;
        try {
          if (window.puter && window.puter.auth && window.puter.auth.isSignedIn()) {
            var t = null;
            try { t = localStorage.getItem('puter.auth.token.v2'); } catch (e) {}
            if (t) { finish(function () { acceptToken(t); }); return; }
          }
          fetch(PUTER_API_ORIGIN + '/login/wait', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session: sessionId })
          }).then(function (res) {
            if (res.ok) res.json().then(function (j) {
              if (j && j.auth_token) finish(function () { acceptToken(j.auth_token); });
            }).catch(function () {});
          }).catch(function () {});
        } catch (e) {}
      }

      function onResume() { pollOnce(); }

      timer = setTimeout(function () {
        finish(function () { reject(new Error('Puter sign-in timed out — puter.com tab me login complete karke wapas aao, phir dobara "Connect Puter" dabao. Ya Groq key lagao.')); });
      }, TAB_SIGNIN_TIMEOUT_MS);

      window.addEventListener('message', onMsg);
      window.addEventListener('focus', onResume);
      document.addEventListener('visibilitychange', onResume);

      var w = null;
      try { w = window.open(url, '_blank'); } catch (e) { w = null; }
      if (!w) { finish(function () { reject(new Error('Sign-in popup blocked by browser')); }); return; }

      pollTimer = setInterval(pollOnce, 2500);
      pollOnce();
    });
  }

  function extractText(res) {
    if (!res) return '';
    if (typeof res === 'string') return res;
    if (res.message && res.message.content != null) {
      var c = res.message.content;
      if (typeof c === 'string') return c;
      if (Array.isArray(c)) return c.map(function (p) { return (p && p.text) || ''; }).join('');
      return String(c);
    }
    if (res.text != null) return String(res.text);
    if (res.content != null) return String(res.content);
    try { return JSON.stringify(res); } catch (e) { return ''; }
  }

  // Compress an image data URL → JPEG data URL (Puter OCR rejects > 10 MB).
  function compressDataUrl(dataUrl, maxDim, quality) {
    maxDim = maxDim || 1600;
    quality = (quality === undefined) ? 0.85 : quality;
    return new Promise(function (resolve) {
      var img = new Image();
      img.onload = function () {
        try {
          var w = img.width, h = img.height;
          if (w > maxDim || h > maxDim) {
            var s = Math.min(maxDim / w, maxDim / h, 1);
            w = Math.round(w * s); h = Math.round(h * s);
          }
          var canvas = document.createElement('canvas');
          canvas.width = w; canvas.height = h;
          var ctx = canvas.getContext('2d');
          if (!ctx) throw new Error('Canvas unavailable');
          ctx.drawImage(img, 0, 0, w, h);
          resolve(canvas.toDataURL('image/jpeg', quality));
        } catch (e) {
          resolve(dataUrl); // compression failed — send original rather than fail OCR
        }
      };
      img.onerror = function () { resolve(dataUrl); };
      img.src = dataUrl;
    });
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
    var dataUrl = await compressDataUrl(b64);
    var res = await window.puter.ai.img2txt(dataUrl);
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
            await signIn();
          } catch (e) {
            final = { ok: false, error: 'Puter sign-in: ' + (e && e.message ? e.message : e) };
            break;
          }
          signedInNow = await isSignedIn();
          if (!signedInNow) {
            final = { ok: false, error: 'Puter sign-in complete nahi hua. Settings ya top-right "Connect Puter" button se sign-in karo, phir dobara Generate dabao.' };
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
