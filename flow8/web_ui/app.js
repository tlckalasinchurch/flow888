(() => {
  const clientId = Math.random().toString(36).slice(2);
  let session = null;
  let activeLayer = 'main'; // 'main' | 'mon1' | 'mon2' | 'fx1' | 'fx2'
  // Inspector target: null (closed), { kind: 'ch', index: 1..7 } or { kind: 'bus', id: 'main'|'mon1'|... }
  let insp = null;
  let view = 'mixer'; // 'mixer' | 'stage' | 'setup'
  let lastLiveView = 'mixer';
  let setupPage = 'inputs';
  let topTab = 'mixer'; // 'mixer' | 'stage' | 'channel' | 'input' | 'eq' | 'comp' | 'sends' | 'fx' | 'presets' | 'setup'
  let selectedCh = 1; // 1..7
  let selectedEqBand = 'low'; // 'lc' | 'low' | 'low_mid' | 'hi_mid' | 'hi'
  let dspClipboard = null;
  let flowAiOpen = false;
  let pendingPlan = null;
  let planPreview = null;
  let presetCategory = 'all';
  let presetQuery = '';
  let selectedPresetId = 'th-pa-mc';
  let presetScopes = { low_cut: true, eq: true, compressor: true };
  let latestMeterLevels = {};

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
  // Band frequencies and shapes as printed in the manufacturer specification
  // (Quick Start Guide V1.0, PDF p. 9; evidence E01, conflict C-04). The guide does
  // not say what the frequency means (corner or centre) and gives no Q, so no
  // response curve is drawn. Only the gain values are exact.
  const BANDS = [
    { key: 'low', label: 'LOW', shortLabel: '1 LOW', hz: '20 Hz', shape: 'Shelving', color: '#2EF2E2' },
    { key: 'low_mid', label: 'LO MID', shortLabel: '2 LOW MID', hz: '300 Hz', shape: null, color: '#52E59A' },
    { key: 'hi_mid', label: 'HI MID', shortLabel: '3 HIGH MID', hz: '1.5 kHz', shape: null, color: '#FFB45B' },
    { key: 'hi', label: 'HIGH', shortLabel: '4 HIGH', hz: '20 kHz', shape: 'Shelving', color: '#BC71FF' },
  ];
  const EQ_SPEC_NOTE = 'ความถี่ตามสเปกผู้ผลิต (Quick Start Guide V1.0) · Q ไม่ทราบ';
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

  // Same POST without the error toast: used for the many intermediate values of
  // one drag, where a toast per frame would be noise.
  async function quietAction(payload) {
    try {
      const res = await fetch('/api/action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...payload, clientId }),
      });
      let body = {};
      try { body = await res.json(); } catch (_) { /* non-JSON error body */ }
      if (!res.ok || body.ok === false) {
        if (body.error) showToast(body.error, true);
        // Keep the rest of the body: a 409 carries staleParameters and fresh rows.
        return { ...body, ok: false };
      }
      return body;
    } catch (_) {
      return { ok: false, error: 'network' };
    }
  }

  const sendAction = (payload, quiet) => (quiet ? quietAction(payload) : postAction(payload));

  // One pointer drag is one ledger step: pointer-down opens a batch on the hub,
  // intermediate values are sent at most every 70 ms, and pointer-up sends the
  // final value and closes the batch.
  const dragBatch = { open: false, timer: null, send: null, value: null };

  function beginDragGesture() {
    if (dragBatch.open || !session || !session.midiConnected) return;
    dragBatch.open = true;
    quietAction({ action: 'beginGesture' });
  }

  function dragSendThrottled(send, value) {
    if (!dragBatch.open) return;
    dragBatch.send = send;
    dragBatch.value = value;
    if (dragBatch.timer) return;
    dragBatch.timer = setTimeout(() => {
      dragBatch.timer = null;
      if (dragBatch.open && dragBatch.send) dragBatch.send(dragBatch.value);
    }, 70);
  }

  async function endDragGesture(send, value) {
    if (!dragBatch.open) {
      if (send) await send(value);
      return;
    }
    clearTimeout(dragBatch.timer);
    dragBatch.timer = null;
    dragBatch.open = false;
    if (send) await send(value);
    await quietAction({ action: 'endGesture' });
    scheduleReload();
  }

  // USB audio is independent of MIDI: losing the capture stream stops the meters
  // but must not pretend the mixer is offline.
  function applyMeterState() {
    const el = document.getElementById('meter-banner');
    if (!el) return;
    const ms = (session && session.meterStatus) || {};
    const lost = ms.state === 'error';
    el.hidden = !lost;
    if (lost) {
      el.textContent = `USB AUDIO LOST — ${ms.detail || 'the capture stream stopped.'} `
        + 'Mixer control continues if MIDI is online; meters retry automatically.';
    }
  }

  // One plain sentence for why the mixer can or cannot be controlled right now.
  // Only observed facts: the transport snapshot the hub reports, never a guess.
  function linkSummary(sess) {
    const tr = (sess && sess.transport) || null;
    if (!tr) {
      const ok = !!(sess && sess.midiConnected);
      return ok
        ? { ok: true, pill: 'MIXER ONLINE', banner: '', title: 'The FLOW 8 is connected.' }
        : { ok: false, pill: 'DISCONNECTED', banner: 'MIXER NOT CONNECTED — controls are locked. Connect the FLOW 8 to the host computer by USB.', title: 'No link to the FLOW 8. Commands are not sent.' };
    }
    const mode = tr.mode || 'usb_midi';
    const usb = tr.usb || {};
    const ble = tr.ble || {};
    const label = { usb_midi: 'USB MIDI', ble: 'BLUETOOTH', hybrid: 'HYBRID' }[mode] || mode;
    if (tr.controlConnected && (mode !== 'usb_midi' || sess.midiConnected !== false)) {
      return { ok: true, pill: 'MIXER ONLINE', banner: '', title: `The FLOW 8 is connected (${label}). SENT values are what this app sent; the mixer does not report every value back.` };
    }
    const seen = (usb.devicesSeen || []).join(', ');
    const usbWhy = {
      no_midi_devices: 'Windows lists no MIDI devices. Check the USB cable and that the mixer is on.',
      flow8_not_listed: `FLOW 8 is not in the Windows MIDI list${seen ? ` (seen: ${seen})` : ''}. Check the USB cable, that the mixer is on, and that it is in USB mode.`,
      open_failed: `FLOW 8 is listed but could not be opened${usb.error ? `: ${usb.error}` : ''}. Another program may be using it.`,
    }[usb.diagnosis] || (usb.error || 'USB MIDI is not connected.');
    const bleWhy = ble.authenticated
      ? 'Bluetooth is confirmed.'
      : ble.connected
        ? `Bluetooth is connected but the mixer has not confirmed it (RX ${ble.packetsRx || 0}).`
        : `Bluetooth is not connected${ble.error ? `: ${ble.error}` : ''}.`;
    if (mode === 'usb_midi') {
      const pill = usb.diagnosis === 'open_failed' ? 'USB BUSY' : 'USB NOT FOUND';
      return { ok: false, pill, banner: `MIXER NOT CONNECTED — ${usbWhy}`, title: usbWhy };
    }
    if (mode === 'ble') {
      return { ok: false, pill: ble.connected ? 'BLE WAITING' : 'BLE NOT FOUND', banner: `MIXER NOT CONNECTED — ${bleWhy} Switch to USB MIDI on Setup, Connection if you have the cable.`, title: bleWhy };
    }
    const usbOk = !!usb.connected;
    const text = usbOk
      ? `HYBRID mode needs Bluetooth for commands. USB is ready, but ${bleWhy} Switch to USB MIDI on Setup, Connection.`
      : `${usbWhy} ${bleWhy}`;
    return { ok: false, pill: usbOk ? 'HYBRID: BLE DOWN' : 'NOT CONNECTED', banner: `MIXER NOT CONNECTED — ${text}`, title: text };
  }

  function openRoutingFromPill() {
    setupPage = 'routing';
    const tab = document.querySelector('.cue-group[data-group="setup"]');
    if (tab) tab.click();
  }

  // Show the connection state: banner, status pill, and locked controls.
  function applyConnectionState(connected, message, pillText, pillTitle) {
    document.body.classList.toggle('offline', !connected);
    const banner = document.getElementById('conn-banner');
    banner.hidden = connected;
    banner.textContent = message || 'MIXER NOT CONNECTED — controls are locked. Connect the FLOW 8 to the host computer by USB.';
    const pill = document.getElementById('status-pill');
    pill.classList.toggle('online', connected);
    pill.classList.toggle('offline', !connected);
    document.getElementById('status-text').textContent = pillText || (connected ? 'MIXER ONLINE' : 'DISCONNECTED');
    pill.title = pillTitle || (connected
      ? 'The FLOW 8 is connected by USB MIDI. SENT values are what this app sent; the mixer does not report every value back.'
      : 'No USB MIDI link to the FLOW 8. Commands are not sent.');
  }
  (() => {
    const pill = document.getElementById('status-pill');
    pill.onclick = openRoutingFromPill;
    pill.onkeydown = (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openRoutingFromPill(); } };
  })();

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
  // Same curve as parameter_mapping.eq_midi_to_db / eq_db_to_midi: 64 = 0 dB.
  const eqRawToDb = (raw) => (raw === 64 ? 0
    : raw < 64 ? ((raw - 64) / 64) * 15 : ((raw - 64) / 63) * 15);
  const dbToEqRaw = (db) => {
    const c = Math.max(-15, Math.min(15, db));
    if (c === 0) return 64;
    return c < 0
      ? Math.max(0, Math.min(64, Math.round(64 + (c / 15) * 64)))
      : Math.max(64, Math.min(127, Math.round(64 + (c / 15) * 63)));
  };
  const eqText = (raw) => { const d = eqRawToDb(raw); return `${d > 0.05 ? '+' : ''}${d.toFixed(1)} dB`; };
  function panText(raw) {
    const pct = Math.round(((raw - 64) / 63.5) * 100);
    if (Math.abs(pct) <= 1) return 'C';
    return pct < 0 ? `L${Math.abs(pct)}` : `R${pct}`;
  }
  const hpfHz = (raw) => (raw <= 0 ? 'OFF' : `${Math.round(20 + (raw / 127) * 580)} Hz`);
  // Inverse of hpfHz for building a plan in the unit the engineer thinks in.
  const hzToHpfRaw = (hz) => Math.max(0, Math.min(127, Math.round(((hz - 20) / 580) * 127)));
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
  // 3-letter form for strips under 1180 px, where the long code does not fit.
  const PROV_SHORT = { UNSYNCED: 'UNS', COMMANDED: 'CMD', OBSERVED: 'OBS', DISPATCH_FAILED: 'ERR', UNSUPPORTED: 'N/A' };
  const provBadge = (p, hint) =>
    `<span class="scribble-prov prov-${p}" role="img" aria-label="${esc(hint)}" title="${esc(hint)}">` +
    `<span class="prov-long">${provCode(p)}</span><span class="prov-short" aria-hidden="true">${PROV_SHORT[p] || p}</span></span>`;
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
    latestMeterLevels = levels || {};
    Object.entries(latestMeterLevels).forEach(([id, l]) => {
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

  // ---------- EQ gain display: the four commanded band gains, no response curve ----------
  // Bars sit at equal spacing, not on a frequency axis: the band frequencies come
  // from the manufacturer specification, but their meaning and Q are unknown (C-04).
  function eqGainBarsSvg(gainsDb, w, h) {
    const mid = h / 2;
    const slot = w / gainsDb.length;
    const barW = slot * 0.5;
    return gainsDb.map((db, i) => {
      const d = Math.max(-15, Math.min(15, db || 0));
      const len = (Math.abs(d) / 15) * (mid - 1);
      const x = (i * slot + (slot - barW) / 2).toFixed(1);
      const y = (d >= 0 ? mid - len : mid).toFixed(1);
      return `<rect class="eq-gain-bar" x="${x}" y="${y}" width="${barW.toFixed(1)}" height="${Math.max(0.6, len).toFixed(1)}" fill="${BANDS[i].color}"/>`;
    }).join('');
  }

  // Limiter threshold: chart end points -30 dB (raw 0) to 0 dB (raw 127); linear in between is approximate.
  const limiterText = (raw) => `≈ ${(-30 + (raw / 127) * 30).toFixed(1)} dB`;

  const channelGainsDb = (ch) => BANDS.map((b) => eqRawToDb(ch.eq ? (ch.eq[b.key] ?? 64) : 64));



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
      beginDragGesture();
    };
    svg.onpointermove = (e) => {
      if (!svg.hasPointerCapture(e.pointerId)) return;
      const span = fineDrag(e) ? 560 : 140; // FINER SLIDERS or Shift: a quarter of the speed
      const delta = Math.round(((startY - e.clientY) / span) * (max - min));
      current = Math.max(min, Math.min(max, startVal + delta));
      updateVisual(current);
      dragSendThrottled(() => onCommit(current, true), current);
    };
    svg.onpointerup = (e) => {
      if (!svg.hasPointerCapture(e.pointerId)) return;
      svg.releasePointerCapture(e.pointerId);
      endDragGesture(() => onCommit(current, true), current);
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
      beginDragGesture();
    };
    well.onpointermove = (e) => {
      if (!well.hasPointerCapture(e.pointerId)) return;
      if (fine) {
        const usable = Math.max(40, well.getBoundingClientRect().height - 28);
        val = Math.max(0, Math.min(127, Math.round(fine.v + ((fine.y - e.clientY) / usable) * 127 / 4)));
      } else val = valFromEvent(e);
      updatePos(val);
      onMove(val);
      dragSendThrottled(() => onCommit(val, true), val);
    };
    well.onpointerup = (e) => {
      if (!well.hasPointerCapture(e.pointerId)) return;
      well.releasePointerCapture(e.pointerId);
      well.classList.remove('grab');
      syncKeys();
      endDragGesture(() => onCommit(val, true), val);
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

  // Read-only summary under each scribble strip (full-size bank only): input
  // type, locked-feature chips, sends, EQ curve and compressor. Moved here from
  // the old overview pane so the strips are shown once.
  function stripInfo(ch) {
    const gainStr = ch.index <= 4 ? gainText(ch.gain) : 'LINE';
    const compVal = ch.index <= 4 ? Math.round(((ch.compressor || 0) / 127) * 100) : null;
    const s = ch.sends || {};
    const bar = (label, v, color) => `<div class="ov-send-row"><span>${label}</span><div class="ov-send-track"><div class="ov-send-fill" style="width:${Math.round(((v || 0) / 127) * 100)}%;background:${color}"></div></div></div>`;
    return `<div class="strip-info">
      <div class="ov-head"><span class="ov-tag">${ch.index <= 4 ? 'GAIN' : 'INPUT'}</span><span class="ov-gain" title="${esc(lockReason('gain'))}">${gainStr}</span></div>
      <div class="ov-chips">
        <span class="ov-chip locked" title="${esc(lockReason('routing'))}">Ø</span>
        ${ch.index <= 2 ? `<span class="ov-chip locked" title="${esc(lockReason('phantom'))}">48V</span>` : ''}
        ${ch.index >= 5 && ch.index <= 6 ? `<span class="ov-chip locked" title="${esc(lockReason('stereoLink'))}">LINK</span>` : ''}
        ${ch.index <= 4 ? `<span class="ov-chip">LC ${hpfHz(ch.lowCut || 0)}</span>` : ''}
      </div>
      <div class="ov-sends">${bar('M1', s.mon1, '#34D399')}${bar('M2', s.mon2, '#34D399')}${bar('FX1', s.fx1, '#A78BFA')}${bar('FX2', s.fx2, '#A78BFA')}</div>
      <div class="ov-curves">
        <svg class="ov-eq-svg" viewBox="0 0 60 22" preserveAspectRatio="none" role="button" tabindex="0" aria-label="Open EQ for channel ${ch.index}"><line x1="0" y1="11" x2="60" y2="11" stroke="#242933" stroke-width="1"/>${eqGainBarsSvg(channelGainsDb(ch), 60, 22)}</svg>
        <div class="ov-comp-box" role="button" tabindex="0" aria-label="Open compressor for channel ${ch.index}">${compVal == null ? '—' : ch.compressorProvenance === 'UNSYNCED' ? '--' : `${compVal}%`}</div>
      </div>
    </div>`;
  }

  function renderConsole() {
    if (!session) return;
    const link = linkSummary(session);
    applyConnectionState(link.ok, link.banner, link.pill, link.title);
    const allMuted = session.channels.filter((c) => c.index <= 7).every((c) => c.mute);
    const muteAllBtn = document.getElementById('btn-mute-all');
    muteAllBtn.textContent = allMuted ? 'UNMUTE ALL' : 'MUTE ALL';
    muteAllBtn.dataset.hold = allMuted ? '' : 'arm'; // only muting needs the hold
    muteAllBtn.title = allMuted ? 'Restore every input mute to unmuted.' : 'Hold 0.6 s to mute all inputs.';
    document.getElementById('all-muted-chip').hidden = !allMuted;
    const bank = document.getElementById('console-bank');
    bank.innerHTML = '';
    const sendLayer = activeLayer !== 'main';
    const layer = LAYERS[activeLayer];

    session.channels.filter((c) => c.index <= 7).forEach((ch) => {
      const sid = stripIdForChannel(ch.index);
      const name = chName(ch);
      const val = sendLayer ? (ch.sends ? ch.sends[activeLayer] : 0) : ch.fader;
      // The send provenance comes from the hub, so a default 0 is never shown as a sent value.
      const prov = sendLayer
        ? ((ch.sendsProvenance && ch.sendsProvenance[activeLayer]) || 'UNSYNCED')
        : ch.faderProvenance;
      const hint = (sendLayer ? `Send level from ${name} to ${layer.label}. ` : '') + provTitle(prov);
      // An UNSYNCED value is unknown: show it as unknown, never as a reading.
      const faderUnk = prov === 'UNSYNCED';
      const panUnk = ch.panProvenance === 'UNSYNCED';
      const muteUnk = ch.muteProvenance === 'UNSYNCED';
      const selected = selectedCh === ch.index;
      const strip = document.createElement('div');
      strip.dataset.strip = sid;
      strip.className = 'strip' + (ch.index === 7 ? ' usb' : '') + (selected ? ' selected' : '') + (faderUnk ? ' fader-unk' : '') + (panUnk ? ' pan-unk' : '');
      strip.innerHTML = `
        <div class="mix-bar" aria-hidden="true"></div>
        <div class="scribble" role="button" tabindex="0" data-focus-key="scribble:${sid}" aria-label="${esc(name)}: select channel" aria-pressed="${selected}" style="--lcd:${lcdColor(ch)}">
          <div class="scribble-top">
            <span class="scribble-num">${String(ch.index).padStart(2, '0')} · ${STRIP_TAG[ch.index]}</span>
            ${provBadge(prov, hint)}
          </div>
          <div class="scribble-name" title="${esc(name)}">${esc(name)}</div>
        </div>
        ${stripInfo(ch)}
        <div class="lamp-row">${LAMPS(sid, prov)}</div>
        <div class="strip-pan-ctrl" title="Pan L–C–R">
          <input type="range" min="0" max="127" value="${ch.pan}" aria-label="${esc(name)} pan" />
          <span class="strip-pan-val">${panUnk ? '--' : panText(ch.pan)}</span>
        </div>
        <div class="fader-zone">
          ${METER(sid)}
          ${FADER_WELL(`fader:${sid}:${activeLayer}`)}
        </div>
        <div class="strip-readout${faderUnk ? ' unk' : prov === 'OBSERVED' ? ' obs' : ''}">${faderUnk ? '--' : midiToDbStr(val)}</div>
        <button class="mute-switch ${ch.mute ? 'muted' : ''}${muteUnk ? ' unknown' : ''}" data-focus-key="mute:${sid}" aria-pressed="${muteUnk ? 'mixed' : ch.mute}" aria-label="Mute ${esc(name)}${muteUnk ? ' (state unknown)' : ''}"${muteUnk ? ' title="Mute state unknown: not sent or reported yet"' : ''}>${ch.mute ? 'MUTED' : 'MUTE'}</button>
      `;
      strip.querySelector('.scribble').onclick = () => selectChannel(ch.index);
      strip.querySelector('.scribble').onkeydown = (e) => {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); selectChannel(ch.index); }
      };
      const openTool = (tab) => (e) => {
        if (e.type === 'keydown' && e.key !== 'Enter' && e.key !== ' ') return;
        e.preventDefault(); e.stopPropagation(); selectChannel(ch.index, tab);
      };
      const eqThumb = strip.querySelector('.ov-eq-svg');
      const compBox = strip.querySelector('.ov-comp-box');
      eqThumb.onclick = eqThumb.onkeydown = openTool('eq');
      compBox.onclick = compBox.onkeydown = openTool('comp');
      const panInput = strip.querySelector('.strip-pan-ctrl input');
      const panLabel = strip.querySelector('.strip-pan-val');
      panInput.oninput = () => { panLabel.textContent = panText(+panInput.value); strip.classList.remove('pan-unk'); };
      panInput.onchange = () => postAction({ action: 'setPan', channel: ch.index, value: +panInput.value });
      strip.querySelector('.mute-switch').onclick = () =>
        postAction({ action: 'setMute', channel: ch.index, value: !ch.mute }).then(scheduleReload);
      const readout = strip.querySelector('.strip-readout');
      attachVerticalFader(
        strip.querySelector('.fader-well'), faderUnk ? 0 : val,
        (v) => { readout.textContent = midiToDbStr(v); readout.classList.remove('unk'); strip.classList.remove('fader-unk'); },
        (v) => (sendLayer
          ? postAction({ action: 'setSend', channel: ch.index, target: activeLayer, value: v })
          : postAction({ action: 'setFader', channel: ch.index, value: v })),
        sendLayer ? `${name} send to ${layer.label}` : `${name} fader`
      );
      bank.appendChild(strip);
    });

    // The master strip follows the selected mix, with a Bus selector dropdown.
    const m = masterOf(activeLayer);
    const mUnk = m.prov === 'UNSYNCED';
    const mainBal = session.channels.find((c) => c.index === 8);
    const selected = insp && insp.kind === 'bus' && insp.id === activeLayer;
    const strip = document.createElement('div');
    strip.dataset.strip = m.sid;
    strip.className = 'strip master' + (selected ? ' selected' : '') + (mUnk ? ' fader-unk' : '');
    strip.innerHTML = `
      <div class="mix-bar" aria-hidden="true"></div>
      <div class="scribble master-lcd" role="button" tabindex="0" data-focus-key="scribble:master" aria-label="${layer.label} master">
        <div class="scribble-top">
          <span class="scribble-num">MAIN LR</span>
          ${provBadge(m.prov, provTitle(m.prov))}
        </div>
        <select class="bus-select" aria-label="Select fader bus">
          ${LAYER_ORDER.map((id) => `<option value="${id}" ${id === activeLayer ? 'selected' : ''}>${LAYERS[id].label}</option>`).join('')}
        </select>
      </div>
      <div class="lamp-row">${LAMPS(m.sid, m.prov)}</div>
      <div class="strip-pan"><span class="strip-pan-val">${activeLayer === 'main' ? `BAL ${mainBal.panProvenance === 'UNSYNCED' ? '--' : panText(mainBal.pan)}` : layer.name}</span></div>
      <div class="fader-zone">
        ${METER(m.sid)}
        ${FADER_WELL(`fader:master:${activeLayer}`)}
      </div>
      <div class="strip-readout${mUnk ? ' unk' : m.prov === 'OBSERVED' ? ' obs' : ''}">${mUnk ? '--' : midiToDbStr(m.fader)}</div>
      <div class="mute-spacer" aria-hidden="true"></div>
    `;
    const busSel = strip.querySelector('.bus-select');
    busSel.onclick = (e) => e.stopPropagation();
    busSel.onchange = () => setLayer(busSel.value);
    // The master label opens the Inspector for the bus on the faders (limiter, GEQ, FX engine).
    wireScribble(strip.querySelector('.master-lcd'), { kind: 'bus', id: activeLayer });
    const readout = strip.querySelector('.strip-readout');
    attachVerticalFader(strip.querySelector('.fader-well'), mUnk ? 0 : m.fader,
      (v) => { readout.textContent = midiToDbStr(v); readout.classList.remove('unk'); strip.classList.remove('fader-unk'); }, m.commit, `${layer.label} master fader`);
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

  // RESET builds a reviewed plan instead of firing five commands: the curve is
  // the same, but the engineer sees what will be sent and can refuse it.
  function openEqResetPlan(ch) {
    const changes = BANDS.map((b) => ({
      channel: ch.index, parameter: `eq_${b.key}`, value: 64,
      reason: `RESET EQ · ${b.label} to 0.0 dB`, risk: 'low',
    }));
    if (ch.index <= 4) {
      changes.push({
        channel: ch.index, parameter: 'low_cut', value: 0,
        reason: 'RESET EQ · Low Cut OFF', risk: 'low',
      });
    }
    previewPlan({ title: `RESET EQ · CH ${String(ch.index).padStart(2, '0')}`, changes });
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

    // Channel keys: mute, rename, presets.
    const keys = document.createElement('div');
    keys.className = 'insp-keys';
    keys.innerHTML = `
      <button class="mute-switch ${ch.mute ? 'muted' : ''}" data-focus-key="insp-mute" aria-pressed="${ch.mute}">${ch.mute ? 'MUTED' : 'MUTE'}</button>
      <button class="key-btn" data-focus-key="insp-rename">✎ RENAME</button>
      <button class="key-btn accent" data-focus-key="insp-presets">★ PRESETS</button>`;
    keys.children[0].onclick = () => postAction({ action: 'setMute', channel: idx, value: !ch.mute }).then(scheduleReload);
    keys.children[1].onclick = () => openScribbleModal(ch);
    keys.children[2].onclick = () => { closeInspector(); selectChannel(idx, 'presets'); };
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
        onCommit: (v, quiet) => sendAction({ action: 'setLowCut', channel: idx, value: v }, quiet),
      }));
      knobs.appendChild(createRotaryKnob({
        label: 'COMP', valueText: `${ch.compressor}%`, raw: ch.compressor, min: 0, max: 100, color: '#A78BFA',
        focusKey: `insp:${sid}:comp`,
        onMove: (v) => `${v}%`,
        onCommit: (v, quiet) => sendAction({ action: 'setCompressor', channel: idx, value: v }, quiet),
      }));
    }
    knobs.appendChild(createRotaryKnob({
      label: has14 ? 'PAN' : 'BALANCE', valueText: panText(ch.pan), raw: ch.pan, min: 0, max: 127, color: '#3FD2E0', bipolar: true,
      focusKey: `insp:${sid}:pan`,
      onMove: panText,
      onCommit: (v, quiet) => sendAction({ action: 'setPan', channel: idx, value: v }, quiet),
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

    // 4-band EQ: band knobs with the manufacturer-spec frequency under each.
    const eq = section('EQ · 4-BAND', `<span title="${esc(provTitle(ch.eqProvenance))}">${provCode(ch.eqProvenance)}</span>`);
    const resetBtn = document.createElement('button');
    resetBtn.className = 'key-btn small';
    resetBtn.textContent = 'RESET';
    resetBtn.dataset.focusKey = 'insp-eq-flat';
    resetBtn.setAttribute('aria-label', `Review an EQ reset for ${name}`);
    resetBtn.onclick = () => openEqResetPlan(ch);
    eq.el.querySelector('.sec-hdr').appendChild(resetBtn);
    const bandRow = document.createElement('div');
    bandRow.className = 'knob-row bands';
    BANDS.forEach((b) => {
      const cell = createRotaryKnob({
        label: `${b.label}`, valueText: eqText(ch.eq[b.key]), raw: ch.eq[b.key], min: 0, max: 127, color: b.color, bipolar: true,
        focusKey: `insp:${sid}:eq:${b.key}`,
        onMove: (v) => { ch.eq[b.key] = v; return eqText(v); },
        onCommit: (v, quiet) => sendAction({ action: 'setEqBand', channel: idx, band: b.key, value: v }, quiet),
      });
      const hz = document.createElement('span');
      hz.className = 'knob-hz';
      hz.textContent = b.hz;
      hz.title = 'Manufacturer specification; meaning of the frequency and Q unknown (C-04)';
      cell.appendChild(hz);
      bandRow.appendChild(cell);
    });
    eq.body.appendChild(bandRow);
    const eqNote = document.createElement('p');
    eqNote.className = 'sec-note';
    eqNote.textContent = `${EQ_SPEC_NOTE}. No response curve is drawn; the gain values are exact.`;
    eq.body.appendChild(eqNote);
    body.appendChild(eq.el);
    // Sends.
    const sends = section('SENDS', 'POST-FADER LEVELS');
    ['mon1', 'mon2', 'fx1', 'fx2'].forEach((t) => {
      sends.body.appendChild(levelRow({
        label: LAYERS[t].label, color: LAYERS[t].color, value: ch.sends ? ch.sends[t] : 0,
        aria: `${name} send to ${LAYERS[t].label}`, focusKey: `insp:${sid}:send:${t}`,
        onCommit: (v, quiet) => sendAction({ action: 'setSend', channel: idx, target: t, value: v }, quiet),
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
        onCommit: (v, quiet) => sendAction({ action: 'setPan', channel: 8, value: v }, quiet),
      }));
      lvl.body.appendChild(row);
    }
    body.appendChild(lvl.el);

    if (!id.startsWith('fx')) {
      // Limiter and 9-band GEQ: documented (chart CC 8, CC 11-19), sent as commanded values.
      // The mixer reports neither, so an unsent value shows "--" (UNSYNCED).
      const dsp = (session.busDsp && session.busDsp[id]) || null;
      const limKnown = dsp && dsp.limiterProvenance !== 'UNSYNCED';
      const lim = section('LIMITER', dsp ? provCode(dsp.limiterProvenance) : 'UNSYNCED');
      const row = document.createElement('div');
      row.className = 'knob-row';
      row.appendChild(createRotaryKnob({
        label: 'LIMIT', valueText: limKnown ? limiterText(dsp.limiter) : '--', raw: limKnown ? dsp.limiter : null,
        min: 0, max: 127, color: '#FFB020', focusKey: `insp:${id}:limiter`,
        onMove: limiterText,
        onCommit: (v, quiet) => sendAction({ action: 'setBusLimiter', bus: id, value: v }, quiet),
      }));
      lim.body.appendChild(row);
      const limNote = document.createElement('p');
      limNote.className = 'sec-note';
      limNote.textContent = 'Threshold −30 to 0 dB (chart end points; the curve between them is approximate).';
      lim.body.appendChild(limNote);
      body.appendChild(lim.el);

      const geq = section('GRAPHIC EQ · 9-BAND', '±15 dB');
      const bands = document.createElement('div');
      bands.className = 'geq geq-live';
      GEQ_BANDS.forEach((bandLabel, i) => {
        const band = i + 1;
        const known = dsp && dsp.geqProvenance[i] !== 'UNSYNCED';
        const raw = dsp ? dsp.geq[i] : 64;
        const cell = document.createElement('div');
        cell.className = 'geq-band' + (known ? '' : ' unk');
        cell.innerHTML = `
          <span class="geq-val">${known ? eqText(raw) : '--'}</span>
          <input class="geq-slider" type="range" min="0" max="127" value="${raw}" data-focus-key="insp:${id}:geq${band}"
            aria-label="${esc(LAYERS[id].label)} GEQ ${bandLabel} Hz" />
          <span class="geq-hz">${bandLabel}</span>`;
        const input = cell.querySelector('input');
        const val = cell.querySelector('.geq-val');
        input.oninput = () => { val.textContent = eqText(+input.value); cell.classList.remove('unk'); };
        input.onchange = () => sendAction({ action: 'setBusGeq', bus: id, band, value: +input.value });
        bands.appendChild(cell);
      });
      geq.body.appendChild(bands);
      const geqNote = document.createElement('p');
      geqNote.className = 'sec-note';
      geqNote.textContent = 'Bands 63 Hz to 16 kHz as the FLOW app labels them (the chart prints 62 Hz, C-11). Values are what this console sent; the mixer does not report them.';
      geq.body.appendChild(geqNote);
      body.appendChild(geq.el);
      return;
    }

    // FX engine: preset (Program Change 1-16 on MIDI ch 13/14), parameter 1 (CC 1, 0-100 %)
    // and parameter 2 (CC 2, A/B). FX mute and tap tempo stay locked: they use channel 16.
    const fx = FX_ENGINE[id];
    const st = (session.fxEngines && session.fxEngines[id]) || null;
    const presetKnown = st && st.presetProvenance !== 'UNSYNCED';
    const p1Known = st && st.param1Provenance !== 'UNSYNCED';
    const p2Known = st && st.param2Provenance !== 'UNSYNCED';
    const eng = section(`${layer.label} ENGINE`, presetKnown ? `PRESET ${st.preset} · ${provCode(st.presetProvenance)}` : 'PRESET UNSYNCED');
    const row = document.createElement('div');
    row.className = 'fx-top';
    row.appendChild(createRotaryKnob({
      label: fx.param, valueText: p1Known ? `${Math.min(100, st.param1)}%` : '--', raw: p1Known ? Math.min(100, st.param1) : null,
      min: 0, max: 100, color: '#A78BFA', focusKey: `insp:${id}:param1`,
      onMove: (v) => `${v}%`,
      onCommit: (v, quiet) => sendAction({ action: 'setFxParam', engine: id, param: 1, value: v }, quiet),
    }));
    const side = document.createElement('div');
    side.className = 'fx-side';
    side.innerHTML = `
      <div class="seg" role="group" aria-label="${fx.param} mode">
        ${fx.modes.map((md, i) => `<button class="seg-btn live ${p2Known && (st.param2 ? 1 : 0) === i ? 'on' : ''}" data-mode="${i}" aria-pressed="${p2Known && (st.param2 ? 1 : 0) === i}">${md}</button>`).join('')}
      </div>
      ${fx.tap ? `<button class="tap-pad" aria-disabled="true" title="${esc(lockReason('tap'))}">TAP TEMPO · — BPM</button>` : ''}
      <button class="key-btn locked fx-mute" aria-disabled="true" title="${esc(lockReason('fxMute'))}">FX MUTE</button>`;
    side.querySelectorAll('.seg-btn').forEach((b) => {
      b.onclick = () => postAction({ action: 'setFxParam', engine: id, param: 2, value: b.dataset.mode === '1' }).then(scheduleReload);
    });
    side.querySelectorAll('.tap-pad, .fx-mute').forEach((b) => {
      b.onclick = () => showToast(lockReason(b.classList.contains('tap-pad') ? 'tap' : 'fxMute'));
    });
    row.appendChild(side);
    eng.body.appendChild(row);
    const grid = document.createElement('div');
    grid.className = 'fx-grid';
    grid.setAttribute('role', 'group');
    grid.setAttribute('aria-label', `${layer.label} presets`);
    for (let i = 1; i <= 16; i++) {
      const b = document.createElement('button');
      const active = presetKnown && st.preset === i;
      b.className = 'fx-preset live' + (active ? ' on' : '');
      b.setAttribute('aria-pressed', active);
      b.innerHTML = `<span class="fx-name">${esc(fx.presets[i - 1])}</span><span class="fx-no">No. ${i}</span>`;
      b.onclick = () => postAction({ action: 'setFxPreset', engine: id, value: i }).then(scheduleReload);
      grid.appendChild(b);
    }
    eng.body.appendChild(grid);
    const fxNote = document.createElement('p');
    fxNote.className = 'sec-note';
    fxNote.textContent = 'Preset names as the FLOW app shows them. The mixer does not report the active preset, so the highlight is the last one this console sent.';
    eng.body.appendChild(fxNote);
    body.appendChild(eng.el);
  }

  // ---------- Stage view ----------
  // Large level knobs for the mix on the faders, with the live input level as a ring.
  function renderStage(hostEl) {
    const host = hostEl || document.getElementById('stage-view');
    if (!host) return;
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
        onCommit: (v, quiet) => (sendLayer
          ? sendAction({ action: 'setSend', channel: ch.index, target: activeLayer, value: v }, quiet)
          : sendAction({ action: 'setFader', channel: ch.index, value: v }, quiet)),
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
      b.onclick = () => { prefs.librarySort = b.dataset.sort; savePrefs(); renderTopPane(); };
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
    const tMode = session.transportMode || session.transport?.mode || 'usb_midi';
    const tr = session.transport || {};
    const tusb = tr.usb || {};
    const tble = tr.ble || session.ble || {};
    const tsync = session.stateSync || {};
    const tfeat = tr.features || {};

    const usbState = tusb.connected ? 'CONNECTED' : 'OFFLINE';
    const bleState = tble.authenticated
      ? `AUTHENTICATED · ${tble.deviceName || tble.device || 'FLOW 8 LE'}`
      : tble.connected
        ? 'HANDSHAKING…'
        : 'OFFLINE';
    const syncCounts = tsync.counts || {};
    const syncBits = ['SYNCED', 'PENDING_DISPATCH', 'DIVERGENT', 'UNKNOWN']
      .filter((k) => syncCounts[k])
      .map((k) => `${k} ${syncCounts[k]}`)
      .join(' · ') || 'no parameters tracked';
    const lastErr = tr.lastError || tusb.error || tble.lastError || tble.error || null;

    const trSec = document.createElement('section');
    trSec.className = 'insp-sec';
    trSec.innerHTML = `
      <div class="sec-hdr"><span class="sec-title">CONTROL TRANSPORT</span><span class="sec-meta">${tMode === 'usb_midi' ? 'USB MIDI' : tMode === 'ble' ? 'BLUETOOTH BLE' : 'HYBRID'}</span></div>
      <div class="seg wide">
        <button class="seg-btn ${tMode === 'usb_midi' ? 'on' : ''}" data-tmode="usb_midi">USB MIDI</button>
        <button class="seg-btn ${tMode === 'ble' ? 'on' : ''}" data-tmode="ble">BLUETOOTH BLE</button>
        <button class="seg-btn ${tMode === 'hybrid' ? 'on' : ''}" data-tmode="hybrid">HYBRID</button>
      </div>
      <dl class="info-list" style="margin-top:8px;">
        <dt>MIDI OUT SEEN</dt><dd>${(tusb.devicesSeen || []).length ? esc(tusb.devicesSeen.join(' · ')) : (tusb.connected ? 'FLOW 8 is open' : 'none')}</dd>
        <dt>USB MIDI</dt><dd>${usbState}${tusb.listening ? ' · meters in' : ''}${tusb.error ? ` — ${esc(tusb.error)}` : ''}</dd>
        <dt>BLUETOOTH LE</dt><dd>${bleState}${tble.packetsRx != null ? ` · RX ${tble.packetsRx} / TX ${tble.packetsTx || 0}` : ''}${tble.dumpChunks ? ` · dump ${tble.dumpChunks} chunks` : ''}</dd>
        <dt>ACTIVE CONTROL</dt><dd>${tr.controlConnected ? 'READY' : 'NOT READY'} — ${esc(tfeat.control || tMode)}</dd>
        <dt>STATE SYNC</dt><dd>${esc(syncBits)}${(tsync.divergent || []).length ? ` · ${tsync.divergent.length} divergent` : ''}</dd>
        ${lastErr ? `<dt>LAST ERROR</dt><dd>${esc(lastErr)}</dd>` : ''}
      </dl>
      ${tfeat.commands ? `<p class="sec-note"><strong>This mode sends:</strong> ${esc(tfeat.commands)}</p>` : ''}
      ${tfeat.limits ? `<p class="sec-note">${esc(tfeat.limits)}</p>` : ''}
      <div style="display:flex;align-items:center;gap:8px;margin-top:6px;">
        <button class="key-btn" id="btn-ble-dump" ${tble.authenticated ? '' : 'disabled'}>SYNC DUMP (0x4B)</button>
        <span class="sec-note" style="margin:0;">USB audio meters stay live in every mode. BLE dump chunks are counted but not decoded (format unverified).</span>
      </div>`;
    trSec.querySelectorAll('[data-tmode]').forEach((b) => {
      b.onclick = async () => {
        const res = await postAction({ action: 'setTransportMode', mode: b.dataset.tmode });
        if (res.ok) showToast(`Transport switched to ${b.dataset.tmode.toUpperCase()}.`);
        loadSession();
      };
    });
    trSec.querySelector('#btn-ble-dump').onclick = async () => {
      const res = await postAction({ action: 'bleDumpTrigger' });
      if (res.ok) showToast(res.triggered ? 'BLE dump trigger (0x4B) sent.' : 'BLE is not authenticated yet.', !res.triggered);
    };
    page.appendChild(trSec);

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
    const tel = session.telemetry || {};
    const lastSeen = tel.lastAt
      ? `${esc(tel.lastParamId || 'unknown')} at ${esc(tel.lastAt)}`
      : 'nothing received yet';
    const disp = session.dispatch || {};
    const lastSent = disp.last
      ? `${esc(disp.last.paramId)} · ${esc(disp.last.status)}`
      : 'nothing sent yet';
    const sec = document.createElement('section');
    sec.className = 'insp-sec';
    sec.innerHTML = `<dl class="info-list">
      <dt>MIDI OUT</dt><dd>${session.midiOutOpen ? 'Open' : 'Closed'}</dd>
      <dt>MIDI IN</dt><dd>${session.midiInOpen ? 'Open' : 'Closed'}${tel.device ? ` (${esc(tel.device)})` : ''}</dd>
      <dt>INBOUND TELEMETRY</dt><dd>${Number(tel.mapped || 0)} mapped / ${Number(tel.ccReceived || 0)} CC · last ${lastSeen}</dd>
      <dt>LINK WATCHDOG</dt><dd>${tel.watchdog ? 'Running' : 'Off'} · auto-reconnect ${tel.autoReconnect ? 'on' : 'off'}</dd>
      <dt>MIDI OUT DISPATCH</dt><dd>${Number(disp.commands || 0)} commands · ${Number(disp.driverDispatched || 0)} accepted by the driver · last ${lastSent}</dd>
      <dt>METERS</dt><dd>${esc(ms.detail || 'Off')}${ms.device ? ` (${esc(ms.device)})` : ''}</dd>
      <dt>SOLO</dt><dd>Solo is not available over MIDI.</dd>
      <dt>SNAPSHOT LIBRARY</dt><dd>${(session.library || []).length} snapshots on the host computer</dd>
      <dt>OPEN ON A TABLET</dt><dd id="info-urls">…</dd></dl>`;
    page.appendChild(sec);

    // Bluetooth on the FLOW 8 has two very different halves. BT audio is a
    // device-side pairing and arrives on CH 7; BT control is the vendor BLE
    // protocol. Only fader writes on strips 1-6 are verified — see ROUTING.
    const bt = document.createElement('section');
    bt.className = 'insp-sec';
    bt.innerHTML = `<div class="sec-hdr"><span class="sec-title">BLUETOOTH</span><span class="sec-meta">AUDIO IN · BLE FADERS 1-6</span></div>
      <dl class="info-list">
        <dt>BT AUDIO</dt><dd>Pair on the mixer (BT PAIRING → PAIR AUDIO). Audio arrives on <strong>CH 7 (USB/BT)</strong>; this console controls that strip normally.</dd>
        <dt>BT CONTROL (BLE)</dt><dd>Vendor BLE service <code>14839ad4-8d7e-415c-9a42-167340cf2339</code>. Verified writes: input faders on strips 1-6 (packet 0x06). Everything else stays on USB MIDI — see the ROUTING page for per-mode capabilities.</dd>
        <dt>BLE PROBE</dt><dd><code>python -m tools.ble_probe --scan-seconds 8</code> (read-only discovery)</dd>
      </dl>
      <button class="hw-btn" id="bt-open-ch7">เปิด CH 7 (USB/BT)</button>`;
    page.appendChild(bt);
    bt.querySelector('#bt-open-ch7').onclick = () => selectChannel(7, 'channel');

    try {
      const st = await (await fetch('/api/status')).json();
      const el = document.getElementById('info-urls');
      if (el) el.innerHTML = (st.lanUrls || []).map((u) => `<code>${esc(u)}</code>`).join('<br>') || 'No LAN address found.';
    } catch (_) { /* the hub banner reports the failure */ }
  }

  // ---------- Split-Screen Pro Console ----------
  // Clean-room Thai catalog (original content, no CueAir data). Loaded additively
  // from /api/presets/thai; values arrive as exact raw MIDI, so the plan that the
  // engineer reviews is exactly what will be sent.
  let thaiCatalog = null;

  function presetPlanChanges(preset, ch, scopes) {
    const changes = [];
    if (scopes.eq) {
      BANDS.forEach((band) => {
        const db = preset.eqDb[band.key];
        changes.push({
          channel: ch.index,
          parameter: `eq_${band.key}`,
          value: preset.eqRaw[band.key],
          reason: `${preset.name} · ${band.label} ${db >= 0 ? '+' : ''}${db.toFixed(1)} dB`,
          risk: Math.abs(db) >= 4 ? 'medium' : 'low',
        });
      });
    }
    if (scopes.low_cut && ch.index <= 4 && preset.lowCutRaw != null) {
      changes.push({
        channel: ch.index,
        parameter: 'low_cut',
        value: preset.lowCutRaw,
        reason: `${preset.name} · Low Cut ${preset.lowCutHz} Hz`,
        risk: 'low',
      });
    }
    if (scopes.compressor && ch.index <= 4 && preset.compressorRaw != null) {
      changes.push({
        channel: ch.index,
        parameter: 'compressor',
        value: preset.compressorRaw,
        reason: `${preset.name} · Comp ${preset.compressorPercent}%`,
        risk: 'medium',
      });
    }
    return changes;
  }

  function selectedChannelObj() {
    if (!session || !session.channels) return null;
    return session.channels.find((c) => c.index === selectedCh) || session.channels[0];
  }

  function updateSelectBadge() {
    const ch = selectedChannelObj();
    if (!ch) return;
    const numEl = document.getElementById('select-num');
    const nameEl = document.getElementById('select-name');
    if (numEl) numEl.textContent = String(ch.index).padStart(2, '0');
    if (nameEl) nameEl.textContent = chName(ch);
    const pasteBtn = document.getElementById('btn-paste');
    if (pasteBtn) pasteBtn.hidden = !dspClipboard;
  }

  function selectChannel(idx, switchTab = null) {
    selectedCh = Math.max(1, Math.min(7, Number(idx) || 1));
    if (switchTab) setTopTab(switchTab);
    else {
      updateSelectBadge();
      renderView();
    }
  }

  function setTopTab(tab, syncHub = true) {
    topTab = tab;
    const prevView = view;
    if (tab === 'mixer' || tab === 'stage') {
      lastLiveView = tab;
      view = tab;
    } else if (tab === 'setup') {
      view = 'setup';
    } else {
      lastLiveView = 'mixer';
      view = 'mixer';
    }
    if (syncHub && (view === 'mixer' || view === 'stage') && (view !== prevView || (session && session.activeView !== view))) {
      fetch('/api/action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'setActiveView', view, clientId }),
      }).catch(() => {});
    }
    renderView();
  }


  function renderCueEqTab(pane) {
    const ch = selectedChannelObj();
    if (!ch) return;
    const hasLowCut = ch.index <= 4;
    const eqBands = [
      ...(hasLowCut ? [{ key: 'lc', label: 'LC', color: '#FFB020' }] : []),
      ...BANDS.map((b) => ({ key: b.key, label: b.shortLabel, color: b.color })),
    ];
    if (!eqBands.some((b) => b.key === selectedEqBand)) selectedEqBand = 'low';

    const wrap = document.createElement('div');
    wrap.className = 'cue-eq-wrap';
    wrap.innerHTML = `
      <div class="cue-eq-stage">
        <div class="cue-eq-bands">
          ${eqBands.map((b) => `<button class="eq-band-pill ${selectedEqBand === b.key ? 'active' : ''}" data-band="${b.key}" style="--band-color:${b.color}">${b.label}</button>`).join('')}
        </div>
        <div class="eq-spec-list" id="cue-eq-list"></div>
        <p class="eq-legend">${EQ_SPEC_NOTE} · ไม่แสดงกราฟการตอบสนอง เพราะรูปร่างและ Q ยังไม่ยืนยัน</p>
      </div>
      <div class="cue-eq-side" id="cue-eq-side"></div>`;
    pane.appendChild(wrap);

    const side = wrap.querySelector('#cue-eq-side');
    const list = wrap.querySelector('#cue-eq-list');

    // One row per band: spec frequency and the gain value (exact). No curve.
    const redraw = () => {
      const unk = ch.eqProvenance !== 'COMMANDED' && ch.eqProvenance !== 'OBSERVED';
      list.innerHTML = BANDS.map((b) => `
        <div class="num-row eq-spec-row${selectedEqBand === b.key ? ' active' : ''}" style="--band-color:${b.color}">
          <span class="num-lbl">${b.shortLabel}</span>
          <span class="num-val">${b.hz} <span class="lock-chip">SPEC</span></span>
          <span class="num-val">${unk ? '--' : eqText(ch.eq[b.key] ?? 64)}</span>
        </div>`).join('');
    };

    const syncPills = () => {
      wrap.querySelectorAll('.eq-band-pill').forEach((p) => p.classList.toggle('active', p.dataset.band === selectedEqBand));
    };

    const renderSide = () => {
      const meta = eqBands.find((b) => b.key === selectedEqBand) || eqBands[0];
      const isLc = meta.key === 'lc';
      const rawVal = isLc ? (ch.lowCut || 0) : (ch.eq[meta.key] ?? 64);
      const band = BANDS.find((b) => b.key === meta.key);
      side.innerHTML = `
        <div class="sec-hdr"><span class="sec-title">${esc(chName(ch))} · ${meta.label}</span>
          <button class="key-btn" id="btn-eq-reset">RESET</button></div>
        <div class="num-row"><span class="num-lbl">SOURCE</span><span class="num-val" title="${esc(provTitle(ch.eqProvenance))}">${provCode(ch.eqProvenance)}</span></div>
        <div class="num-row"><span class="num-lbl">TYPE</span><span class="num-val">${isLc ? 'High Pass · 12 dB/oct' : (band.shape ? `${band.shape} <span class="lock-chip">SPEC</span>` : 'ไม่ระบุในสเปก')}</span></div>
        <div class="num-row"><span class="num-lbl">FREQ</span><span class="num-val">${isLc ? hpfHz(rawVal) : `${band.hz} <span class="lock-chip">SPEC</span>`}</span></div>
        <div class="num-row"><span class="num-lbl">${isLc ? 'CUTOFF' : 'GAIN'}</span><span class="num-val" id="eq-side-val">${isLc ? hpfHz(rawVal) : eqText(rawVal)}</span></div>
        <input class="studio-range" id="eq-side-range" type="range" min="0" max="127" value="${rawVal}" aria-label="${meta.label} value" />
        <div class="num-row"><span class="num-lbl">Q</span><span class="num-val">${isLc ? '—' : 'ไม่ทราบ'}</span></div>
        <p class="sec-note" style="margin:0">เลื่อนแถบด้านบน ค่าที่ส่งคือค่าตัวเลขนี้ (ส่งเมื่อปล่อยแถบ)</p>`;
      const rng = side.querySelector('#eq-side-range');
      const valEl = side.querySelector('#eq-side-val');
      rng.oninput = () => {
        const v = +rng.value;
        if (isLc) { ch.lowCut = v; valEl.textContent = hpfHz(v); }
        else { ch.eq[meta.key] = v; valEl.textContent = eqText(v); }
        redraw();
      };
      rng.onchange = () => {
        const v = +rng.value;
        if (isLc) sendAction({ action: 'setLowCut', channel: ch.index, value: v, unit: 'raw' });
        else sendAction({ action: 'setEqBand', channel: ch.index, band: meta.key, value: v });
      };
      side.querySelector('#btn-eq-reset').onclick = () => openEqResetPlan(ch);
    };

    wrap.querySelectorAll('.eq-band-pill').forEach((btn) => {
      btn.onclick = () => {
        selectedEqBand = btn.dataset.band;
        syncPills();
        redraw();
        renderSide();
      };
    });

    redraw();
    renderSide();
  }


  async function renderCuePresetsTab(pane) {
    const ch = selectedChannelObj();
    if (!ch) return;
    if (!thaiCatalog) {
      try {
        const res = await fetch('/api/presets/thai');
        thaiCatalog = await res.json();
      } catch (_) {
        pane.innerHTML = '<p class="sec-note">โหลดคลังพรีเซ็ตไม่ได้ — ตรวจสอบการเชื่อมต่อฮับ</p>';
        return;
      }
    }
    const wrap = document.createElement('div');
    wrap.className = 'cue-presets-wrap';
    wrap.innerHTML = '<div class="presets-left" id="presets-left"></div><div class="presets-right" id="presets-right"></div>';
    pane.appendChild(wrap);
    const left = wrap.querySelector('#presets-left');
    const right = wrap.querySelector('#presets-right');
    const cats = ['all', ...(thaiCatalog.categories || [])];

    const drawPresets = () => {
      const q = presetQuery.trim().toLowerCase();
      const list = (thaiCatalog.presets || []).filter((p) => (presetCategory === 'all' || p.category === presetCategory)
        && (!q || p.name.toLowerCase().includes(q) || p.summary.toLowerCase().includes(q)));

      left.innerHTML = `
        <div class="sec-hdr"><span class="sec-title">เลือกพรีเซ็ต · CH ${String(ch.index).padStart(2, '0')} (${esc(chName(ch))})</span><span class="sec-meta">CLEAN-ROOM</span></div>
        <input type="search" class="text-input search" id="cue-preset-search" placeholder="ค้นหาพรีเซ็ต (เช่น ไมค์พูด, ร้อง, กีตาร์, BGM)..." value="${esc(presetQuery)}" />
        <div class="cat-chips">
          ${cats.map((c) => `<button class="cat-chip ${presetCategory === c ? 'active' : ''}" data-cat="${esc(c)}">${c === 'all' ? 'ทั้งหมด' : esc(c)}</button>`).join('')}
        </div>
        <div class="preset-cards">
          ${list.map((p) => `
            <button class="preset-card ${selectedPresetId === p.id ? 'active' : ''}" data-pid="${esc(p.id)}">
              <span class="preset-card-title">${esc(p.name)}</span>
              <span class="preset-card-sub">${esc(p.category)}</span>
            </button>`).join('') || '<p class="sec-note">ไม่พบพรีเซ็ตที่ตรงกับการค้นหา</p>'}
        </div>`;
      left.querySelector('#cue-preset-search').oninput = (e) => { presetQuery = e.target.value; drawPresets(); };
      left.querySelectorAll('.cat-chip').forEach((b) => { b.onclick = () => { presetCategory = b.dataset.cat; drawPresets(); }; });
      left.querySelectorAll('.preset-card').forEach((b) => { b.onclick = () => { selectedPresetId = b.dataset.pid; drawPresets(); }; });

      const sel = list.find((p) => p.id === selectedPresetId) || list[0];
      if (!sel) { right.innerHTML = '<p class="sec-note">ไม่มีพรีเซ็ตให้แสดง</p>'; return; }
      const supports = {
        low_cut: ch.index <= 4 && sel.lowCutRaw != null,
        eq: true,
        compressor: ch.index <= 4 && sel.compressorRaw != null,
      };
      const previewEq = {
        low: sel.eqDb.low, low_mid: sel.eqDb.low_mid, hi_mid: sel.eqDb.hi_mid, hi: sel.eqDb.hi,
      };
      right.innerHTML = `
        <div class="sec-hdr"><span class="sec-title">${esc(sel.name)}</span><span class="sec-meta">${esc(sel.category)}</span></div>
        <p class="sec-note" style="margin:0">${esc(sel.summary)}</p>
        <svg class="preset-preview-svg" viewBox="0 0 180 64" preserveAspectRatio="none" role="img" aria-label="ค่า Gain ของ EQ 4 แบนด์ที่พรีเซ็ตจะส่ง (ไม่ใช่กราฟการตอบสนอง)">
          <line x1="0" y1="32" x2="180" y2="32" stroke="#242A35" stroke-width="1"/>
          ${eqGainBarsSvg(BANDS.map((b) => previewEq[b.key]), 180, 64)}
        </svg>
        <div class="preset-scope-row">
          <label><input type="checkbox" id="ps-lc" ${presetScopes.low_cut ? 'checked' : ''} ${supports.low_cut ? '' : 'disabled'}/> Low Cut ${sel.lowCutHz ? `(${sel.lowCutHz} Hz)` : ''}</label>
          <label><input type="checkbox" id="ps-eq" ${presetScopes.eq ? 'checked' : ''}/> EQ (4-band)</label>
          <label><input type="checkbox" id="ps-comp" ${presetScopes.compressor ? 'checked' : ''} ${supports.compressor ? '' : 'disabled'}/> Comp ${sel.compressorPercent != null ? `(${sel.compressorPercent}%)` : ''}</label>
        </div>
        <div class="phantom-safety-row">
          <span>พรีเซ็ตไม่แตะ Gain, +48V, Fader, Pan และ Sends</span>
          <span class="lock-chip">SAFE</span>
        </div>
        <ul class="preset-notes">
          ${sel.why.map((line) => `<li>${esc(line)}</li>`).join('')}
          <li>ค่าที่จะส่ง: ${BANDS.map((b) => `${b.label} ${sel.eqDb[b.key] >= 0 ? '+' : ''}${sel.eqDb[b.key].toFixed(1)} dB`).join(' · ')}${sel.lowCutHz ? ` · LC ${sel.lowCutHz} Hz` : ''}${sel.compressorPercent != null ? ` · Comp ${sel.compressorPercent}%` : ''}</li>
        </ul>
        <button class="hw-btn accent" id="btn-review-preset">ตรวจแผนก่อนใช้กับ CH ${String(ch.index).padStart(2, '0')}</button>
        <p class="sec-note" style="margin:0">ทุกค่าเข้าสู่แผงตรวจ Change Plan ก่อน — กด COMMIT แล้วจึงจะส่ง และ UNDO คืนได้ในขั้นเดียว</p>`;
      right.querySelector('#ps-lc').onchange = (e) => { presetScopes.low_cut = e.target.checked; };
      right.querySelector('#ps-eq').onchange = (e) => { presetScopes.eq = e.target.checked; };
      right.querySelector('#ps-comp').onchange = (e) => { presetScopes.compressor = e.target.checked; };
      right.querySelector('#btn-review-preset').onclick = () => {
        const scopes = {
          eq: right.querySelector('#ps-eq').checked,
          low_cut: supports.low_cut && right.querySelector('#ps-lc').checked,
          compressor: supports.compressor && right.querySelector('#ps-comp').checked,
        };
        if (!scopes.eq && !scopes.low_cut && !scopes.compressor) {
          showToast('เลือกอย่างน้อย 1 ส่วน (EQ / Low Cut / Comp)', true);
          return;
        }
        const changes = presetPlanChanges(sel, ch, scopes);
        if (!changes.length) {
          showToast('ช่องนี้ไม่รองรับส่วนที่เลือก', true);
          return;
        }
        previewPlan({ title: `พรีเซ็ต · ${sel.name} · CH ${String(ch.index).padStart(2, '0')}`, changes });
      };
    };
    drawPresets();
  }


  function renderCueChannelTab(pane) {
    const ch = selectedChannelObj();
    if (!ch) return;
    const grid = document.createElement('div');
    grid.className = 'top-grid-3';
    grid.innerHTML = `
      <section class="insp-sec">
        <div class="sec-hdr"><span class="sec-title">CHANNEL ${String(ch.index).padStart(2, '0')}</span><button class="key-btn" id="cue-rename">RENAME</button></div>
        <p class="sec-note" style="margin:0 0 6px;">${esc(chName(ch))} · Pan ${panText(ch.pan)} · ${ch.mute ? 'MUTED' : 'ACTIVE'}</p>
        <div class="num-row"><span class="num-lbl">PREAMP GAIN</span><span class="num-val">${ch.index <= 4 ? gainText(ch.gain) : 'LINE'} <span class="lock-chip">LOCKED</span></span></div>
        ${ch.index <= 4 ? `<div class="num-row"><span class="num-lbl">LOW CUT</span><span class="num-val">${hpfHz(ch.lowCut || 0)}</span></div>` : ''}
      </section>
      <section class="insp-sec">
        <div class="sec-hdr"><span class="sec-title">4-BAND EQ</span><button class="key-btn accent" id="cue-go-eq">OPEN EQ</button></div>
        <svg class="preset-preview-svg" style="height:64px" viewBox="0 0 180 64" preserveAspectRatio="none">
          <line x1="0" y1="32" x2="180" y2="32" stroke="#242A35" stroke-width="1"/>
          ${eqGainBarsSvg(channelGainsDb(ch), 180, 64)}
        </svg>
      </section>
      <section class="insp-sec">
        <div class="sec-hdr"><span class="sec-title">COMP & SENDS</span><button class="key-btn" id="cue-go-sends">SENDS</button></div>
        <div class="num-row"><span class="num-lbl">COMP</span><span class="num-val">${ch.index <= 4 ? `${Math.round(((ch.compressor || 0) / 127) * 100)}%` : 'N/A'}</span></div>
        <div class="num-row"><span class="num-lbl">MON 1 / MON 2</span><span class="num-val">${midiToDbStr(ch.sends?.mon1 || 0)} / ${midiToDbStr(ch.sends?.mon2 || 0)}</span></div>
        <div class="num-row"><span class="num-lbl">FX 1 / FX 2</span><span class="num-val">${midiToDbStr(ch.sends?.fx1 || 0)} / ${midiToDbStr(ch.sends?.fx2 || 0)}</span></div>
      </section>
    `;
    grid.querySelector('#cue-rename').onclick = () => openScribbleModal(ch);
    grid.querySelector('#cue-go-eq').onclick = () => setTopTab('eq');
    grid.querySelector('#cue-go-sends').onclick = () => setTopTab('sends');
    pane.appendChild(grid);
  }

  function renderCueInputTab(pane) {
    const ch = selectedChannelObj();
    if (!ch) return;
    const grid = document.createElement('div');
    grid.className = 'top-grid-2';
    const left = document.createElement('section');
    left.className = 'insp-sec';
    left.innerHTML = `
      <div class="sec-hdr"><span class="sec-title">INPUT · CH ${String(ch.index).padStart(2, '0')} (${esc(chName(ch))})</span></div>
      <div class="num-row"><span class="num-lbl">GAIN</span><span class="num-val">${ch.index <= 4 ? gainText(ch.gain) : 'LINE'} <span class="lock-chip" title="${esc(lockReason('gain'))}">LOCKED</span></span></div>
      <div class="num-row"><span class="num-lbl">+48V PHANTOM</span><span class="num-val">${ch.index <= 2 ? (ch.phantom ? 'ON' : 'OFF') : 'N/A'} <span class="lock-chip" title="${esc(lockReason('phantom'))}">HOST ONLY</span></span></div>
      <div class="num-row"><span class="num-lbl">PHASE (Ø)</span><span class="num-val">NORMAL <span class="lock-chip">LOCKED</span></span></div>
      <div class="num-row"><span class="num-lbl">STEREO LINK</span><span class="num-val">${ch.index >= 5 && ch.index <= 6 ? 'LINKED PAIR' : 'MONO'} <span class="lock-chip">LOCKED</span></span></div>
      ${ch.index <= 4 ? `<div class="num-row"><span class="num-lbl">LOW CUT</span><span class="num-val" id="inp-lc-val">${hpfHz(ch.lowCut || 0)}</span></div>
      <input class="studio-range" id="inp-lc-rng" type="range" min="0" max="127" value="${ch.lowCut || 0}" aria-label="Low cut" />` : '<p class="sec-note">Low cut applies to Channels 1–4 only.</p>'}
    `;
    if (ch.index <= 4) {
      const rng = left.querySelector('#inp-lc-rng');
      const valEl = left.querySelector('#inp-lc-val');
      rng.oninput = () => { ch.lowCut = +rng.value; valEl.textContent = hpfHz(ch.lowCut); };
      rng.onchange = () => postAction({ action: 'setLowCut', channel: ch.index, value: +rng.value, unit: 'raw' });
    }
    const right = document.createElement('div');
    renderInputsPage(right);
    grid.appendChild(left);
    grid.appendChild(right);
    pane.appendChild(grid);
  }

  function renderCueCompTab(pane) {
    const ch = selectedChannelObj();
    if (!ch) return;
    const sec = document.createElement('section');
    sec.className = 'insp-sec';
    if (ch.index > 4) {
      sec.innerHTML = `<div class="sec-hdr"><span class="sec-title">COMPRESSOR · CH ${String(ch.index).padStart(2, '0')}</span></div>
        <p class="sec-note">1-Knob Compressor is available on Channels 1–4 (MIC 1–2 & COMBO 3–4).</p>`;
      pane.appendChild(sec);
      return;
    }
    const pct = Math.round(((ch.compressor || 0) / 127) * 100);
    sec.innerHTML = `<div class="sec-hdr"><span class="sec-title">1-KNOB COMPRESSOR · CH ${String(ch.index).padStart(2, '0')} (${esc(chName(ch))})</span><span class="sec-meta">${pct}%</span></div>`;
    const row = document.createElement('div');
    row.style.display = 'flex';
    row.style.alignItems = 'center';
    row.style.gap = '20px';
    row.appendChild(createRotaryKnob({
      label: 'COMP', valueText: `${pct}%`, raw: ch.compressor || 0, min: 0, max: 127,
      color: '#34D399', big: true, focusKey: `cue-comp:${ch.index}`,
      onMove: (v) => `${Math.round((v / 127) * 100)}%`,
      onCommit: (v, quiet) => sendAction({ action: 'setCompressor', channel: ch.index, value: v, unit: 'raw' }, quiet),
    }));
    const note = document.createElement('p');
    note.className = 'sec-note';
    note.textContent = 'Drag the dial up/down (or double-click to reset to 0%) to tame vocal or instrument peaks.';
    row.appendChild(note);
    sec.appendChild(row);
    pane.appendChild(sec);
  }

  function renderCueSendsTab(pane) {
    const ch = selectedChannelObj();
    if (!ch) return;
    const sec = document.createElement('section');
    sec.className = 'insp-sec';
    sec.innerHTML = `<div class="sec-hdr"><span class="sec-title">BUS SENDS · CH ${String(ch.index).padStart(2, '0')} (${esc(chName(ch))})</span></div>`;
    ['mon1', 'mon2', 'fx1', 'fx2'].forEach((target) => {
      sec.appendChild(levelRow({
        label: LAYERS[target].label,
        color: LAYERS[target].color,
        value: ch.sends ? ch.sends[target] : 0,
        aria: `${chName(ch)} send to ${LAYERS[target].label}`,
        focusKey: `cue-send:${ch.index}:${target}`,
        onCommit: (v, quiet) => sendAction({ action: 'setSend', channel: ch.index, target, value: v }, quiet),
      }));
    });
    pane.appendChild(sec);
  }

  function renderCueFxTab(pane) {
    const grid = document.createElement('div');
    grid.className = 'top-grid-2';
    ['fx1', 'fx2'].forEach((fxId) => {
      const fx = FX_ENGINE[fxId];
      const bus = session.buses.find((b) => b.id === fxId);
      const st = (session.fxEngines && session.fxEngines[fxId]) || null;
      const presetKnown = st && st.presetProvenance !== 'UNSYNCED';
      const card = document.createElement('section');
      card.className = 'insp-sec';
      card.innerHTML = `
        <div class="sec-hdr"><span class="sec-title">${fxId.toUpperCase()} (${fxId === 'fx1' ? 'REVERB' : 'DELAY / MOD'})</span><span class="sec-meta">${presetKnown ? `PRESET ${st.preset}` : 'PRESET UNSYNCED'}</span></div>
        <div class="fx-matrix">${fx.presets.map((name, i) => `<button class="fx-tile live ${presetKnown && st.preset === i + 1 ? 'on' : ''}" data-preset="${i + 1}" aria-pressed="${presetKnown && st.preset === i + 1}">${i + 1}. ${esc(name)}</button>`).join('')}</div>
      `;
      card.querySelectorAll('.fx-tile').forEach((b) => {
        b.onclick = () => postAction({ action: 'setFxPreset', engine: fxId, value: +b.dataset.preset }).then(scheduleReload);
      });
      // Parameter 1 (CC 1, 0-100 %) and parameter 2 (CC 2, A/B), as on the FLOW app FX page.
      const p1Known = st && st.param1Provenance !== 'UNSYNCED';
      const p2Known = st && st.param2Provenance !== 'UNSYNCED';
      const params = document.createElement('div');
      params.className = 'fx-top';
      params.appendChild(createRotaryKnob({
        label: fx.param, valueText: p1Known ? `${Math.min(100, st.param1)}%` : '--', raw: p1Known ? Math.min(100, st.param1) : null,
        min: 0, max: 100, color: '#A78BFA', focusKey: `cue-fx:${fxId}:param1`,
        onMove: (v) => `${v}%`,
        onCommit: (v, quiet) => sendAction({ action: 'setFxParam', engine: fxId, param: 1, value: v }, quiet),
      }));
      const seg = document.createElement('div');
      seg.className = 'seg';
      seg.setAttribute('role', 'group');
      seg.setAttribute('aria-label', `${fxId.toUpperCase()} ${fx.param} mode`);
      seg.innerHTML = fx.modes.map((md, i) => `<button class="seg-btn live ${p2Known && (st.param2 ? 1 : 0) === i ? 'on' : ''}" data-mode="${i}" aria-pressed="${p2Known && (st.param2 ? 1 : 0) === i}">${md}</button>`).join('');
      seg.querySelectorAll('.seg-btn').forEach((b) => {
        b.onclick = () => postAction({ action: 'setFxParam', engine: fxId, param: 2, value: b.dataset.mode === '1' }).then(scheduleReload);
      });
      params.appendChild(seg);
      card.appendChild(params);
      card.appendChild(levelRow({
        label: `${fxId.toUpperCase()} RETURN`,
        color: '#A78BFA',
        value: bus ? bus.fader : 0,
        aria: `${fxId.toUpperCase()} return level`,
        focusKey: `cue-fx-ret:${fxId}`,
        onCommit: (v, quiet) => sendAction({ action: 'setBusFader', bus: fxId, value: v }, quiet),
      }));
      grid.appendChild(card);
    });
    pane.appendChild(grid);
  }

  function renderCueSetupTab(pane) {
    const pages = [
      ['inputs', 'Inputs'],
      ['snapshots', 'Snapshots'],
      ['showmodes', 'Show modes'],
      ['prefs', 'Preferences'],
      ['routing', 'Connection'],
      ['info', 'Info'],
    ];
    if (setupPage === 'library') setupPage = 'snapshots'; // the library now lives on the Snapshots page
    if (!pages.some(([id]) => id === setupPage)) setupPage = 'inputs';
    const layout = document.createElement('div');
    layout.className = 'setup-layout';
    const nav = document.createElement('nav');
    nav.className = 'setup-list';
    nav.setAttribute('aria-label', 'Setup pages');
    nav.innerHTML = pages.map(([id, label]) =>
      `<button class="setup-item${setupPage === id ? ' active' : ''}" data-sp="${id}"${setupPage === id ? ' aria-current="page"' : ''}>${label}</button>`).join('');
    nav.querySelectorAll('.setup-item').forEach((b) => {
      b.onclick = () => { setupPage = b.dataset.sp; renderTopPane(); };
    });
    const body = document.createElement('div');
    body.className = 'setup-body';
    layout.append(nav, body);
    pane.appendChild(layout);
    if (setupPage === 'inputs') renderInputsPage(body);
    else if (setupPage === 'snapshots') {
      // Scene slots and the saved library, stacked on one page (no second menu).
      const slots = document.createElement('section');
      const lib = document.createElement('section');
      lib.className = 'setup-section';
      body.append(slots, lib);
      renderSnapshotsPage(slots);
      renderLibraryPage(lib);
    }
    else if (setupPage === 'showmodes') renderShowModesPage(body);
    else if (setupPage === 'prefs') renderPrefsPage(body);
    else if (setupPage === 'routing') renderRoutingPage(body);
    else renderInfoPage(body);
  }

  // ---------- Staged change plan (F7) ----------
  // A plan is reviewed as a diff before anything is sent. COMMIT sends every
  // changed value once, as one ledger step, so a single UNDO restores the mix.
  function planValueText(parameter, raw) {
    if (raw === null || raw === undefined) return 'unknown';
    if (parameter === 'mute') return raw ? 'MUTED' : 'OPEN';
    if (parameter === 'pan') return panText(raw);
    if (parameter === 'low_cut') return hpfHz(raw);
    if (parameter === 'compressor') return `${Math.round((raw / 127) * 100)}%`;
    if (parameter.startsWith('eq_')) return eqText(raw);
    return midiToDbStr(raw);
  }

  function planChannelText(channel) {
    if (typeof channel === 'string') return LAYERS[channel] ? LAYERS[channel].label : channel.toUpperCase();
    if (Number(channel) === 8) return 'MAIN L/R';
    const ch = session && session.channels ? session.channels.find((c) => c.index === Number(channel)) : null;
    const num = String(channel).padStart(2, '0');
    return ch ? `CH ${num} · ${chName(ch)}` : `CH ${num}`;
  }

  async function previewPlan(plan) {
    const res = await postAction({ action: 'previewChangePlan', title: plan.title, changes: plan.changes });
    if (!res || res.ok === false) return;
    pendingPlan = plan;
    planPreview = res;
    renderPlanPanel();
  }

  function closePlanPanel() {
    pendingPlan = null;
    planPreview = null;
    const panel = document.getElementById('plan-panel');
    if (panel) panel.hidden = true;
  }

  function renderPlanPanel() {
    const panel = document.getElementById('plan-panel');
    if (!panel) return;
    if (!pendingPlan || !planPreview) { panel.hidden = true; return; }
    panel.hidden = false;
    const rows = planPreview.rows || [];
    const willSend = Number(planPreview.willSend || 0);
    const staleRows = planPreview.staleRows || [];
    const staleById = new Map(staleRows.map((item) => [item.parameterId, item]));
    document.getElementById('plan-title').textContent = pendingPlan.title || 'Change plan';
    document.getElementById('plan-sub').textContent = staleRows.length
      ? 'STALE — the mix moved after this preview'
      : willSend
        ? `Preview only — ${willSend} of ${rows.length} change${rows.length === 1 ? '' : 's'} will be sent on COMMIT`
        : 'Nothing would change — every value is already set';
    const body = document.getElementById('plan-body');
    body.innerHTML = '';
    if (planPreview.notice) {
      const notice = document.createElement('p');
      notice.className = 'plan-stale-note';
      notice.textContent = planPreview.notice;
      body.appendChild(notice);
    }
    rows.forEach((row) => {
      const unknown = row.from === null || row.from === undefined;
      const moved = staleById.get(row.parameterId);
      const el = document.createElement('div');
      el.className = `plan-row ${row.status === 'no_change' ? 'no-change' : ''} ${moved ? 'stale' : ''}`;
      const movedNote = moved
        ? `<p class="plan-stale-diff">was ${moved.previewFrom === null || moved.previewFrom === undefined
            ? 'unknown' : esc(planValueText(row.parameter, moved.previewFrom))}
            · now ${moved.currentFrom === null || moved.currentFrom === undefined
            ? 'unknown' : esc(planValueText(row.parameter, moved.currentFrom))}</p>`
        : '';
      el.innerHTML = `
        <div class="plan-row-head">
          <span class="plan-where">${esc(planChannelText(row.channel))} · ${esc(row.parameterLabel || row.parameter)}</span>
          ${moved
            ? '<span class="plan-stale-badge">STALE</span>'
            : `<span class="plan-risk ${esc(row.risk || 'low')}">${esc(String(row.risk || 'low').toUpperCase())}</span>`}
        </div>
        <div class="plan-diff">
          <span class="plan-from ${unknown ? 'unknown' : ''}">${unknown ? 'unknown' : esc(planValueText(row.parameter, row.from))}</span>
          <span class="plan-arrow">→</span>
          <span class="plan-to">${esc(planValueText(row.parameter, row.to))}</span>
        </div>
        <span class="plan-prov" title="${esc(provTitle(row.fromProvenance))}">FROM ${esc(provCode(row.fromProvenance))}</span>
        ${movedNote}
        ${row.reason ? `<p class="plan-reason">${esc(row.reason)}</p>` : ''}
        ${row.note ? `<p class="plan-note">${esc(row.note)}</p>` : ''}
      `;
      body.appendChild(el);
    });
    const commit = document.getElementById('plan-commit');
    commit.disabled = willSend === 0;
    commit.textContent = staleRows.length
      ? `REVIEWED — COMMIT ${willSend} AGAIN`
      : willSend ? `COMMIT ${willSend} CHANGE${willSend === 1 ? '' : 'S'}` : 'NOTHING TO SEND';
  }

  // A commit carries the guard from the preview. If anything moved since then,
  // the service refuses it, and the panel shows the fresh diff as STALE.
  async function commitPlan() {
    if (!pendingPlan || !planPreview) return;
    const button = document.getElementById('plan-commit');
    button.disabled = true;
    const res = await quietAction({
      action: 'commitChangePlan',
      title: pendingPlan.title,
      changes: pendingPlan.changes,
      guard: planPreview.guard,
    });
    button.disabled = false;
    if (res && res.ok !== false) {
      const parts = [`${res.applied} change${res.applied === 1 ? '' : 's'} sent`];
      if (res.skipped) parts.push(`${res.skipped} already set`);
      parts.push(res.undoReady
        ? 'UNDO restores the mix in one step'
        : 'previous value unknown, so UNDO cannot restore it');
      showToast(`Plan committed · ${parts.join(' · ')}`);
      closePlanPanel();
      loadSession();
      return;
    }
    if (res && (res.code === 'stale_plan' || res.code === 'preview_required')) {
      const staleRows = res.staleParameters || [];
      const refreshed = await quietAction({
        action: 'previewChangePlan',
        title: pendingPlan.title,
        changes: pendingPlan.changes,
      });
      if (refreshed && refreshed.ok !== false) {
        planPreview = refreshed;
        planPreview.staleRows = staleRows;
        planPreview.notice = res.code === 'stale_plan'
          ? 'ค่าเป้าหมายถูกเปลี่ยนหลังตรวจแผน (จากฮาร์ดแวร์หรืออีกหน้าจอ) — ตรวจ diff ใหม่แล้วกด COMMIT อีกครั้ง'
          : 'แผนนี้ยังไม่ถูกตรวจหรือหมดอายุ — ตรวจใหม่แล้วกด COMMIT อีกครั้ง';
        renderPlanPanel();
        showToast('ค่ามิกซ์เปลี่ยนหลังตรวจแผน — ตรวจ diff ที่เป็น STALE แล้วยืนยันอีกครั้ง', true);
        return;
      }
    }
    showToast((res && res.error) || 'Commit failed; nothing was sent.', true);
    closePlanPanel();
    loadSession();
  }

  // Merge several FlowAi suggestions into one reviewed plan; a later card wins
  // a duplicated channel+parameter so the plan never has two conflicting rows.
  function mergePlanChanges(cards) {
    const byKey = new Map();
    cards.forEach((card) => (card.changes || []).forEach((change) => {
      byKey.set(`${change.channel}:${change.parameter}`, change);
    }));
    return [...byKey.values()];
  }

  function renderFlowAiDrawer() {
    const drawer = document.getElementById('flowai-drawer');
    const btn = document.getElementById('btn-flowai');
    if (btn) btn.setAttribute('aria-pressed', flowAiOpen ? 'true' : 'false');
    if (!drawer) return;
    drawer.hidden = !flowAiOpen;
    if (!flowAiOpen || !session) return;
    const ch = selectedChannelObj();
    if (!ch) return;
    const body = document.getElementById('flowai-body');
    const sid = stripIdForChannel(ch.index);
    const meter = latestMeterLevels[sid] || meters[sid];
    const peakDb = meter ? meter.peak : -120;
    const cards = [];

    if (peakDb >= -2.0) {
      cards.push({
        badge: 'GAIN ADVICE', warn: true,
        title: `สัญญาณ CH ${String(ch.index).padStart(2, '0')} ใกล้พีค (${peakDb.toFixed(1)} dBFS)`,
        desc: 'แนะนำลด Preamp Gain ที่ตัวเครื่อง FLOW 8 เพื่อป้องกันเสียงแตก (ไม่สามารถปรับ Gain ผ่าน LAN เพื่อความปลอดภัย)',
      });
    }
    if (ch.index <= 4 && (ch.lowCut || 0) < 10) {
      cards.push({
        badge: 'HPF',
        title: 'เปิด Low Cut 100 Hz เพื่อลดเสียงลม/เสียงฮัม',
        desc: `ช่อง ${esc(chName(ch))} ยังไม่ได้เปิด Low Cut แนะนำตัดย่านต่ำกว่า 100 Hz เพื่อความสะอาดของมิกซ์`,
        changes: [{
          channel: ch.index, parameter: 'low_cut', value: hzToHpfRaw(100),
          reason: 'Cut wind and rumble below 100 Hz', risk: 'low',
        }],
      });
    }
    const eqFlat = ['low', 'low_mid', 'hi_mid', 'hi'].every((k) => Math.abs(eqRawToDb(ch.eq[k] ?? 64)) < 0.3);
    if (eqFlat && ch.index <= 4) {
      cards.push({
        badge: 'SMART EQ',
        title: 'ปรับ EQ ลดความก้อง & เพิ่มความคมชัดเสียงร้อง/พูด',
        desc: 'Low-Mid -2.0 dB ลดความขุ่น + Hi-Mid +1.5 dB ช่วยให้เสียงพุ่งชัดขึ้น (Undo ได้ใน 1 ขั้น)',
        changes: [
          { channel: ch.index, parameter: 'eq_low_mid', value: dbToEqRaw(-2.0), reason: 'Take out boxiness', risk: 'medium' },
          { channel: ch.index, parameter: 'eq_hi_mid', value: dbToEqRaw(1.5), reason: 'Add presence', risk: 'medium' },
        ],
      });
    }
    if (ch.index <= 4 && (ch.sends?.fx1 || 0) === 0) {
      cards.push({
        badge: 'SPACE',
        title: 'เพิ่ม Reverb FX 1 เล็กน้อย (-18 dB)',
        desc: 'ช่วยให้เสียงร้องหรือเครื่องดนตรีไม่แห้งจนเกินไปในห้องสด',
        changes: [{
          channel: ch.index, parameter: 'send_fx1', value: 76,
          reason: 'A little reverb space (-18 dB)', risk: 'low',
        }],
      });
    }
    if (!cards.length) {
      cards.push({
        badge: 'OK',
        title: `CH ${String(ch.index).padStart(2, '0')} (${esc(chName(ch))}) อยู่ในสภาพสมดุล`,
        desc: 'ค่า Low Cut, EQ และระดับสัญญาณปัจจุบันอยู่ในเกณฑ์ปลอดภัยพร้อมใช้งาน',
      });
    }

    body.innerHTML = '';
    const intro = document.createElement('p');
    intro.className = 'sec-note';
    intro.style.margin = '0';
    intro.innerHTML = `วิเคราะห์สดจาก <strong>CH ${String(ch.index).padStart(2, '0')} · ${esc(chName(ch))}</strong> (ทุกข้อเสนอถูกตรวจเป็นแผนก่อนส่ง — Gain และ +48V เป็นคำแนะนำเท่านั้น)`;
    body.appendChild(intro);

    const actionable = cards.filter((c) => (c.changes || []).length);
    if (actionable.length) {
      const all = document.createElement('button');
      all.className = 'hw-btn accent';
      all.textContent = `REVIEW ALL ${actionable.length} AS ONE PLAN`;
      all.onclick = () => previewPlan({
        title: `FlowAi · CH ${String(ch.index).padStart(2, '0')}`,
        changes: mergePlanChanges(actionable),
      });
      body.appendChild(all);
    }

    cards.forEach((c) => {
      const el = document.createElement('div');
      el.className = 'ai-card';
      el.innerHTML = `
        <div class="ai-card-hdr"><span>${c.title}</span><span class="ai-badge ${c.warn ? 'warn' : ''}">${c.badge}</span></div>
        <p class="ai-card-desc">${c.desc}</p>
        ${(c.changes || []).length ? `<button class="hw-btn accent">REVIEW &amp; APPLY</button>` : ''}
      `;
      if ((c.changes || []).length) {
        el.querySelector('button').onclick = () => previewPlan({
          title: `FlowAi · CH ${String(ch.index).padStart(2, '0')} · ${c.badge}`,
          changes: c.changes,
        });
      }
      body.appendChild(el);
    });
  }

  function renderTopPane() {
    const pane = document.getElementById('top-pane');
    if (!pane || !session) return;
    pane.innerHTML = '';
    if (topTab === 'mixer') return; // Mix > Faders is the fader bank itself; no second copy of the strips
    if (topTab === 'stage') {
      const stageHost = document.createElement('div');
      stageHost.className = 'stage-view';
      pane.appendChild(stageHost);
      renderStage(stageHost);
    } else if (topTab === 'channel') renderCueChannelTab(pane);
    else if (topTab === 'input') renderCueInputTab(pane);
    else if (topTab === 'eq') renderCueEqTab(pane);
    else if (topTab === 'comp') renderCueCompTab(pane);
    else if (topTab === 'sends') renderCueSendsTab(pane);
    else if (topTab === 'fx') renderCueFxTab(pane);
    else if (topTab === 'presets') renderCuePresetsTab(pane);
    else if (topTab === 'setup') renderCueSetupTab(pane);
  }

  // ---------- Views ----------
  // Ten views in four sections. Presets and Setup are single views, so they have no second row.
  const TAB_GROUP = {
    mixer: 'mix', stage: 'mix',
    input: 'sound', eq: 'sound', comp: 'sound', sends: 'sound', fx: 'sound', channel: 'sound',
    presets: 'presets', setup: 'setup',
  };
  const lastTabInGroup = { mix: 'mixer', sound: 'eq', presets: 'presets', setup: 'setup' };
  function renderView() {
    if (!session) return;
    document.body.dataset.view = view;
    const group = TAB_GROUP[topTab] || 'mix';
    document.body.dataset.section = group; // CSS picks header tools and fader-bank size from these
    document.body.dataset.tab = topTab;
    lastTabInGroup[group] = topTab;
    document.querySelectorAll('.cue-group').forEach((g) => {
      const on = g.dataset.group === group;
      g.classList.toggle('active', on);
      g.setAttribute('aria-selected', on ? 'true' : 'false');
    });
    document.querySelectorAll('.cue-tab').forEach((b) => {
      const on = b.dataset.tab === topTab;
      b.hidden = b.dataset.group !== group;
      b.classList.toggle('active', on);
      b.setAttribute('aria-selected', on ? 'true' : 'false');
    });
    document.getElementById('cue-tabs').hidden = !Array.from(document.querySelectorAll('.cue-tab')).some((b) => !b.hidden);
    updateSelectBadge();
    renderTopPane();
    renderConsole(); // persistent bottom fader bank + connection banner
    renderFlowAiDrawer();
    renderInspector(); // the Inspector is state (insp), so every view render redraws it
    renderChrome(); // sidebar, mix tabs and selected-channel panel (navigation only; no commands)
  }

  // ---------- Chrome: sidebar, mix tabs, selected-channel panel ----------
  // Navigation and shortcuts only. Every control here calls an existing handler
  // (setTopTab, setLayer, selectChannel, openScribbleModal). Nothing here sends a command.
  const LAYER_TABS = { main: 'Main Mix', mon1: 'Monitor 1', mon2: 'Monitor 2', fx1: 'FX 1', fx2: 'FX 2' };
  const ICON = {
    mic: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="9" y="3" width="6" height="11" rx="3" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>',
    chevron: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 6 6 6-6 6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    input: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="7" fill="none" stroke="currentColor" stroke-width="1.8"/><circle cx="12" cy="12" r="2" fill="currentColor"/></svg>',
    gate: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 19c4 0 5-1 7-6s3-7 11-7" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>',
    eq: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2 13h4l2-6 3 12 3-9 2 3h6" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    comp: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 20c6 0 6-14 18-14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>',
    sends: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 20 20 4M9 4h11v11" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    fx: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="6" width="18" height="12" rx="2" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M7 10v4M7 10h3M7 12h2M13 10l4 4M17 10l-4 4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>',
    book: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 5c3-1 6-1 9 1v14c-3-2-6-2-9-1zM21 5c-3-1-6-1-9 1v14c3-2 6-2 9-1z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/></svg>',
    phones: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 15v-3a8 8 0 0 1 16 0v3M4 15h4v5H5a1 1 0 0 1-1-1zM20 15h-4v5h3a1 1 0 0 0 1-1z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/></svg>',
    play: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="4" width="16" height="16" rx="3" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="m10 8.5 5 3.5-5 3.5z" fill="currentColor"/></svg>',
  };

  function renderSideNav() {
    document.querySelectorAll('#side-nav .side-item').forEach((b) => {
      const go = b.dataset.go;
      const on = go === 'mixer' ? (topTab === 'mixer' || topTab === 'stage') : topTab === go;
      b.classList.toggle('active', on);
      if (on) b.setAttribute('aria-current', 'page'); else b.removeAttribute('aria-current');
      b.onclick = () => setTopTab(go);
    });
  }

  function renderLayerTabs() {
    const nav = document.getElementById('layer-tabs');
    if (!nav) return;
    nav.innerHTML = LAYER_ORDER.map((id) =>
      `<button class="layer-tab${id === activeLayer ? ' active' : ''}" role="tab" aria-selected="${id === activeLayer}" data-layer="${id}">${LAYER_TABS[id]}</button>`).join('');
    nav.querySelectorAll('.layer-tab').forEach((b) => { b.onclick = () => setLayer(b.dataset.layer); });
  }

  function renderSelPanel() {
    const host = document.getElementById('sel-panel');
    const ch = selectedChannelObj();
    if (!host || !ch) return;
    const name = chName(ch);
    const unk = ch.faderProvenance === 'UNSYNCED';
    const hasComp = ch.index <= 4; // the console exposes the compressor on channels 1-4 only
    const tile = (id, icon, en, th, tab, off) => off
      ? `<button class="sp-tile unavailable" disabled aria-disabled="true" title="${esc(off)}">${icon}<span><b>${en}</b><i>${th}</i></span><em>Not available</em></button>`
      : `<button class="sp-tile${topTab === tab ? ' active' : ''}" data-tab="${tab}">${icon}<span><b>${en}</b><i>${th}</i></span></button>`;
    host.innerHTML = `
      <section class="sp-card">
        <header class="sp-head"><h2>Selected channel <i>ช่องที่เลือก</i></h2><span class="sp-chip">CH ${String(ch.index).padStart(2, '0')}</span></header>
        <button class="sp-name" id="sp-rename" aria-label="Rename ${esc(name)}" title="Rename channel">${ICON.mic}<span>${esc(name)}</span>${ICON.chevron}</button>
        <div class="sp-meta"><span>${esc(STRIP_TAG[ch.index])}</span><span class="${unk ? 'unk' : ''}">${unk ? '-- (not synced)' : midiToDbStr(ch.fader)}</span>${provBadge(ch.faderProvenance, provTitle(ch.faderProvenance))}</div>
        <div class="sp-tiles">
          ${tile('input', ICON.input, 'Input', 'อินพุต', 'input')}
          ${tile('gate', ICON.gate, 'Gate', 'เกท', null, lockReason('gate') === 'Not available over MIDI.' ? 'Gate: no gate parameter is documented for the FLOW 8, so this control is not offered.' : lockReason('gate'))}
          ${tile('eq', ICON.eq, 'EQ', 'อีควอไลเซอร์', 'eq')}
          ${tile('comp', ICON.comp, 'Comp', 'คอมเพรสเซอร์', 'comp', hasComp ? null : 'Compressor is offered on channels 1 to 4 only.')}
          ${tile('sends', ICON.sends, 'Sends', 'ส่งสัญญาณ', 'sends')}
          ${tile('fx', ICON.fx, 'FX', 'เอฟเฟกต์', 'fx')}
        </div>
        <p class="sp-note">Solo and Gate: not available. The mixer has no verified MIDI control for them.</p>
      </section>
      <section class="sp-card">
        <header class="sp-head"><h2>${ICON.book} Preset <i>พรีเซ็ต</i></h2></header>
        <button class="sp-preset" id="sp-presets">Open preset list ${ICON.chevron}</button>
        <p class="sp-note">Presets set EQ, low cut and compressor only. They never change level, gain or +48V. A plan is shown before anything is sent.</p>
      </section>
      <section class="sp-card">
        <header class="sp-head"><h2>Quick access <i>ควบคุมด่วน</i></h2></header>
        <div class="sp-quick">
          ${['mon1', 'mon2', 'fx1', 'fx2'].map((id) => `<button class="sp-q ${id.startsWith('fx') ? 'fx' : 'mon'}${activeLayer === id ? ' active' : ''}" data-layer="${id}" aria-pressed="${activeLayer === id}">${id.startsWith('fx') ? ICON.play : ICON.phones}<b>${LAYER_TABS[id].replace('Monitor ', 'MON ')}</b></button>`).join('')}
        </div>
      </section>`;
    host.querySelector('#sp-rename').onclick = () => openScribbleModal(ch);
    host.querySelector('#sp-presets').onclick = () => setTopTab('presets');
    host.querySelectorAll('.sp-tile[data-tab]').forEach((b) => { b.onclick = () => setTopTab(b.dataset.tab); });
    host.querySelectorAll('.sp-q').forEach((b) => { b.onclick = () => { setLayer(b.dataset.layer, false); setTopTab('mixer'); }; });
  }

  function renderChrome() {
    renderSideNav();
    renderLayerTabs();
    renderSelPanel();
  }
  document.getElementById('btn-save').onclick = () => setView('setup', 'snapshots');
  document.getElementById('btn-settings').onclick = () => setView('setup', 'prefs');

  function setView(v, page, syncHub = true) {
    if (v === 'setup') {
      if (page) setupPage = page;
      setTopTab('setup', syncHub);
      return;
    }
    setTopTab(v === 'stage' ? 'stage' : 'mixer', syncHub);
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
    applyMeterState();
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
    const planPanel = document.getElementById('plan-panel');
    if (planPanel && !planPanel.hidden) { e.preventDefault(); closePlanPanel(); return; }
    if (insp && view !== 'setup') { e.preventDefault(); closeInspector(); return; }
    if (view === 'setup') { e.preventDefault(); setView(lastLiveView); }
  });

  // ---------- Bus selector ----------
  // The Bus dropdown on the master strip puts a mix on the faders.
  function setLayer(layer, render = true, syncHub = true) {
    activeLayer = layer;
    document.body.dataset.layer = layer;
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
  document.getElementById('insp-close').onclick = closeInspector;
  document.querySelectorAll('.cue-tab').forEach((b) => { b.onclick = () => setTopTab(b.dataset.tab); });
  document.querySelectorAll('.cue-group').forEach((g) => { g.onclick = () => setTopTab(lastTabInGroup[g.dataset.group]); });
  document.getElementById('select-badge').onclick = () => selectChannel((selectedCh % 7) + 1);
  document.getElementById('btn-flowai').onclick = () => { flowAiOpen = !flowAiOpen; renderFlowAiDrawer(); };
  document.getElementById('plan-close').onclick = closePlanPanel;
  document.getElementById('plan-discard').onclick = closePlanPanel;
  document.getElementById('plan-commit').onclick = commitPlan;
  document.getElementById('flowai-close').onclick = () => { flowAiOpen = false; renderFlowAiDrawer(); };
  document.getElementById('btn-copy').onclick = () => {
    const ch = selectedChannelObj();
    if (!ch) return;
    dspClipboard = {
      sourceName: chName(ch),
      eq: { ...(ch.eq || {}) },
      lowCut: ch.index <= 4 ? ch.lowCut : null,
      compressor: ch.index <= 4 ? ch.compressor : null,
      sends: { ...(ch.sends || {}) },
    };
    updateSelectBadge();
    showToast(`Copied DSP from CH ${String(ch.index).padStart(2, '0')} (${chName(ch)}). Gain & +48V are excluded.`);
  };
  document.getElementById('btn-paste').onclick = async () => {
    if (!dspClipboard) return;
    const ch = selectedChannelObj();
    if (!ch) return;
    const res = await postAction({
      action: 'pasteChannelDsp',
      channel: ch.index,
      unit: 'raw',
      eq: dspClipboard.eq,
      lowCut: ch.index <= 4 ? dspClipboard.lowCut : null,
      compressor: ch.index <= 4 ? dspClipboard.compressor : null,
      sends: dspClipboard.sends,
    });
    if (res.ok) showToast(`Pasted DSP from ${dspClipboard.sourceName} to CH ${String(ch.index).padStart(2, '0')} (1 undo step).`);
    loadSession();
  };
  document.getElementById('insp-prev').onclick = () => stepInspector(-1);
  document.getElementById('insp-next').onclick = () => stepInspector(1);

  async function toggleMuteAll() {
    if (!session || !session.channels) return;
    // Toggle: if every input is already muted, the button restores them.
    const inputs = session.channels.filter((c) => c.index <= 7);
    const allMuted = inputs.every((c) => c.mute);
    const res = await postAction({ action: 'muteAll', value: !allMuted });
    if (res.ok) showToast(allMuted ? 'All inputs unmuted.' : 'All inputs muted. Press UNMUTE ALL to restore.');
    loadSession();
  }
  // Muting the whole PA needs a 0.6 s hold. Restoring is a single tap.
  const muteAllBtn = document.getElementById('btn-mute-all');
  attachHold(muteAllBtn, 600, toggleMuteAll, () => {
    if (muteAllBtn.dataset.hold === 'arm') showToast('Hold MUTE ALL for 0.6 s to mute every input.');
    else toggleMuteAll();
  });
  document.getElementById('btn-undo').onclick = () => postAction({ action: 'undo' }).then(scheduleReload);
  document.getElementById('btn-redo').onclick = () => postAction({ action: 'redo' }).then(scheduleReload);
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
    if (e.target.closest('.fader-well, .knob-svg, .eq-graph, .studio-range, .phantom-key, .snap-slot')) pointerBusy = true;
  }, true);
  const releasePointer = () => {
    if (!pointerBusy) return;
    pointerBusy = false;
    if (reloadPending) setTimeout(scheduleReload, 60);
  };
  window.addEventListener('pointerup', releasePointer, true);
  window.addEventListener('pointercancel', releasePointer, true);
  // Canvas buffers are sized from the layout, so a resize needs one redraw.
  let resizeTimer = null;
  window.addEventListener('resize', () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => { if (!pointerBusy) loadSession(); }, 250);
  });

  // ---------- Show Mode (MC / BAND) ----------
  // One hold switches the whole mix between two ordered macro lists kept on the
  // host. Cuts (mutes, zeros) run first on the server; UNDO stays up after a run.
  const SHOW_MODE_HOLD_MS = 450;
  const SHOW_MODE_UNDO_MS = 8000;
  const SHOW_PARAM_LABELS = {
    mute: 'MUTE', fader: 'FADER', send_fx1: 'SEND FX 1', send_fx2: 'SEND FX 2',
    send_mon1: 'SEND MON 1', send_mon2: 'SEND MON 2',
  };
  let showModeSig = '';
  let showModeUndoTimer = null;
  let showModeBusy = false;
  // Unsaved editor edits live here, not in the DOM: the page is rebuilt on every
  // hub event, and a rebuild must not wipe what was typed.
  const showModeDrafts = {};

  const showModeNotSet = (m) => `${m.name} has ${m.unsetCount} step${m.unsetCount === 1 ? '' : 's'} NOT SET. Open Setup > Show modes.`;

  function renderShowModes() {
    const box = document.getElementById('show-modes');
    if (!box || !session) return;
    const modes = session.showModes || [];
    // Rebuilding mid-hold would cancel the hold, so rebuild only when something changed.
    const sig = JSON.stringify(modes.map((m) => [m.id, m.name, m.ready, m.unsetCount]));
    if (sig === showModeSig) return;
    showModeSig = sig;
    box.innerHTML = '';
    modes.forEach((m) => {
      const btn = document.createElement('button');
      btn.className = 'hw-btn show-mode-btn' + (m.ready ? '' : ' unset');
      btn.dataset.mode = m.id;
      btn.dataset.focusKey = `showmode:${m.id}`;
      btn.setAttribute('aria-label', m.ready
        ? `Switch to ${m.name}. Hold to confirm.`
        : `${m.name}: ${m.unsetCount} steps not set.`);
      const label = document.createElement('span');
      label.textContent = m.name;
      btn.appendChild(label);
      if (!m.ready) {
        const small = document.createElement('small');
        small.textContent = 'NOT SET';
        btn.appendChild(small);
      }
      attachHold(btn, SHOW_MODE_HOLD_MS, () => runShowMode(m),
        () => showToast(m.ready ? `Hold ${m.name} for 0.45 s to switch.` : showModeNotSet(m), !m.ready));
      box.appendChild(btn);
    });
  }

  function hideShowModeUndo() {
    clearTimeout(showModeUndoTimer);
    const btn = document.getElementById('show-mode-undo');
    if (btn) btn.hidden = true;
  }

  function showShowModeUndo(name) {
    const btn = document.getElementById('show-mode-undo');
    btn.textContent = `UNDO ${name}`;
    btn.hidden = false;
    btn.onclick = async () => {
      btn.hidden = true;
      await postAction({ action: 'undo' });
      scheduleReload();
    };
    clearTimeout(showModeUndoTimer);
    showModeUndoTimer = setTimeout(() => { btn.hidden = true; }, SHOW_MODE_UNDO_MS);
  }

  async function runShowMode(m) {
    if (!m.ready) { showToast(showModeNotSet(m), true); return; }
    if (showModeBusy) return;
    showModeBusy = true;
    let res;
    try { res = await postAction({ action: 'runShowMode', id: m.id }); } finally { showModeBusy = false; }
    if (!res.ok) return;
    if (!res.applied) { showToast(`${m.name} already active.`); loadSession(); return; }
    let msg = `${m.name} ON · ${res.applied} changed` + (res.skipped ? `, ${res.skipped} already set` : '');
    if (res.unknownBefore) msg += ` · ${res.unknownBefore} earlier value${res.unknownBefore === 1 ? '' : 's'} unknown, undo cannot restore ${res.unknownBefore === 1 ? 'it' : 'them'}`;
    showToast(msg, !!res.unknownBefore);
    showShowModeUndo(m.name);
    scheduleReload();
  }

  const parseChannels = (text) => text.split(/[,\s]+/).filter(Boolean)
    .map((t) => (/^\d+$/.test(t) ? Number(t) : t.toLowerCase()));

  // Current commanded/observed fader of an input channel; null when the app does not know it.
  function currentFader(step) {
    const n = step.channels[0];
    const ch = typeof n === 'number' && session ? (session.channels || []).find((c) => c.index === n) : null;
    return ch && ch.faderProvenance && ch.faderProvenance !== 'UNSYNCED' ? ch.fader : null;
  }

  function showModeEditor(mode) {
    const draft = showModeDrafts[mode.id] || (showModeDrafts[mode.id] = JSON.parse(JSON.stringify(mode.steps)));
    const card = document.createElement('section');
    card.className = 'show-mode-card';
    function draw() {
      card.innerHTML = '';
      const head = document.createElement('h3');
      head.className = 'show-mode-title';
      head.textContent = mode.name;
      card.appendChild(head);
      draft.forEach((step, i) => {
        const row = document.createElement('div');
        row.className = 'show-step';
        const param = document.createElement('select');
        param.setAttribute('aria-label', `Step ${i + 1} parameter`);
        Object.entries(SHOW_PARAM_LABELS).forEach(([k, label]) => {
          const o = document.createElement('option');
          o.value = k; o.textContent = label; o.selected = k === step.parameter;
          param.appendChild(o);
        });
        param.onchange = () => { step.parameter = param.value; step.value = null; draw(); };
        const chans = document.createElement('input');
        chans.className = 'text-input';
        chans.value = step.channels.join(', ');
        chans.setAttribute('aria-label', `Step ${i + 1} channels (1-7, or fx1 mon1 for fader)`);
        chans.dataset.focusKey = `showstep:${mode.id}:${i}:ch`;
        chans.oninput = () => { step.channels = parseChannels(chans.value); };
        row.append(param, chans);
        let value;
        if (step.parameter === 'mute') {
          value = document.createElement('select');
          [['', 'NOT SET'], ['mute', 'MUTE'], ['unmute', 'UNMUTE']].forEach(([v, label]) => {
            const o = document.createElement('option');
            o.value = v; o.textContent = label;
            o.selected = (v === '' && step.value === null) || (v === 'mute' && step.value === true) || (v === 'unmute' && step.value === false);
            value.appendChild(o);
          });
          value.onchange = () => { step.value = value.value === '' ? null : value.value === 'mute'; };
        } else {
          value = document.createElement('input');
          value.type = 'number'; value.min = 0; value.max = 127; value.placeholder = 'NOT SET';
          value.className = 'text-input';
          value.value = step.value === null ? '' : step.value;
          value.dataset.focusKey = `showstep:${mode.id}:${i}:val`;
          value.oninput = () => { step.value = value.value === '' ? null : Number(value.value); };
        }
        value.setAttribute('aria-label', `Step ${i + 1} value`);
        row.appendChild(value);
        if (step.parameter === 'fader') {
          const use = document.createElement('button');
          use.className = 'key-btn';
          use.textContent = 'USE CURRENT';
          use.title = 'Take the fader value this app currently knows for the first channel';
          use.onclick = () => {
            const v = currentFader(step);
            if (v === null) { showToast('This fader value is not known yet (UNSYNCED). Set it by hand.', true); return; }
            step.value = v; draw();
          };
          row.appendChild(use);
        }
        const del = document.createElement('button');
        del.className = 'key-btn';
        del.textContent = 'DELETE';
        del.setAttribute('aria-label', `Delete step ${i + 1}`);
        del.onclick = () => { draft.splice(i, 1); draw(); };
        row.appendChild(del);
        card.appendChild(row);
      });
      const foot = document.createElement('div');
      foot.className = 'show-mode-foot';
      const add = document.createElement('button');
      add.className = 'key-btn';
      add.textContent = 'ADD STEP';
      add.onclick = () => { draft.push({ parameter: 'fader', channels: [1], value: null }); draw(); };
      const save = document.createElement('button');
      save.className = 'key-btn';
      save.textContent = 'SAVE';
      save.onclick = async () => {
        const res = await postAction({ action: 'saveShowMode', id: mode.id, steps: draft });
        if (res.ok) { delete showModeDrafts[mode.id]; showToast(`${mode.name} saved.`); loadSession(); }
      };
      foot.append(add, save);
      card.appendChild(foot);
    }
    draw();
    return card;
  }

  function renderShowModesPage(page) {
    pageHead(page, 'SHOW MODES');
    const note = document.createElement('p');
    note.className = 'sec-note';
    note.textContent = 'A mode changes only what is listed. Cuts (mutes and zeros) run first, then raises. A mode with a step NOT SET cannot run. +48V and preamp gain are never part of a mode.';
    page.appendChild(note);
    if (session.showModesError) {
      const err = document.createElement('p');
      err.className = 'sec-note';
      err.textContent = session.showModesError;
      page.appendChild(err);
    }
    (session.showModes || []).forEach((m) => page.appendChild(showModeEditor(m)));
  }

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
    renderShowModes();
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
      // UNDO <mode> undoes the last change, so any other change retires it.
      if (ev.action !== 'runShowMode') hideShowModeUndo();
      if (ev.action === 'muteAll') for (let i = 1; i <= 7; i++) markLamp(`ch${i}`, 'tx');
      else if (ev.bus) markLamp(ev.bus, 'tx');
      else if (ev.channel != null) markLamp(stripIdForChannel(+ev.channel), 'tx');
    }
    scheduleReload();
  };
  requestAnimationFrame(frame);
})();
