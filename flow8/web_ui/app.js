(() => {
  const clientId = Math.random().toString(36).slice(2);
  let session = null;
  let presets = [];
  let activeLayer = 'main'; // 'main' | 'mon1' | 'mon2' | 'fx1' | 'fx2'
  // Inspector target: null (closed), { kind: 'ch', index: 1..7 } or { kind: 'bus', id: 'main'|'mon1'|... }
  let insp = null;
  let view = 'mixer'; // 'mixer' | 'stage' | 'setup'
  let lastLiveView = 'mixer';
  let setupPage = 'inputs';

  // Settings of this device only. Storage can fail (private mode): defaults then apply.
  const PREF_DEFAULTS = { displayDb: true, finerSliders: false, recallScope: ['CH', 'FX', 'MAIN', 'MON'], librarySort: 'date' };
  const prefs = { ...PREF_DEFAULTS };
  try { Object.assign(prefs, JSON.parse(localStorage.getItem('flow8.prefs') || '{}')); } catch (_) { /* defaults */ }
  const savePrefs = () => { try { localStorage.setItem('flow8.prefs', JSON.stringify(prefs)); } catch (_) { /* not stored */ } };

  // Strip legends as printed on the FLOW 8 panel.
  const STRIP_TAG = { 1: 'MIC 1', 2: 'MIC 2', 3: 'COMBO 3', 4: 'COMBO 4', 5: 'LINE 5/6', 6: 'LINE 7/8', 7: 'USB/BT' };
  const LAYERS = {
    main: { label: 'MAIN', name: 'Main L/R', color: '#E6E8EB' },
    mon1: { label: 'MON 1', name: 'Monitor 1', color: '#34D399' },
    mon2: { label: 'MON 2', name: 'Monitor 2', color: '#34D399' },
    fx1: { label: 'FX 1', name: 'FX 1 engine', color: '#A78BFA' },
    fx2: { label: 'FX 2', name: 'FX 2 engine', color: '#A78BFA' },
  };
  const LAYER_ORDER = ['main', 'mon1', 'mon2', 'fx1', 'fx2'];
  const USB_BLUE = '#4FA8FF';
  const HUB_DEFAULT_COLOR = '#38bdf8';
  // Band labels from the FLOW 8 app. The curve is an approximate picture (conflict C-04).
  const BANDS = [
    { key: 'low', label: 'LOW', freq: 100, hz: '100 Hz', color: '#2EF2E2' },
    { key: 'low_mid', label: 'LO MID', freq: 500, hz: '500 Hz', color: '#52E59A' },
    { key: 'hi_mid', label: 'HI MID', freq: 2000, hz: '2 kHz', color: '#FFB45B' },
    { key: 'hi', label: 'HIGH', freq: 12000, hz: '12 kHz', color: '#BC71FF' },
  ];
  const GEQ_BANDS = ['63', '125', '250', '500', '1k', '2k', '4k', '8k', '16k'];
  // Preset names as the FLOW 8 app (v1.14) shows them. Tap tempo exists on FX 2 only.
  const FX_ENGINE = {
    fx1: {
      param: 'DECAY', modes: ['INSTRUMENT', 'VOCAL'], tap: false,
      presets: ['AMBIENCE', 'PERC-REV1', 'PERC-REV2', 'GUIT-REV1', 'GUIT-REV2', 'CHAMBER', 'ROOM', 'CONCERT',
        'CHURCH', 'CATHEDRAL', 'TEMPLE', 'STADIUM', 'FLANGER', 'SOFT CHOR', 'WARM CHOR', 'DEEP CHOR'],
    },
    fx2: {
      param: 'FEEDBACK', modes: ['DULL', 'BRIGHT'], tap: true,
      presets: ['DELAY 1/1', 'DELAY 1/2', 'DELAY 1/3', 'DELAY 2/1', 'ECHO 1/1', 'ECHO 1/2', 'ECHO 1/3', 'ECHO 2/1',
        'WIDE ECHO', 'PING PONG', 'PING P 1/3', 'PING P R>L', 'FLANGER', 'SOFT CHOR', 'WARM CHOR', 'DEEP CHOR'],
    },
  };
  const SCRIBBLE_PALETTE = ['#2EF2E2', '#52E59A', '#FFB45B', '#BC71FF', '#FF6BAA', '#C5FF4A', '#4FA8FF', '#D5DAE1'];
  const SCRIBBLE_NAMES = { '#2EF2E2': 'cyan', '#52E59A': 'green', '#FFB45B': 'amber', '#BC71FF': 'purple', '#FF6BAA': 'pink', '#C5FF4A': 'lime', '#4FA8FF': 'blue', '#D5DAE1': 'silver' };

  // LCD backlight colour: the hub default shows as silver, USB/BT as blue.
  const lcdColor = (ch) => (!ch.color || ch.color === HUB_DEFAULT_COLOR ? (ch.index === 7 ? USB_BLUE : '#D5DAE1') : ch.color);
  const chName = (ch) => ch.label || ch.name;

  let hubDown = false;
  let toastTimer = null;
  function showToast(message, isError = false) {
    const el = document.getElementById('toast');
    el.textContent = message;
    el.classList.toggle('error', isError);
    el.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.remove('show'), isError ? 4500 : 2200);
  }

  // Send one action. Never throws. On failure it shows the reason and reloads
  // the real state, so the screen does not keep a value the mixer never got.
  async function postAction(payload) {
    try {
      const res = await fetch('/api/action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...payload, clientId }),
      });
      let body = {};
      try { body = await res.json(); } catch (_) { /* non-JSON error body */ }
      if (!res.ok || body.ok === false) {
        showToast(body.error || `Command failed (HTTP ${res.status}).`, true);
        loadSession();
        return { ok: false, error: body.error, code: body.code };
      }
      return body;
    } catch (_) {
      showToast('Cannot reach the FLOW 8 hub. The command was not sent.', true);
      applyConnectionState(false, 'HUB UNREACHABLE — check the host computer and the Wi-Fi link.');
      return { ok: false, error: 'network' };
    }
  }

  // Show the connection state: banner, status pill, and locked controls.
  function applyConnectionState(connected, message) {
    document.body.classList.toggle('offline', !connected);
    const banner = document.getElementById('conn-banner');
    banner.hidden = connected;
    banner.textContent = message || 'MIXER NOT CONNECTED — controls are locked. Connect the FLOW 8 to the host computer by USB.';
    const pill = document.getElementById('status-pill');
    pill.classList.toggle('online', connected);
    pill.classList.toggle('offline', !connected);
    document.getElementById('status-text').textContent = connected ? 'MIXER ONLINE' : 'DISCONNECTED';
    pill.title = connected
      ? 'The FLOW 8 is connected by USB MIDI. SENT values are what this app sent; the mixer does not report every value back.'
      : 'No USB MIDI link to the FLOW 8. Commands are not sent.';
  }

  function confirmAction(title, text, okLabel, style = 'danger') {
    return new Promise((resolve) => {
      const modal = document.getElementById('confirm-modal');
      document.getElementById('confirm-title').textContent = title;
      document.getElementById('confirm-text').textContent = text;
      const ok = document.getElementById('btn-confirm-ok');
      const cancel = document.getElementById('btn-confirm-cancel');
      ok.textContent = okLabel;
      ok.className = `hw-btn ${style}`;
      const done = (v) => {
        ok.onclick = cancel.onclick = null;
        modal.onModalClose = null;
        closeModal('confirm-modal');
        resolve(v);
      };
      ok.onclick = () => done(true);
      cancel.onclick = () => done(false);
      modal.onModalClose = () => done(false); // Escape or backdrop click
      openModal('confirm-modal', cancel);
    });
  }

  // ---------- Value text ----------
  // DISPLAY DECIBEL off: show fader travel in percent, as the FLOW 8 app does.
  function midiToDbStr(raw) {
    if (!prefs.displayDb) return `${Math.round((raw / 127) * 100)}%`;
    if (raw <= 0) return '-∞ dB';
    const db = raw >= 101 ? ((raw - 101) / 26) * 10 : ((raw - 101) / 101) * 70;
    return `${db >= 0 ? '+' : ''}${db.toFixed(1)} dB`;
  }
  const eqRawToDb = (raw) => ((raw - 64) / 63.5) * 15.0;
  const dbToEqRaw = (db) => Math.max(0, Math.min(127, Math.round((Math.max(-15, Math.min(15, db)) / 15.0) * 63.5 + 64)));
  const eqText = (raw) => { const d = eqRawToDb(raw); return `${d > 0.05 ? '+' : ''}${d.toFixed(1)} dB`; };
  function panText(raw) {
    const pct = Math.round(((raw - 64) / 63.5) * 100);
    if (Math.abs(pct) <= 1) return 'C';
    return pct < 0 ? `L${Math.abs(pct)}` : `R${pct}`;
  }
  const hpfHz = (raw) => (raw <= 0 ? 'OFF' : `${Math.round(20 + (raw / 127) * 580)} Hz`);
  // Approximate preamp gain (parameter_mapping.gain_midi_to_db: -20..+60 dB linear).
  const gainText = (raw) => (raw == null ? '—' : `${Math.round(-20 + (raw / 127) * 80)} dB`);

  // Short provenance codes fit a narrow strip header. The title gives the full meaning.
  const PROV = {
    UNSYNCED: ['UNSYNC', 'Unsynced: the app does not know the mixer value yet.'],
    COMMANDED: ['SENT', 'Sent: this app sent the value. The mixer does not report it back.'],
    OBSERVED: ['LIVE', 'Live: the mixer reported this value.'],
    DISPATCH_FAILED: ['FAILED', 'Failed: the last command was rejected.'],
    UNSUPPORTED: ['N/A', 'Not available on the FLOW 8.'],
  };
  const provCode = (p) => (PROV[p] ? PROV[p][0] : p);
  const provTitle = (p) => (PROV[p] ? PROV[p][1] : p);
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const lockReason = (key) => (session && session.locked && session.locked[key]) || 'Not available over MIDI.';

  // Keyboard control for a custom slider (fader, knob, EQ band).
  // Arrow keys step 1, Page keys step 10, Home/End go to the limits.
  // The value is sent 300 ms after the last key press.
  function attachSliderKeys(el, { label, min, max, get, set, text, onCommit, focusKey }) {
    el.tabIndex = 0;
    el.dataset.focusKey = focusKey || el.dataset.focusKey || `slider:${label}`;
    el.setAttribute('role', 'slider');
    el.setAttribute('aria-label', label);
    el.setAttribute('aria-valuemin', min);
    el.setAttribute('aria-valuemax', max);
    const sync = () => {
      el.setAttribute('aria-valuenow', get());
      el.setAttribute('aria-valuetext', text(get()));
    };
    sync();
    let commitTimer = null;
    el.addEventListener('keydown', (e) => {
      const steps = { ArrowUp: 1, ArrowRight: 1, ArrowDown: -1, ArrowLeft: -1, PageUp: 10, PageDown: -10 };
      let v = get();
      if (e.key in steps) v += steps[e.key];
      else if (e.key === 'Home') v = min;
      else if (e.key === 'End') v = max;
      else return;
      e.preventDefault();
      v = Math.max(min, Math.min(max, v));
      set(v);
      sync();
      clearTimeout(commitTimer);
      commitTimer = setTimeout(() => onCommit(v), 300);
    });
    return sync;
  }

  // ---------- Live lamps and meters ----------
  // Lamp timestamps live outside the DOM, so a re-render never loses a flash.
  const LAMP_MS = 220;
  const lamps = {};   // stripId -> { rx: ms, tx: ms }
  const meters = {};  // stripId -> { peak, rms, hold, holdAt, clipAt }
  // -Infinity: nothing has happened yet, so no lamp or meter starts lit.
  let lastRxAny = -Infinity;
  let lastMeterFrame = -Infinity;
  const stripIdForChannel = (idx) => (idx === 8 ? 'main' : `ch${idx}`);
  const stripIdForParam = (pid) => String(pid).split('.')[0].replace('balance', 'main');
  function markLamp(id, kind) {
    if (!id) return;
    (lamps[id] = lamps[id] || {})[kind] = performance.now();
    if (kind === 'rx') lastRxAny = performance.now();
  }
  // Meter scale: 0 dBFS at the top, -60 dBFS at the bottom.
  const meterFrac = (db) => Math.max(0, Math.min(1, (db + 60) / 60));
  function onMeterFrame(levels) {
    const now = performance.now();
    lastMeterFrame = now;
    Object.entries(levels).forEach(([id, l]) => {
      const m = meters[id] = meters[id] || { peak: -120, rms: -120, hold: -120, holdAt: 0, clipAt: 0 };
      m.peak = l.peak;
      m.rms = l.rms;
      if (l.peak >= m.hold || now - m.holdAt > 1500) { m.hold = l.peak; m.holdAt = now; }
      if (l.peak >= -0.5) m.clipAt = now;
    });
  }
  function frame() {
    const now = performance.now();
    document.querySelectorAll('[data-lamp]').forEach((el) => {
      const [id, kind] = el.dataset.lamp.split(':');
      const t = (lamps[id] || {})[kind] ?? -Infinity;
      el.classList.toggle('on', now - t < LAMP_MS);
    });
    document.getElementById('lamp-rx').classList.toggle('on', now - lastRxAny < LAMP_MS);
    const live = now - lastMeterFrame < 2000;
    document.body.classList.toggle('meters-live', live);
    document.getElementById('lamp-meter').classList.toggle('on', live);
    if (live) {
      document.querySelectorAll('[data-meter]').forEach((el) => {
        const m = meters[el.dataset.meter];
        if (!m) return;
        el.style.setProperty('--rms', meterFrac(m.rms));
        el.style.setProperty('--peak', meterFrac(m.peak));
        el.style.setProperty('--hold', meterFrac(m.hold));
        el.classList.add('has-data');
        el.classList.toggle('sig', m.peak > -50);
        el.classList.toggle('clip', now - m.clipAt < 1500);
      });
      document.querySelectorAll('[data-sig]').forEach((el) => {
        const m = meters[el.dataset.sig];
        el.classList.toggle('on', !!m && m.peak > -50);
      });
      document.querySelectorAll('[data-meter-ring]').forEach((el) => {
        const m = meters[el.dataset.meterRing];
        if (!m) return;
        const f = meterFrac(m.rms) * 100;
        el.setAttribute('stroke-dasharray', `${f.toFixed(1)} 100`);
        el.setAttribute('stroke', now - m.clipAt < 1500 ? 'var(--led-red)' : (m.peak > -6 ? 'var(--led-amber)' : 'var(--led-green)'));
      });
    } else {
      document.querySelectorAll('[data-meter-ring]').forEach((el) => el.setAttribute('stroke-dasharray', '0 100'));
    }
    requestAnimationFrame(frame);
  }

  // ---------- EQ response (approximate picture, not a measured curve) ----------
  function eqResponseAt(freq, gains) {
    const lf = Math.log10(Math.max(20, freq));
    let total = 0;
    BANDS.forEach((b, idx) => {
      const lc = Math.log10(b.freq);
      let w = 0;
      if (idx === 0) w = 1 / (1 + Math.exp(5 * (lf - lc)));
      else if (idx === 3) w = 1 / (1 + Math.exp(-5 * (lf - lc)));
      else w = Math.exp(-Math.pow(lf - lc, 2) / (2 * Math.pow(0.28, 2)));
      total += gains[idx] * w;
    });
    return Math.max(-15, Math.min(15, total));
  }
  function eqThumbPath(ch, w = 60, h = 18) {
    const gains = BANDS.map((b) => eqRawToDb(ch.eq ? ch.eq[b.key] : 64));
    const pts = [];
    for (let i = 0; i <= 24; i++) {
      const f = 20 * Math.pow(1000, i / 24);
      const db = eqResponseAt(f, gains);
      pts.push(`${((i / 24) * w).toFixed(1)},${(h / 2 - (db / 15) * (h / 2 - 1)).toFixed(1)}`);
    }
    return `M${pts.join(' L')}`;
  }
  const freqToX = (freq, w) => 14 + ((Math.log10(freq) - Math.log10(20)) / (Math.log10(20000) - Math.log10(20))) * (w - 28);
  const dbToY = (db, h) => h / 2 - (db / 16) * (h * 0.42);
  const yToDb = (y, h) => Math.max(-15, Math.min(15, ((h / 2 - y) / (h * 0.42)) * 16));

  function drawEqCanvas(canvas, ch) {
    const ctx = canvas.getContext('2d');
    const w = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);
    ctx.lineWidth = 1;
    ctx.font = '600 11px "Barlow Condensed", sans-serif';
    [[100, '100'], [1000, '1k'], [10000, '10k']].forEach(([f, t]) => {
      const x = freqToX(f, w);
      ctx.strokeStyle = '#1F242C';
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke();
      ctx.fillStyle = '#4B525C';
      ctx.fillText(t, x + 3, h - 4);
    });
    [-10, 0, 10].forEach((d) => {
      const y = dbToY(d, h);
      ctx.strokeStyle = d === 0 ? '#2E343D' : '#1A1E25';
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
    });
    const gains = BANDS.map((b) => eqRawToDb(ch.eq[b.key]));
    const known = ch.eqProvenance === 'COMMANDED' || ch.eqProvenance === 'OBSERVED';
    ctx.beginPath();
    for (let i = 0; i <= 96; i++) {
      const f = Math.pow(10, Math.log10(20) + (i / 96) * 3);
      const x = freqToX(f, w);
      const y = dbToY(eqResponseAt(f, gains), h);
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    ctx.strokeStyle = known ? '#3FD2E0' : '#5D6A80';
    ctx.lineWidth = 2.2;
    ctx.stroke();
    ctx.lineTo(freqToX(20000, w), h / 2);
    ctx.lineTo(freqToX(20, w), h / 2);
    ctx.closePath();
    ctx.fillStyle = known ? 'rgba(63, 210, 224, 0.10)' : 'rgba(93, 106, 128, 0.07)';
    ctx.fill();
    BANDS.forEach((b, idx) => {
      ctx.beginPath();
      ctx.arc(freqToX(b.freq, w), dbToY(gains[idx], h), 7, 0, Math.PI * 2);
      ctx.fillStyle = '#0B0D10';
      ctx.fill();
      ctx.lineWidth = 2.2;
      ctx.strokeStyle = b.color;
      ctx.stroke();
    });
  }

  // Drag a band point up or down. The value is sent on release.
  function attachEqCanvas(canvas, ch, onBandMove) {
    let drag = null;
    canvas.onpointerdown = (e) => {
      const rect = canvas.getBoundingClientRect();
      const sx = ((e.clientX - rect.left) / rect.width) * canvas.width;
      const sy = ((e.clientY - rect.top) / rect.height) * canvas.height;
      let best = null;
      let bestDist = 34;
      BANDS.forEach((b) => {
        const d = Math.hypot(sx - freqToX(b.freq, canvas.width), sy - dbToY(eqRawToDb(ch.eq[b.key]), canvas.height));
        if (d < bestDist) { bestDist = d; best = b; }
      });
      if (!best) return;
      drag = best;
      canvas.setPointerCapture(e.pointerId);
    };
    canvas.onpointermove = (e) => {
      if (!drag) return;
      const rect = canvas.getBoundingClientRect();
      const sy = ((e.clientY - rect.top) / rect.height) * canvas.height;
      ch.eq[drag.key] = dbToEqRaw(yToDb(sy, canvas.height));
      drawEqCanvas(canvas, ch);
      onBandMove(drag.key, ch.eq[drag.key]);
    };
    canvas.onpointerup = (e) => {
      if (!drag) return;
      const key = drag.key;
      drag = null;
      if (canvas.hasPointerCapture(e.pointerId)) canvas.releasePointerCapture(e.pointerId);
      postAction({ action: 'setEqBand', channel: ch.index, band: key, value: ch.eq[key] });
    };
  }

  // ---------- Rotary knob ----------
  // locked: show the value, refuse input, and give the reason in the title.
  // meterSid: draw the live pre-fader level as an outer ring (stage view).
  function createRotaryKnob({ label, valueText, raw, min, max, color, bipolar = false, locked = null, focusKey, meterSid, big = false, onMove, onCommit }) {
    const cell = document.createElement('div');
    cell.className = 'knob-cell' + (locked ? ' locked' : '') + (big ? ' big' : '');
    const startDeg = -135;
    const endDeg = 135;
    const known = raw != null;
    const norm = known ? (raw - min) / (max - min) : (bipolar ? 0.5 : 0);
    const curDeg = startDeg + norm * (endDeg - startDeg);
    const polar = (deg, r) => {
      const rad = ((deg - 90) * Math.PI) / 180;
      return [26 + r * Math.cos(rad), 26 + r * Math.sin(rad)];
    };
    const arcPath = (a1, a2, r) => {
      const [x1, y1] = polar(a1, r);
      const [x2, y2] = polar(a2, r);
      const large = Math.abs(a2 - a1) > 180 ? 1 : 0;
      const sweep = a2 >= a1 ? 1 : 0;
      return `M ${x1.toFixed(1)} ${y1.toFixed(1)} A ${r} ${r} 0 ${large} ${sweep} ${x2.toFixed(1)} ${y2.toFixed(1)}`;
    };
    const arcFrom = bipolar ? 0 : startDeg;
    const [px, py] = polar(curDeg, 12);
    cell.innerHTML = `
      <span class="knob-lbl">${label}${locked ? ' <span class="lock-glyph" aria-hidden="true">●</span>' : ''}</span>
      <svg class="knob-svg" viewBox="0 0 52 52">
        ${meterSid ? `<path d="${arcPath(startDeg, endDeg, 24.6)}" fill="none" stroke="#14171C" stroke-width="2" />
        <path class="k-meter" data-meter-ring="${meterSid}" d="${arcPath(startDeg, endDeg, 24.6)}" pathLength="100" fill="none" stroke-width="2" stroke-dasharray="0 100" />` : ''}
        <path d="${arcPath(startDeg, endDeg, 21)}" fill="none" stroke="#232831" stroke-width="3.5" stroke-linecap="round" />
        <path class="k-arc" d="${known ? arcPath(arcFrom, curDeg, 21) : ''}" fill="none" stroke="${locked ? '#5D646E' : color}" stroke-width="3.5" stroke-linecap="round" />
        <circle cx="26" cy="26" r="15.5" fill="#181B21" stroke="#30353E" stroke-width="1.2" />
        <line class="k-ptr" x1="26" y1="26" x2="${px}" y2="${py}" stroke="${locked ? '#79808A' : color}" stroke-width="2.4" stroke-linecap="round" />
      </svg>
      <span class="knob-val">${valueText}</span>
    `;
    const svg = cell.querySelector('svg');
    if (locked) {
      cell.title = locked;
      svg.setAttribute('role', 'img');
      svg.setAttribute('aria-label', `${label}: ${valueText}. Locked. ${locked}`);
      return cell;
    }
    const arcEl = cell.querySelector('.k-arc');
    const ptrEl = cell.querySelector('.k-ptr');
    const valEl = cell.querySelector('.knob-val');
    let current = known ? raw : min;
    let startY = 0;
    let startVal = current;
    const updateVisual = (v) => {
      const deg = startDeg + ((v - min) / (max - min)) * (endDeg - startDeg);
      arcEl.setAttribute('d', arcPath(arcFrom, deg, 21));
      const [x, y] = polar(deg, 12);
      ptrEl.setAttribute('x2', x);
      ptrEl.setAttribute('y2', y);
      valEl.textContent = onMove(v);
    };
    svg.onpointerdown = (e) => {
      svg.setPointerCapture(e.pointerId);
      startY = e.clientY;
      startVal = current;
    };
    svg.onpointermove = (e) => {
      if (!svg.hasPointerCapture(e.pointerId)) return;
      const span = fineDrag(e) ? 560 : 140; // FINER SLIDERS or Shift: a quarter of the speed
      const delta = Math.round(((startY - e.clientY) / span) * (max - min));
      current = Math.max(min, Math.min(max, startVal + delta));
      updateVisual(current);
    };
    svg.onpointerup = (e) => {
      if (!svg.hasPointerCapture(e.pointerId)) return;
      svg.releasePointerCapture(e.pointerId);
      onCommit(current);
    };
    const syncKeys = attachSliderKeys(svg, {
      label, min, max, focusKey,
      get: () => current,
      set: (v) => { current = v; updateVisual(v); },
      text: (v) => onMove(v),
      onCommit,
    });
    svg.addEventListener('pointerup', syncKeys);
    svg.ondblclick = () => {
      current = bipolar ? Math.round((min + max) / 2) : min;
      updateVisual(current);
      onCommit(current);
    };
    return cell;
  }

  const fineDrag = (e) => prefs.finerSliders || (e && e.shiftKey);

  // Hold a key for `ms` to run onDone. A short tap runs onTap instead.
  function attachHold(btn, ms, onDone, onTap) {
    let timer = null;
    btn.style.setProperty('--hold-ms', `${ms}ms`);
    const cancel = () => {
      btn.classList.remove('holding');
      if (timer) { clearTimeout(timer); timer = null; return true; }
      return false;
    };
    btn.onpointerdown = () => {
      cancel();
      void btn.offsetWidth; // restart the progress animation
      btn.classList.add('holding');
      timer = setTimeout(() => { timer = null; btn.classList.remove('holding'); onDone(); }, ms);
    };
    btn.onpointerup = () => { if (cancel() && onTap) onTap(); };
    btn.onpointerleave = cancel;
    btn.onpointercancel = cancel;
    btn.onkeydown = (e) => {
      if (e.key !== 'Enter' && e.key !== ' ') return;
      e.preventDefault();
      if (e.repeat) return;
      btn.onpointerdown();
      const up = (ev) => { if (ev.key === e.key) { btn.removeEventListener('keyup', up); btn.onpointerup(); } };
      btn.addEventListener('keyup', up);
    };
  }

  // ---------- Fader bank ----------
  // Tick labels at the raw values that midiToDbStr() maps to +10, 0, -20 and -40 dB.
  const FADER_TICKS = `<div class="fader-ticks" aria-hidden="true">${
    [['+10', 127], ['0', 101], ['-20', 72], ['-40', 43], ['-∞', 0]]
      .map(([t, raw]) => `<div class="fader-tick" style="bottom:${((raw / 127) * 100).toFixed(2)}%">${t}</div>`).join('')
  }</div>`;

  // RX: the mixer reported a change. TX: a command went to the mixer.
  // The third lamp is steady and shows where the fader value comes from.
  const LAMPS = (sid, prov) => `
    <span class="lamp lamp-rx" data-lamp="${sid}:rx" title="RX: the mixer reported a change on this strip"></span>
    <span class="lamp lamp-tx" data-lamp="${sid}:tx" title="TX: a command went to the mixer"></span>
    <span class="lamp lamp-state state-${prov}" title="${esc(provTitle(prov))}"></span>`;
  // Meter: shown only while a measured meter feed is live (body.meters-live).
  const METER_TITLE = { main: 'Main L/R mix level from the USB capture' };
  const METER = (sid) => `
    <div class="meter" data-meter="${sid}" aria-hidden="true" title="${METER_TITLE[sid] || 'Input level before the fader (USB capture). The fader does not change it.'}">
      <div class="meter-rms"></div><div class="meter-hold"></div><span class="meter-clip"></span>
    </div>`;
  const FADER_WELL = (focusKey) => `
    <div class="fader-well" data-focus-key="${focusKey}">
      ${FADER_TICKS}
      <div class="fader-slot"></div>
      <div class="unity-mark"></div>
      <div class="fader-fill"></div>
      <div class="fader-cap"></div>
    </div>`;

  function attachVerticalFader(well, initialVal, onMove, onCommit, label) {
    let val = initialVal;
    const fill = well.querySelector('.fader-fill');
    const cap = well.querySelector('.fader-cap');
    const unity = well.querySelector('.unity-mark');
    const updatePos = (v) => {
      const h = well.clientHeight || 160;
      const usable = Math.max(40, h - 28);
      const px = 14 + (v / 127) * usable;
      fill.style.height = `${px - 14}px`;
      cap.style.bottom = `${px}px`;
      cap.dataset.v = midiToDbStr(v);
      unity.style.bottom = `${14 + (101 / 127) * usable}px`;
    };
    requestAnimationFrame(() => updatePos(val));
    const syncKeys = attachSliderKeys(well, {
      label, min: 0, max: 127,
      get: () => val,
      set: (v) => { val = v; updatePos(v); onMove(v); },
      text: (v) => midiToDbStr(v),
      onCommit,
    });
    const valFromEvent = (e) => {
      const rect = well.getBoundingClientRect();
      const usable = Math.max(40, rect.height - 28);
      const yBottom = rect.bottom - e.clientY - 14;
      return Math.max(0, Math.min(127, Math.round((yBottom / usable) * 127)));
    };
    // Normal: the cap jumps to the finger. FINER SLIDERS or Shift: the cap moves
    // from where it is, at a quarter of the finger travel.
    let fine = null;
    well.onpointerdown = (e) => {
      well.setPointerCapture(e.pointerId);
      well.classList.add('grab');
      fine = fineDrag(e) ? { y: e.clientY, v: val } : null;
      if (!fine) val = valFromEvent(e);
      updatePos(val);
      onMove(val);
    };
    well.onpointermove = (e) => {
      if (!well.hasPointerCapture(e.pointerId)) return;
      if (fine) {
        const usable = Math.max(40, well.getBoundingClientRect().height - 28);
        val = Math.max(0, Math.min(127, Math.round(fine.v + ((fine.y - e.clientY) / usable) * 127 / 4)));
      } else val = valFromEvent(e);
      updatePos(val);
      onMove(val);
    };
    well.onpointerup = (e) => {
      if (!well.hasPointerCapture(e.pointerId)) return;
      well.releasePointerCapture(e.pointerId);
      well.classList.remove('grab');
      syncKeys();
      onCommit(val);
    };
  }

  // Selecting a strip (or the master) opens the Inspector. The keyboard opens it too.
  function wireScribble(scribble, target) {
    const open = (byKey) => openInspector(target, byKey);
    scribble.onclick = () => open(false);
    scribble.onkeydown = (e) => {
      if (e.target !== scribble || (e.key !== 'Enter' && e.key !== ' ')) return;
      e.preventDefault();
      open(true);
    };
  }

  // Values of the mix on the right-hand master strip.
  function masterOf(layer) {
    if (layer === 'main') {
      const m = session.channels.find((c) => c.index === 8);
      return { sid: 'main', fader: m.fader, prov: m.faderProvenance, commit: (v) => postAction({ action: 'setFader', channel: 8, value: v }) };
    }
    const b = session.buses.find((x) => x.id === layer);
    return { sid: layer, fader: b.fader, prov: b.faderProvenance, commit: (v) => postAction({ action: 'setBusFader', bus: layer, value: v }) };
  }

  function renderConsole() {
    if (!session) return;
    applyConnectionState(!!session.midiConnected);
    const allMuted = session.channels.filter((c) => c.index <= 7).every((c) => c.mute);
    document.getElementById('btn-mute-all').textContent = allMuted ? 'UNMUTE ALL' : 'MUTE ALL';
    const bank = document.getElementById('console-bank');
    bank.innerHTML = '';
    const sendLayer = activeLayer !== 'main';
    const layer = LAYERS[activeLayer];

    session.channels.filter((c) => c.index <= 7).forEach((ch) => {
      const sid = stripIdForChannel(ch.index);
      const name = chName(ch);
      const val = sendLayer ? (ch.sends ? ch.sends[activeLayer] : 0) : ch.fader;
      const prov = sendLayer ? (ch.sends ? 'COMMANDED' : 'UNSYNCED') : ch.faderProvenance;
      const code = sendLayer ? `→${layer.label.replace(' ', '')}` : provCode(ch.faderProvenance);
      const hint = sendLayer ? `Send level from ${name} to ${layer.label}` : provTitle(ch.faderProvenance);
      const selected = insp && insp.kind === 'ch' && insp.index === ch.index;
      const strip = document.createElement('div');
      strip.dataset.strip = sid;
      strip.className = 'strip' + (ch.index === 7 ? ' usb' : '') + (selected ? ' selected' : '');
      strip.innerHTML = `
        <div class="mix-bar" aria-hidden="true"></div>
        <div class="scribble" role="button" tabindex="0" data-focus-key="scribble:${sid}" aria-label="${esc(name)}: open settings" aria-expanded="${selected}" style="--lcd:${lcdColor(ch)}">
          <div class="scribble-top">
            <span class="scribble-num">${STRIP_TAG[ch.index]}</span>
            <span class="scribble-prov" title="${esc(hint)}">${code}</span>
          </div>
          <div class="scribble-name" title="${esc(name)}">${esc(name)}</div>
        </div>
        <div class="lamp-row">${LAMPS(sid, prov)}</div>
        <svg class="eq-thumb" viewBox="0 0 60 18" preserveAspectRatio="none" aria-hidden="true"><line x1="0" y1="9" x2="60" y2="9" class="eq-thumb-zero"/><path d="${eqThumbPath(ch)}"/></svg>
        <div class="strip-pan"><span class="strip-pan-val">${panText(ch.pan)}</span></div>
        <button class="mute-switch ${ch.mute ? 'muted' : ''}" data-focus-key="mute:${sid}" aria-pressed="${ch.mute}" aria-label="Mute ${esc(name)}">${ch.mute ? 'MUTED' : 'MUTE'}</button>
        <div class="fader-zone">
          ${METER(sid)}
          ${FADER_WELL(`fader:${sid}:${activeLayer}`)}
        </div>
        <div class="strip-readout">${midiToDbStr(val)}</div>
      `;
      wireScribble(strip.querySelector('.scribble'), { kind: 'ch', index: ch.index });
      strip.querySelector('.mute-switch').onclick = () =>
        postAction({ action: 'setMute', channel: ch.index, value: !ch.mute }).then(scheduleReload);
      const readout = strip.querySelector('.strip-readout');
      attachVerticalFader(
        strip.querySelector('.fader-well'), val,
        (v) => { readout.textContent = midiToDbStr(v); },
        (v) => (sendLayer
          ? postAction({ action: 'setSend', channel: ch.index, target: activeLayer, value: v })
          : postAction({ action: 'setFader', channel: ch.index, value: v })),
        sendLayer ? `${name} send to ${layer.label}` : `${name} fader`
      );
      bank.appendChild(strip);
    });

    // The master strip follows the selected mix, as on the FLOW 8 app.
    const m = masterOf(activeLayer);
    const selected = insp && insp.kind === 'bus' && insp.id === activeLayer;
    const strip = document.createElement('div');
    strip.dataset.strip = m.sid;
    strip.className = 'strip master' + (selected ? ' selected' : '');
    strip.innerHTML = `
      <div class="mix-bar" aria-hidden="true"></div>
      <div class="scribble master-lcd" role="button" tabindex="0" data-focus-key="scribble:master" aria-label="${layer.label} master: open settings" aria-expanded="${selected}">
        <div class="scribble-top">
          <span class="scribble-num">MASTER</span>
          <span class="scribble-prov" title="${esc(provTitle(m.prov))}">${provCode(m.prov)}</span>
        </div>
        <div class="scribble-name">${layer.label}</div>
      </div>
      <div class="lamp-row">${LAMPS(m.sid, m.prov)}</div>
      <div class="eq-thumb eq-thumb-none">${activeLayer.startsWith('fx') ? 'FX RETURN' : 'GEQ · LIMIT'}</div>
      <div class="strip-pan"><span class="strip-pan-val">${activeLayer === 'main' ? `BAL ${panText(session.channels.find((c) => c.index === 8).pan)}` : 'BUS'}</span></div>
      <div class="mute-na" title="The FLOW 8 has no MIDI mute for the ${layer.label} bus.">NO MUTE</div>
      <div class="fader-zone">
        ${METER(m.sid)}
        ${FADER_WELL(`fader:master:${activeLayer}`)}
      </div>
      <div class="strip-readout">${midiToDbStr(m.fader)}</div>
    `;
    wireScribble(strip.querySelector('.scribble'), { kind: 'bus', id: activeLayer });
    const readout = strip.querySelector('.strip-readout');
    attachVerticalFader(strip.querySelector('.fader-well'), m.fader,
      (v) => { readout.textContent = midiToDbStr(v); }, m.commit, `${layer.label} master fader`);
    bank.appendChild(strip);
    requestAnimationFrame(updateScrollHint);
  }

  // Fade the right edge while more strips are off screen.
  function updateScrollHint() {
    const bank = document.getElementById('console-bank');
    const more = bank.scrollWidth - bank.clientWidth - bank.scrollLeft > 4;
    bank.classList.toggle('scroll-more', more);
  }
  document.getElementById('console-bank').addEventListener('scroll', updateScrollHint, { passive: true });
  window.addEventListener('resize', updateScrollHint);

  // ---------- Inspector ----------
  const INSP_ORDER = [1, 2, 3, 4, 5, 6, 7].map((i) => ({ kind: 'ch', index: i }))
    .concat(LAYER_ORDER.map((id) => ({ kind: 'bus', id })));
  const sameTarget = (a, b) => !!a && !!b && a.kind === b.kind && (a.kind === 'ch' ? a.index === b.index : a.id === b.id);

  function openInspector(target, focusTitle = false) {
    insp = target;
    // A bus Inspector shows that mix on the faders, so the two views agree.
    if (target.kind === 'bus' && target.id !== activeLayer) setLayer(target.id, false);
    renderView();
    if (focusTitle) document.getElementById('insp-title').focus({ preventScroll: true });
  }
  function closeInspector() {
    if (!insp) return;
    const was = insp;
    insp = null;
    renderView();
    const back = document.querySelector(was.kind === 'ch' ? `[data-focus-key="scribble:ch${was.index}"]` : '[data-focus-key="scribble:master"]');
    if (back) back.focus({ preventScroll: true });
  }
  function stepInspector(dir) {
    const i = INSP_ORDER.findIndex((t) => sameTarget(t, insp));
    openInspector(INSP_ORDER[(i + dir + INSP_ORDER.length) % INSP_ORDER.length]);
  }

  function section(title, meta, locked) {
    const el = document.createElement('section');
    el.className = 'insp-sec' + (locked ? ' locked' : '');
    el.innerHTML = `
      <div class="sec-hdr"><span class="sec-title">${title}</span>${meta ? `<span class="sec-meta">${meta}</span>` : ''}</div>
      ${locked ? `<p class="lock-note"><span class="lock-chip">LOCKED</span>${esc(locked)}</p>` : ''}`;
    const body = document.createElement('div');
    body.className = 'sec-body';
    el.appendChild(body);
    return { el, body };
  }

  // A labelled horizontal level control (send or bus level).
  function levelRow({ label, color, value, aria, focusKey, onCommit, disabled = false }) {
    const row = document.createElement('div');
    row.className = 'level-row';
    row.style.setProperty('--c', color);
    row.innerHTML = `
      <span class="level-lbl">${label}</span>
      <input class="studio-range" type="range" min="0" max="127" value="${value}" data-focus-key="${focusKey}"
        aria-label="${esc(aria)}" aria-valuetext="${midiToDbStr(value)}" ${disabled ? 'disabled' : ''} />
      <span class="level-val">${midiToDbStr(value)}</span>`;
    const rng = row.querySelector('input');
    const paint = () => rng.style.setProperty('--fill', `${(rng.value / 127) * 100}%`);
    paint();
    rng.oninput = () => {
      row.querySelector('.level-val').textContent = midiToDbStr(+rng.value);
      rng.setAttribute('aria-valuetext', midiToDbStr(+rng.value));
      paint();
    };
    rng.onchange = () => onCommit(+rng.value);
    return row;
  }

  function renderInspector() {
    const aside = document.getElementById('inspector');
    const show = !!insp && !!session && view !== 'setup';
    document.body.classList.toggle('insp-open', show);
    if (!show) { aside.hidden = true; return; }
    aside.hidden = false;
    const body = document.getElementById('insp-body');
    const scroll = body.scrollTop;
    body.innerHTML = '';
    if (insp.kind === 'ch') renderChannelInspector(body, session.channels.find((c) => c.index === insp.index));
    else renderBusInspector(body, insp.id);
    body.scrollTop = scroll;
  }

  function renderChannelInspector(body, ch) {
    const name = chName(ch);
    const idx = ch.index;
    const sid = `ch${idx}`;
    const chip = document.getElementById('insp-chip');
    chip.textContent = STRIP_TAG[idx];
    chip.style.setProperty('--lcd', lcdColor(ch));
    document.getElementById('insp-title').textContent = name;
    document.getElementById('insp-sub').textContent = `Fader ${midiToDbStr(ch.fader)} · ${provCode(ch.faderProvenance)}`;
    const aside = document.getElementById('inspector');
    aside.style.setProperty('--insp-accent', lcdColor(ch));

    // Channel keys: mute, solo, rename, presets.
    const keys = document.createElement('div');
    keys.className = 'insp-keys';
    keys.innerHTML = `
      <button class="mute-switch ${ch.mute ? 'muted' : ''}" data-focus-key="insp-mute" aria-pressed="${ch.mute}">${ch.mute ? 'MUTED' : 'MUTE'}</button>
      <button class="key-btn locked" data-focus-key="insp-solo" aria-disabled="true" title="${esc(lockReason('solo'))}">SOLO</button>
      <button class="key-btn" data-focus-key="insp-rename">✎ RENAME</button>
      <button class="key-btn accent" data-focus-key="insp-presets">★ PRESETS</button>`;
    keys.children[0].onclick = () => postAction({ action: 'setMute', channel: idx, value: !ch.mute }).then(scheduleReload);
    keys.children[1].onclick = () => showToast(lockReason('solo'));
    keys.children[2].onclick = () => openScribbleModal(ch);
    keys.children[3].onclick = () => openPresetsModal(idx);
    body.appendChild(keys);

    // Input stage.
    const has14 = idx <= 4;
    const input = section('INPUT', has14 ? (idx <= 2 ? 'MIC · XLR' : 'COMBO · XLR / TRS') : (idx === 7 ? 'USB / BLUETOOTH' : 'STEREO LINE'));
    const knobs = document.createElement('div');
    knobs.className = 'knob-row';
    if (has14) {
      knobs.appendChild(createRotaryKnob({
        label: 'GAIN', valueText: gainText(ch.gain), raw: ch.gain, min: 0, max: 127, color: '#FFB020',
        locked: lockReason('gain'),
      }));
      knobs.appendChild(createRotaryKnob({
        label: 'LOW CUT', valueText: hpfHz(ch.lowCut), raw: ch.lowCut, min: 0, max: 127, color: '#FFB020',
        focusKey: `insp:${sid}:lowcut`,
        onMove: hpfHz,
        onCommit: (v) => postAction({ action: 'setLowCut', channel: idx, value: v }),
      }));
      knobs.appendChild(createRotaryKnob({
        label: 'COMP', valueText: `${ch.compressor}%`, raw: ch.compressor, min: 0, max: 100, color: '#A78BFA',
        focusKey: `insp:${sid}:comp`,
        onMove: (v) => `${v}%`,
        onCommit: (v) => postAction({ action: 'setCompressor', channel: idx, value: v }),
      }));
    }
    knobs.appendChild(createRotaryKnob({
      label: has14 ? 'PAN' : 'BALANCE', valueText: panText(ch.pan), raw: ch.pan, min: 0, max: 127, color: '#3FD2E0', bipolar: true,
      focusKey: `insp:${sid}:pan`,
      onMove: panText,
      onCommit: (v) => postAction({ action: 'setPan', channel: idx, value: v }),
    }));
    input.body.appendChild(knobs);
    if (idx <= 2) input.body.appendChild(phantomKey(ch));
    if (!has14) {
      const note = document.createElement('p');
      note.className = 'sec-note';
      note.textContent = 'Gain, low cut and compressor exist on CH 1–4 only.';
      input.body.appendChild(note);
    }
    body.appendChild(input.el);

    // 4-band EQ.
    const eq = section('EQ · 4-BAND', `<span title="${esc(provTitle(ch.eqProvenance))}">${provCode(ch.eqProvenance)}</span>`);
    const flat = document.createElement('button');
    flat.className = 'key-btn small';
    flat.textContent = 'FLAT';
    flat.dataset.focusKey = 'insp-eq-flat';
    flat.setAttribute('aria-label', `Reset the EQ of ${name} to flat`);
    flat.onclick = () => postAction({ action: 'resetEqFlat', channel: idx }).then(loadSession);
    eq.el.querySelector('.sec-hdr').appendChild(flat);
    const canvas = document.createElement('canvas');
    canvas.id = 'eq-canvas';
    canvas.width = 560;
    canvas.height = 150;
    canvas.setAttribute('aria-label', 'Approximate EQ curve. Drag a band point, or use the band knobs below.');
    eq.body.appendChild(canvas);
    const bandRow = document.createElement('div');
    bandRow.className = 'knob-row bands';
    const bandVal = {};
    BANDS.forEach((b) => {
      const cell = createRotaryKnob({
        label: `${b.label}`, valueText: eqText(ch.eq[b.key]), raw: ch.eq[b.key], min: 0, max: 127, color: b.color, bipolar: true,
        focusKey: `insp:${sid}:eq:${b.key}`,
        onMove: (v) => { ch.eq[b.key] = v; drawEqCanvas(canvas, ch); return eqText(v); },
        onCommit: (v) => postAction({ action: 'setEqBand', channel: idx, band: b.key, value: v }),
      });
      const hz = document.createElement('span');
      hz.className = 'knob-hz';
      hz.textContent = b.hz;
      cell.appendChild(hz);
      bandVal[b.key] = cell.querySelector('.knob-val');
      bandRow.appendChild(cell);
    });
    eq.body.appendChild(bandRow);
    const eqNote = document.createElement('p');
    eqNote.className = 'sec-note';
    eqNote.textContent = 'The curve is an approximate picture. Band gain values are exact.';
    eq.body.appendChild(eqNote);
    body.appendChild(eq.el);
    drawEqCanvas(canvas, ch);
    attachEqCanvas(canvas, ch, (key, v) => { bandVal[key].textContent = eqText(v); });

    // Sends.
    const sends = section('SENDS', 'POST-FADER LEVELS');
    ['mon1', 'mon2', 'fx1', 'fx2'].forEach((t) => {
      sends.body.appendChild(levelRow({
        label: LAYERS[t].label, color: LAYERS[t].color, value: ch.sends ? ch.sends[t] : 0,
        aria: `${name} send to ${LAYERS[t].label}`, focusKey: `insp:${sid}:send:${t}`,
        onCommit: (v) => postAction({ action: 'setSend', channel: idx, target: t, value: v }),
      }));
    });
    body.appendChild(sends.el);
  }

  // +48V: hold 1 s to switch, as on the FLOW 8 app. While the hub policy locks
  // +48V, the key shows the mixer state and a tap explains the lock.
  function phantomKey(ch) {
    const wrap = document.createElement('div');
    wrap.className = 'phantom-row';
    const allowed = !!(session.lanPolicy && session.lanPolicy.phantom);
    const state = ch.phantom == null ? 'UNKNOWN' : (ch.phantom ? 'ON' : 'OFF');
    wrap.innerHTML = `
      <button class="phantom-key ${ch.phantom ? 'on' : ''} ${allowed ? '' : 'locked'}" data-focus-key="insp:ch${ch.index}:48v"
        aria-label="+48V phantom power on ${esc(chName(ch))}: ${state}. ${allowed ? 'Hold for 1 second to switch.' : 'Locked.'}">
        <span class="phantom-led" aria-hidden="true"></span>+48V
      </button>
      <span class="phantom-text">${state === 'UNKNOWN' ? 'State unknown' : `Phantom ${state}`} · ${allowed ? 'hold 1 s to switch' : 'host only'}</span>`;
    const btn = wrap.querySelector('button');
    if (!allowed) {
      btn.title = lockReason('phantom');
      btn.onclick = () => showToast(lockReason('phantom'));
    } else {
      attachHold(btn, 1000,
        () => postAction({ action: 'setPhantom', channel: ch.index, value: !ch.phantom }).then(scheduleReload),
        () => showToast('Hold +48V for 1 second to switch it.'));
    }
    return wrap;
  }

  function renderBusInspector(body, id) {
    const layer = LAYERS[id];
    const m = masterOf(id);
    const chip = document.getElementById('insp-chip');
    chip.textContent = id.startsWith('fx') ? 'FX' : 'BUS';
    chip.style.setProperty('--lcd', layer.color);
    document.getElementById('insp-title').textContent = layer.label;
    document.getElementById('insp-sub').textContent = `${layer.name} · ${provCode(m.prov)}`;
    document.getElementById('inspector').style.setProperty('--insp-accent', layer.color);

    const lvl = section(id.startsWith('fx') ? 'FX RETURN LEVEL' : 'LEVEL', provCode(m.prov));
    lvl.body.appendChild(levelRow({
      label: 'LEVEL', color: layer.color, value: m.fader, aria: `${layer.label} level`, focusKey: `insp:${id}:level`,
      onCommit: m.commit,
    }));
    if (id === 'main') {
      const main = session.channels.find((c) => c.index === 8);
      const row = document.createElement('div');
      row.className = 'knob-row';
      row.appendChild(createRotaryKnob({
        label: 'BALANCE', valueText: panText(main.pan), raw: main.pan, min: 0, max: 127, color: '#3FD2E0', bipolar: true,
        focusKey: 'insp:main:balance',
        onMove: panText,
        onCommit: (v) => postAction({ action: 'setPan', channel: 8, value: v }),
      }));
      lvl.body.appendChild(row);
    }
    body.appendChild(lvl.el);

    if (!id.startsWith('fx')) {
      const lim = section('LIMITER', 'THRESHOLD', lockReason('limiter'));
      const row = document.createElement('div');
      row.className = 'knob-row';
      row.appendChild(createRotaryKnob({ label: 'LIMIT', valueText: '—', raw: null, min: 0, max: 127, color: '#FFB020', locked: lockReason('limiter') }));
      lim.body.appendChild(row);
      body.appendChild(lim.el);

      const geq = section('GRAPHIC EQ · 9-BAND', '±15 dB', lockReason('geq'));
      const grid = document.createElement('div');
      grid.className = 'geq';
      grid.setAttribute('role', 'img');
      grid.setAttribute('aria-label', '9-band graphic EQ. Values unknown. Locked.');
      grid.innerHTML = GEQ_BANDS.map((f) => `
          <div class="geq-band">
            <div class="geq-track"><div class="geq-zero"></div><div class="geq-cap"></div></div>
            <span class="geq-val">—</span>
            <span class="geq-hz">${f}</span>
          </div>`).join('');
      geq.body.appendChild(grid);
      body.appendChild(geq.el);
      return;
    }

    const fx = FX_ENGINE[id];
    const eng = section(`${layer.label} ENGINE`, '16 PRESETS', lockReason('fx'));
    const row = document.createElement('div');
    row.className = 'fx-top';
    row.appendChild(createRotaryKnob({ label: fx.param, valueText: '—', raw: null, min: 0, max: 100, color: '#A78BFA', locked: lockReason('fx') }));
    const side = document.createElement('div');
    side.className = 'fx-side';
    side.innerHTML = `
      <div class="seg" role="group" aria-label="${fx.param} mode (locked)">
        ${fx.modes.map((md) => `<button class="seg-btn" aria-disabled="true" title="${esc(lockReason('fx'))}">${md}</button>`).join('')}
      </div>
      ${fx.tap ? `<button class="tap-pad" aria-disabled="true" title="${esc(lockReason('tap'))}">TAP TEMPO · — BPM</button>` : ''}
      <button class="key-btn locked fx-mute" aria-disabled="true" title="${esc(lockReason('fx'))}">FX MUTE</button>`;
    side.querySelectorAll('button').forEach((b) => { b.onclick = () => showToast(lockReason(b.classList.contains('tap-pad') ? 'tap' : 'fx')); });
    row.appendChild(side);
    eng.body.appendChild(row);
    const grid = document.createElement('div');
    grid.className = 'fx-grid';
    grid.setAttribute('role', 'group');
    grid.setAttribute('aria-label', `${layer.label} presets (locked)`);
    for (let i = 1; i <= 16; i++) {
      const b = document.createElement('button');
      b.className = 'fx-preset';
      b.innerHTML = `<span class="fx-name">${esc(fx.presets[i - 1])}</span><span class="fx-no">No. ${i}</span>`;
      b.setAttribute('aria-disabled', 'true');
      b.title = lockReason('fx');
      b.onclick = () => showToast(lockReason('fx'));
      grid.appendChild(b);
    }
    eng.body.appendChild(grid);
    body.appendChild(eng.el);
  }

  // ---------- Stage view ----------
  // Large level knobs for the mix on the faders, with the live input level as a ring.
  function renderStage() {
    const host = document.getElementById('stage-view');
    host.innerHTML = '';
    const sendLayer = activeLayer !== 'main';
    const layer = LAYERS[activeLayer];
    session.channels.filter((c) => c.index <= 7).forEach((ch) => {
      const sid = stripIdForChannel(ch.index);
      const name = chName(ch);
      const val = sendLayer ? (ch.sends ? ch.sends[activeLayer] : 0) : ch.fader;
      const card = document.createElement('div');
      card.className = 'stage-card' + (ch.index === 7 ? ' usb' : '');
      card.dataset.strip = sid;
      card.innerHTML = `
        <div class="mix-bar" aria-hidden="true"></div>
        <div class="scribble" role="button" tabindex="0" data-focus-key="stage-scribble:${sid}" aria-label="${esc(name)}: open settings" style="--lcd:${lcdColor(ch)}">
          <div class="scribble-top"><span class="scribble-num">${STRIP_TAG[ch.index]}</span><span class="scribble-prov">${sendLayer ? `→${layer.label.replace(' ', '')}` : ''}</span></div>
          <div class="scribble-name">${esc(name)}</div>
        </div>`;
      const knob = createRotaryKnob({
        label: sendLayer ? `SEND ${layer.label}` : 'LEVEL',
        valueText: midiToDbStr(val), raw: val, min: 0, max: 127, color: layer.color, big: true,
        meterSid: ch.index <= 6 ? sid : null,
        focusKey: `stage:${sid}:${activeLayer}`,
        onMove: midiToDbStr,
        onCommit: (v) => (sendLayer
          ? postAction({ action: 'setSend', channel: ch.index, target: activeLayer, value: v })
          : postAction({ action: 'setFader', channel: ch.index, value: v })),
      });
      card.appendChild(knob);
      const mute = document.createElement('button');
      mute.className = `mute-switch ${ch.mute ? 'muted' : ''}`;
      mute.dataset.focusKey = `stage-mute:${sid}`;
      mute.setAttribute('aria-pressed', ch.mute);
      mute.setAttribute('aria-label', `Mute ${name}`);
      mute.textContent = ch.mute ? 'MUTED' : 'MUTE';
      mute.onclick = () => postAction({ action: 'setMute', channel: ch.index, value: !ch.mute }).then(scheduleReload);
      card.appendChild(mute);
      wireScribble(card.querySelector('.scribble'), { kind: 'ch', index: ch.index });
      host.appendChild(card);
    });
    const tap = document.createElement('div');
    tap.className = 'stage-card tap-card';
    tap.innerHTML = `
      <div class="mix-bar" aria-hidden="true"></div>
      <span class="sec-title">FX 2 · TAP TEMPO</span>
      <button class="tap-pad big" aria-disabled="true" title="${esc(lockReason('tap'))}"><span class="bpm">— BPM</span><span>TAP</span></button>
      <p class="lock-note"><span class="lock-chip">LOCKED</span>${esc(lockReason('tap'))}</p>`;
    tap.querySelector('button').onclick = () => showToast(lockReason('tap'));
    host.appendChild(tap);
  }

  // ---------- Setup view ----------
  const SETUP_PAGES = {
    inputs: renderInputsPage, snapshots: renderSnapshotsPage, library: renderLibraryPage,
    prefs: renderPrefsPage, routing: renderRoutingPage, info: renderInfoPage,
  };
  function renderSetup() {
    document.querySelectorAll('.setup-tab').forEach((t) => {
      const on = t.dataset.page === setupPage;
      t.classList.toggle('active', on);
      t.setAttribute('aria-current', on ? 'page' : 'false');
    });
    const page = document.getElementById('setup-page');
    const scroll = page.scrollTop;
    page.innerHTML = '';
    SETUP_PAGES[setupPage](page);
    page.scrollTop = scroll;
  }
  function pageHead(page, title, actions = '') {
    const head = document.createElement('div');
    head.className = 'page-head';
    head.innerHTML = `<h2 class="page-title">${title}</h2><div class="page-actions">${actions}</div>`;
    page.appendChild(head);
    return head;
  }
  function lockedNote(key) {
    const p = document.createElement('p');
    p.className = 'lock-note';
    p.innerHTML = `<span class="lock-chip">LOCKED</span>${esc(lockReason(key))}`;
    return p;
  }
  // A checkbox row. locked: shown, not changeable.
  function checkRow(label, checked, { locked = null, radio = false, onChange } = {}) {
    const row = document.createElement('label');
    row.className = 'check-row' + (locked ? ' locked' : '');
    row.innerHTML = `<input type="${radio ? 'radio' : 'checkbox'}" ${checked ? 'checked' : ''} ${locked ? 'disabled' : ''} /><span class="check-box ${radio ? 'radio' : ''}" aria-hidden="true"></span><span>${label}</span>`;
    if (locked) row.title = locked;
    else row.querySelector('input').onchange = (e) => onChange(e.target.checked);
    return row;
  }

  // Jack drawings: XLR, combo (XLR + 1/4"), 1/4" TRS.
  const JACK_SVG = {
    xlr: '<svg viewBox="0 0 64 64" aria-hidden="true"><circle cx="32" cy="32" r="27" class="j-ring"/><circle cx="32" cy="32" r="21" class="j-face"/><circle cx="22" cy="27" r="3.4" class="j-pin"/><circle cx="42" cy="27" r="3.4" class="j-pin"/><circle cx="32" cy="42" r="3.4" class="j-pin"/><rect x="29" y="8" width="6" height="5" rx="1" class="j-pin"/></svg>',
    combo: '<svg viewBox="0 0 64 64" aria-hidden="true"><circle cx="32" cy="32" r="27" class="j-ring"/><circle cx="32" cy="32" r="21" class="j-face"/><circle cx="20" cy="24" r="3" class="j-pin"/><circle cx="44" cy="24" r="3" class="j-pin"/><circle cx="32" cy="46" r="3" class="j-pin"/><circle cx="32" cy="31" r="7.5" class="j-hole"/></svg>',
    trs: '<svg viewBox="0 0 64 64" aria-hidden="true"><circle cx="32" cy="32" r="22" class="j-ring"/><circle cx="32" cy="32" r="15" class="j-face"/><circle cx="32" cy="32" r="7.5" class="j-hole"/></svg>',
  };
  const JACKS = [
    { label: 'MIC', num: 1, jack: 'xlr', meter: 'ch1', ch: 1 },
    { label: 'MIC', num: 2, jack: 'xlr', meter: 'ch2', ch: 2 },
    { label: 'COMBO', num: 3, jack: 'combo', meter: 'ch3', ch: 3 },
    { label: 'COMBO', num: 4, jack: 'combo', meter: 'ch4', ch: 4 },
    { label: 'LINE', num: 5, jack: 'trs', meter: 'in5', ch: 5 },
    { label: 'LINE', num: 6, jack: 'trs', meter: 'in6', ch: 5, hiz: true },
    { label: 'LINE', num: 7, jack: 'trs', meter: 'in7', ch: 6 },
    { label: 'LINE', num: 8, jack: 'trs', meter: 'in8', ch: 6, hiz: true },
  ];
  function renderInputsPage(page) {
    pageHead(page, 'CONFIGURE INPUTS');
    const grid = document.createElement('div');
    grid.className = 'jack-grid';
    JACKS.forEach((j) => {
      const ch = session.channels.find((c) => c.index === j.ch);
      const card = document.createElement('div');
      card.className = 'jack-card';
      card.innerHTML = `
        <div class="jack-tag"><span>${j.label}</span><b>${j.num}</b></div>
        <div class="jack-art">${JACK_SVG[j.jack]}${j.hiz ? '<span class="hiz" title="Hi-Z input: plug a guitar or bass in here directly.">🎸 HI-Z</span>' : ''}</div>
        <div class="meter h" data-meter="${j.meter}" title="Input level from the USB capture"><div class="meter-rms"></div><div class="meter-hold"></div><span class="meter-clip"></span></div>
        <div class="jack-foot"><span class="jack-ch">→ ${esc(chName(ch))}</span><span class="lamp lamp-link" data-sig="${j.meter}" title="Lit while the input has signal"></span></div>`;
      if (j.ch <= 2) card.appendChild(phantomKey(ch));
      grid.appendChild(card);
    });
    // Stereo / mono link between the jacks of each line pair, below the jacks.
    JACKS.forEach((j) => {
      if (j.num === 6 || j.num === 8) {
        const link = document.createElement('div');
        link.className = 'pair-link';
        link.innerHTML = `<span class="sec-meta">LINE ${j.num - 1}/${j.num}</span>
          <div class="seg"><button class="seg-btn" aria-disabled="true">STEREO</button><button class="seg-btn" aria-disabled="true">MONO</button></div>`;
        link.querySelectorAll('button').forEach((b) => { b.title = lockReason('stereoLink'); b.onclick = () => showToast(lockReason('stereoLink')); });
        grid.appendChild(link);
      }
    });
    page.appendChild(grid);
    page.appendChild(lockedNote('stereoLink'));
    const note = document.createElement('p');
    note.className = 'sec-note';
    note.textContent = 'Meters show the level before the fader (FLOW 8 in Recording Mode). Gain stays on the mixer.';
    page.appendChild(note);
  }

  function scopeSummary(sc) {
    return Object.entries(sc || {}).filter(([, n]) => n).map(([k]) => k).join(' · ') || 'empty';
  }
  function whatToLoad() {
    const box = document.createElement('div');
    box.className = 'what-to-load';
    box.innerHTML = '<span class="sec-title">WHAT TO LOAD</span>';
    (session.recallScopes || ['CH', 'FX', 'MAIN', 'MON']).forEach((sc) => {
      box.appendChild(checkRow(sc, prefs.recallScope.includes(sc), {
        onChange: (on) => {
          prefs.recallScope = on ? [...new Set([...prefs.recallScope, sc])] : prefs.recallScope.filter((x) => x !== sc);
          savePrefs();
        },
      }));
    });
    box.appendChild(checkRow('ROUT', false, { locked: lockReason('routing') }));
    return box;
  }
  const recallScope = () => (session.recallScopes || []).filter((s) => prefs.recallScope.includes(s));
  const fullScope = () => recallScope().length === (session.recallScopes || []).length;

  function renderSnapshotsPage(page) {
    pageHead(page, 'MIXER SNAPSHOTS');
    const wrap = document.createElement('div');
    wrap.className = 'snap-wrap';
    const grid = document.createElement('div');
    grid.className = 'snap-grid';
    const info = Object.fromEntries((session.sceneInfo || []).map((i) => [i.name, i]));
    for (let i = 1; i <= (session.sceneSlots || 15); i++) {
      const name = `SCENE ${i}`;
      const slot = info[name];
      const num = String(i).padStart(2, '0');
      const pad = document.createElement('button');
      pad.className = 'snap-slot' + (slot ? ' saved' : '') + (session.currentScene === name ? ' current' : '');
      pad.dataset.focusKey = `snap:${i}`;
      const time = slot ? new Date(slot.capturedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false }) : '';
      pad.innerHTML = `<span class="snap-num">${num}</span><span class="snap-body">${slot ? `<b>${time}</b><small>${scopeSummary(slot.scopes)}</small>` : '<small>EMPTY · HOLD TO SAVE</small>'}</span>`;
      pad.setAttribute('aria-label', slot
        ? `Snapshot ${num}, saved ${time}: tap or Enter to recall, hold or Shift+Enter to overwrite`
        : `Snapshot ${num}: empty, hold or Shift+Enter to save`);
      const save = async () => {
        if (slot && !(await confirmAction(`OVERWRITE ${num}?`, `Snapshot ${num} already holds a mix. Save the current mix over it?`, 'OVERWRITE'))) return;
        const res = await postAction({ action: 'captureScene', name });
        if (res.ok) showToast(`Saved the current mix to ${num}.`);
        loadSession();
      };
      const recall = async () => {
        if (!slot) { showToast(`${num} is empty. Hold the slot (or press Shift+Enter) to save the current mix.`); return; }
        const scope = recallScope();
        if (!scope.length) { showToast('Select at least one item under WHAT TO LOAD.', true); return; }
        const res = await postAction({ action: 'recallScene', name, scope: fullScope() ? undefined : scope });
        if (res.ok) showToast(`Recalled ${num}${fullScope() ? '' : ` (${scope.join(', ')} only)`}.`);
        loadSession();
      };
      attachHold(pad, 550, save, recall);
      pad.onkeydown = (e) => {
        if (e.key !== 'Enter' && e.key !== ' ') return;
        e.preventDefault();
        if (e.shiftKey) save(); else recall();
      };
      grid.appendChild(pad);
    }
    const reset = document.createElement('button');
    reset.className = 'snap-slot reset';
    reset.setAttribute('aria-disabled', 'true');
    reset.title = lockReason('hwSnapshots');
    reset.innerHTML = '<span class="snap-num">RESET</span><span class="snap-body"><small>LOCKED</small></span>';
    reset.onclick = () => showToast(lockReason('hwSnapshots'));
    grid.appendChild(reset);
    wrap.appendChild(grid);
    const side = whatToLoad();
    side.appendChild(Object.assign(document.createElement('p'), {
      className: 'sec-note',
      textContent: 'Tap a slot to recall, hold to save. Recall is one undo step. Gain and +48V are never stored.',
    }));
    wrap.appendChild(side);
    page.appendChild(wrap);
    page.appendChild(lockedNote('hwSnapshots'));
  }

  let libraryQuery = '';
  function renderLibraryPage(page) {
    pageHead(page, 'SNAPSHOT LIBRARY', `
      <button class="key-btn icon-btn ${prefs.librarySort === 'date' ? 'on' : ''}" data-sort="date" aria-pressed="${prefs.librarySort === 'date'}" title="Sort by date">DATE</button>
      <button class="key-btn icon-btn ${prefs.librarySort === 'name' ? 'on' : ''}" data-sort="name" aria-pressed="${prefs.librarySort === 'name'}" title="Sort by name">A–Z</button>
      <button class="key-btn" id="lib-import">IMPORT</button>
      <a class="key-btn" id="lib-export" href="/api/library/export" download="flow8-snapshot-library.json">EXPORT</a>
      <button class="key-btn accent" id="lib-new">NEW</button>`);
    page.querySelectorAll('[data-sort]').forEach((b) => {
      b.onclick = () => { prefs.librarySort = b.dataset.sort; savePrefs(); renderSetup(); };
    });
    page.querySelector('#lib-new').onclick = async () => {
      const name = await promptName('NEW SNAPSHOT', '', 'SAVE');
      if (!name) return;
      const res = await postAction({ action: 'librarySave', name });
      if (res.ok) showToast(`Saved the current mix as "${res.name}".`);
      loadSession();
    };
    page.querySelector('#lib-import').onclick = () => document.getElementById('library-file').click();

    const search = document.createElement('input');
    search.className = 'text-input search';
    search.type = 'search';
    search.placeholder = 'Search snapshots';
    search.value = libraryQuery;
    search.dataset.focusKey = 'lib-search';
    search.setAttribute('aria-label', 'Search snapshots');
    page.appendChild(search);
    const wrap = document.createElement('div');
    wrap.className = 'snap-wrap';
    const list = document.createElement('div');
    list.className = 'lib-list';
    list.setAttribute('role', 'list');
    wrap.appendChild(list);
    wrap.appendChild(whatToLoad());
    page.appendChild(wrap);
    if (session.libraryError) page.insertBefore(Object.assign(document.createElement('p'), { className: 'lock-note error', textContent: session.libraryError }), wrap);

    const draw = () => {
      const q = libraryQuery.trim().toLowerCase();
      const items = (session.library || [])
        .filter((e) => !q || e.name.toLowerCase().includes(q))
        .sort((a, b) => (prefs.librarySort === 'name'
          ? a.name.localeCompare(b.name, undefined, { sensitivity: 'base' })
          : b.updatedAt.localeCompare(a.updatedAt)));
      list.innerHTML = items.length ? '' : `<p class="sec-note">${(session.library || []).length ? 'No snapshot matches the search.' : 'No snapshots yet. Press NEW to save the current mix.'}</p>`;
      items.forEach((e) => {
        const row = document.createElement('div');
        row.className = 'lib-row';
        row.setAttribute('role', 'listitem');
        row.innerHTML = `
          <div class="lib-main"><span class="lib-name">${esc(e.name)}</span><span class="lib-meta">${esc(e.updatedAt.slice(0, 10))} · ${scopeSummary(e.scopes)}</span></div>
          <button class="key-btn accent" data-act="load" data-focus-key="lib-load:${e.id}">LOAD</button>
          <button class="key-btn" data-act="update" title="Save the current mix into this snapshot">UPDATE</button>
          <button class="key-btn" data-act="rename">RENAME</button>
          <button class="key-btn danger" data-act="delete" aria-label="Delete ${esc(e.name)}">✕</button>`;
        row.querySelector('[data-act="load"]').onclick = async () => {
          const scope = recallScope();
          if (!scope.length) { showToast('Select at least one item under WHAT TO LOAD.', true); return; }
          if (!(await confirmAction(`LOAD "${e.name}"?`, `This sends ${scope.join(', ')} values to the mixer now. Press UNDO to go back.`, 'LOAD', 'accent'))) return;
          const res = await postAction({ action: 'libraryLoad', id: e.id, scope: fullScope() ? undefined : scope });
          if (res.ok) showToast(`Loaded "${e.name}" (${res.applied} values${res.failed ? `, ${res.failed} failed` : ''}).`, !!res.failed);
          loadSession();
        };
        row.querySelector('[data-act="update"]').onclick = async () => {
          if (!(await confirmAction(`UPDATE "${e.name}"?`, 'Replace the stored values with the current mix?', 'UPDATE'))) return;
          const res = await postAction({ action: 'librarySave', id: e.id, name: e.name });
          if (res.ok) showToast(`Updated "${e.name}".`);
          loadSession();
        };
        row.querySelector('[data-act="rename"]').onclick = async () => {
          const name = await promptName('RENAME SNAPSHOT', e.name, 'RENAME');
          if (!name || name === e.name) return;
          await postAction({ action: 'libraryRename', id: e.id, name });
          loadSession();
        };
        row.querySelector('[data-act="delete"]').onclick = async () => {
          if (!(await confirmAction(`DELETE "${e.name}"?`, 'The snapshot is removed from the library on the host computer. This cannot be undone.', 'DELETE'))) return;
          await postAction({ action: 'libraryDelete', id: e.id });
          loadSession();
        };
        list.appendChild(row);
      });
    };
    search.oninput = () => { libraryQuery = search.value; draw(); };
    draw();
  }

  function renderPrefsPage(page) {
    pageHead(page, 'PREFERENCES');
    const cols = document.createElement('div');
    cols.className = 'pref-cols';
    const group = (title, rows, note) => {
      const g = document.createElement('section');
      g.className = 'insp-sec';
      g.innerHTML = `<div class="sec-hdr"><span class="sec-title">${title}</span></div>`;
      if (note) g.appendChild(note);
      rows.forEach((r) => g.appendChild(r));
      cols.appendChild(g);
    };
    const local = (key, label) => checkRow(label, prefs[key], {
      onChange: (on) => { prefs[key] = on; savePrefs(); renderView(); },
    });
    group('VOLUME · THIS DEVICE', [local('displayDb', 'DISPLAY DECIBEL'), local('finerSliders', 'FINER SLIDERS')],
      Object.assign(document.createElement('p'), { className: 'sec-note', textContent: 'Finer sliders: faders and knobs move at a quarter of the finger travel. On a desktop, hold Shift for the same effect.' }));
    group('EQ', [checkRow('FULL PARAMETRIC', false, { locked: lockReason('eqParametric') })], lockedNote('eqParametric'));
    group('OUTPUT PAD', [checkRow('-10 dBV MAIN OUT', false, { locked: lockReason('outputPad') }), checkRow('-10 dBV MONITOR OUT', false, { locked: lockReason('outputPad') })], lockedNote('outputPad'));
    group('FOOT SWITCH MODE', [checkRow('FX – MUTE / TAP', false, { locked: lockReason('footswitch'), radio: true }), checkRow('SNAPSHOT UP / DOWN', false, { locked: lockReason('footswitch'), radio: true })], lockedNote('footswitch'));
    page.appendChild(cols);
  }

  function renderRoutingPage(page) {
    pageHead(page, 'ROUTING');
    const ms = session.meterStatus || {};
    const mode = ms.mode === 'recording' ? 'RECORDING' : ms.mode === 'streaming' ? 'STREAMING' : 'UNKNOWN';
    const usb = document.createElement('section');
    usb.className = 'insp-sec';
    usb.innerHTML = `<div class="sec-hdr"><span class="sec-title">USB AUDIO MODE</span><span class="sec-meta">READ FROM THE USB DEVICE</span></div>
      <div class="seg wide"><span class="seg-btn ${mode === 'RECORDING' ? 'on' : ''}">RECORDING</span><span class="seg-btn ${mode === 'STREAMING' ? 'on' : ''}">STREAMING</span></div>
      <p class="sec-note">${mode === 'UNKNOWN' ? 'No USB audio device found, so the mode is unknown.' : `The hub sees the FLOW 8 in ${mode.toLowerCase()} mode.`} Change the mode on the mixer.</p>`;
    page.appendChild(usb);
    const rt = document.createElement('section');
    rt.className = 'insp-sec locked';
    rt.innerHTML = '<div class="sec-hdr"><span class="sec-title">SIGNAL ROUTING</span></div>';
    rt.appendChild(lockedNote('routing'));
    const body = document.createElement('div');
    body.className = 'sec-body route-grid';
    [['PHONES', ['MAIN', 'MON 1/2'], ['PRE', 'POST']], ['MONITOR 1/2', ['PRE', 'POST'], ['STEREO LINK 1/2']],
      ['BT/USB PLAY', ['TO MAIN MIX', 'PHONES ONLY']], ['FX 1 / FX 2', ['TO MAIN', 'TO MON 1', 'TO MON 2']], ['FROM PC (USB 1/2, 3/4)', ['TO CHANNEL', 'MON OUT 1/2']]]
      .forEach(([t, ...sets]) => {
        const g = document.createElement('div');
        g.innerHTML = `<span class="sec-meta">${t}</span>`;
        sets.forEach((opts) => opts.forEach((o) => g.appendChild(checkRow(o, false, { locked: lockReason('routing') }))));
        body.appendChild(g);
      });
    rt.appendChild(body);
    page.appendChild(rt);
  }

  async function renderInfoPage(page) {
    pageHead(page, 'INFO');
    const ms = session.meterStatus || {};
    const sec = document.createElement('section');
    sec.className = 'insp-sec';
    sec.innerHTML = `<dl class="info-list">
      <dt>MIDI OUT</dt><dd>${session.midiOutOpen ? 'Open' : 'Closed'}</dd>
      <dt>MIDI IN</dt><dd>${session.midiInOpen ? 'Open' : 'Closed'}</dd>
      <dt>METERS</dt><dd>${esc(ms.detail || 'Off')}${ms.device ? ` (${esc(ms.device)})` : ''}</dd>
      <dt>SNAPSHOT LIBRARY</dt><dd>${(session.library || []).length} snapshots on the host computer</dd>
      <dt>OPEN ON A TABLET</dt><dd id="info-urls">…</dd></dl>`;
    page.appendChild(sec);
    try {
      const st = await (await fetch('/api/status')).json();
      const el = document.getElementById('info-urls');
      if (el) el.innerHTML = (st.lanUrls || []).map((u) => `<code>${esc(u)}</code>`).join('<br>') || 'No LAN address found.';
    } catch (_) { /* the hub banner reports the failure */ }
  }

  // ---------- Views ----------
  function renderView() {
    if (!session) return;
    document.body.dataset.view = view;
    document.querySelectorAll('.view-btn').forEach((b) => {
      const on = b.dataset.view === view;
      b.classList.toggle('active', on);
      b.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
    document.getElementById('console-bank').hidden = view !== 'mixer';
    document.getElementById('stage-view').hidden = view !== 'stage';
    document.getElementById('workspace').hidden = view === 'setup';
    document.getElementById('setup-view').hidden = view !== 'setup';
    document.getElementById('btn-snapshots').classList.toggle('on', view === 'setup' && (setupPage === 'snapshots' || setupPage === 'library'));
    document.getElementById('btn-setup').classList.toggle('on', view === 'setup' && setupPage !== 'snapshots' && setupPage !== 'library');
    renderConsole(); // also updates the connection banner and MUTE ALL
    if (view === 'stage') renderStage();
    if (view === 'setup') renderSetup();
    renderInspector();
  }
  function setView(v, page, syncHub = true) {
    if (v !== 'setup') lastLiveView = v;
    view = v;
    if (page) setupPage = page;
    if (syncHub && (v === 'mixer' || v === 'stage')) {
      fetch('/api/action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'setActiveView', view: v, clientId }),
      }).catch(() => {});
    }
    renderView();
  }

  function promptName(title, value, okLabel) {
    return new Promise((resolve) => {
      const modal = document.getElementById('prompt-modal');
      const inp = document.getElementById('prompt-input');
      const count = document.getElementById('prompt-count');
      document.getElementById('prompt-title').textContent = title;
      document.getElementById('btn-prompt-ok').textContent = okLabel;
      inp.value = value;
      const upd = () => { count.textContent = `${inp.value.length}/40`; };
      inp.oninput = upd;
      upd();
      const done = (v) => {
        modal.onModalClose = null;
        closeModal('prompt-modal');
        resolve(v);
      };
      document.getElementById('btn-prompt-ok').onclick = () => { if (inp.value.trim()) done(inp.value.trim()); };
      document.getElementById('btn-prompt-cancel').onclick = () => done(null);
      inp.onkeydown = (e) => { if (e.key === 'Enter' && inp.value.trim()) { e.preventDefault(); done(inp.value.trim()); } };
      modal.onModalClose = () => done(null);
      openModal('prompt-modal', inp);
      inp.select();
    });
  }

  document.getElementById('library-file').onchange = async (e) => {
    const file = e.target.files[0];
    e.target.value = '';
    if (!file) return;
    if (file.size > 900000) { showToast('The file is too large (limit 900 KB).', true); return; }
    let data;
    try { data = JSON.parse(await file.text()); } catch (_) { showToast('The file is not valid JSON.', true); return; }
    const res = await postAction({ action: 'libraryImport', data });
    if (res.ok) showToast(`Imported ${res.added} snapshot(s)${res.skipped ? `, skipped ${res.skipped} invalid` : ''}.`, !!res.skipped);
    loadSession();
  };

  function renderStatusBar() {
    if (!session) return;
    const set = (id, on) => document.getElementById(id).classList.toggle('on', !!on);
    set('lamp-usb', session.midiOutOpen);
    const ms = session.meterStatus || {};
    const meterLink = document.getElementById('lamp-meter').parentElement;
    meterLink.title = ms.detail
      ? `${ms.detail}${ms.device ? ` (${ms.device})` : ''}`
      : 'No meter source. The FLOW 8 does not send meters over MIDI.';
    meterLink.classList.toggle('fault', ms.state === 'error' || ms.state === 'no_device' || ms.state === 'unavailable');
    set('lamp-midi-in', session.midiInOpen);
    const scene = document.getElementById('scene-display');
    const cur = session.currentScene;
    scene.querySelector('.scene-name').textContent = cur ? cur.replace('SCENE ', '').padStart(2, '0') : 'No scene';
    scene.classList.toggle('edited', !!(cur && session.sceneEdited));
    scene.classList.toggle('empty', !cur);
    scene.title = !cur
      ? 'No scene recalled or saved in this session.'
      : session.sceneEdited
        ? `The mix changed after ${cur} was recalled or saved. Hold the pad to save it again.`
        : `The mix matches ${cur}.`;
  }
  const clockEl = document.getElementById('clock');
  const tickClock = () => {
    clockEl.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
  };
  tickClock();
  setInterval(tickClock, 1000);

  // ---------- Panel lock ----------
  // Tap LOCK to lock all controls. Hold it for 0.8 s to unlock, so a stray touch
  // during a show cannot change the mix.
  (() => {
    const btn = document.getElementById('btn-lock');
    let holdTimer = null;
    const setLocked = (on) => {
      document.body.classList.toggle('locked', on);
      btn.setAttribute('aria-pressed', on ? 'true' : 'false');
      btn.querySelector('.lock-text').textContent = on ? 'LOCKED' : 'LOCK';
      btn.title = on ? 'Hold for 0.8 s to unlock the controls.' : 'Lock all controls against stray touches.';
      showToast(on ? 'Controls locked. Hold LOCK to unlock.' : 'Controls unlocked.');
    };
    btn.onpointerdown = () => {
      if (!document.body.classList.contains('locked')) { setLocked(true); return; }
      btn.classList.add('holding');
      holdTimer = setTimeout(() => { holdTimer = null; btn.classList.remove('holding'); setLocked(false); }, 800);
    };
    const cancel = () => {
      btn.classList.remove('holding');
      if (holdTimer) { clearTimeout(holdTimer); holdTimer = null; showToast('Hold LOCK for 0.8 s to unlock.'); }
    };
    btn.onpointerup = cancel;
    btn.onpointerleave = () => { btn.classList.remove('holding'); if (holdTimer) { clearTimeout(holdTimer); holdTimer = null; } };
    btn.onkeydown = (e) => {
      if (e.key !== 'Enter' && e.key !== ' ') return;
      e.preventDefault();
      setLocked(!document.body.classList.contains('locked'));
    };
  })();

  // ---------- Modals ----------
  async function openPresetsModal(targetIdx) {
    if (!presets.length) {
      const res = await fetch('/api/presets');
      presets = (await res.json()).presets || [];
    }
    document.getElementById('preset-modal-title').textContent = `PRESETS FOR CH ${targetIdx} (LEVELS ALWAYS PRESERVED)`;
    const list = document.getElementById('preset-list');
    list.innerHTML = '';
    presets.forEach((p) => {
      const item = document.createElement('div');
      item.className = 'preset-item';
      item.innerHTML = `
        <div>
          <h4>[${esc(p.category)}] ${esc(p.name)}</h4>
          <p>${esc(p.summary)}</p>
        </div>
        <button class="hw-btn accent" aria-label="Apply ${esc(p.name)} to CH ${targetIdx}">APPLY</button>
      `;
      item.querySelector('button').onclick = async () => {
        const replaces = targetIdx <= 4 ? 'the 4-band EQ, low cut and compressor' : 'the 4-band EQ';
        const okay = await confirmAction(
          `APPLY TO CH ${targetIdx}?`,
          `"${p.name}" replaces ${replaces} on CH ${targetIdx}. Fader, pan, mute and sends do not change. Press UNDO to go back.`,
          'APPLY',
          'accent'
        );
        if (!okay) return;
        const res = await postAction({ action: 'applyPreset', channel: targetIdx, presetId: p.id });
        if (res.ok) {
          closeModal('preset-modal');
          showToast(`Applied "${p.name}" to CH ${targetIdx}.`);
        }
        loadSession();
      };
      list.appendChild(item);
    });
    openModal('preset-modal');
  }

  function openScribbleModal(ch) {
    const inp = document.getElementById('scribble-input');
    inp.value = chName(ch).slice(0, 14);
    const counter = document.getElementById('scribble-count');
    const count = () => { counter.textContent = `${inp.value.length}/14`; };
    inp.oninput = count;
    count();
    document.getElementById('scribble-title').textContent = `RENAME ${STRIP_TAG[ch.index]}`;
    let chosenColor = ch.color || HUB_DEFAULT_COLOR;
    const box = document.getElementById('scribble-colors');
    box.innerHTML = '';
    SCRIBBLE_PALETTE.forEach((col) => {
      const dot = document.createElement('button');
      dot.className = 'color-dot';
      dot.style.background = col;
      dot.setAttribute('aria-label', `Color ${SCRIBBLE_NAMES[col] || col}`);
      dot.setAttribute('aria-pressed', col === chosenColor ? 'true' : 'false');
      dot.onclick = () => {
        chosenColor = col;
        [...box.children].forEach((c) => c.setAttribute('aria-pressed', 'false'));
        dot.setAttribute('aria-pressed', 'true');
      };
      box.appendChild(dot);
    });
    const save = async () => {
      const res = await postAction({ action: 'setScribble', channel: ch.index, label: inp.value.trim(), color: chosenColor });
      if (res.ok) closeModal('scribble-modal');
      loadSession();
    };
    document.getElementById('btn-save-scribble').onclick = save;
    inp.onkeydown = (e) => { if (e.key === 'Enter') { e.preventDefault(); save(); } };
    openModal('scribble-modal', inp);
    inp.select();
  }

  const modalReturnFocus = {};
  function openModal(id, focusEl) {
    const modal = document.getElementById(id);
    modalReturnFocus[id] = document.activeElement;
    modal.classList.add('open');
    (focusEl || modal.querySelector('input, button')).focus();
  }
  function closeModal(id) {
    const modal = document.getElementById(id);
    if (!modal.classList.contains('open')) return;
    modal.classList.remove('open');
    const back = modalReturnFocus[id];
    if (back && document.contains(back)) back.focus();
  }
  // Escape or a click on the dark backdrop closes the top modal.
  // The confirm modal resolves as "cancel" through its onModalClose hook.
  function dismissModal(modal) {
    if (modal.onModalClose) modal.onModalClose();
    else closeModal(modal.id);
  }
  document.querySelectorAll('.modal-backdrop').forEach((m) => {
    m.addEventListener('click', (e) => { if (e.target === m) dismissModal(m); });
  });
  // Escape closes the top modal first, then the Inspector.
  document.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape') return;
    const open = [...document.querySelectorAll('.modal-backdrop.open')];
    if (open.length) { e.preventDefault(); dismissModal(open[open.length - 1]); return; }
    if (insp && view !== 'setup') { e.preventDefault(); closeInspector(); return; }
    if (view === 'setup') { e.preventDefault(); setView(lastLiveView); }
  });

  // ---------- Bus selector ----------
  // Tap a mix to put it on the faders. Tap the active mix again to open its settings.
  function setLayer(layer, render = true, syncHub = true) {
    activeLayer = layer;
    document.body.dataset.layer = layer;
    document.querySelectorAll('.bus-tab').forEach((b) => {
      const on = b.dataset.layer === layer;
      b.classList.toggle('active', on);
      b.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
    // A bus Inspector follows the selected mix.
    if (insp && insp.kind === 'bus') insp = { kind: 'bus', id: layer };
    if (syncHub) {
      fetch('/api/action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'setActiveBus', bus: layer, clientId }),
      }).catch(() => {});
    }
    if (render) renderView();
  }
  document.querySelectorAll('.bus-tab').forEach((btn) => {
    btn.title = `Put the ${LAYERS[btn.dataset.layer].label} mix on the faders. Tap again for its settings.`;
    btn.onclick = () => {
      const layer = btn.dataset.layer;
      if (layer !== activeLayer) { setLayer(layer); return; }
      if (insp && insp.kind === 'bus' && insp.id === layer) closeInspector();
      else openInspector({ kind: 'bus', id: layer });
    };
  });

  document.getElementById('insp-close').onclick = closeInspector;
  document.querySelectorAll('.view-btn').forEach((b) => { b.onclick = () => setView(b.dataset.view); });
  document.getElementById('btn-snapshots').onclick = () => (view === 'setup' && setupPage === 'snapshots' ? setView(lastLiveView) : setView('setup', 'snapshots'));
  document.getElementById('btn-setup').onclick = () => (view === 'setup' && setupPage !== 'snapshots' && setupPage !== 'library' ? setView(lastLiveView) : setView('setup', setupPage === 'snapshots' || setupPage === 'library' ? 'inputs' : setupPage));
  document.getElementById('setup-close').onclick = () => setView(lastLiveView);
  document.querySelectorAll('.setup-tab').forEach((t) => { t.onclick = () => setView('setup', t.dataset.page); });
  document.getElementById('insp-prev').onclick = () => stepInspector(-1);
  document.getElementById('insp-next').onclick = () => stepInspector(1);

  document.getElementById('btn-mute-all').onclick = async () => {
    if (!session || !session.channels) return;
    // Toggle: if every input is already muted, the button restores them.
    const inputs = session.channels.filter((c) => c.index <= 7);
    const allMuted = inputs.every((c) => c.mute);
    const res = await postAction({ action: 'muteAll', value: !allMuted });
    if (res.ok) showToast(allMuted ? 'All inputs unmuted.' : 'All inputs muted. Press UNMUTE ALL to restore.');
    loadSession();
  };
  document.getElementById('btn-undo').onclick = () => postAction({ action: 'undo' }).then(scheduleReload);
  document.getElementById('btn-redo').onclick = () => postAction({ action: 'redo' }).then(scheduleReload);
  document.getElementById('btn-close-presets').onclick = () => closeModal('preset-modal');
  document.getElementById('btn-close-scribble').onclick = () => closeModal('scribble-modal');

  // While a finger or mouse holds a control, a re-render would drop the drag.
  // Reloads wait until the pointer is released.
  let pointerBusy = false;
  let reloadPending = false;
  let reloadTimer = null;
  function scheduleReload() {
    reloadPending = true;
    if (pointerBusy) return;
    clearTimeout(reloadTimer);
    reloadTimer = setTimeout(() => {
      if (pointerBusy) return; // a drag started after scheduling; release will reload
      reloadPending = false;
      loadSession();
    }, 120);
  }
  document.addEventListener('pointerdown', (e) => {
    if (e.target.closest('.fader-well, .knob-svg, #eq-canvas, .studio-range, .phantom-key, .snap-slot')) pointerBusy = true;
  }, true);
  const releasePointer = () => {
    if (!pointerBusy) return;
    pointerBusy = false;
    if (reloadPending) setTimeout(scheduleReload, 60);
  };
  window.addEventListener('pointerup', releasePointer, true);
  window.addEventListener('pointercancel', releasePointer, true);

  async function loadSession() {
    const focusKey = document.activeElement && document.activeElement.dataset ? document.activeElement.dataset.focusKey : null;
    try {
      const res = await fetch('/api/session');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      session = await res.json();
    } catch (_) {
      hubDown = true;
      applyConnectionState(false, 'HUB UNREACHABLE — check the host computer and the Wi-Fi link.');
      return;
    }
    if (session.activeBus && LAYERS[session.activeBus] && session.activeBus !== activeLayer) {
      setLayer(session.activeBus, false, false);
    }
    if (session.activeView && (session.activeView === 'mixer' || session.activeView === 'stage') && view !== 'setup' && session.activeView !== view) {
      setView(session.activeView, undefined, false);
      return;
    }
    renderView();
    renderStatusBar();
    if (focusKey) {
      const el = document.querySelector(`[data-focus-key="${CSS.escape(focusKey)}"]`);
      if (el) el.focus({ preventScroll: true });
    }
  }

  loadSession();
  setInterval(async () => {
    try {
      const st = await (await fetch('/api/status')).json();
      if (hubDown || (session && !!st.midiConnected !== !!session.midiConnected)) loadSession();
      hubDown = false;
    } catch (_) {
      hubDown = true;
      applyConnectionState(false, 'HUB UNREACHABLE — check the host computer and the Wi-Fi link.');
    }
  }, 3000);
  const es = new EventSource('/api/events?clientId=' + clientId);
  es.onopen = () => document.getElementById('lamp-hub').classList.add('on');
  es.onerror = () => document.getElementById('lamp-hub').classList.remove('on');
  es.onmessage = (msg) => {
    let ev = {};
    try { ev = JSON.parse(msg.data); } catch (_) { return; }
    if (ev.type === 'meters') { onMeterFrame(ev.levels || {}); return; }
    if (ev.type === 'connected') return;
    if (ev.type === 'rx') markLamp(stripIdForParam(ev.paramId), 'rx');
    if (ev.type === 'tx') {
      if (ev.action === 'muteAll') for (let i = 1; i <= 7; i++) markLamp(`ch${i}`, 'tx');
      else if (ev.bus) markLamp(ev.bus, 'tx');
      else if (ev.channel != null) markLamp(stripIdForChannel(+ev.channel), 'tx');
    }
    scheduleReload();
  };
  requestAnimationFrame(frame);
})();
