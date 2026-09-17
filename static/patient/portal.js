/**
 * Patient Self-Monitoring Portal — front-end (Smart OPD).
 *
 * Design: graphs aur Excel-style table **server se HTML** aate hain
 * (`/my/<token>/content`), is liye client par koi chart code nahi hai —
 * screen aur downloaded file hamesha ek jaise rehte hain.
 */
(function () {
  'use strict';

  var CFG = window.PP_PORTAL || {};
  var TOKEN = CFG.token || '';
  var VERIFIED = !!CFG.verified;
  var METRICS = CFG.metrics || [];

  function $(id) { return document.getElementById(id); }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function show(el, text) { if (el) { el.textContent = text || ''; el.style.display = text ? 'block' : 'none'; } }

  // ─── Phone verification ────────────────────────────────────────────────────
  if (!VERIFIED) {
    var phoneInput = $('pp-phone');
    var verifyBtn = $('pp-verify-btn');
    var errBox = $('pp-verify-error');

    if (phoneInput) {
      phoneInput.addEventListener('input', function () {
        phoneInput.value = phoneInput.value.replace(/\D/g, '').slice(0, 10);
      });
      phoneInput.focus();
    }

    function doVerify() {
      var digits = (phoneInput && phoneInput.value || '').replace(/\D/g, '');
      if (digits.length < 10) {
        show(errBox, 'Kripya apna pura 10-digit mobile number dalein');
        return;
      }
      verifyBtn.disabled = true;
      verifyBtn.textContent = 'Verify ho raha hai…';
      fetch('/my/' + TOKEN + '/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone: digits })
      })
        .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
        .then(function (res) {
          if (res.ok && res.j && res.j.ok) {
            window.location.reload();
            return;
          }
          show(errBox, (res.j && res.j.error) || 'Number match nahi hua');
          verifyBtn.disabled = false;
          verifyBtn.textContent = 'Unlock Portal 🔓';
        })
        .catch(function () {
          show(errBox, 'Internet problem — dobara koshish karein');
          verifyBtn.disabled = false;
          verifyBtn.textContent = 'Unlock Portal 🔓';
        });
    }

    if (verifyBtn) verifyBtn.addEventListener('click', doVerify);
    if (phoneInput) {
      phoneInput.addEventListener('keydown', function (e) { if (e.key === 'Enter') doVerify(); });
    }
    return; // portal ke baaki hisse sirf verified state me chalte hain
  }

  // ─── Entry rows ────────────────────────────────────────────────────────────
  var rowsBox = $('pp-rows');
  var dtInput = $('pp-datetime');

  function localNow() {
    var d = new Date();
    d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
    return d.toISOString().slice(0, 16);
  }

  function metricRow(metric) {
    var div = document.createElement('div');
    div.className = 'pp-row';
    div.dataset.code = metric.code;
    div.innerHTML =
      '<span class="pp-row-label">' + esc(metric.label) + '</span>' +
      '<input class="pp-input" type="number" step="any" inputmode="decimal" placeholder="Value">' +
      '<span class="pp-row-unit">' + esc(metric.unit || '') + '</span>';
    return div;
  }

  function customRow() {
    var div = document.createElement('div');
    div.className = 'pp-row';
    div.dataset.code = 'custom';
    div.innerHTML =
      '<input class="pp-input" placeholder="Field name (Hemoglobin)" data-role="label">' +
      '<input class="pp-input" type="number" step="any" inputmode="decimal" placeholder="Value">' +
      '<input class="pp-input" placeholder="Unit (g/dL)" data-role="unit">' +
      '<button class="pp-row-remove" title="Hatao">✕</button>';
    div.querySelector('.pp-row-remove').addEventListener('click', function () { div.remove(); });
    return div;
  }

  function buildRows() {
    if (!rowsBox) return;
    rowsBox.innerHTML = '';
    METRICS.forEach(function (m) { rowsBox.appendChild(metricRow(m)); });
    if (dtInput) dtInput.value = localNow();
  }

  function collectRows() {
    var out = [];
    if (!rowsBox) return out;
    Array.prototype.forEach.call(rowsBox.children, function (row) {
      var code = row.dataset.code;
      var inputs = row.querySelectorAll('input');
      var valueInput = row.querySelector('input[type="number"]');
      if (!valueInput || valueInput.value.trim() === '') return;
      var value = Number(valueInput.value);
      if (isNaN(value)) return;
      var item = { code: code, value: value };
      if (code === 'custom') {
        var labelInput = row.querySelector('[data-role="label"]');
        var unitInput = row.querySelector('[data-role="unit"]');
        var label = (labelInput && labelInput.value || '').trim();
        if (!label) return;
        item.label = label;
        item.unit = (unitInput && unitInput.value || '').trim();
      }
      out.push(item);
    });
    return out;
  }

  function applyContent(data) {
    if (!data) return;
    if (data.trends != null && $('pp-trends')) $('pp-trends').innerHTML = data.trends;
    if (data.table != null && $('pp-table')) $('pp-table').innerHTML = data.table;
    if (data.flags != null && $('pp-flags')) $('pp-flags').innerHTML = data.flags;
    if (data.summary != null && $('pp-summary')) $('pp-summary').innerHTML = data.summary;
    if (data.count != null && $('pp-count')) $('pp-count').textContent = data.count + ' readings';
  }

  buildRows();

  if ($('pp-add-custom')) {
    $('pp-add-custom').addEventListener('click', function () { rowsBox.appendChild(customRow()); });
  }

  if ($('pp-save')) {
    $('pp-save').addEventListener('click', function () {
      var values = collectRows();
      if (!values.length) {
        show($('pp-save-err'), 'Pehle koi reading value bharo (jaise BP, sugar ya pulse)');
        return;
      }
      var btn = $('pp-save');
      btn.disabled = true;
      btn.textContent = 'Saving…';
      var dateTime = dtInput && dtInput.value ? new Date(dtInput.value).toISOString() : new Date().toISOString();
      fetch('/my/' + TOKEN + '/readings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dateTime: dateTime, values: values })
      })
        .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
        .then(function (res) {
          btn.disabled = false;
          btn.textContent = '💾 Save readings';
          if (!res.ok || !res.j || !res.j.ok) {
            show($('pp-save-err'), (res.j && res.j.error) || 'Save nahi ho paya — dobara koshish karein');
            return;
          }
          show($('pp-save-err'), '');
          applyContent(res.j);
          var msg = '✅ ' + res.j.saved.length + ' reading save ho gayi — trend graph neeche update ho gaya hai.';
          var alerts = res.j.alerts || [];
          if (alerts.length) {
            msg += ' ⚠️ ' + alerts.length + ' value normal range se bahar hai — doctor ko dikhayein.';
          }
          show($('pp-save-msg'), msg);
          buildRows();
          setTimeout(function () { show($('pp-save-msg'), ''); }, 6000);
          window.scrollTo({ top: 0, behavior: 'smooth' });
        })
        .catch(function () {
          btn.disabled = false;
          btn.textContent = '💾 Save readings';
          show($('pp-save-err'), 'Internet problem — aapki values safe hain, dobara Save dabayein');
        });
    });
  }

  // ─── Doctor share link ─────────────────────────────────────────────────────
  var shareBox = $('pp-share-box');

  function doShare(reuse) {
    var btn = reuse ? $('pp-share-refresh') : $('pp-share-btn');
    var note = ($('pp-share-note') && $('pp-share-note').value || '').trim();
    if (btn) { btn.disabled = true; btn.textContent = reuse ? 'Bhej rahe hain…' : 'Link ban raha hai…'; }
    show($('pp-share-err'), '');
    show($('pp-share-msg'), '');
    fetch('/my/' + TOKEN + '/share', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ note: note, days: CFG.shareDays || 7, reuse: !!reuse })
    })
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (res) {
        if (btn) { btn.disabled = false; btn.textContent = reuse ? '🔄 Latest data bhejo' : '🔗 Doctor ke liye link banao'; }
        if (!res.ok || !res.j || !res.j.ok) {
          show($('pp-share-err'), (res.j && res.j.error) || 'Link nahi ban paya — dobara koshish karein');
          return;
        }
        var j = res.j;
        if ($('pp-share-url')) $('pp-share-url').value = j.url;
        if ($('pp-share-wa')) $('pp-share-wa').href = j.whatsapp_url;
        if ($('pp-share-preview')) $('pp-share-preview').href = j.url;
        if ($('pp-share-valid')) {
          $('pp-share-valid').textContent = j.expires_text
            ? 'Yahi link doctor ko dikhega — valid till ' + j.expires_text + '. Naya data bharne ke baad "Latest data bhejo" dabayein, wahi link fresh ho jayega.'
            : '';
        }
        if (shareBox) shareBox.style.display = 'block';
        show($('pp-share-msg'), '✅ Link ban gaya — neeche se copy karke doctor ko WhatsApp par bhej dein.');
        if ($('pp-share-refresh')) $('pp-share-refresh').style.display = 'inline-flex';
        if ($('pp-share-btn')) $('pp-share-btn').style.display = 'none';
      })
      .catch(function () {
        if (btn) { btn.disabled = false; btn.textContent = reuse ? '🔄 Latest data bhejo' : '🔗 Doctor ke liye link banao'; }
        show($('pp-share-err'), 'Internet problem — thodi der baad dobara koshish karein');
      });
  }

  if ($('pp-share-btn')) $('pp-share-btn').addEventListener('click', function () { doShare(false); });
  if ($('pp-share-refresh')) $('pp-share-refresh').addEventListener('click', function () { doShare(true); });

  if ($('pp-share-copy')) {
    $('pp-share-copy').addEventListener('click', function () {
      var url = ($('pp-share-url') && $('pp-share-url').value) || '';
      if (!url) return;
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(url).then(function () {
          $('pp-share-copy').textContent = 'Copied ✓';
          setTimeout(function () { $('pp-share-copy').textContent = '📋 Link copy karo'; }, 2500);
        }).catch(function () {
          $('pp-share-url').select();
          show($('pp-share-err'), 'Copy nahi hua — link par ungli rakh kar "Copy" karein');
        });
      } else {
        $('pp-share-url').select();
      }
    });
  }
})();
