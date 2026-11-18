(() => {
  const clientId = Math.random().toString(36).slice(2);
  let session = null;
  let presets = [];
  let selectedCh = 1;
  let activeLayer = 'main'; // 'main' | 'mon1' | 'mon2' | 'fx1' | 'fx2'
  let mobileView = 'faders'; // 'faders' | 'buses' | 'dsp'

  const BANDS = [
    { key: 'low', label: 'LOW', freq: 80, color: '#2EF2E2' },
    { key: 'low_mid', label: 'L-MID', freq: 400, color: '#52E59A' },
    { key: 'hi_mid', label: 'H-MID', freq: 2000, color: '#FFB45B' },
    { key: 'hi', label: 'HI', freq: 8000, color: '#BC71FF' },
  ];
  const SCRIBBLE_PALETTE = ['#2EF2E2', '#52E59A', '#FFB45B', '#BC71FF', '#FF6BAA', '#C5FF4A'];
  const SCRIBBLE_NAMES = { '#2EF2E2': 'cyan', '#52E59A': 'green', '#FFB45B': 'amber', '#BC71FF': 'purple', '#FF6BAA': 'pink', '#C5FF4A': 'lime' };

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

  function midiToDbStr(raw) {
    if (raw <= 0) return '-∞ dB';
    const db = raw >= 101 ? ((raw - 101) / 26) * 10 : ((raw - 101) / 101) * 70;
    return `${db >= 0 ? '+' : ''}${db.toFixed(1)} dB`;
  }

  function eqRawToDb(raw) {
    return ((raw - 64) / 63.5) * 15.0;
  }

  function dbToEqRaw(db) {
    return Math.max(0, Math.min(127, Math.round((Math.max(-15, Math.min(15, db)) / 15.0) * 63.5 + 64)));
  }

  function panText(raw) {
    const pct = Math.round(((raw - 64) / 63.5) * 100);
    if (Math.abs(pct) <= 1) return 'C';
    return pct < 0 ? `L${Math.abs(pct)}` : `R${pct}`;
  }

  function hpfHz(raw) {
    if (raw <= 0) return 'OFF';
    return `${Math.round(20 + (raw / 127) * 580)} Hz`;
  }

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

  // Keyboard control for a custom slider (fader, knob, EQ band).
  // Arrow keys step 1, Page keys step 10, Home/End go to the limits.
  // The value is sent 300 ms after the last key press.
  function attachSliderKeys(el, { label, min, max, get, set, text, onCommit }) {
    el.tabIndex = 0;
    el.dataset.focusKey = el.dataset.focusKey || `slider:${label}`;
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
        el.classList.toggle('sig', m.peak > -50);
        el.classList.toggle('clip', now - m.clipAt < 1500);
      });
    }
    requestAnimationFrame(frame);
  }

  // Overview EQ curve for a strip, drawn from the known band values.
  function eqThumbPath(ch, w = 60, h = 18) {
    const gains = BANDS.map((b) => eqRawToDb(ch.eq ? ch.eq[b.key] : 64));
    const pts = [];
    for (let i = 0; i <= 24; i++) {
      const f = 20 * Math.pow(1000, i / 24);
      const db = Math.max(-15, Math.min(15, eqResponseAt(f, gains)));
      pts.push(`${((i / 24) * w).toFixed(1)},${(h / 2 - (db / 15) * (h / 2 - 1)).toFixed(1)}`);
    }
    return `M${pts.join(' L')}`;
  }

  // ---------- Rotary SVG Knob Builder ----------
  function createRotaryKnob({ label, valueText, raw, min, max, color, bipolar = false, disabled = false, onMove, onCommit }) {
    const cell = document.createElement('div');
    cell.className = 'knob-cell' + (disabled ? ' disabled' : '');
    const norm = (raw - min) / (max - min);
    const startDeg = -135;
    const endDeg = 135;
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
    cell.innerHTML = `
      <span class="knob-lbl">${label}</span>
      <svg class="knob-svg" viewBox="0 0 52 52">
        <path d="${arcPath(startDeg, endDeg, 21)}" fill="none" stroke="#1e2738" stroke-width="3.5" stroke-linecap="round" />
        <path class="k-arc" d="${arcPath(arcFrom, curDeg, 21)}" fill="none" stroke="${color}" stroke-width="3.5" stroke-linecap="round" />
        <circle cx="26" cy="26" r="15.5" fill="#1a2130" stroke="#334155" stroke-width="1.2" />
        <line class="k-ptr" x1="26" y1="26" x2="${polar(curDeg, 12)[0]}" y2="${polar(curDeg, 12)[1]}" stroke="${color}" stroke-width="2.4" stroke-linecap="round" />
      </svg>
      <span class="knob-val">${valueText}</span>
    `;

    if (!disabled) {
      const svg = cell.querySelector('svg');
      const arcEl = cell.querySelector('.k-arc');
      const ptrEl = cell.querySelector('.k-ptr');
      const valEl = cell.querySelector('.knob-val');
      let current = raw;
      let startY = 0;
      let startVal = raw;

      const updateVisual = (v) => {
        const n = (v - min) / (max - min);
        const deg = startDeg + n * (endDeg - startDeg);
        arcEl.setAttribute('d', arcPath(arcFrom, deg, 21));
        const [px, py] = polar(deg, 12);
        ptrEl.setAttribute('x2', px);
        ptrEl.setAttribute('y2', py);
        valEl.textContent = onMove(v);
      };

      svg.onpointerdown = (e) => {
        svg.setPointerCapture(e.pointerId);
        startY = e.clientY;
        startVal = current;
      };
      svg.onpointermove = (e) => {
        if (!svg.hasPointerCapture(e.pointerId)) return;
        const delta = Math.round(((startY - e.clientY) / 110) * (max - min));
        current = Math.max(min, Math.min(max, startVal + delta));
        updateVisual(current);
      };
      svg.onpointerup = (e) => {
        if (!svg.hasPointerCapture(e.pointerId)) return;
        svg.releasePointerCapture(e.pointerId);
        onCommit(current);
      };
      const syncKeys = attachSliderKeys(svg, {
        label, min, max,
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
    }
    return cell;
  }

  // ---------- Interactive 4-Band EQ Canvas ----------
  let eqNodeDrag = null;
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

  function freqToX(freq, w) {
    const minL = Math.log10(20), maxL = Math.log10(20000);
    return 14 + ((Math.log10(freq) - minL) / (maxL - minL)) * (w - 28);
  }

  function dbToY(db, h) {
    return h / 2 - (db / 16) * (h * 0.42);
  }

  function yToDb(y, h) {
    return Math.max(-15, Math.min(15, ((h / 2 - y) / (h * 0.42)) * 16));
  }

  function drawEqCanvas(ch) {
    const canvas = document.getElementById('eq-canvas');
    const ctx = canvas.getContext('2d');
    const w = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);

    // Subtle frequency & dB grid
    ctx.strokeStyle = '#1b2232';
    ctx.lineWidth = 1;
    [50, 100, 250, 500, 1000, 2500, 5000, 10000].forEach((f) => {
      const x = freqToX(f, w);
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke();
    });
    [-10, 0, 10].forEach((d) => {
      const y = dbToY(d, h);
      ctx.strokeStyle = d === 0 ? '#2b364d' : '#181f2d';
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
    });

    if (!ch || !ch.eq) return;
    const gains = BANDS.map((b) => eqRawToDb(ch.eq[b.key]));
    const active = ch.eqProvenance === 'COMMANDED' || ch.eqProvenance === 'OBSERVED';
    const curveColor = active ? '#38bdf8' : '#5d6a80';

    ctx.beginPath();
    for (let i = 0; i <= 80; i++) {
      const f = Math.pow(10, Math.log10(20) + (i / 80) * (Math.log10(20000) - Math.log10(20)));
      const x = freqToX(f, w);
      const y = dbToY(eqResponseAt(f, gains), h);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.strokeStyle = curveColor;
    ctx.lineWidth = 2.4;
    ctx.stroke();

    // Area fill under curve
    ctx.lineTo(freqToX(20000, w), h / 2);
    ctx.lineTo(freqToX(20, w), h / 2);
    ctx.closePath();
    ctx.fillStyle = active ? 'rgba(56, 189, 248, 0.12)' : 'rgba(93, 106, 128, 0.08)';
    ctx.fill();

    // Draggable Band Nodes
    if (ch.index <= 7) {
      BANDS.forEach((b, idx) => {
        const nx = freqToX(b.freq, w);
        const ny = dbToY(gains[idx], h);
        ctx.beginPath();
        ctx.arc(nx, ny, 6.5, 0, Math.PI * 2);
        ctx.fillStyle = '#090c11';
        ctx.fill();
        ctx.lineWidth = 2.2;
        ctx.strokeStyle = b.color;
        ctx.stroke();
      });
    }
  }

  function setupEqCanvasInteraction() {
    const canvas = document.getElementById('eq-canvas');
    canvas.onpointerdown = (e) => {
      if (!session) return;
      const ch = session.channels.find((c) => c.index === selectedCh);
      if (!ch || ch.index === 8) return;
      const rect = canvas.getBoundingClientRect();
      const sx = ((e.clientX - rect.left) / rect.width) * canvas.width;
      const sy = ((e.clientY - rect.top) / rect.height) * canvas.height;
      let best = null;
      let bestDist = 28;
      BANDS.forEach((b) => {
        const nx = freqToX(b.freq, canvas.width);
        const ny = dbToY(eqRawToDb(ch.eq[b.key]), canvas.height);
        const d = Math.hypot(sx - nx, sy - ny);
        if (d < bestDist) { bestDist = d; best = b; }
      });
      if (best) {
        eqNodeDrag = best;
        canvas.setPointerCapture(e.pointerId);
      }
    };
    canvas.onpointermove = (e) => {
      if (!eqNodeDrag || !session) return;
      const ch = session.channels.find((c) => c.index === selectedCh);
      if (!ch) return;
      const rect = canvas.getBoundingClientRect();
      const sy = ((e.clientY - rect.top) / rect.height) * canvas.height;
      const db = yToDb(sy, canvas.height);
      ch.eq[eqNodeDrag.key] = dbToEqRaw(db);
      ch.eqProvenance = 'COMMANDED';
      drawEqCanvas(ch);
      const valEl = document.getElementById(`eq-val-${eqNodeDrag.key}`);
      if (valEl) valEl.textContent = `${eqRawToDb(ch.eq[eqNodeDrag.key]).toFixed(1)} dB`;
    };
    canvas.onpointerup = (e) => {
      if (!eqNodeDrag || !session) return;
      const ch = session.channels.find((c) => c.index === selectedCh);
      const bandKey = eqNodeDrag.key;
      eqNodeDrag = null;
      if (canvas.hasPointerCapture(e.pointerId)) canvas.releasePointerCapture(e.pointerId);
      if (ch) postAction({ action: 'setEqBand', channel: ch.index, band: bandKey, value: ch.eq[bandKey] });
    };
  }

  // ---------- Render Top DSP Rack ----------
  function renderDsp() {
    if (!session) return;
    const ch = session.channels.find((c) => c.index === selectedCh) || session.channels[0];
    const title = ch.index === 8 ? 'MAIN L/R' : `CH ${String(ch.index).padStart(2, '0')} · ${ch.label || ch.name}`;
    document.getElementById('eq-title').textContent = `${title} · 4-BAND EQ`;
    document.getElementById('eq-prov').textContent = `COMMANDED — not measured (${ch.eqProvenance || 'UNSYNCED'})`;

    const eqRow = document.getElementById('eq-band-row');
    eqRow.innerHTML = '';
    BANDS.forEach((b) => {
      const raw = ch.eq ? ch.eq[b.key] : 64;
      const chip = document.createElement('div');
      chip.className = 'band-chip';
      chip.innerHTML = `
        <div class="b-name" style="color:${b.color}">${b.label}</div>
        <div class="b-val" id="eq-val-${b.key}">${eqRawToDb(raw).toFixed(1)} dB</div>
      `;
      if (ch.eq && ch.index <= 7) {
        let bandRaw = raw;
        attachSliderKeys(chip, {
          label: `${b.label} EQ gain, CH ${ch.index}`,
          min: 0, max: 127,
          get: () => bandRaw,
          set: (v) => {
            bandRaw = v;
            ch.eq[b.key] = v;
            chip.querySelector('.b-val').textContent = `${eqRawToDb(v).toFixed(1)} dB`;
            drawEqCanvas(ch);
          },
          text: (v) => `${eqRawToDb(v).toFixed(1)} dB`,
          onCommit: (v) => postAction({ action: 'setEqBand', channel: ch.index, band: b.key, value: v }),
        });
      }
      eqRow.appendChild(chip);
    });
    drawEqCanvas(ch);

    const picker = document.getElementById('ch-picker');
    picker.innerHTML = '';
    session.channels.forEach((c) => {
      const btn = document.createElement('button');
      btn.className = 'ch-pick' + (c.index === ch.index ? ' active' : '');
      btn.textContent = c.index === 8 ? 'MAIN' : String(c.index);
      btn.title = c.label || c.name;
      btn.setAttribute('aria-label', `Edit ${c.label || c.name}`);
      btn.setAttribute('aria-pressed', c.index === ch.index ? 'true' : 'false');
      btn.onclick = () => { selectedCh = c.index; renderConsole(); renderDsp(); };
      picker.appendChild(btn);
    });

    // Rotary Knobs: Pan/Bal, Low Cut (HPF), Compressor
    const knobsRow = document.getElementById('knobs-row');
    knobsRow.innerHTML = '';
    const isInput14 = ch.index <= 4;
    document.getElementById('dyn-scope').textContent = isInput14 ? 'ACTIVE (CH 1–4)' : 'HPF/COMP: CH 1–4 ONLY';

    knobsRow.appendChild(createRotaryKnob({
      label: ch.index === 8 ? 'BALANCE' : 'PAN',
      valueText: panText(ch.pan),
      raw: ch.pan,
      min: 0,
      max: 127,
      color: '#38bdf8',
      bipolar: true,
      onMove: (v) => panText(v),
      onCommit: (v) => postAction({ action: 'setPan', channel: ch.index, value: v }),
    }));

    knobsRow.appendChild(createRotaryKnob({
      label: 'LOW CUT',
      valueText: hpfHz(ch.lowCut || 0),
      raw: ch.lowCut || 0,
      min: 0,
      max: 127,
      color: '#f59e0b',
      disabled: !isInput14,
      onMove: (v) => hpfHz(v),
      onCommit: (v) => postAction({ action: 'setLowCut', channel: ch.index, value: v }),
    }));

    knobsRow.appendChild(createRotaryKnob({
      label: 'COMP',
      valueText: `${ch.compressor || 0}%`,
      raw: ch.compressor || 0,
      min: 0,
      max: 100,
      color: '#a78bfa',
      disabled: !isInput14,
      onMove: (v) => `${v}%`,
      onCommit: (v) => postAction({ action: 'setCompressor', channel: ch.index, value: v }),
    }));

    // Scenes
    const sceneGrid = document.getElementById('scene-grid');
    sceneGrid.innerHTML = '';
    for (let i = 1; i <= 8; i++) {
      const name = `SCENE ${i}`;
      const saved = session.scenes.includes(name);
      const pad = document.createElement('button');
      pad.className = 'scene-pad' + (saved ? ' saved' : '');
      pad.textContent = `S${i}`;
      const HOLD_MS = 550;
      let timer = null;
      const cancelHold = () => {
        pad.classList.remove('holding');
        if (timer) { clearTimeout(timer); timer = null; }
      };
      pad.setAttribute('aria-label', saved
        ? `Scene ${i}: tap or Enter to recall, hold or Shift+Enter to overwrite`
        : `Scene ${i}: empty, hold or Shift+Enter to save`);
      const saveScene = async () => {
        if (saved && !(await confirmAction(`OVERWRITE S${i}?`, `Scene S${i} already holds a saved mix. Save the current mix over it?`, 'OVERWRITE'))) return;
        const res = await postAction({ action: 'captureScene', name });
        if (res.ok) showToast(`Saved current mix to S${i}.`);
        loadSession();
      };
      const recallScene = async () => {
        if (!saved) { showToast(`S${i} is empty. Hold the pad (or press Shift+Enter) to save the current mix.`); return; }
        const res = await postAction({ action: 'recallScene', name });
        if (res.ok) showToast(`Recalled S${i}.`);
        loadSession();
      };
      pad.onkeydown = (e) => {
        if (e.key !== 'Enter' && e.key !== ' ') return;
        e.preventDefault();
        if (e.shiftKey) saveScene(); else recallScene();
      };
      pad.onpointerdown = () => {
        cancelHold();
        void pad.offsetWidth; // restart the progress animation
        pad.classList.add('holding');
        timer = setTimeout(() => {
          timer = null;
          pad.classList.remove('holding');
          held = true;
          saveScene();
        }, HOLD_MS);
      };
      let held = false;
      pad.onpointerup = () => {
        // The hold timer is still pending only when the finger lifted before the hold time.
        const wasTap = !!timer;
        cancelHold();
        if (held) { held = false; return; }
        if (wasTap) recallScene();
      };
      pad.onpointercancel = cancelHold;
      pad.onpointerleave = cancelHold;
      sceneGrid.appendChild(pad);
    }

    // Aux Sends
    const sendsList = document.getElementById('sends-list');
    sendsList.innerHTML = '';
    ['mon1', 'mon2', 'fx1', 'fx2'].forEach((t) => {
      const val = ch.sends ? ch.sends[t] : 0;
      const box = document.createElement('div');
      box.className = 'send-box';
      box.innerHTML = `
        <div class="send-top"><span>${t.toUpperCase()}</span><span class="s-val">${midiToDbStr(val)}</span></div>
        <input class="studio-range" type="range" min="0" max="127" value="${val}" aria-label="${t.toUpperCase()} send, CH ${ch.index}" aria-valuetext="${midiToDbStr(val)}" ${ch.index === 8 ? 'disabled' : ''} />
      `;
      const rng = box.querySelector('input');
      rng.oninput = () => {
        box.querySelector('.s-val').textContent = midiToDbStr(+rng.value);
        rng.setAttribute('aria-valuetext', midiToDbStr(+rng.value));
      };
      rng.onchange = () => postAction({ action: 'setSend', channel: ch.index, target: t, value: +rng.value });
      sendsList.appendChild(box);
    });
  }

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
  const METER = (sid) => `
    <div class="meter" data-meter="${sid}" aria-hidden="true">
      <div class="meter-rms"></div><div class="meter-hold"></div><span class="meter-clip"></span>
    </div>`;

  // ---------- Vertical Fader Pointer Engine ----------
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

    well.onpointerdown = (e) => {
      well.setPointerCapture(e.pointerId);
      well.classList.add('grab');
      val = valFromEvent(e);
      updatePos(val);
      onMove(val);
    };
    well.onpointermove = (e) => {
      if (!well.hasPointerCapture(e.pointerId)) return;
      val = valFromEvent(e);
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

  // ---------- Render Bottom Fader Bank ----------
  function renderConsole() {
    if (!session) return;
    applyConnectionState(!!session.midiConnected);
    const allMuted = session.channels.filter((c) => c.index <= 7).every((c) => c.mute);
    document.getElementById('btn-mute-all').textContent = allMuted ? 'UNMUTE ALL' : 'MUTE ALL';

    const bank = document.getElementById('console-bank');
    bank.innerHTML = '';

    const layerClass = activeLayer === 'main' ? '' : (activeLayer.startsWith('mon') ? ' layer-mon' : ' layer-fx');

    // Input Channels 1-7 + Main L/R
    if (mobileView !== 'buses') {
      session.channels.forEach((ch) => {
        const isMaster = ch.index === 8;
        const isSendLayer = !isMaster && activeLayer !== 'main';
        const faderVal = isSendLayer ? (ch.sends ? ch.sends[activeLayer] : 0) : ch.fader;
        const faderProv = isSendLayer ? activeLayer.toUpperCase() : provCode(ch.faderProvenance);
        const provHint = isSendLayer ? `Send level to ${activeLayer.toUpperCase()}` : provTitle(ch.faderProvenance);
        const name = ch.label || ch.name;
        const notInLayer = isMaster && activeLayer !== 'main';

        const sid = stripIdForChannel(ch.index);
        const prov = isSendLayer ? (ch.sends ? 'COMMANDED' : 'UNSYNCED') : ch.faderProvenance;
        const strip = document.createElement('div');
        strip.dataset.strip = sid;
        strip.className = 'strip' + (isMaster ? ' master' : '') + (selectedCh === ch.index ? ' selected' : '') + (isSendLayer ? layerClass : '') + (notInLayer ? ' not-in-layer' : '');
        if (notInLayer) strip.title = `Main L/R is not part of the ${activeLayer.toUpperCase()} mix. Its fader sets the main level.`;
        const tagColor = ch.color || '#38bdf8';

        strip.innerHTML = `
          <div class="scribble" role="button" tabindex="0" data-focus-key="scribble:${sid}" aria-label="Select ${esc(name)}" style="--lcd:${tagColor}">
            <div class="scribble-top">
              <span class="scribble-num">${isMaster ? 'MAIN' : String(ch.index).padStart(2, '0')}</span>
              <span class="scribble-prov" title="${esc(provHint)}">${faderProv}</span>
            </div>
            <div class="scribble-name" title="${esc(name)}">${esc(name)}</div>
          </div>
          <div class="lamp-row">
            ${LAMPS(sid, prov)}
          </div>
          ${isMaster ? '<div class="eq-thumb eq-thumb-none">MAIN L/R</div>' : `<svg class="eq-thumb" viewBox="0 0 60 18" preserveAspectRatio="none" aria-hidden="true"><line x1="0" y1="9" x2="60" y2="9" class="eq-thumb-zero"/><path d="${eqThumbPath(ch)}"/></svg>`}
          <div class="strip-pan${!isMaster && selectedCh === ch.index ? ' has-edit' : ''}">
            ${!isMaster && selectedCh === ch.index ? `<button class="scribble-edit" aria-label="Rename ${esc(name)}" title="Rename channel">✎</button>` : ''}
            <span class="strip-pan-val">${notInLayer ? 'MAIN MIX' : panText(ch.pan)}</span>
          </div>
          ${isMaster
            ? '<div class="mute-na" title="The FLOW 8 has no MIDI mute for Main L/R. Use MUTE ALL or the main fader.">NO MUTE</div>'
            : `<button class="mute-switch ${ch.mute ? 'muted' : ''}" data-focus-key="mute:${sid}" aria-pressed="${ch.mute}" aria-label="Mute ${esc(name)}">${ch.mute ? 'MUTED' : 'MUTE'}</button>`}
          <div class="fader-zone">
            ${METER(sid)}
            <div class="fader-well" data-focus-key="fader:${sid}:${activeLayer}">
              ${FADER_TICKS}
              <div class="fader-slot"></div>
              <div class="unity-mark"></div>
              <div class="fader-fill"></div>
              <div class="fader-cap"></div>
            </div>
          </div>
          <div class="strip-readout">${midiToDbStr(faderVal)}</div>
        `;

        const scribble = strip.querySelector('.scribble');
        const editBtn = strip.querySelector('.scribble-edit');
        if (editBtn) editBtn.onclick = () => openScribbleModal(ch);
        scribble.onclick = () => {
          if (selectedCh === ch.index && !isMaster) openScribbleModal(ch);
          else { selectedCh = ch.index; renderConsole(); renderDsp(); }
        };
        scribble.onkeydown = (e) => {
          if (e.target !== scribble || (e.key !== 'Enter' && e.key !== ' ')) return;
          e.preventDefault();
          scribble.click();
        };

        if (!isMaster) {
          strip.querySelector('.mute-switch').onclick = () =>
            postAction({ action: 'setMute', channel: ch.index, value: !ch.mute }).then(scheduleReload);
        }

        const readout = strip.querySelector('.strip-readout');
        attachVerticalFader(
          strip.querySelector('.fader-well'),
          faderVal,
          (v) => { readout.textContent = midiToDbStr(v); },
          (v) => {
            if (isSendLayer) postAction({ action: 'setSend', channel: ch.index, target: activeLayer, value: v });
            else postAction({ action: 'setFader', channel: ch.index, value: v });
          },
          isSendLayer ? `${name} send to ${activeLayer.toUpperCase()}` : `${name} fader`
        );
        bank.appendChild(strip);
      });
    }

    // 4 Bus Master Strips (MON 1, MON 2, FX 1, FX 2)
    if (mobileView !== 'faders' || window.innerWidth > 760) {
      session.buses.forEach((b) => {
        const strip = document.createElement('div');
        strip.className = 'strip bus-strip' + (b.id.startsWith('fx') ? ' layer-fx' : ' layer-mon');
        strip.dataset.strip = b.id;
        strip.innerHTML = `
          <div class="scribble" style="--lcd:${b.id.startsWith('fx') ? '#BC71FF' : '#FFB45B'}">
            <div class="scribble-top"><span class="scribble-num">BUS</span><span class="scribble-prov" title="${esc(provTitle(b.faderProvenance))}">${provCode(b.faderProvenance)}</span></div>
            <div class="scribble-name">${b.id.toUpperCase().replace(/(\d)/, ' $1')}</div>
          </div>
          <div class="lamp-row">
            ${LAMPS(b.id, b.faderProvenance)}
          </div>
          <div class="eq-thumb eq-thumb-none">${b.id.startsWith('fx') ? 'FX SEND' : 'MONITOR'}</div>
          <div class="strip-pan"><span class="strip-pan-val">MASTER</span></div>
          <div class="mute-na mute-spacer" aria-hidden="true"></div>
          <div class="fader-zone">
            ${METER(b.id)}
            <div class="fader-well" data-focus-key="fader:${b.id}">
              ${FADER_TICKS}
              <div class="fader-slot"></div>
              <div class="unity-mark"></div>
              <div class="fader-fill"></div>
              <div class="fader-cap"></div>
            </div>
          </div>
          <div class="strip-readout">${midiToDbStr(b.fader)}</div>
        `;
        const readout = strip.querySelector('.strip-readout');
        attachVerticalFader(
          strip.querySelector('.fader-well'),
          b.fader,
          (v) => { readout.textContent = midiToDbStr(v); },
          (v) => postAction({ action: 'setBusFader', bus: b.id, value: v }),
          `${b.id.toUpperCase()} master fader`
        );
        bank.appendChild(strip);
      });
    }
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

  function renderStatusBar() {
    if (!session) return;
    const set = (id, on) => document.getElementById(id).classList.toggle('on', !!on);
    set('lamp-usb', session.midiOutOpen);
    set('lamp-midi-in', session.midiInOpen);
    const scene = document.getElementById('scene-display');
    const cur = session.currentScene;
    scene.querySelector('.scene-name').textContent = cur ? cur.replace('SCENE ', 'S') : 'No scene';
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
  async function openPresetsModal() {
    if (!presets.length) {
      const res = await fetch('/api/presets');
      presets = (await res.json()).presets || [];
    }
    const ch = session?.channels.find((c) => c.index === selectedCh);
    const targetIdx = ch && ch.index <= 7 ? ch.index : 1;
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

  let scribbleTarget = null;
  function openScribbleModal(ch) {
    scribbleTarget = ch;
    const inp = document.getElementById('scribble-input');
    inp.value = (ch.label || ch.name).slice(0, 14);
    const counter = document.getElementById('scribble-count');
    const count = () => { counter.textContent = `${inp.value.length}/14`; };
    inp.oninput = count;
    count();
    document.getElementById('scribble-title').textContent = `RENAME CH ${String(ch.index).padStart(2, '0')}`;
    let chosenColor = ch.color || '#38bdf8';
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
  document.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape') return;
    const open = [...document.querySelectorAll('.modal-backdrop.open')];
    if (open.length) { e.preventDefault(); dismissModal(open[open.length - 1]); }
  });

  // ---------- Event Wiring ----------
  document.getElementById('layer-bar').querySelectorAll('.layer-btn').forEach((btn) => {
    btn.onclick = () => {
      activeLayer = btn.dataset.layer;
      document.querySelectorAll('.layer-btn').forEach((b) => { b.classList.remove('active'); b.setAttribute('aria-pressed', 'false'); });
      btn.classList.add('active');
      btn.setAttribute('aria-pressed', 'true');
      document.body.classList.toggle('layer-mon', activeLayer.startsWith('mon'));
      document.body.classList.toggle('layer-fx', activeLayer.startsWith('fx'));
      renderConsole();
    };
  });

  document.getElementById('mobile-nav').querySelectorAll('.mobile-tab').forEach((btn) => {
    btn.onclick = () => {
      mobileView = btn.dataset.view;
      document.querySelectorAll('.mobile-tab').forEach((b) => { b.classList.remove('active'); b.setAttribute('aria-selected', 'false'); });
      btn.classList.add('active');
      btn.setAttribute('aria-selected', 'true');
      // Fader layers apply to the FADERS view only.
      document.body.dataset.view = mobileView;
      document.getElementById('dsp-rack').classList.toggle('mobile-show', mobileView === 'dsp');
      document.getElementById('console-bank').classList.toggle('mobile-hide', mobileView === 'dsp');
      renderConsole();
    };
  });

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
  document.getElementById('btn-presets').onclick = openPresetsModal;
  document.getElementById('btn-close-presets').onclick = () => closeModal('preset-modal');
  document.getElementById('btn-close-scribble').onclick = () => closeModal('scribble-modal');
  document.getElementById('btn-eq-flat').onclick = () => {
    const target = selectedCh <= 7 ? selectedCh : 1;
    postAction({ action: 'resetEqFlat', channel: target }).then(loadSession);
  };

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
    if (e.target.closest('.fader-well, .knob-svg, #eq-canvas, .studio-range')) pointerBusy = true;
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
    renderConsole();
    renderDsp();
    renderStatusBar();
    if (focusKey) {
      const el = document.querySelector(`[data-focus-key="${CSS.escape(focusKey)}"]`);
      if (el) el.focus({ preventScroll: true });
    }
  }

  setupEqCanvasInteraction();
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
