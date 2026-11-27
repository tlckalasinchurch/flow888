/* FLOW 888 v3 console.
 * Reads GET /api/session, listens to /api/events (SSE) and sends every command with POST /api/action.
 * The hub (lan_hub.py → Flow8Service → command boundary → safety) decides what reaches the mixer;
 * nothing here can bypass it. Gain and +48V have no sender in this file.
 * Provenance rule: only OBSERVED (mixer reported) or COMMANDED (this app sent) values are shown as
 * values. Everything else reads "--". */
(() => {
  'use strict';

  const clientId = Math.random().toString(36).slice(2);
  const LS = 'flow888.v3.';
  const store = {
    get: (k, d) => { try { const v = localStorage.getItem(LS + k); return v == null ? d : JSON.parse(v); } catch (_) { return d; } },
    set: (k, v) => { try { localStorage.setItem(LS + k, JSON.stringify(v)); } catch (_) { /* private mode */ } },
  };

  // ---------- Constants ----------
  const MIXES = [
    { id: 'main', label: 'MAIN', color: 'var(--mix-main)' },
    { id: 'mon1', label: 'MON 1', color: 'var(--mix-mon)' },
    { id: 'mon2', label: 'MON 2', color: 'var(--mix-mon)' },
    { id: 'fx1', label: 'FX 1', color: 'var(--mix-fx)' },
    { id: 'fx2', label: 'FX 2', color: 'var(--mix-fx)' },
  ];
  const TAGS = { 1: 'MIC 1', 2: 'MIC 2', 3: 'COMBO 3', 4: 'COMBO 4', 5: 'LINE 5/6', 6: 'LINE 7/8', 7: 'USB/BT' };
  const FX_NAMES = {
    fx1: ['AMBIENCE', 'PERC-REV1', 'PERC-REV2', 'GUIT-REV1', 'GUIT-REV2', 'CHAMBER', 'ROOM', 'CONCERT', 'CHURCH', 'CATHEDRAL', 'TEMPLE', 'STADIUM', 'FLANGER', 'SOFT CHOR', 'WARM CHOR', 'DEEP CHOR'],
    fx2: ['DELAY 1/1', 'DELAY 1/2', 'DELAY 1/3', 'DELAY 2/1', 'ECHO 1/1', 'ECHO 1/2', 'ECHO 1/3', 'ECHO 2/1', 'WIDE ECHO', 'PING PONG', 'PING P 1/3', 'PING P R>L', 'FLANGER', 'SOFT CHOR', 'WARM CHOR', 'DEEP CHOR'],
  };
  // Manufacturer centres (Quick Start Guide). Frequency and Q are not controls until tested.
  const EQ_BANDS = [
    { key: 'low', name: 'LOW', hz: 20, label: '20 Hz', shape: 'shelf', c: 'var(--band-1)' },
    { key: 'low_mid', name: 'LOW MID', hz: 300, label: '300 Hz', shape: 'peak', c: 'var(--band-2)' },
    { key: 'hi_mid', name: 'HI MID', hz: 1500, label: '1.5 kHz', shape: 'peak', c: 'var(--band-3)' },
    { key: 'hi', name: 'HIGH', hz: 20000, label: '20 kHz', shape: 'shelf', c: 'var(--band-4)' },
  ];
  // Short strip labels as printed on the mixer.
  const LAB = { 1: '1', 2: '2', 3: '3', 4: '4', 5: '5/6', 6: '7/8', 7: 'USB' };
  const chLab = (i) => (i === 7 ? 'USB/BT' : `CH ${LAB[i]}`);
  const GEQ_HZ = ['63', '125', '250', '500', '1k', '2k', '4k', '8k', '16k'];

  // ---------- Conversions (same curves as flow8/parameter_mapping.py and the v2 console) ----------
  const known = (p) => p === 'OBSERVED' || p === 'COMMANDED';
  const PROV = { OBSERVED: 'LIV', COMMANDED: 'SNT', UNSYNCED: 'UNK', DISPATCH_FAILED: 'ERR', UNSUPPORTED: 'N/A' };
  const PROV_TIP = {
    OBSERVED: 'The mixer reported this value.', COMMANDED: 'This app sent this value. The mixer does not report it back.',
    UNSYNCED: 'Not known yet. Move the control to set it.', DISPATCH_FAILED: 'The last command was rejected.', UNSUPPORTED: 'Not available on the FLOW 8.',
  };
  const dbText = (raw) => {
    if (raw <= 0) return '-∞';
    const db = raw >= 101 ? ((raw - 101) / 26) * 10 : ((raw - 101) / 101) * 70;
    return `${db >= 0 ? '+' : ''}${db.toFixed(1)}`;
  };
  const eqRawToDb = (raw) => (raw === 64 ? 0 : raw < 64 ? ((raw - 64) / 64) * 15 : ((raw - 64) / 63) * 15);
  const dbToEqRaw = (db) => {
    const c = Math.max(-15, Math.min(15, db));
    if (c === 0) return 64;
    return c < 0 ? Math.max(0, Math.round(64 + (c / 15) * 64)) : Math.min(127, Math.round(64 + (c / 15) * 63));
  };
  const lcText = (raw) => `${Math.round(20 + (raw / 127) * 580)} Hz`;
  const compPct = (raw) => Math.round((raw / 127) * 100);
  const limDb = (raw) => Math.round((raw / 127) * 30 - 30);

  // ---------- State ----------
  let session = null;
  let hubUp = false;
  let presets = [];
  const ui = {
    page: store.get('page', 'mix'), mix: 'main', sel: 1, outMix: 'main', monMix: store.get('monMix', 'mon1'),
    fine: false, locked: false, night: store.get('night', false), me: store.get('me', 1),
    groups: store.get('groups', [
      { name: 'GROUP A', members: [] }, { name: 'GROUP B', members: [] }, { name: 'GROUP C', members: [] }, { name: 'GROUP D', members: [] },
    ]).map(({ name, members }) => ({ name, members })),
    editGroup: null, armed: null, cueNow: store.get('cueNow', null), calc: store.get('calc', { metres: 12, temp: 28 }),
    dragging: 0, proc: store.get('proc', 'eq'),
    cueDraft: '', // the cue name being typed; kept across re-renders, never saved by itself
  };

  const $ = (s, r = document) => r.querySelector(s);
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const chs = () => (session ? session.channels.filter((c) => c.index <= 7) : []);
  const chById = (n) => chs().find((c) => c.index === n);
  const mixOf = (id) => MIXES.find((m) => m.id === id);
  const chName = (c) => (c.label && c.label !== c.name ? c.label : c.name);
  let toastTimer;
  const toast = (msg, bad) => {
    const t = $('#toast'); t.textContent = msg; t.classList.toggle('bad', !!bad); t.classList.add('show');
    clearTimeout(toastTimer); toastTimer = setTimeout(() => t.classList.remove('show'), bad ? 3600 : 2000);
  };

  // Level of a channel on a mix: MAIN is the channel fader, every other mix is a send.
  const chLevel = (c, mix) => (mix === 'main'
    ? { value: c.fader, prov: c.faderProvenance }
    : { value: (c.sends || {})[mix] || 0, prov: (c.sendsProvenance || {})[mix] || 'UNSYNCED' });
  const masterLevel = (mix) => {
    if (mix === 'main') { const m = session.channels.find((c) => c.index === 8); return m ? { value: m.fader, prov: m.faderProvenance } : { value: 0, prov: 'UNSYNCED' }; }
    const b = (session.buses || []).find((x) => x.id === mix);
    return b ? { value: b.fader, prov: b.faderProvenance } : { value: 0, prov: 'UNSYNCED' };
  };
  const chLevelCmd = (c, mix, v) => (mix === 'main'
    ? { action: 'setFader', channel: c.index, value: v }
    : { action: 'setSend', channel: c.index, target: mix, value: v, unit: 'raw' });
  const masterCmd = (mix, v) => (mix === 'main' ? { action: 'setFader', channel: 8, value: v } : { action: 'setBusFader', bus: mix, value: v });

  // ---------- Hub I/O ----------
  async function action(payload, { quiet = false } = {}) {
    try {
      const res = await fetch('/api/action', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...payload, clientId }),
      });
      let body = {};
      try { body = await res.json(); } catch (_) { /* empty body */ }
      if (!res.ok || body.ok === false) {
        if (!quiet || res.status !== 503) toast(body.error || `Command failed (HTTP ${res.status}). Nothing was changed.`, true);
        scheduleReload();
        return { ...body, ok: false };
      }
      return body;
    } catch (_) {
      hubUp = false; renderLink();
      toast('Cannot reach the host PC. The command was not sent.', true);
      return { ok: false, error: 'network' };
    }
  }

  // One drag = one undo step: beginGesture, values at most every 70 ms, final value, endGesture.
  function gesture(build) {
    let timer = null; let last = null; let open = false;
    return {
      start() { ui.dragging += 1; open = true; action({ action: 'beginGesture' }, { quiet: true }); },
      move(v) {
        last = v;
        if (timer) return;
        timer = setTimeout(() => { timer = null; if (open && last != null) action(build(last), { quiet: true }); }, 70);
      },
      async end(v) {
        if (!open) return;
        open = false; clearTimeout(timer); timer = null;
        ui.dragging = Math.max(0, ui.dragging - 1);
        if (v != null) await action(build(v));
        await action({ action: 'endGesture' }, { quiet: true });
        scheduleReload();
      },
    };
  }

  async function loadSession() {
    try {
      const res = await fetch('/api/session', { cache: 'no-store' });
      if (!res.ok) throw new Error(String(res.status));
      session = await res.json();
      hubUp = true;
    } catch (_) {
      hubUp = false; renderLink(); return;
    }
    render();
  }
  let reloadTimer = null; let reloadPending = false;
  function scheduleReload() {
    reloadPending = true;
    clearTimeout(reloadTimer);
    reloadTimer = setTimeout(() => {
      if (ui.dragging) return; // the drag's end reloads
      reloadPending = false;
      loadSession();
    }, 120);
  }
  const mixerReady = () => !!session && !!(session.transport ? session.transport.controlConnected : session.midiConnected);

  // ---------- Top bar ----------
  function renderLink() {
    const ready = mixerReady();
    const ok = hubUp && ready;
    const l = $('#link');
    l.className = `state ${ok ? 'ok' : hubUp ? 'warn' : 'bad'}`;
    l.querySelector('.tx').textContent = !hubUp ? 'NO HOST PC' : ready ? 'CONNECTED' : 'NO MIXER';
    l.title = !hubUp ? 'This device cannot reach the host PC.'
      : ready ? 'Host PC reachable. The FLOW 8 is connected.' : 'Host PC reachable, but the FLOW 8 is not connected to it. Commands are not sent.';
    $('#midi .tx').textContent = session && session.transportMode === 'ble' ? 'BLUETOOTH' : 'USB MIDI';
    $('#midi').classList.toggle('off', !ok);
    document.body.classList.toggle('offline', !ok);
  }
  const cueList = () => (session && session.library) || [];
  function renderCue() {
    if (!$('#cue')) return; // the cue line lives on the Show page
    const list = cueList();
    const i = list.findIndex((e) => e.id === ui.cueNow);
    const now = list[i];
    const next = list[i + 1] || (i < 0 ? list[0] : null);
    $('#cue').innerHTML = `${now ? `<small>NOW</small><b>${esc(now.name)}</b>` : '<small>NO CUE LOADED</small>'}${next ? `<small>NEXT</small><span>${esc(next.name)}</span>` : ''}`;
  }

  // ---------- Navigation ----------
  const PAGES = [
    ['mix', 'MIX', 'mix', 'มิกซ์'], ['fx', 'FX', 'wave', 'เอฟเฟกต์'], ['stage', 'MY MON', 'phones', 'มอนิเตอร์ของฉัน'],
    ['show', 'SHOW', 'show', 'คิวงาน'], ['output', 'OUTPUT', 'out', 'เอาต์พุต'], ['safety', 'SETUP', 'gear', 'ตั้งค่าและสิ่งที่ล็อก'],
  ];
  const NAV_OF = { sends: 'mix', channel: 'mix' };
  const icon = (n) => `<svg class="ic" aria-hidden="true"><use href="#i-${n}"/></svg>`;
  const go = (page) => { ui.page = page; ui.armed = null; ui.cueDraft = ''; store.set('page', page); render(); };
  function renderRail() {
    const cur = NAV_OF[ui.page] || ui.page;
    $('#rail').innerHTML = PAGES.map((p) => `<button type="button" data-page="${p[0]}" title="${p[3]}" ${cur === p[0] ? 'aria-current="page"' : ''}>${icon(p[2])}${p[1]}</button>`).join('');
    $('#rail').querySelectorAll('button').forEach((b) => { b.onclick = () => go(b.dataset.page); });
  }

  // ---------- Fader ----------
  // Relative drag (the cap never jumps to the finger); FINE divides travel by 4; arrows step by 1.
  // A fader repaints whenever its well changes size (resize before the debounced render, a late
  // font swap, the offline banner); before this, caps kept stale positions until the next render.
  const faderSizes = typeof ResizeObserver === 'function' ? new ResizeObserver((es) => es.forEach((e) => e.target.paint && e.target.paint())) : null;
  function fader(get, cmd, label, id) {
    const wrap = document.createElement('div');
    wrap.className = 'well';
    if (id) wrap.id = id; // render() restores focus by id after each keyboard step
    wrap.setAttribute('role', 'slider');
    wrap.setAttribute('aria-label', label);
    wrap.setAttribute('aria-valuemin', '0'); wrap.setAttribute('aria-valuemax', '127');
    wrap.tabIndex = 0;
    wrap.innerHTML = `<span class="slot"></span><span class="fill"></span>
      ${[[127, '+10'], [101, '0'], [64, '-20'], [32, '-40'], [0, '-∞']].map(([r, t]) => `<span class="tick" data-r="${r}">${t}</span>`).join('')}
      <span class="cap"></span>`;
    let local = null;
    const cur = () => local || get();
    const paint = () => {
      const x = cur();
      const h = wrap.clientHeight - 24;
      const y = known(x.prov) ? (x.value / 127) * h : 0;
      wrap.querySelector('.cap').style.bottom = `${12 + y}px`;
      wrap.querySelector('.cap').classList.toggle('unk', !known(x.prov));
      wrap.querySelector('.fill').style.height = `${known(x.prov) ? y : 0}px`;
      wrap.querySelectorAll('.tick').forEach((t) => { t.style.top = `${12 + h - (t.dataset.r / 127) * h}px`; });
      wrap.setAttribute('aria-valuetext', known(x.prov) ? `${dbText(x.value)} dB` : 'unknown');
      const read = wrap.closest('.strip') && wrap.closest('.strip').querySelector('.s-read');
      if (read) {
        read.querySelector('.v').textContent = known(x.prov) ? dbText(x.value) : '--';
        read.classList.toggle('unk', !known(x.prov));
        const b = read.querySelector('.prov'); // the badge follows the value it describes
        b.className = `prov ${x.prov}`; b.textContent = PROV[x.prov] || x.prov; b.title = PROV_TIP[x.prov] || '';
      }
    };
    const g = gesture(cmd);
    let start = null;
    wrap.onpointerdown = (e) => {
      if (ui.locked || !mixerReady()) return;
      wrap.setPointerCapture(e.pointerId);
      const x = get();
      start = { y: e.clientY, v: known(x.prov) ? x.value : 0 };
      g.start();
    };
    wrap.onpointermove = (e) => {
      if (!start || !wrap.hasPointerCapture(e.pointerId)) return;
      const h = wrap.clientHeight - 24;
      const v = Math.max(0, Math.min(127, Math.round(start.v + (((start.y - e.clientY) / h) * 127) / (ui.fine ? 4 : 1))));
      local = { value: v, prov: 'COMMANDED' };
      paint();
      g.move(v);
    };
    const end = () => { if (!start) return; start = null; g.end(local ? local.value : null); };
    wrap.onpointerup = end;
    wrap.onlostpointercapture = end;
    wrap.onkeydown = (e) => {
      const step = { ArrowUp: 1, ArrowDown: -1, PageUp: 8, PageDown: -8 }[e.key];
      if (!step || ui.locked || !mixerReady()) return;
      e.preventDefault();
      const x = cur();
      local = { value: Math.max(0, Math.min(127, (known(x.prov) ? x.value : 0) + step)), prov: 'COMMANDED' };
      paint();
      action(cmd(local.value)).then(scheduleReload);
    };
    wrap.paint = paint;
    if (faderSizes) faderSizes.observe(wrap);
    requestAnimationFrame(paint);
    return wrap;
  }

  function stripEl({ num, name, prov, color, chips, get, cmd, mute, onMute, sel, master, sid, head }) {
    const el = document.createElement('section');
    el.className = `strip${sel ? ' sel' : ''}${master ? ' master' : ''}`;
    el.style.setProperty('--mc', color);
    const x = get();
    const muteKnown = mute && known(mute.prov);
    el.innerHTML = `
      <div class="s-head" ${head ? 'tabindex="0" role="button"' : ''} aria-label="${esc(name)}">
        <span class="num">${esc(num)}</span>
        <span class="nm">${esc(name)}</span>
      </div>
      <div class="s-chips">${chips || ''}</div>
      <div class="s-fader"><div class="meter" data-sid="${sid || ''}"><span class="lvl"></span></div></div>
      <div class="s-read${known(x.prov) ? '' : ' unk'}"><span class="v">${known(x.prov) ? dbText(x.value) : '--'}</span><span class="prov ${prov}" title="${PROV_TIP[prov] || ''}">${PROV[prov] || prov}</span></div>
      ${mute ? `<button type="button" class="s-mute${muteKnown ? '' : ' unk'}" aria-pressed="${!!(muteKnown && mute.value)}" aria-disabled="${!mixerReady()}">${icon('mute')}${muteKnown ? (mute.value ? 'MUTED' : 'MUTE') : 'MUTE ?'}</button>` : '<div class="s-mute-space"></div>'}`;
    el.querySelector('.s-fader').prepend(fader(get, cmd, `${name} level`, `fdr-${String(num).replace(/[^A-Za-z0-9]+/g, '-')}`));
    if (mute) el.querySelector('.s-mute').onclick = onMute;
    if (head) {
      const h = el.querySelector('.s-head');
      h.onclick = head;
      h.onkeydown = (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); head(); } };
    }
    return el;
  }

  function mixButtons(current, list = MIXES) {
    return `<div class="mixes" role="group" aria-label="Choose a mix">${list.map((m) =>
      `<button type="button" data-mix="${m.id}" style="--mc:${m.color}" aria-pressed="${m.id === current}">${m.label}</button>`).join('')}</div>`;
  }
  const wireMix = (root, onPick) => root.querySelectorAll('[data-mix]').forEach((b) => { b.onclick = () => onPick(b.dataset.mix); });
  const offlineNote = () => (mixerReady() ? '' : `<div class="offline-note" role="status">The FLOW 8 is not connected to the host PC. Values show "--" and controls are paused until it reconnects.</div>`);

  // ---------- Mix: console workspace ----------
  // Left: what to edit on the selected channel. Top: that editor. Bottom: the faders of the chosen
  // mix. Right: the master of that mix and the five mixes. Nothing here is new to the hub.
  const PROCS = [['source', 'SOURCE', 'in'], ['eq', 'EQ', 'eq'], ['comp', 'COMP', 'comp'], ['fxsend', 'FX SEND', 'fxsend'], ['monsend', 'MON SEND', 'spk']];
  const knob = (db, on) => {
    const a = ((on ? db : 0) / 15) * 135; // -135..+135 degrees
    const r = (deg) => [20 + 15 * Math.sin((deg * Math.PI) / 180), 20 - 15 * Math.cos((deg * Math.PI) / 180)].map((v) => v.toFixed(1));
    const [x0, y0] = r(0); const [x1, y1] = r(a);
    // Unknown gain: an empty dashed ring, no pointer, so the knob never reads as 0 dB.
    return `<svg class="knob${on ? '' : ' unk'}" viewBox="0 0 40 40" aria-hidden="true"><circle cx="20" cy="20" r="17"/>${on && a ? `<path d="M${x0} ${y0}A15 15 0 0 ${a > 0 ? 1 : 0} ${x1} ${y1}"/>` : ''}${on ? `<line x1="20" y1="20" x2="${x1}" y2="${y1}"/>` : ''}</svg>`;
  };
  const busSub = (m) => {
    const x = masterLevel(m.id);
    const badge = (p) => `<span class="prov ${p}" title="${PROV_TIP[p] || ''}">${PROV[p] || p}</span>`;
    if (known(x.prov)) return `${dbText(x.value)} dB ${badge(x.prov)}`;
    // An FX mix whose level is unknown shows the preset it holds, when that is known (blueprint rev 7).
    const fx = m.id.startsWith('fx') && session && (session.fxEngines || {})[m.id];
    if (fx && known(fx.presetProvenance)) return `${esc(FX_NAMES[m.id][fx.preset - 1] || String(fx.preset))} ${badge(fx.presetProvenance)}`;
    return badge('UNSYNCED');
  };

  function procView(c) {
    const lab = `${chLab(c.index)} · ${esc(chName(c))}`;
    const head = (t, sub, prov) => `<div class="pv-h"><span class="tabx">${t}</span><span class="t">${sub}</span><span class="sp"></span>${prov ? `<span class="prov ${prov}" title="${PROV_TIP[prov] || ''}">${PROV[prov] || prov}</span>` : ''}`;
    if (ui.proc === 'eq') {
      const eqKnown = known(c.eqProvenance);
      const gains = EQ_BANDS.map((b) => eqRawToDb(c.eq[b.key] ?? 64));
      const geo = eqGeometry(gains, eqKnown);
      return { geo, gains, eqKnown, html: `${head('EQ', `4-BAND · ${lab}`, c.eqProvenance)}<button type="button" class="mini" id="eq-flat">FLAT</button></div>
        <div class="eq-wrap">${geo.svg}${EQ_BANDS.map((b, k) => `<div class="eq-node${eqKnown ? ' on' : ''}" id="eqn-${k}" data-k="${k}" style="--bc:${b.c};left:${(geo.xOf(b.hz) / geo.W) * 100}%;top:${((geo.mid - (eqKnown ? gains[k] : 0) * 7) / geo.H) * 100}%" role="slider" tabindex="0" aria-label="${b.name} gain" aria-valuetext="${eqKnown ? `${gains[k].toFixed(1)} dB` : 'unknown'}"><span>${k + 1}</span></div>`).join('')}</div>
        <div class="bands">${EQ_BANDS.map((b, k) => `<div class="band" style="--bc:${b.c}"><span class="hd"><i>${k + 1}</i>${b.name}</span>
          <dl><dt>Freq</dt><dd class="fixed" title="Fixed by the mixer">${b.label} ${icon('lock')}</dd><dt>Gain</dt><dd data-eqv="${k}">${eqKnown ? `${gains[k] > 0 ? '+' : ''}${gains[k].toFixed(1)} dB` : '--'}</dd><dt>Q</dt><dd class="fixed">fixed</dd></dl>${knob(gains[k], eqKnown)}</div>`).join('')}</div>` };
    }
    if (ui.proc === 'source') {
      return { html: `${head('SOURCE', lab, c.index <= 4 ? c.lowCutProvenance : '')}</div><div class="pv-rows">
        <div class="row"><span class="k">GAIN</span><span class="lockline">${icon('lock')}${esc(lockReason('gain'))}</span></div>
        ${c.index <= 2 ? `<div class="row"><span class="k">+48V</span><span class="lockline">${icon('lock')}${esc(lockReason('phantom'))}</span></div>` : ''}
        ${c.index <= 4 ? rangeRow('lc', 'LOW CUT', c.lowCut, c.lowCutProvenance, lcText) : '<p class="note">Low cut exists on channels 1–4 only.</p>'}</div>` };
    }
    if (ui.proc === 'comp') {
      return { html: `${head('COMP', lab, c.index <= 4 ? c.compressorProvenance : '')}</div><div class="pv-rows">
        ${c.index <= 4 ? rangeRow('cp', 'AMOUNT', c.compressor, c.compressorProvenance, (v) => `${compPct(v)}%`) : '<p class="note">The compressor exists on channels 1–4 only.</p>'}</div>` };
    }
    const ids = ui.proc === 'fxsend' ? ['fx1', 'fx2'] : ['mon1', 'mon2'];
    return { html: `${head(ui.proc === 'fxsend' ? 'FX SEND' : 'MON SEND', lab, '')}<button type="button" class="mini" id="all-sends">${icon('grid')}ALL SENDS</button></div>
      <div class="pv-rows sends1">${ids.map((id) => `<div class="row"><span class="k" style="color:${mixOf(id).color}">${mixOf(id).label}</span>${cellHtml(c, mixOf(id))}</div>`).join('')}</div>` };
  }
  const rangeRow = (id, label, v, prov, fmt) => `<div class="row"><label for="${id}">${label}</label><input id="${id}" type="range" min="0" max="127" value="${v}" class="${known(prov) ? '' : 'unk-range'}"><span class="v${known(prov) ? '' : ' unk'}">${known(prov) ? fmt(v) : '--'}</span></div>`;

  function pageMix(root) {
    const m = mixOf(ui.mix);
    const c = chById(ui.sel) || chs()[0];
    if (!c) return;
    const pv = procView(c);
    // The workspace has no visible title (its height is fader travel); the h1 names it for assistive tech.
    root.innerHTML = `<h1 class="sr-only">Mix: ${m.label} on the faders, ${chLab(c.index)} selected</h1>${offlineNote()}${ui.editGroup != null ? groupEditor() : ''}
      <div class="ws">
        <aside class="panel proc" aria-label="Selected channel">
          <button type="button" class="chsel" id="ch-next" title="Next channel"><b>${chLab(c.index)}</b><span>${esc(chName(c))}</span>${icon('chev')}</button>
          ${PROCS.map(([id, label, ic]) => `<button type="button" class="item" data-proc="${id}" aria-pressed="${ui.proc === id}">${icon(ic)}${label}</button>`).join('')}
          <button type="button" class="item" id="to-channel">${icon('strip')}CHANNEL</button>
          <div class="foot">
            <h3>MUTE GROUPS</h3>
            <div class="grps">${ui.groups.map((g, i) => { const st = groupState(g); return `<button type="button" class="grp" data-g="${i}" aria-pressed="${GROUP_PRESSED[st]}" title="${esc(g.name)}: ${GROUP_TIP[st]} Tap to mute or unmute, hold to edit.${g.members.length ? ` CH ${g.members.join(', ')}` : ''}">${esc(g.name.replace(/^GROUP /, '') || i + 1)}</button>`; }).join('')}</div>
            <button type="button" class="btn" id="to-presets">${icon('preset')}PRESET</button>
          </div>
        </aside>
        <div class="chrow" role="group" aria-label="Channel">${chs().map((x) => `<button type="button" data-ch="${x.index}" aria-pressed="${x.index === c.index}"><b>${chLab(x.index)}</b><span>${esc(chName(x))}</span></button>`).join('')}</div>
        <section class="panel pv pv-${ui.proc}" aria-label="${esc(ui.proc)} of channel ${c.index}">${pv.html}</section>
        <section class="panel bank" aria-label="Faders, ${m.label} mix"></section>
        <aside class="mast" aria-label="Master and mixes">
          <div class="panel mstrip"><h2>${ui.mix === 'main' ? 'MAIN OUT' : `${m.label} OUT`}</h2></div>
          <div class="buses" role="group" aria-label="Mix on the faders">${MIXES.map((x) => `<button type="button" class="bus" data-mix="${x.id}" style="--mc:${x.color}" aria-pressed="${x.id === ui.mix}">${icon(x.id === 'main' ? 'spk' : x.id.startsWith('mon') ? 'phones' : 'fx')}<b>${x.label}</b><small>${busSub(x)}</small>${icon('chev')}</button>`).join('')}</div>
        </aside>
      </div>`;
    wireMix(root, (id) => { ui.mix = id; action({ action: 'setActiveBus', bus: id }, { quiet: true }); render(); });
    wireGroups(root);
    const pick = (n) => { ui.sel = n; ui.armed = null; render(); };
    root.querySelector('#ch-next').onclick = () => { const list = chs(); const i = list.findIndex((x) => x.index === c.index); pick(list[(i + 1) % list.length].index); };
    root.querySelectorAll('.chrow [data-ch]').forEach((b) => { b.onclick = () => pick(+b.dataset.ch); });
    root.querySelectorAll('[data-proc]').forEach((b) => { b.onclick = () => { ui.proc = b.dataset.proc; store.set('proc', ui.proc); render(); }; });
    root.querySelector('#to-channel').onclick = () => go('channel');
    root.querySelector('#to-presets').onclick = () => go('channel');
    const all = root.querySelector('#all-sends');
    if (all) all.onclick = () => go('sends');
    if (pv.geo) { wireEqNodes(root, c, pv.geo, pv.gains, pv.eqKnown); wireFlat(root, c); }
    bindRange(root, c, '#lc', 'setLowCut', lcText);
    bindRange(root, c, '#cp', 'setCompressor', (v) => `${compPct(v)}%`);
    wireCells(root);
    const bank = root.querySelector('.bank');
    chs().forEach((x) => bank.appendChild(stripEl({
      num: chLab(x.index), name: chName(x), prov: chLevel(x, ui.mix).prov, color: m.color,
      get: () => chLevel(x, ui.mix), cmd: (v) => chLevelCmd(x, ui.mix, v),
      mute: ui.mix === 'main' ? { value: x.mute, prov: x.muteProvenance } : null, onMute: () => toggleMute(x),
      sel: x.index === c.index, sid: `ch${x.index}`, head: () => pick(x.index),
    })));
    const ml = masterLevel(ui.mix);
    root.querySelector('.mstrip').appendChild(stripEl({
      num: m.label, name: ui.mix === 'main' ? 'Main L/R' : `${m.label} level`, prov: ml.prov, color: m.color, master: true,
      get: () => masterLevel(ui.mix), cmd: (v) => masterCmd(ui.mix, v), sid: ui.mix === 'main' ? 'main' : '',
    }));
  }
  const lockReason = (k) => (session && session.locked && session.locked[k]) || 'Set on the mixer.';

  function groupEditor() {
    const g = ui.groups[ui.editGroup];
    return `<div class="grp-edit" role="group" aria-label="Edit mute group">
      <input id="grp-name" class="grp-name" type="text" maxlength="12" value="${esc(g.name)}" aria-label="Group name">
      ${chs().map((c) => `<button type="button" class="grp-ch" data-ch="${c.index}" aria-pressed="${g.members.includes(c.index)}">${c.index} · ${esc(chName(c))}</button>`).join('')}
      <button type="button" class="grp-done">DONE</button></div>`;
  }
  function wireGroups(root) {
    root.querySelectorAll('.grp').forEach((b) => {
      let t = null; let long = false;
      b.onpointerdown = () => { long = false; t = setTimeout(() => { long = true; ui.editGroup = +b.dataset.g; render(); }, 600); };
      b.onpointerup = () => { clearTimeout(t); if (!long) toggleGroup(+b.dataset.g); };
      b.onpointerleave = () => clearTimeout(t);
      b.onkeydown = (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleGroup(+b.dataset.g); } };
    });
    const ed = root.querySelector('.grp-edit');
    if (!ed) return;
    const g = ui.groups[ui.editGroup];
    // Keep exactly what is typed while editing (a re-render must not trim or move the caret); tidy on DONE.
    ed.querySelector('.grp-name').oninput = (e) => { g.name = e.target.value; };
    ed.querySelectorAll('.grp-ch').forEach((b) => {
      b.onclick = () => {
        const n = +b.dataset.ch;
        g.members = g.members.includes(n) ? g.members.filter((x) => x !== n) : [...g.members, n].sort((a, c) => a - c);
        b.setAttribute('aria-pressed', g.members.includes(n));
      };
    });
    ed.querySelector('.grp-done').onclick = () => { g.name = g.name.trim().toUpperCase() || 'GROUP'; ui.editGroup = null; saveGroups(); render(); };
  }
  const saveGroups = () => store.set('groups', ui.groups.map(({ name, members }) => ({ name, members })));

  async function toggleMute(c) {
    if (ui.locked) return;
    if (!mixerReady()) { toast('The FLOW 8 is not connected. Nothing was sent.', true); return; }
    const next = known(c.muteProvenance) ? !c.mute : true;
    await action({ action: 'setMute', channel: c.index, value: next });
    scheduleReload();
  }
  // A group's lamp comes from the hub's channel mutes, never from this browser: ON when every
  // member is muted and known, OFF when every member is known and one is unmuted, UNKNOWN when
  // any member's mute is not known (fresh start, reconnect, rejected command).
  function groupState(g) {
    const members = g.members.map(chById).filter(Boolean);
    if (!members.length) return 'empty';
    if (members.some((c) => !known(c.muteProvenance))) return 'unknown';
    return members.every((c) => c.mute) ? 'on' : 'off';
  }
  const GROUP_PRESSED = { on: 'true', off: 'false', empty: 'false', unknown: 'mixed' };
  const GROUP_TIP = { on: 'all channels muted.', off: 'not all channels muted.', empty: 'no channels yet.', unknown: 'mute state not known yet.' };
  // Group mutes are sent as one undo step. A channel stays muted while another group that is ON
  // holds it. The lamp changes only when the reloaded session confirms the mutes.
  async function toggleGroup(i) {
    if (ui.locked || !mixerReady()) return;
    const g = ui.groups[i];
    if (!g.members.length) { ui.editGroup = i; render(); return; }
    const turnOn = groupState(g) !== 'on'; // unknown mutes, as a strip MUTE does
    await action({ action: 'beginGesture' }, { quiet: true });
    for (const n of g.members) {
      const held = turnOn || ui.groups.some((x, j) => j !== i && x.members.includes(n) && groupState(x) === 'on');
      await action({ action: 'setMute', channel: n, value: held });
    }
    await action({ action: 'endGesture' }, { quiet: true });
    scheduleReload();
  }

  // ---------- Sends ----------
  function pageSends(root) {
    const cols = MIXES.filter((m) => m.id !== 'main');
    root.innerHTML = `${offlineNote()}
      <div class="page-head"><h1>Sends<i lang="th">ส่งสัญญาณ</i></h1><span class="sp"></span><span class="note">Drag a cell sideways. Every channel to every mix.</span></div>
      <table class="matrix"><thead><tr><th></th>${cols.map((m) => `<th style="--mc:${m.color}">${m.label}</th>`).join('')}</tr></thead>
      <tbody>${chs().map((c) => `<tr><th><b>${chLab(c.index)}</b> ${esc(chName(c))}</th>${cols.map((m) => {
        return `<td>${cellHtml(c, m)}</td>`;
      }).join('')}</tr>`).join('')}</tbody></table>`;
    wireCells(root);
  }
  function cellHtml(c, m) {
    const x = chLevel(c, m.id);
    return `<div class="cell${known(x.prov) ? '' : ' unk'}" id="cell-${c.index}-${m.id}" style="--mc:${m.color}" data-c="${c.index}" data-m="${m.id}" role="slider" tabindex="0" aria-label="${esc(chName(c))} to ${m.label}" aria-valuetext="${known(x.prov) ? `${dbText(x.value)} dB` : 'unknown'}">
          <span class="bar-fill" style="width:${known(x.prov) ? (x.value / 127) * 100 : 0}%"></span><b class="prov ${x.prov}" title="${PROV_TIP[x.prov] || ''}">${PROV[x.prov] || x.prov}</b><span>${known(x.prov) ? dbText(x.value) : '--'}</span></div>`;
  }
  function wireCells(root) {
    root.querySelectorAll('.cell').forEach((cell) => {
      const c = chById(+cell.dataset.c);
      const id = cell.dataset.m;
      const g = gesture((v) => chLevelCmd(c, id, v));
      let start = null; let val = null;
      const show = (v) => { cell.classList.remove('unk'); const pb = cell.querySelector('.prov'); pb.className = 'prov COMMANDED'; pb.textContent = PROV.COMMANDED; cell.querySelector('.bar-fill').style.width = `${(v / 127) * 100}%`; cell.querySelector('span:last-child').textContent = dbText(v); };
      cell.onpointerdown = (e) => {
        if (ui.locked || !mixerReady()) return;
        cell.setPointerCapture(e.pointerId);
        const x = chLevel(c, id);
        start = { x: e.clientX, v: known(x.prov) ? x.value : 0 };
        g.start();
      };
      cell.onpointermove = (e) => {
        if (!start) return;
        val = Math.max(0, Math.min(127, Math.round(start.v + (((e.clientX - start.x) / cell.clientWidth) * 127) / (ui.fine ? 4 : 1))));
        show(val); g.move(val);
      };
      const end = () => { if (!start) return; start = null; g.end(val); val = null; };
      cell.onpointerup = end; cell.onlostpointercapture = end;
      cell.onkeydown = (e) => {
        const step = { ArrowRight: 1, ArrowLeft: -1, ArrowUp: 1, ArrowDown: -1 }[e.key];
        if (!step || ui.locked || !mixerReady()) return;
        e.preventDefault();
        const x = chLevel(c, id);
        const v = Math.max(0, Math.min(127, (known(x.prov) ? x.value : 0) + step));
        show(v); action(chLevelCmd(c, id, v)).then(scheduleReload);
      };
    });
  }

  // ---------- Channel ----------
  function eqGeometry(gains, knownEq) {
    const W = 1000; const H = 260; const mid = H / 2;
    // 70-unit gutters: band 1 (20 Hz) stays clear of the dB scale, and band 4's 44 px touch
    // circle stays inside the graph on a phone.
    const xOf = (hz) => (Math.log10(hz / 20) / Math.log10(1000)) * (W - 140) + 70;
    const pts = [];
    for (let i = 0; i <= 200; i++) {
      const hz = 20 * Math.pow(1000, i / 200);
      let db = 0;
      EQ_BANDS.forEach((b, k) => {
        const gk = gains[k];
        if (b.shape === 'shelf') db += gk / (1 + Math.pow(k === 0 ? hz / 120 : 8000 / hz, 2));
        else db += gk * Math.exp(-Math.pow(Math.log2(hz / b.hz) / 0.9, 2));
      });
      pts.push(`${xOf(hz).toFixed(1)},${(mid - db * 7).toFixed(1)}`);
    }
    // Grid lines live in the stretched SVG; their labels are HTML so they keep the 12 px type floor
    // and are not squashed by preserveAspectRatio="none".
    const DB = [-12, -6, 0, 6, 12]; const HZ = [100, 1000, 10000];
    const MINOR = [30, 40, 50, 60, 70, 80, 90, 200, 300, 400, 500, 600, 700, 800, 900, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000];
    const LABEL = [50, 100, 200, 500, 1000, 2000, 5000, 10000];
    const grid = DB.map((d) => `<line x1="0" x2="${W}" y1="${mid - d * 7}" y2="${mid - d * 7}" stroke="var(--line)" stroke-width="${d ? 1 : 1.5}" vector-effect="non-scaling-stroke"/>`).join('')
      + HZ.map((hz) => `<line y1="0" y2="${H}" x1="${xOf(hz)}" x2="${xOf(hz)}" stroke="var(--line-2)" vector-effect="non-scaling-stroke"/>`).join('')
      + MINOR.map((hz) => `<line y1="0" y2="${H}" x1="${xOf(hz)}" x2="${xOf(hz)}" stroke="var(--line)" stroke-width="0.6" vector-effect="non-scaling-stroke"/>`).join('');
    const axis = DB.map((d) => `<span class="ax db" style="top:${((mid - d * 7) / H) * 100}%">${d > 0 ? '+' : ''}${d}</span>`).join('')
      + LABEL.map((hz) => `<span class="ax hz${HZ.includes(hz) ? '' : ' minor'}" style="left:${(xOf(hz) / W) * 100}%">${hz >= 1000 ? `${hz / 1000}k` : hz}</span>`).join('');
    const line = knownEq
      ? `<polyline points="${pts.join(' ')}" fill="none" stroke="var(--eq)" stroke-width="3" vector-effect="non-scaling-stroke"/>`
      : `<line x1="0" x2="${W}" y1="${mid}" y2="${mid}" stroke="var(--ink-3)" stroke-width="2" stroke-dasharray="8 8" vector-effect="non-scaling-stroke"/>`;
    return { svg: `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" aria-hidden="true">${grid}${line}</svg><div class="eq-axis" aria-hidden="true">${axis}</div>`, xOf, mid, W, H };
  }

  function pageChannel(root) {
    const c = chById(ui.sel) || chs()[0];
    if (!c) return;
    const eqKnown = known(c.eqProvenance);
    const gains = EQ_BANDS.map((b) => eqRawToDb(c.eq[b.key] ?? 64));
    const geo = eqGeometry(gains, eqKnown);
    const mic = c.index <= 4;
    root.innerHTML = `${offlineNote()}
      <div class="page-head"><h1>${chLab(c.index)} · ${esc(chName(c))}<i>${TAGS[c.index]}</i></h1><span class="sp"></span>
        <div class="mixes">${chs().map((x) => `<button type="button" data-ch="${x.index}" style="--mc:var(--line-2)" aria-pressed="${x.index === c.index}" aria-label="${chLab(x.index)}">${LAB[x.index]}</button>`).join('')}</div></div>
      <div class="ch-grid">
        <section class="panel"><h2>EQ · 4 BAND<span class="sp"></span><span class="prov ${c.eqProvenance}" title="${PROV_TIP[c.eqProvenance] || ''}">${PROV[c.eqProvenance] || c.eqProvenance}</span><button type="button" class="mini" id="eq-flat">FLAT</button></h2>
          <div class="eq-wrap">${geo.svg}${EQ_BANDS.map((b, k) => `<div class="eq-node${eqKnown ? ' on' : ''}" id="eqn-${k}" data-k="${k}" style="--bc:${b.c};left:${(geo.xOf(b.hz) / geo.W) * 100}%;top:${((geo.mid - (eqKnown ? gains[k] : 0) * 7) / geo.H) * 100}%" role="slider" tabindex="0" aria-label="${b.name} gain" aria-valuetext="${eqKnown ? `${gains[k].toFixed(1)} dB` : 'unknown'}"><span>${k + 1}</span></div>`).join('')}</div>
          <div class="eq-legend">${EQ_BANDS.map((b, k) => `<div style="--bc:${b.c}"><small>${b.name} · ${b.label}</small><b data-eqv="${k}">${eqKnown ? `${gains[k] > 0 ? '+' : ''}${gains[k].toFixed(1)} dB` : '--'}</b></div>`).join('')}</div>
          <p class="lockline" style="margin:10px 0 0"><span class="chip lock">FREQ · Q</span>Frequency and Q stay at the manufacturer's values until they are tested on this mixer. Drag a dot up or down for gain.</p>
        </section>
        <div class="col">
          <section class="panel"><h2>INPUT &amp; DYNAMICS</h2>
            <div class="row"><span class="k">GAIN</span><span class="lockline"><span class="chip lock">ON MIXER</span>${esc(lockReason('gain'))}</span></div>
            ${mic ? `<div class="row"><label for="lc">LOW CUT</label><input id="lc" type="range" min="0" max="127" value="${c.lowCut}" class="${known(c.lowCutProvenance) ? '' : 'unk-range'}"><span class="v${known(c.lowCutProvenance) ? '' : ' unk'}">${known(c.lowCutProvenance) ? lcText(c.lowCut) : '--'}</span></div>
            <div class="row"><label for="cp">COMP</label><input id="cp" type="range" min="0" max="127" value="${c.compressor}" class="${known(c.compressorProvenance) ? '' : 'unk-range'}"><span class="v${known(c.compressorProvenance) ? '' : ' unk'}">${known(c.compressorProvenance) ? `${compPct(c.compressor)}%` : '--'}</span></div>` : '<p class="note">Low cut and compressor exist on channels 1–4 only.</p>'}
          </section>
          <section class="panel"><h2>START FROM A PRESET<span class="sp"></span><span class="note">EQ, low cut, comp only</span></h2>
            <div class="preset-list">${presets.length ? presets.map((p) => `<button type="button" class="preset" data-p="${esc(p.id)}" aria-pressed="${ui.armed === `preset:${p.id}`}"><b>${esc(p.name)}</b><span class="cat">${esc(p.category || '')}</span><p>${ui.armed === `preset:${p.id}` ? 'Tap again to apply to this channel. Level, gain and +48V stay as they are; one undo step.' : esc(p.summary || '')}</p></button>`).join('') : '<p class="note">No presets from the host.</p>'}</div>
          </section>
        </div>
      </div>`;
    root.querySelectorAll('[data-ch]').forEach((b) => { b.onclick = () => { ui.sel = +b.dataset.ch; ui.armed = null; render(); }; });
    wireFlat(root, c);
    wireEqNodes(root, c, geo, gains, eqKnown);
    bindRange(root, c, '#lc', 'setLowCut', lcText);
    bindRange(root, c, '#cp', 'setCompressor', (v) => `${compPct(v)}%`);
    root.querySelectorAll('.preset').forEach((b) => {
      b.onclick = async () => {
        if (ui.locked || !mixerReady()) return;
        const key = `preset:${b.dataset.p}`;
        if (ui.armed !== key) { ui.armed = key; render(); return; }
        ui.armed = null;
        const res = await action({ action: 'applyPreset', channel: c.index, presetId: b.dataset.p });
        if (res.ok !== false) toast('Preset applied. Undo takes it back in one step.');
        scheduleReload();
      };
    });
  }

  function wireFlat(root, c) {
    root.querySelector('#eq-flat').onclick = async () => {
      if (ui.locked || !mixerReady()) return;
      if (ui.armed !== 'flat') { ui.armed = 'flat'; toast('Tap FLAT again to set all four bands to 0 dB.'); return; }
      ui.armed = null; await action({ action: 'resetEqFlat', channel: c.index }); scheduleReload();
    };
  }
  function wireEqNodes(root, c, geo, gains, eqKnown) {
    const wrap = root.querySelector('.eq-wrap');
    root.querySelectorAll('.eq-node').forEach((node) => {
      const k = +node.dataset.k;
      const band = EQ_BANDS[k];
      const g = gesture((raw) => ({ action: 'setEqBand', channel: c.index, band: band.key, value: raw, unit: 'raw' }));
      let start = null; let raw = null;
      const show = (db) => {
        node.style.top = `${((geo.mid - db * 7) / geo.H) * 100}%`;
        node.classList.add('on');
        const v = root.querySelector(`[data-eqv="${k}"]`);
        if (v) v.textContent = `${db > 0 ? '+' : ''}${db.toFixed(1)} dB`;
        node.setAttribute('aria-valuetext', `${db.toFixed(1)} dB`);
      };
      node.onpointerdown = (e) => {
        if (ui.locked || !mixerReady()) return;
        node.setPointerCapture(e.pointerId);
        start = { y: e.clientY, db: eqKnown ? gains[k] : 0 };
        g.start();
      };
      node.onpointermove = (e) => {
        if (!start) return;
        const db = Math.max(-15, Math.min(15, start.db + (((start.y - e.clientY) / (wrap.clientHeight / 2)) * 18.5) / (ui.fine ? 4 : 1)));
        const snapped = Math.round(db * 2) / 2;
        raw = dbToEqRaw(snapped);
        show(snapped); g.move(raw);
      };
      const end = () => { if (!start) return; start = null; g.end(raw); raw = null; };
      node.onpointerup = end; node.onlostpointercapture = end;
      node.onkeydown = (e) => {
        const step = { ArrowUp: 0.5, ArrowDown: -0.5 }[e.key];
        if (!step || ui.locked || !mixerReady()) return;
        e.preventDefault();
        const db = Math.max(-15, Math.min(15, (eqKnown ? gains[k] : 0) + step));
        show(db); action({ action: 'setEqBand', channel: c.index, band: band.key, value: dbToEqRaw(db), unit: 'raw' }).then(scheduleReload);
      };
    });
  }
  function bindRange(root, c, sel, act, fmt) {
    const r = root.querySelector(sel);
    if (!r) return;
    r.oninput = () => { r.classList.remove('unk-range'); r.nextElementSibling.textContent = fmt(+r.value); r.nextElementSibling.classList.remove('unk'); };
    r.onchange = () => { if (ui.locked || !mixerReady()) { scheduleReload(); return; } action({ action: act, channel: c.index, value: +r.value, unit: 'raw' }).then(scheduleReload); };
  }

  // ---------- Output ----------
  function pageOutput(root) {
    const id = ui.outMix;
    const dsp = (session.busDsp || {})[id] || { limiter: 127, limiterProvenance: 'UNSYNCED', geq: Array(9).fill(64), geqProvenance: Array(9).fill('UNSYNCED') };
    const speed = 331.3 + 0.606 * ui.calc.temp;
    const ms = (ui.calc.metres / speed) * 1000;
    const limKnown = known(dsp.limiterProvenance);
    root.innerHTML = `${offlineNote()}
      <div class="page-head"><h1>Output<i lang="th">เอาต์พุต</i></h1>${mixButtons(id, MIXES.filter((m) => ['main', 'mon1', 'mon2'].includes(m.id)))}</div>
      <div class="out-grid">
        <section class="panel"><h2>GRAPHIC EQ · 9 BAND<span class="sp"></span><span class="note">± 15 dB · dashed = not sent yet</span></h2>
          <div class="geq">${GEQ_HZ.map((hz, i) => {
            const k = known(dsp.geqProvenance[i]);
            const db = eqRawToDb(dsp.geq[i]);
            return `<div class="geq-band"><b data-i="${i}">${k ? `${db > 0 ? '+' : ''}${db.toFixed(1)}` : '--'}</b><div class="well geq-well" id="geq-${i}" data-i="${i}" role="slider" tabindex="0" aria-label="${hz} Hz" aria-valuemin="-15" aria-valuemax="15"${k ? ` aria-valuenow="${Math.round(db * 10) / 10}"` : ''} aria-valuetext="${k ? `${db > 0 ? '+' : ''}${db.toFixed(1)} dB` : 'unknown'}"><span class="slot"></span><span class="cap${k ? '' : ' unk'}" style="bottom:${(((k ? db : 0) + 15) / 30) * 100}%"></span></div><small>${hz}</small></div>`;
          }).join('')}</div>
        </section>
        <div class="col">
          <section class="panel"><h2>LIMITER<span class="sp"></span><span class="prov ${dsp.limiterProvenance}" title="${PROV_TIP[dsp.limiterProvenance] || ''}">${PROV[dsp.limiterProvenance] || ''}</span></h2>
            <div class="row"><label for="lim">THRESHOLD</label><input id="lim" type="range" min="0" max="127" value="${limKnown ? dsp.limiter : 127}" class="${limKnown ? '' : 'unk-range'}"><span class="v${limKnown ? '' : ' unk'}">${limKnown ? `${limDb(dsp.limiter)} dB` : '--'}</span></div>
          </section>
          <section class="panel calc"><h2>DELAY CALCULATOR</h2>
            <div class="row"><label for="dm">DISTANCE</label><input id="dm" type="number" inputmode="decimal" min="0" max="200" step="0.5" value="${ui.calc.metres}"><span class="note">metres from the main speakers</span></div>
            <div class="row"><label for="dt">AIR TEMP</label><input id="dt" type="number" inputmode="decimal" min="-10" max="45" value="${ui.calc.temp}"><span class="note">°C · ${speed.toFixed(1)} m/s</span></div>
            <div class="result"><b id="calc-ms">${ms.toFixed(1)} ms</b><p class="note" style="margin:4px 0 0">Set this as the output delay of the fill speakers. The app calculates only; it does not send delay.</p></div>
          </section>
        </div>
      </div>`;
    wireMix(root, (m) => { ui.outMix = m; render(); });
    // GEQ band: -15..+15 dB in 0.5 dB steps, sent raw via dbToEqRaw. Mouse and keyboard share set().
    const GEQ_STEP = 0.5;
    root.querySelectorAll('.geq-well').forEach((w) => {
      const i = +w.dataset.i;
      const g = gesture((raw) => ({ action: 'setBusGeq', bus: id, band: i + 1, value: raw }));
      let cur = known(dsp.geqProvenance[i]) ? eqRawToDb(dsp.geq[i]) : 0; // unknown starts at 0 dB, as the mouse always did
      let start = null; let raw = null;
      const set = (db) => {
        cur = Math.max(-15, Math.min(15, Math.round(db / GEQ_STEP) * GEQ_STEP));
        const text = `${cur > 0 ? '+' : ''}${cur.toFixed(1)}`;
        w.querySelector('.cap').style.bottom = `${((cur + 15) / 30) * 100}%`; w.querySelector('.cap').classList.remove('unk');
        root.querySelector(`.geq-band b[data-i="${i}"]`).textContent = text;
        w.setAttribute('aria-valuenow', cur); w.setAttribute('aria-valuetext', `${text} dB`);
        return dbToEqRaw(cur);
      };
      w.onpointerdown = (e) => {
        if (ui.locked || !mixerReady()) return;
        w.setPointerCapture(e.pointerId);
        start = { y: e.clientY, db: cur };
        g.start();
      };
      w.onpointermove = (e) => {
        if (!start) return;
        raw = set(start.db + (((start.y - e.clientY) / w.clientHeight) * 30) / (ui.fine ? 4 : 1)); g.move(raw);
      };
      const end = () => { if (!start) return; start = null; g.end(raw); raw = null; };
      w.onpointerup = end; w.onlostpointercapture = end;
      w.onkeydown = (e) => {
        const target = { ArrowUp: cur + GEQ_STEP, ArrowRight: cur + GEQ_STEP, ArrowDown: cur - GEQ_STEP, ArrowLeft: cur - GEQ_STEP, Home: -15, End: 15 }[e.key];
        if (target === undefined) return;
        e.preventDefault(); // arrows/Home/End adjust the band; they must not scroll the page
        if (ui.locked || !mixerReady()) return;
        action({ action: 'setBusGeq', bus: id, band: i + 1, value: set(target) }).then(scheduleReload);
      };
    });
    const lim = root.querySelector('#lim');
    lim.oninput = () => { lim.classList.remove('unk-range'); lim.nextElementSibling.textContent = `${limDb(+lim.value)} dB`; lim.nextElementSibling.classList.remove('unk'); };
    lim.onchange = () => { if (ui.locked || !mixerReady()) { scheduleReload(); return; } action({ action: 'setBusLimiter', bus: id, value: +lim.value }).then(scheduleReload); };
    const recalc = () => {
      const sp = 331.3 + 0.606 * ui.calc.temp;
      $('#calc-ms').textContent = `${((ui.calc.metres / sp) * 1000).toFixed(1)} ms`;
      store.set('calc', ui.calc);
    };
    root.querySelector('#dm').oninput = (e) => { ui.calc.metres = Math.max(0, +e.target.value || 0); recalc(); };
    root.querySelector('#dt').oninput = (e) => { ui.calc.temp = +e.target.value || 0; recalc(); };
  }

  // ---------- FX ----------
  function pageFx(root) {
    root.innerHTML = `${offlineNote()}
      <div class="page-head"><h1>FX<i lang="th">เอฟเฟกต์</i></h1><span class="sp"></span>
        <span class="note">Preset names as the FLOW app shows them. FX MIDI channel numbering is still to be confirmed on the mixer.</span></div>
      <div class="fx-grid">${['fx1', 'fx2'].map((id) => {
        const st = (session.fxEngines || {})[id] || {};
        const pk = known(st.presetProvenance);
        const p1k = known(st.param1Provenance);
        const p2k = known(st.param2Provenance);
        return `<section class="panel"><h2>${id === 'fx1' ? 'FX 1 · REVERB' : 'FX 2 · DELAY / MOD'}<span class="sp"></span><span class="prov ${st.presetProvenance}" title="${PROV_TIP[st.presetProvenance] || ''}">${pk ? `${PROV[st.presetProvenance]} · ${FX_NAMES[id][st.preset - 1] || st.preset}` : PROV.UNSYNCED}</span></h2>
          <div class="presets16">${FX_NAMES[id].map((n, i) => `<button type="button" data-fx="${id}" data-p="${i + 1}" aria-pressed="${pk && st.preset === i + 1}">${n}<small>${i + 1}</small></button>`).join('')}</div>
          <div class="row" style="margin-top:8px"><label for="${id}-p1">PARAM 1</label><input id="${id}-p1" type="range" min="0" max="100" value="${p1k ? Math.min(100, st.param1) : 0}" class="${p1k ? '' : 'unk-range'}"><span class="v${p1k ? '' : ' unk'}">${p1k ? `${Math.min(100, st.param1)}%` : '--'}</span></div>
          <div class="row"><span class="k">VARIANT</span><div class="seg" role="group" aria-label="Parameter 2">${['A', 'B'].map((x, i) => `<button type="button" data-v="${id}:${i}" aria-pressed="${p2k && !!st.param2 === (i === 1)}">${x}</button>`).join('')}</div>
            <span class="lockline" style="margin-left:auto"><span class="chip lock" title="${esc(lockReason('tap'))}">TAP</span><span class="chip lock" title="${esc(lockReason('fxMute'))}">FX MUTE</span>on the mixer</span></div>
        </section>`;
      }).join('')}</div>`;
    root.querySelectorAll('[data-fx]').forEach((b) => {
      b.onclick = async () => { if (ui.locked || !mixerReady()) return; await action({ action: 'setFxPreset', engine: b.dataset.fx, value: +b.dataset.p }); scheduleReload(); };
    });
    root.querySelectorAll('[data-v]').forEach((b) => {
      b.onclick = async () => { if (ui.locked || !mixerReady()) return; const [id, i] = b.dataset.v.split(':'); await action({ action: 'setFxParam', engine: id, param: 2, value: i === '1' }); scheduleReload(); };
    });
    ['fx1', 'fx2'].forEach((id) => {
      const r = root.querySelector(`#${id}-p1`);
      r.oninput = () => { r.classList.remove('unk-range'); r.nextElementSibling.textContent = `${r.value}%`; r.nextElementSibling.classList.remove('unk'); };
      r.onchange = () => { if (ui.locked || !mixerReady()) { scheduleReload(); return; } action({ action: 'setFxParam', engine: id, param: 1, value: +r.value }).then(scheduleReload); };
    });
  }

  // ---------- Show ----------
  // Cues are the host's snapshot library, in order. GO loads the next one (two taps). Show modes keep their hold.
  function pageShow(root) {
    const list = cueList();
    const i = list.findIndex((e) => e.id === ui.cueNow);
    const next = list[i + 1] || (i < 0 ? list[0] : null);
    const modes = session.showModes || [];
    const armedGo = next && ui.armed === `go:${next.id}`;
    root.innerHTML = `${offlineNote()}
      <div class="page-head"><h1>Show<i lang="th">คิวงาน</i></h1><span class="sp"></span><span class="note">Cues load levels, mutes, EQ and sends. Never gain or +48V.</span></div>
      <div class="show">
        <div class="cues">${list.length ? list.map((c, k) => `<button type="button" class="cuecard${k === i ? ' now' : ''}${next && c.id === next.id ? ' next' : ''}" data-id="${esc(c.id)}" aria-pressed="${ui.armed === `cue:${c.id}`}">
            <span class="n">${k + 1}</span><span><b>${esc(c.name)}</b><p>${ui.armed === `cue:${c.id}` ? 'Tap again to load this cue now.' : esc(c.createdAt ? `saved ${String(c.createdAt).slice(0, 16).replace('T', ' ')}` : '')}</p></span>
            <span class="cue-tag">${k === i ? 'NOW' : next && c.id === next.id ? 'NEXT' : ''}</span></button>`).join('')
          : '<p class="note">No cues yet. Set the mix for the first part of the show, then save it as a cue.</p>'}
          <div class="cue-save"><input id="cue-name" type="text" maxlength="40" value="${esc(ui.cueDraft)}" placeholder="Name this cue, e.g. Worship set" aria-label="Cue name"><button type="button" id="cue-add" class="mini" ${ui.locked ? 'disabled title="Locked. Hold LOCK to unlock first."' : ''}>SAVE CURRENT MIX</button></div>
        </div>
        <div class="col">
          <section class="panel"><h2>GO</h2>
            <button type="button" class="go${armedGo ? ' armed' : ''}" id="go" ${next ? '' : 'disabled'}>${next ? `${armedGo ? 'CONFIRM' : 'GO'} · ${esc(next.name)}` : list.length ? 'END OF LIST' : 'NO CUES YET'}<small>${next ? (armedGo ? 'Tap again to load it now. Undo takes it back.' : 'Tap, then tap again to load the next cue.') : ''}</small></button>
          </section>
          <section class="panel"><h2>SHOW MODES<span class="sp"></span><span class="note">hold to run</span></h2>
            <div class="modes">${modes.map((m) => `<button type="button" class="mode${m.ready ? '' : ' unset'}" data-mode="${esc(m.id)}"><span class="fill"></span><b>${esc(m.name)}</b><small>${m.ready ? 'hold 0.45 s' : `${m.unsetCount} step${m.unsetCount === 1 ? '' : 's'} NOT SET`}</small></button>`).join('')}</div>
            <p class="note" style="margin:8px 0 0">Cuts run before raises. Set the steps in the v2 console, Setup &gt; Show modes.</p>
          </section>
        </div>
      </div>`;
    const load = async (entry) => {
      if (ui.locked || !mixerReady()) return;
      ui.armed = null;
      const res = await action({ action: 'libraryLoad', id: entry.id });
      if (res.ok !== false) { ui.cueNow = entry.id; store.set('cueNow', entry.id); toast(`Cue loaded: ${entry.name}`); }
      scheduleReload();
    };
    root.querySelectorAll('.cuecard').forEach((b) => {
      b.onclick = () => {
        const entry = list.find((e) => e.id === b.dataset.id);
        if (ui.armed !== `cue:${entry.id}`) { ui.armed = `cue:${entry.id}`; render(); return; }
        load(entry);
      };
    });
    const go = root.querySelector('#go');
    if (go && next) go.onclick = () => { if (ui.armed !== `go:${next.id}`) { ui.armed = `go:${next.id}`; render(); return; } load(next); };
    root.querySelector('#cue-name').oninput = (e) => { ui.cueDraft = e.target.value; };
    root.querySelector('#cue-add').onclick = async () => {
      if (ui.locked) { toast('Locked. Hold LOCK to unlock first.', true); return; }
      const name = ui.cueDraft.trim();
      if (!name) { toast('Give the cue a name first.', true); root.querySelector('#cue-name').focus(); return; }
      const res = await action({ action: 'librarySave', name });
      if (res.ok !== false) { ui.cueDraft = ''; toast(`Saved "${name}" as a cue.`); }
      scheduleReload();
    };
    root.querySelectorAll('.mode').forEach((b) => {
      const m = modes.find((x) => x.id === b.dataset.mode);
      hold(b, 450, async () => {
        if (ui.locked || !mixerReady()) return;
        if (!m.ready) { toast(`${m.name} has steps NOT SET. Set them first.`, true); return; }
        const res = await action({ action: 'runShowMode', id: m.id });
        if (res.ok !== false) toast(`${m.name}: ${res.applied ?? ''} change(s) sent. UNDO takes it back.`);
        scheduleReload();
      });
    });
  }

  // ---------- My Mon (musician view) ----------
  function pageStage(root) {
    const mon = ui.monMix;
    const me = chById(ui.me) || chs()[0];
    root.innerHTML = `${offlineNote()}
      <div class="page-head"><h1>My Mon<i lang="th">มอนิเตอร์ของฉัน</i></h1>${mixButtons(mon, MIXES.filter((m) => m.id.startsWith('mon')))}<span class="sp"></span>
        <span class="note">Only sends to this monitor. No mutes, no EQ, no main mix.</span></div>
      <div class="mymon">
        <div class="me"><div class="note">I am</div>
          ${chs().filter((c) => c.index <= 6).map((c) => `<button type="button" class="big" data-me="${c.index}" aria-pressed="${c.index === me.index}">${esc(chName(c))}</button>`).join('')}
        </div>
        <div class="others"></div>
      </div>`;
    wireMix(root, (id) => { ui.monMix = id; store.set('monMix', id); render(); });
    root.querySelectorAll('[data-me]').forEach((b) => { b.onclick = () => { ui.me = +b.dataset.me; store.set('me', ui.me); render(); }; });
    const box = root.querySelector('.others');
    [me, ...chs().filter((c) => c.index !== me.index)].forEach((c) => box.appendChild(stripEl({
      num: c.index === me.index ? 'ME' : chLab(c.index), name: chName(c), prov: chLevel(c, mon).prov, color: 'var(--mix-mon)', sel: c.index === me.index,
      get: () => chLevel(c, mon), cmd: (v) => chLevelCmd(c, mon, v), sid: `ch${c.index}`,
    })));
    box.appendChild(stripEl({ num: mixOf(mon).label, name: 'My level', prov: masterLevel(mon).prov, color: 'var(--mix-mon)', master: true, get: () => masterLevel(mon), cmd: (v) => masterCmd(mon, v) }));
  }

  // ---------- Safety ----------
  function pageSafety(root) {
    const L = session.locked || {};
    const NAMES = { gain: 'Preamp gain', phantom: '+48V phantom', solo: 'Solo', fxMute: 'FX mute', tap: 'Tap tempo', eqParametric: 'EQ frequency and Q', snapshots: 'Mixer snapshots 1–15', routing: 'Routing and phase', stereoLink: 'Stereo link', outputPad: 'Output pads', footswitch: 'Foot switch mode', hwSnapshots: 'Mixer memory snapshots' };
    const TEST = {
      fxChannels: ['FX MIDI channels', 'The manual says 13/14; a tested third-party chart says 14/15. One controlled test decides it. Until then FX preset select may not do what it shows.'],
    };
    root.innerHTML = `
      <div class="page-head"><h1>Safety<i lang="th">สิ่งที่ล็อกไว้</i></h1><span class="sp"></span><span class="note">Every lock is enforced on the host PC, not only on this screen.</span></div>
      <div class="locks">${Object.entries(L).map(([k, why]) => `<div class="lockcard${k === 'eqParametric' ? ' test' : ''}"><b>${esc(NAMES[k] || k)}</b><p>${esc(why)}</p></div>`).join('')}
        ${Object.values(TEST).map(([t, d]) => `<div class="lockcard test"><b>${t}</b><p>${d}</p></div>`).join('')}
        <div class="lockcard"><b>Mixer reset</b><p>Program Change 16 on MIDI channel 16. Forbidden everywhere; no control sends it.</p></div></div>`;
  }

  // ---------- Global controls ----------
  function hold(btn, ms, done) {
    let t = null; let fired = false;
    btn.style.setProperty('--hold', `${ms}ms`);
    const cancel = () => { clearTimeout(t); btn.classList.remove('holding'); };
    btn.onpointerdown = () => { fired = false; btn.classList.add('holding'); t = setTimeout(() => { cancel(); fired = true; done(); }, ms); };
    btn.onpointerup = cancel; btn.onpointerleave = cancel; btn.onpointercancel = cancel;
    // A short tap explains the hold; the click that ends a successful hold says nothing.
    btn.onclick = (e) => { if (fired || e.detail === 0) { fired = false; return; } toast(`Press and hold ${btn.textContent.trim()}.`); };
    btn.onkeydown = (e) => { if ((e.key === 'Enter' || e.key === ' ') && !e.repeat) { e.preventDefault(); btn.onpointerdown(); } };
    btn.onkeyup = (e) => { if (e.key === 'Enter' || e.key === ' ') cancel(); };
  }
  hold($('#btn-lock'), 800, () => {
    ui.locked = !ui.locked;
    $('#btn-lock').setAttribute('aria-pressed', ui.locked);
    $('#btn-lock').lastChild.textContent = ui.locked ? 'LOCKED' : 'LOCK';
    document.body.classList.toggle('locked', ui.locked);
    render(); // controls that show a disabled state (SAVE CURRENT MIX) follow the lock
    toast(ui.locked ? 'Controls locked on this device. Hold LOCK to unlock.' : 'Controls unlocked.');
  });
  const allMuted = () => chs().length > 0 && chs().every((c) => known(c.muteProvenance) && c.mute);
  hold($('#btn-muteall'), 600, async () => {
    if (ui.locked) { toast('Locked. Hold LOCK to unlock first.', true); return; }
    if (!mixerReady()) { toast('The FLOW 8 is not connected. Nothing was sent.', true); return; }
    const target = !allMuted();
    const res = await action({ action: 'muteAll', value: target });
    if (res.ok !== false) toast(target ? 'All inputs muted.' : 'All inputs unmuted.');
    scheduleReload();
  });
  $('#btn-fine').onclick = () => { ui.fine = !ui.fine; $('#btn-fine').setAttribute('aria-pressed', ui.fine); toast(ui.fine ? 'Fine: a quarter of the travel.' : 'Fine off.'); };
  const applyNight = () => { document.body.classList.toggle('night', ui.night); if (ui.night) document.documentElement.setAttribute('data-theme', 'night'); else document.documentElement.removeAttribute('data-theme'); $('#btn-night').setAttribute('aria-pressed', ui.night); };
  $('#btn-night').onclick = () => { ui.night = !ui.night; store.set('night', ui.night); applyNight(); };
  $('#btn-undo').onclick = async () => { if (ui.locked) return; const res = await action({ action: 'undo' }); if (res.ok !== false) toast('Undone.'); scheduleReload(); };
  $('#btn-redo').onclick = async () => { if (ui.locked) return; const res = await action({ action: 'redo' }); if (res.ok !== false) toast('Redone.'); scheduleReload(); };
  $('#btn-set').onclick = () => { const m = $('#setmenu'); m.hidden = !m.hidden; $('#btn-set').setAttribute('aria-expanded', !m.hidden); };
  document.addEventListener('pointerdown', (e) => { if (!e.target.closest('.setwrap')) { $('#setmenu').hidden = true; $('#btn-set').setAttribute('aria-expanded', 'false'); } });
  $('#link').onclick = () => toast($('#link').title);

  // ---------- Render ----------
  const PAGE_FN = { mix: pageMix, sends: pageSends, channel: pageChannel, output: pageOutput, fx: pageFx, show: pageShow, stage: pageStage, safety: pageSafety };
  function render() {
    renderRail();
    renderLink();
    const stage = $('#stage');
    if (!session) { stage.innerHTML = '<div class="page"><div class="offline-note">Connecting to the host PC…</div></div>'; return; }
    renderCue();
    const scroll = stage.scrollTop;
    // Focus and caret survive the rebuild for any field with an id (text fields keep their value in ui).
    const active = document.activeElement;
    const focusKey = active && active.id;
    const caret = active && typeof active.selectionStart === 'number' ? [active.selectionStart, active.selectionEnd, active.selectionDirection] : null;
    if (faderSizes) faderSizes.disconnect(); // the old wells are about to go
    stage.innerHTML = '<div class="page"></div>';
    (PAGE_FN[ui.page] || pageMix)(stage.firstChild);
    stage.scrollTop = scroll;
    const again = focusKey && document.getElementById(focusKey);
    if (again) {
      again.focus();
      if (caret && typeof again.selectionStart === 'number') again.setSelectionRange(...caret);
    }
    paintMeters();
  }

  // ---------- Meters (USB audio via SSE; the FLOW 8 sends no meters over MIDI) ----------
  let levels = {}; let lastMeter = 0;
  const meterFrac = (db) => Math.max(0, Math.min(1, (db + 60) / 60));
  function paintMeters() {
    const live = performance.now() - lastMeter < 2000;
    document.querySelectorAll('.meter').forEach((m) => {
      const l = levels[m.dataset.sid];
      m.firstChild.style.setProperty('--clip', `${(1 - (live && l ? meterFrac(l.peak) : 0)) * 100}%`);
    });
  }
  let meterRaf = false;
  let sseConnectedOnce = false;
  const es = new EventSource(`/api/events?clientId=${clientId}`);
  es.onopen = () => { hubUp = true; renderLink(); };
  es.onerror = () => { hubUp = false; renderLink(); };
  es.onmessage = (msg) => {
    let ev = {};
    try { ev = JSON.parse(msg.data); } catch (_) { return; }
    if (ev.type === 'meters') {
      levels = ev.levels || {}; lastMeter = performance.now();
      if (!meterRaf) { meterRaf = true; requestAnimationFrame(() => { meterRaf = false; paintMeters(); }); }
      return;
    }
    if (ev.type === 'connected') {
      // A reconnect may have missed events while the stream was down: reload state.
      if (sseConnectedOnce) scheduleReload();
      sseConnectedOnce = true;
      return;
    }
    if (ev.type === 'tx' && ev.clientId === clientId) return; // our own command: the action's reload covers it
    scheduleReload();
  };
  setInterval(paintMeters, 500); // meters fall to zero when the feed stops
  setInterval(() => { if (!ui.dragging) loadSession(); }, 5000); // connection state, other clients without SSE

  let resizeT;
  window.addEventListener('resize', () => { clearTimeout(resizeT); resizeT = setTimeout(render, 150); });
  applyNight();
  fetch('/api/presets').then((r) => r.json()).then((d) => { presets = d.presets || []; if (ui.page === 'channel') render(); }).catch(() => {});
  render();
  loadSession();
})();
