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
    document.getElementById('status-text').textContent = connected ? 'MIDI OPEN' : 'DISCONNECTED';
  }

  function confirmAction(title, text, okLabel) {
    return new Promise((resolve) => {
      const modal = document.getElementById('confirm-modal');
      document.getElementById('confirm-title').textContent = title;
      document.getElementById('confirm-text').textContent = text;
      const ok = document.getElementById('btn-confirm-ok');
      const cancel = document.getElementById('btn-confirm-cancel');
      ok.textContent = okLabel;
      const done = (v) => {
        modal.classList.remove('open');
        ok.onclick = cancel.onclick = modal.onclick = null;
        resolve(v);
      };
      ok.onclick = () => done(true);
      cancel.onclick = () => done(false);
      modal.onclick = (e) => { if (e.target === modal) done(false); };
      modal.classList.add('open');
      cancel.focus();
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
      eqRow.appendChild(chip);
    });
    drawEqCanvas(ch);

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
      pad.setAttribute('aria-label', saved ? `Scene ${i}: tap to recall, hold to overwrite` : `Scene ${i}: empty, hold to save`);
      pad.onpointerdown = () => {
        cancelHold();
        void pad.offsetWidth; // restart the progress animation
        pad.classList.add('holding');
        timer = setTimeout(async () => {
          timer = null;
          pad.classList.remove('holding');
          held = true;
          if (saved && !(await confirmAction(`OVERWRITE S${i}?`, `Scene S${i} already holds a saved mix. Save the current mix over it?`, 'OVERWRITE'))) return;
          const res = await postAction({ action: 'captureScene', name });
          if (res.ok) showToast(`Saved current mix to S${i}.`);
          loadSession();
        }, HOLD_MS);
      };
      let held = false;
      pad.onpointerup = async () => {
        // The hold timer is still pending only when the finger lifted before the hold time.
        const wasTap = !!timer;
        cancelHold();
        if (held) { held = false; return; }
        if (!wasTap) return;
        if (!saved) { showToast(`S${i} is empty. Hold the pad to save the current mix.`); return; }
        const res = await postAction({ action: 'recallScene', name });
        if (res.ok) showToast(`Recalled S${i}.`);
        loadSession();
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
        <input class="studio-range" type="range" min="0" max="127" value="${val}" ${ch.index === 8 ? 'disabled' : ''} />
      `;
      const rng = box.querySelector('input');
      rng.oninput = () => { box.querySelector('.s-val').textContent = midiToDbStr(+rng.value); };
      rng.onchange = () => postAction({ action: 'setSend', channel: ch.index, target: t, value: +rng.value });
      sendsList.appendChild(box);
    });
  }

  // ---------- Vertical Fader Pointer Engine ----------
  function attachVerticalFader(well, initialVal, onMove, onCommit) {
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
      unity.style.bottom = `${14 + (101 / 127) * usable}px`;
    };
    requestAnimationFrame(() => updatePos(val));

    const valFromEvent = (e) => {
      const rect = well.getBoundingClientRect();
      const usable = Math.max(40, rect.height - 28);
      const yBottom = rect.bottom - e.clientY - 14;
      return Math.max(0, Math.min(127, Math.round((yBottom / usable) * 127)));
    };

    well.onpointerdown = (e) => {
      well.setPointerCapture(e.pointerId);
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
        const faderProv = isSendLayer ? activeLayer.toUpperCase() : ch.faderProvenance;

        const strip = document.createElement('div');
        strip.className = 'strip' + (isMaster ? ' master' : '') + (selectedCh === ch.index ? ' selected' : '') + (isSendLayer ? layerClass : '');
        const tagColor = ch.color || '#38bdf8';

        strip.innerHTML = `
          <div class="scribble">
            <div class="scribble-bar" style="background:${tagColor}"></div>
            <div class="scribble-top">
              <span class="scribble-num">${isMaster ? 'MAIN' : String(ch.index).padStart(2, '0')}</span>
              <span>${faderProv}</span>
            </div>
            <div class="scribble-name">${ch.label || ch.name}</div>
          </div>
          <div class="strip-pan">
            <span class="strip-pan-val">${panText(ch.pan)}</span>
          </div>
          ${isMaster ? '<div style="height:26px"></div>' : `<button class="mute-switch ${ch.mute ? 'muted' : ''}">${ch.mute ? 'MUTED' : 'MUTE'}</button>`}
          <div class="fader-well">
            <div class="fader-ticks">
              <div class="fader-tick">+10</div>
              <div class="fader-tick">0</div>
              <div class="fader-tick">-20</div>
              <div class="fader-tick">-∞</div>
            </div>
            <div class="fader-slot"></div>
            <div class="unity-mark"></div>
            <div class="fader-fill"></div>
            <div class="fader-cap"></div>
          </div>
          <div class="strip-readout">${midiToDbStr(faderVal)}</div>
        `;

        const scribble = strip.querySelector('.scribble');
        scribble.onclick = () => {
          if (selectedCh === ch.index && !isMaster) openScribbleModal(ch);
          else { selectedCh = ch.index; renderConsole(); renderDsp(); }
        };

        if (!isMaster) {
          strip.querySelector('.mute-switch').onclick = () =>
            postAction({ action: 'setMute', channel: ch.index, value: !ch.mute }).then(loadSession);
        }

        const readout = strip.querySelector('.strip-readout');
        attachVerticalFader(
          strip.querySelector('.fader-well'),
          faderVal,
          (v) => { readout.textContent = midiToDbStr(v); },
          (v) => {
            if (isSendLayer) postAction({ action: 'setSend', channel: ch.index, target: activeLayer, value: v });
            else postAction({ action: 'setFader', channel: ch.index, value: v });
          }
        );
        bank.appendChild(strip);
      });
    }

    // 4 Bus Master Strips (MON 1, MON 2, FX 1, FX 2)
    if (mobileView !== 'faders' || window.innerWidth > 760) {
      session.buses.forEach((b) => {
        const strip = document.createElement('div');
        strip.className = 'strip bus-strip' + (b.id.startsWith('fx') ? ' layer-fx' : ' layer-mon');
        strip.innerHTML = `
          <div class="scribble">
            <div class="scribble-bar" style="background:${b.id.startsWith('fx') ? '#a78bfa' : '#f59e0b'}"></div>
            <div class="scribble-top"><span class="scribble-num">BUS</span><span>${b.faderProvenance}</span></div>
            <div class="scribble-name">${b.id.toUpperCase()}</div>
          </div>
          <div class="strip-pan"><span class="strip-pan-val">MASTER</span></div>
          <div style="height:26px"></div>
          <div class="fader-well">
            <div class="fader-ticks">
              <div class="fader-tick">+10</div>
              <div class="fader-tick">0</div>
              <div class="fader-tick">-20</div>
              <div class="fader-tick">-∞</div>
            </div>
            <div class="fader-slot"></div>
            <div class="unity-mark"></div>
            <div class="fader-fill"></div>
            <div class="fader-cap"></div>
          </div>
          <div class="strip-readout">${midiToDbStr(b.fader)}</div>
        `;
        const readout = strip.querySelector('.strip-readout');
        attachVerticalFader(
          strip.querySelector('.fader-well'),
          b.fader,
          (v) => { readout.textContent = midiToDbStr(v); },
          (v) => postAction({ action: 'setBusFader', bus: b.id, value: v })
        );
        bank.appendChild(strip);
      });
    }
  }

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
          <h4>[${p.category}] ${p.name}</h4>
          <p>${p.summary}</p>
        </div>
        <button class="hw-btn accent">APPLY</button>
      `;
      item.querySelector('button').onclick = async () => {
        await postAction({ action: 'applyPreset', channel: targetIdx, presetId: p.id });
        document.getElementById('preset-modal').classList.remove('open');
        loadSession();
      };
      list.appendChild(item);
    });
    document.getElementById('preset-modal').classList.add('open');
  }

  let scribbleTarget = null;
  function openScribbleModal(ch) {
    scribbleTarget = ch;
    const inp = document.getElementById('scribble-input');
    inp.value = ch.label || ch.name;
    let chosenColor = ch.color || '#38bdf8';
    const box = document.getElementById('scribble-colors');
    box.innerHTML = '';
    SCRIBBLE_PALETTE.forEach((col) => {
      const dot = document.createElement('button');
      dot.style.cssText = `width:26px;height:26px;border-radius:50%;border:2px solid ${col === chosenColor ? '#fff' : 'transparent'};background:${col};cursor:pointer;`;
      dot.onclick = () => {
        chosenColor = col;
        [...box.children].forEach((c) => { c.style.borderColor = 'transparent'; });
        dot.style.borderColor = '#fff';
      };
      box.appendChild(dot);
    });
    document.getElementById('btn-save-scribble').onclick = async () => {
      await postAction({ action: 'setScribble', channel: ch.index, label: inp.value, color: chosenColor });
      document.getElementById('scribble-modal').classList.remove('open');
      loadSession();
    };
    document.getElementById('scribble-modal').classList.add('open');
  }

  // ---------- Event Wiring ----------
  document.getElementById('layer-bar').querySelectorAll('.layer-btn').forEach((btn) => {
    btn.onclick = () => {
      activeLayer = btn.dataset.layer;
      document.querySelectorAll('.layer-btn').forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      renderConsole();
    };
  });

  document.getElementById('mobile-nav').querySelectorAll('.mobile-tab').forEach((btn) => {
    btn.onclick = () => {
      mobileView = btn.dataset.view;
      document.querySelectorAll('.mobile-tab').forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
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
  document.getElementById('btn-undo').onclick = () => postAction({ action: 'undo' }).then(loadSession);
  document.getElementById('btn-redo').onclick = () => postAction({ action: 'redo' }).then(loadSession);
  document.getElementById('btn-presets').onclick = openPresetsModal;
  document.getElementById('btn-close-presets').onclick = () => document.getElementById('preset-modal').classList.remove('open');
  document.getElementById('btn-close-scribble').onclick = () => document.getElementById('scribble-modal').classList.remove('open');
  document.getElementById('btn-eq-flat').onclick = () => {
    const target = selectedCh <= 7 ? selectedCh : 1;
    postAction({ action: 'resetEqFlat', channel: target }).then(loadSession);
  };

  async function loadSession() {
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
  es.onmessage = () => loadSession();
})();
