/* FLOW 888 v3 prototype.
 * Mock state only: there is no fetch, no WebSocket and no MIDI here, so nothing can reach a mixer.
 * Provenance is part of the mock on purpose: OBSERVED (mixer reported), COMMANDED (this app sent),
 * UNSYNCED (unknown, shown as "--"). Touching a control turns its value into COMMANDED. */
(() => {
  'use strict';

  // ---------- Mock state ----------
  const MIXES = [
    { id: 'main', label: 'MAIN', color: 'var(--mix-main)' },
    { id: 'mon1', label: 'MON 1', color: 'var(--mix-mon)' },
    { id: 'mon2', label: 'MON 2', color: 'var(--mix-mon)' },
    { id: 'fx1', label: 'FX 1', color: 'var(--mix-fx)' },
    { id: 'fx2', label: 'FX 2', color: 'var(--mix-fx)' },
  ];
  const v = (value, prov) => ({ value, prov });
  const ch = (n, tag, name, fader, prov, extra = {}) => ({
    n, tag, name,
    level: { main: v(fader, prov), mon1: v(extra.m1 ?? 0, extra.m1 == null ? 'UNSYNCED' : 'COMMANDED'), mon2: v(0, 'UNSYNCED'), fx1: v(extra.f1 ?? 0, extra.f1 == null ? 'UNSYNCED' : 'COMMANDED'), fx2: v(0, 'UNSYNCED') },
    mute: v(!!extra.mute, extra.muteProv || prov),
    eq: v(extra.eq || [0, 0, 0, 0], extra.eq ? 'COMMANDED' : 'UNSYNCED'),
    lowCut: v(extra.lc ?? 0, extra.lc == null ? 'UNSYNCED' : 'COMMANDED'),
    comp: v(extra.comp ?? 0, extra.comp == null ? 'UNSYNCED' : 'COMMANDED'),
    mic: n <= 4, phantom: n <= 2,
  });
  const S = {
    page: 'mix', mix: 'main', sel: 1, fine: false, locked: false, night: false, allMuted: false,
    channels: [
      ch(1, 'MIC 1', 'Pastor', 96, 'OBSERVED', { m1: 84, eq: [0, -2, 1.5, 0], lc: 23, comp: 30, f1: 40 }),
      ch(2, 'MIC 2', 'Worship Lead', 101, 'OBSERVED', { m1: 90, f1: 62, eq: [0, -1, 2, 1], lc: 18, comp: 40 }),
      ch(3, 'COMBO 3', 'Acoustic Gtr', 88, 'COMMANDED', { m1: 70, lc: 30 }),
      ch(4, 'COMBO 4', 'Bass DI', 0, 'UNSYNCED'),
      ch(5, 'LINE 5/6', 'Keys', 92, 'COMMANDED', { m1: 76 }),
      ch(6, 'LINE 7/8', 'Drum Sub', 85, 'OBSERVED', { mute: true }),
      ch(7, 'USB/BT', 'Playback', 0, 'UNSYNCED'),
    ],
    master: { main: v(101, 'OBSERVED'), mon1: v(96, 'COMMANDED'), mon2: v(0, 'UNSYNCED'), fx1: v(88, 'COMMANDED'), fx2: v(0, 'UNSYNCED') },
    groups: [
      { name: 'BAND', members: [3, 4, 5, 6], on: false },
      { name: 'SPEECH', members: [1], on: false },
      { name: 'PLAYBACK', members: [7], on: false },
      { name: 'VOCALS', members: [1, 2], on: false },
    ],
    geq: { main: Array(9).fill(null), mon1: Array(9).fill(null), mon2: Array(9).fill(null) },
    limiter: { main: v(0, 'UNSYNCED'), mon1: v(0, 'UNSYNCED'), mon2: v(0, 'UNSYNCED') },
    outMix: 'main',
    fx: { fx1: { preset: v(9, 'COMMANDED'), p1: v(60, 'COMMANDED'), p2: v(1, 'COMMANDED') }, fx2: { preset: v(0, 'UNSYNCED'), p1: v(0, 'UNSYNCED'), p2: v(0, 'UNSYNCED') } },
    calc: { metres: 12, temp: 28 },
    cues: [
      { name: 'Walk-in', note: 'Playback up, mics parked', scope: ['Levels', 'Mutes'] },
      { name: 'Welcome + prayer', note: 'Pastor live, band muted', scope: ['Levels', 'Mutes', 'FX sends'] },
      { name: 'Worship set', note: 'Band + vocals, FX 1 hall', scope: ['Levels', 'Mutes', 'FX sends', 'EQ'] },
      { name: 'Message', note: 'Pastor only, low cut 120 Hz', scope: ['Levels', 'Mutes', 'EQ'] },
      { name: 'Response song', note: 'Keys + vocals', scope: ['Levels', 'Mutes'] },
    ],
    cueNow: 1,
    me: 2,
    undo: [],
  };
  const FX_NAMES = {
    fx1: ['AMBIENCE', 'PERC-REV1', 'PERC-REV2', 'GUIT-REV1', 'GUIT-REV2', 'CHAMBER', 'ROOM', 'CONCERT', 'CHURCH', 'CATHEDRAL', 'TEMPLE', 'STADIUM', 'FLANGER', 'SOFT CHOR', 'WARM CHOR', 'DEEP CHOR'],
    fx2: ['DELAY 1/1', 'DELAY 1/2', 'DELAY 1/3', 'DELAY 2/1', 'ECHO 1/1', 'ECHO 1/2', 'ECHO 1/3', 'ECHO 2/1', 'WIDE ECHO', 'PING PONG', 'PING P 1/3', 'PING P R>L', 'FLANGER', 'SOFT CHOR', 'WARM CHOR', 'DEEP CHOR'],
  };
  const EQ_BANDS = [
    { name: 'LOW', hz: 20, label: '20 Hz', shape: 'shelf', c: '#2EF2E2' },
    { name: 'LOW MID', hz: 300, label: '300 Hz', shape: 'peak', c: '#52E59A' },
    { name: 'HI MID', hz: 1500, label: '1.5 kHz', shape: 'peak', c: '#FFB45B' },
    { name: 'HIGH', hz: 20000, label: '20 kHz', shape: 'shelf', c: '#BC71FF' },
  ];
  const GEQ_HZ = ['63', '125', '250', '500', '1k', '2k', '4k', '8k', '16k'];
  const PRESETS = [
    { name: 'Speech · handheld', why: 'Low cut 120 Hz removes handling noise; a little 3 kHz lift keeps words clear without raising the level.' },
    { name: 'Worship lead · warm', why: 'Cuts 300 Hz boxiness by 2 dB and adds 1.5 dB at 1.5 kHz so the voice sits above the band.' },
    { name: 'Acoustic guitar', why: 'Low cut 90 Hz keeps the body out of the bass; mid scoop stops it fighting the vocal.' },
  ];

  // ---------- Helpers ----------
  const $ = (s, r = document) => r.querySelector(s);
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const known = (x) => x && (x.prov === 'OBSERVED' || x.prov === 'COMMANDED');
  const PROV = { OBSERVED: 'LIVE', COMMANDED: 'SENT', UNSYNCED: 'UNKNOWN' };
  const PROV_TIP = { OBSERVED: 'The mixer reported this value.', COMMANDED: 'This app sent this value. The mixer does not report it back.', UNSYNCED: 'Not known yet. Move the control to set it.' };
  // FLOW 8 level curve: v=0 is -inf, otherwise dB = (v-1)/126*80 - 70.
  const dbText = (raw) => (raw <= 0 ? '-∞' : `${((raw - 1) / 126 * 80 - 70).toFixed(1)}`);
  const lcText = (raw) => `${Math.floor(20 * Math.pow(30, raw / 127))} Hz`;
  const chById = (n) => S.channels.find((c) => c.n === n);
  const mixOf = (id) => MIXES.find((m) => m.id === id);
  let toastTimer;
  const toast = (msg) => { const t = $('#toast'); t.textContent = msg; t.classList.add('show'); clearTimeout(toastTimer); toastTimer = setTimeout(() => t.classList.remove('show'), 1800); };
  const remember = (label, undoFn) => { S.undo.push({ label, undoFn }); if (S.undo.length > 50) S.undo.shift(); };

  // ---------- Rail ----------
  const ICON = {
    mix: '<path d="M5 4v16M12 4v16M19 4v16M3 9h4M10 15h4M17 8h4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>',
    sends: '<path d="M4 6h16M4 12h16M4 18h16M9 4v4M15 10v4M12 16v4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>',
    channel: '<path d="M2 13h4l2-6 3 12 3-9 2 3h6" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>',
    output: '<path d="M4 9v6h4l5 4V5L8 9zM17 8a5 5 0 0 1 0 8M19.5 5.5a9 9 0 0 1 0 13" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>',
    fx: '<rect x="3" y="6" width="18" height="12" rx="2" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M7 10v4M7 10h3M7 12h2M13 10l4 4M17 10l-4 4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>',
    show: '<path d="M4 5h16v10H4zM8 19h8M12 15v4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/><path d="M10 8l4 2-4 2z" fill="currentColor"/>',
    stage: '<path d="M6 12a6 6 0 0 1 12 0v5h-3v-5M6 12v5h3v-5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/>',
    safety: '<path d="M12 3l7 3v5c0 5-3 8-7 10-4-2-7-5-7-10V6z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/>',
  };
  const PAGES = [
    ['mix', 'Mix', 'มิกซ์'], ['sends', 'Sends', 'ส่งสัญญาณ'], ['channel', 'Channel', 'ช่อง'], ['output', 'Output', 'เอาต์พุต'],
    ['fx', 'FX', 'เอฟเฟกต์'], ['show', 'Show', 'คิวงาน'], ['stage', 'My Mon', 'มอนิเตอร์'], null, ['safety', 'Safety', 'ล็อก'],
  ];
  function renderRail() {
    $('#rail').innerHTML = PAGES.map((p) => (p
      ? `<button type="button" data-page="${p[0]}" ${S.page === p[0] ? 'aria-current="page"' : ''}><svg viewBox="0 0 24 24" aria-hidden="true">${ICON[p[0]]}</svg><b>${p[1]}</b><i lang="th">${p[2]}</i></button>`
      : '<span class="sp"></span>')).join('');
    $('#rail').querySelectorAll('button').forEach((b) => { b.onclick = () => { S.page = b.dataset.page; render(); }; });
  }

  function renderCue() {
    const c = S.cues[S.cueNow];
    const n = S.cues[S.cueNow + 1];
    $('#cue').innerHTML = `<small>NOW</small><b>${esc(c.name)}</b>${n ? `<small>NEXT</small><span>${esc(n.name)}</span>` : ''}`;
  }

  // ---------- Fader ----------
  // A vertical fader well. Drag anywhere moves relatively (no jump), FINE divides travel by 4.
  function fader(get, set, label) {
    const wrap = document.createElement('div');
    wrap.className = 'well';
    wrap.setAttribute('role', 'slider');
    wrap.setAttribute('aria-label', label);
    wrap.tabIndex = 0;
    wrap.innerHTML = `<span class="slot"></span><span class="fill"></span>
      ${[[127, '+10'], [101, '0'], [64, '-20'], [32, '-40'], [0, '-∞']].map(([r, t]) => `<span class="tick" data-r="${r}">${t}</span>`).join('')}
      <span class="cap"></span>`;
    const paint = () => {
      const x = get();
      const h = wrap.clientHeight - 24;
      const y = known(x) ? (x.value / 127) * h : 0;
      wrap.querySelector('.cap').style.bottom = `${12 + y}px`;
      wrap.querySelector('.cap').classList.toggle('unk', !known(x));
      wrap.querySelector('.fill').style.height = `${known(x) ? y : 0}px`;
      wrap.querySelectorAll('.tick').forEach((t) => { t.style.top = `${12 + h - (t.dataset.r / 127) * h}px`; });
      wrap.setAttribute('aria-valuetext', known(x) ? `${dbText(x.value)} dB` : 'unknown');
    };
    let start = null;
    wrap.onpointerdown = (e) => {
      if (S.locked) return;
      wrap.setPointerCapture(e.pointerId);
      const x = get();
      start = { y: e.clientY, v: known(x) ? x.value : 0, before: { ...x } };
    };
    wrap.onpointermove = (e) => {
      if (!start || !wrap.hasPointerCapture(e.pointerId)) return;
      const h = wrap.clientHeight - 24;
      const dv = ((start.y - e.clientY) / h) * 127 / (S.fine ? 4 : 1);
      set({ value: Math.max(0, Math.min(127, Math.round(start.v + dv))), prov: 'COMMANDED' });
      paint();
    };
    const end = () => {
      if (!start) return;
      const before = start.before;
      remember(label, () => set(before));
      start = null;
      render();
    };
    wrap.onpointerup = end;
    wrap.onlostpointercapture = end;
    wrap.onkeydown = (e) => {
      const step = { ArrowUp: 1, ArrowDown: -1, PageUp: 8, PageDown: -8 }[e.key];
      if (!step || S.locked) return;
      e.preventDefault();
      const x = get();
      set({ value: Math.max(0, Math.min(127, (known(x) ? x.value : 0) + step)), prov: 'COMMANDED' });
      render();
    };
    requestAnimationFrame(paint);
    return wrap;
  }

  function stripEl({ head, num, name, prov, color, chips, get, set, mute, onMute, sel, master, sid }) {
    const el = document.createElement('section');
    el.className = `strip${sel ? ' sel' : ''}${master ? ' master' : ''}`;
    el.style.setProperty('--mc', color);
    const x = get();
    el.innerHTML = `
      <div class="s-head" tabindex="0" role="button" aria-label="Select ${esc(name)}">
        <span class="num"><span>${esc(num)}</span><span class="prov ${prov}" title="${PROV_TIP[prov]}">${PROV[prov]}</span></span>
        <span class="nm">${esc(name)}</span>
      </div>
      <div class="s-chips">${chips || ''}</div>
      <div class="s-fader"><div class="meter" data-sid="${sid}"><span class="lvl"></span></div></div>
      <div class="s-read${known(x) ? '' : ' unk'}">${known(x) ? dbText(x.value) : '--'}</div>
      ${mute ? `<button type="button" class="s-mute${known(mute) ? '' : ' unk'}" aria-pressed="${known(mute) && mute.value}">${known(mute) ? 'MUTE' : 'MUTE ?'}</button>` : '<div style="height:58px"></div>'}`;
    el.querySelector('.s-fader').prepend(fader(get, set, `${name} level`));
    if (mute) el.querySelector('.s-mute').onclick = onMute;
    if (head) el.querySelector('.s-head').onclick = head;
    return el;
  }

  // ---------- Pages ----------
  function mixButtons(current, onPick, list = MIXES) {
    return `<div class="mixes" role="group" aria-label="Mix on the faders">${list.map((m) =>
      `<button type="button" data-mix="${m.id}" style="--mc:${m.color}" aria-pressed="${m.id === current}">${m.label}</button>`).join('')}</div>`;
  }
  function wireMix(root, onPick) { root.querySelectorAll('[data-mix]').forEach((b) => { b.onclick = () => onPick(b.dataset.mix); }); }

  function pageMix(root) {
    const m = mixOf(S.mix);
    root.innerHTML = `
      <div class="page-head"><h1>Mix<i lang="th">มิกซ์</i></h1>${mixButtons(S.mix)}<span class="sp"></span>
        <span class="note">${S.mix === 'main' ? 'Faders set the level into MAIN.' : `Faders show each channel's send to ${m.label}.`}</span></div>
      <div class="groups"><span>MUTE GROUPS</span>${S.groups.map((g, i) => `<button type="button" class="grp" data-g="${i}" aria-pressed="${g.on}">${esc(g.name)}<small>CH ${g.members.join(' · ')}</small></button>`).join('')}</div>
      <div class="bank"></div>`;
    wireMix(root, (id) => { S.mix = id; render(); });
    root.querySelectorAll('.grp').forEach((b) => { b.onclick = () => toggleGroup(+b.dataset.g); });
    const bank = root.querySelector('.bank');
    S.channels.forEach((c) => {
      const inGrp = S.groups.filter((g) => g.on && g.members.includes(c.n)).map((g) => g.name);
      const chips = [
        c.mic ? '<span class="chip lock" title="Preamp gain is set on the mixer">GAIN</span>' : '',
        c.phantom ? '<span class="chip lock" title="+48V is host-only">48V</span>' : '',
        c.mic ? `<span class="chip">LC ${known(c.lowCut) ? lcText(c.lowCut.value) : '--'}</span>` : '',
        ...inGrp.map((g) => `<span class="chip grp-chip">${esc(g)}</span>`),
      ].join('');
      bank.appendChild(stripEl({
        num: `${String(c.n).padStart(2, '0')} · ${c.tag}`, name: c.name, prov: c.level[S.mix].prov, color: m.color, chips,
        get: () => c.level[S.mix], set: (x) => { c.level[S.mix] = x; },
        mute: S.mix === 'main' ? c.mute : null, onMute: () => toggleMute(c), sel: c.n === S.sel, sid: c.n,
        head: () => { S.sel = c.n; render(); },
      }));
    });
    bank.appendChild(stripEl({
      num: m.label, name: S.mix === 'main' ? 'Main LR' : `${m.label} master`, prov: S.master[S.mix].prov, color: m.color, master: true,
      get: () => S.master[S.mix], set: (x) => { S.master[S.mix] = x; }, sid: 'm',
    }));
  }

  function pageSends(root) {
    const cols = MIXES.filter((m) => m.id !== 'main');
    root.innerHTML = `
      <div class="page-head"><h1>Sends<i lang="th">ส่งสัญญาณ</i></h1><span class="sp"></span><span class="note">Drag a cell sideways. Every channel and every mix in one grid.</span></div>
      <table class="matrix"><thead><tr><th></th>${cols.map((m) => `<th style="--mc:${m.color}">${m.label}</th>`).join('')}</tr></thead>
      <tbody>${S.channels.map((c) => `<tr><th>${String(c.n).padStart(2, '0')} ${esc(c.name)}</th>${cols.map((m) => {
        const x = c.level[m.id];
        return `<td><div class="cell${known(x) ? '' : ' unk'}" style="--mc:${m.color}" data-c="${c.n}" data-m="${m.id}" role="slider" tabindex="0" aria-label="${esc(c.name)} to ${m.label}">
          <span class="bar-fill" style="width:${known(x) ? (x.value / 127) * 100 : 0}%"></span><span>${known(x) ? dbText(x.value) : '--'}</span></div></td>`;
      }).join('')}</tr>`).join('')}</tbody></table>`;
    root.querySelectorAll('.cell').forEach((cell) => {
      const c = chById(+cell.dataset.c);
      const id = cell.dataset.m;
      let start = null;
      cell.onpointerdown = (e) => { if (S.locked) return; cell.setPointerCapture(e.pointerId); start = { x: e.clientX, v: known(c.level[id]) ? c.level[id].value : 0, before: { ...c.level[id] } }; };
      cell.onpointermove = (e) => {
        if (!start) return;
        const nv = Math.max(0, Math.min(127, Math.round(start.v + ((e.clientX - start.x) / cell.clientWidth) * 127 / (S.fine ? 4 : 1))));
        c.level[id] = { value: nv, prov: 'COMMANDED' };
        cell.classList.remove('unk');
        cell.querySelector('.bar-fill').style.width = `${(nv / 127) * 100}%`;
        cell.querySelector('span:last-child').textContent = dbText(nv);
      };
      const end = () => { if (!start) return; const before = start.before; remember('send', () => { c.level[id] = before; }); start = null; };
      cell.onpointerup = end; cell.onlostpointercapture = end;
    });
  }

  function eqSvg(c) {
    // Gain-only display at the manufacturer's fixed centres. Frequency and Q are not drawn as controls.
    const W = 1000, H = 260, mid = H / 2;
    const xOf = (hz) => (Math.log10(hz / 20) / Math.log10(1000)) * (W - 60) + 30;
    const gains = known(c.eq) ? c.eq.value : [0, 0, 0, 0];
    const curve = [];
    for (let i = 0; i <= 200; i++) {
      const hz = 20 * Math.pow(1000, i / 200);
      let db = 0;
      EQ_BANDS.forEach((b, k) => {
        const g = gains[k];
        if (b.shape === 'shelf') db += g / (1 + Math.pow(k === 0 ? hz / 120 : 8000 / hz, 2));
        else db += g * Math.exp(-Math.pow(Math.log2(hz / b.hz) / 0.9, 2));
      });
      curve.push(`${xOf(hz).toFixed(1)},${(mid - db * 7).toFixed(1)}`);
    }
    const grid = [-12, -6, 0, 6, 12].map((d) => `<line x1="0" x2="${W}" y1="${mid - d * 7}" y2="${mid - d * 7}" stroke="var(--line)" stroke-width="${d ? 1 : 1.5}"/><text x="6" y="${mid - d * 7 - 4}" fill="var(--ink-3)" font-size="18">${d > 0 ? '+' : ''}${d}</text>`).join('')
      + [100, 1000, 10000].map((hz) => `<line y1="0" y2="${H}" x1="${xOf(hz)}" x2="${xOf(hz)}" stroke="var(--line)"/><text x="${xOf(hz) + 4}" y="${H - 8}" fill="var(--ink-3)" font-size="18">${hz >= 1000 ? `${hz / 1000}k` : hz}</text>`).join('');
    const path = known(c.eq)
      ? `<polyline points="${curve.join(' ')}" fill="none" stroke="var(--sel)" stroke-width="3"/>`
      : `<line x1="0" x2="${W}" y1="${mid}" y2="${mid}" stroke="var(--ink-3)" stroke-width="2" stroke-dasharray="8 8"/>`;
    return { svg: `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" aria-hidden="true">${grid}${path}</svg>`, xOf, mid, W, H, gains };
  }

  function pageChannel(root) {
    const c = chById(S.sel);
    const g = eqSvg(c);
    root.innerHTML = `
      <div class="page-head"><h1>${String(c.n).padStart(2, '0')} · ${esc(c.name)}<i>${c.tag}</i></h1><span class="sp"></span>
        <div class="mixes">${S.channels.map((x) => `<button type="button" data-ch="${x.n}" style="--mc:var(--sel)" aria-pressed="${x.n === c.n}">${x.n}</button>`).join('')}</div></div>
      <div class="ch-grid">
        <section class="panel"><h2>EQ · 4 BAND<span class="sp"></span><span class="prov ${c.eq.prov}">${PROV[c.eq.prov]}</span></h2>
          <div class="eq-wrap">${g.svg}${EQ_BANDS.map((b, k) => `<div class="eq-node${known(c.eq) ? ' on' : ''}" data-k="${k}" style="--bc:${b.c};left:${(g.xOf(b.hz) / g.W) * 100}%;top:${((g.mid - g.gains[k] * 7) / g.H) * 100}%" role="slider" tabindex="0" aria-label="${b.name} gain"></div>`).join('')}</div>
          <div class="eq-legend">${EQ_BANDS.map((b, k) => `<div style="--bc:${b.c}"><small>${b.name} · ${b.label}</small><b>${known(c.eq) ? `${g.gains[k] > 0 ? '+' : ''}${g.gains[k].toFixed(1)} dB` : '--'}</b></div>`).join('')}</div>
          <p class="lockline" style="margin:10px 0 0"><span class="chip lock">FREQ · Q</span>Frequency and Q stay at the manufacturer's values until they are tested on this mixer. Drag a dot up or down for gain.</p>
        </section>
        <div style="display:flex;flex-direction:column;gap:12px">
          <section class="panel"><h2>INPUT &amp; DYNAMICS</h2>
            <div class="row"><span class="k">GAIN</span><span class="lockline"><span class="chip lock">ON MIXER</span>set on the FLOW 8</span></div>
            ${c.mic ? `<div class="row"><label for="lc">LOW CUT</label><input id="lc" type="range" min="0" max="127" value="${c.lowCut.value}" class="${known(c.lowCut) ? '' : 'unk-range'}"><span class="v${known(c.lowCut) ? '' : ' unk'}">${known(c.lowCut) ? lcText(c.lowCut.value) : '--'}</span></div>
            <div class="row"><label for="cp">COMP</label><input id="cp" type="range" min="0" max="100" value="${c.comp.value}" class="${known(c.comp) ? '' : 'unk-range'}"><span class="v${known(c.comp) ? '' : ' unk'}">${known(c.comp) ? `${c.comp.value}%` : '--'}</span></div>` : '<p class="note">Low cut and compressor exist on channels 1–4 only.</p>'}
          </section>
          <section class="panel"><h2>START FROM A PRESET<span class="sp"></span><span class="note">EQ, low cut, comp only · never level, gain or +48V</span></h2>
            ${PRESETS.map((p, i) => `<button type="button" class="preset" data-p="${i}"><b>${esc(p.name)}</b><p>${esc(p.why)}</p></button>`).join('')}
          </section>
        </div>
      </div>`;
    root.querySelectorAll('[data-ch]').forEach((b) => { b.onclick = () => { S.sel = +b.dataset.ch; render(); }; });
    const wrap = root.querySelector('.eq-wrap');
    root.querySelectorAll('.eq-node').forEach((node) => {
      let start = null;
      node.onpointerdown = (e) => { if (S.locked) return; node.setPointerCapture(e.pointerId); start = { y: e.clientY, g: known(c.eq) ? c.eq.value[node.dataset.k] : 0, before: { value: [...c.eq.value], prov: c.eq.prov } }; };
      node.onpointermove = (e) => {
        if (!start) return;
        const db = Math.max(-15, Math.min(15, start.g + ((start.y - e.clientY) / (wrap.clientHeight / 2)) * 18.5 / (S.fine ? 4 : 1)));
        const next = known(c.eq) ? [...c.eq.value] : [0, 0, 0, 0];
        next[node.dataset.k] = Math.round(db * 2) / 2;
        c.eq = { value: next, prov: 'COMMANDED' };
        const keep = node.dataset.k;
        pageChannel(root);
        const again = root.querySelector(`.eq-node[data-k="${keep}"]`);
        again.setPointerCapture(e.pointerId);
        again.onpointermove = node.onpointermove; again.onpointerup = node.onpointerup;
      };
      node.onpointerup = () => { if (!start) return; const before = start.before; remember('EQ', () => { c.eq = before; }); start = null; };
    });
    const lc = root.querySelector('#lc');
    if (lc) {
      lc.oninput = () => { lc.classList.remove('unk-range'); c.lowCut = { value: +lc.value, prov: 'COMMANDED' }; lc.nextElementSibling.textContent = lcText(+lc.value); lc.nextElementSibling.classList.remove('unk'); };
      const cp = root.querySelector('#cp');
      cp.oninput = () => { cp.classList.remove('unk-range'); c.comp = { value: +cp.value, prov: 'COMMANDED' }; cp.nextElementSibling.textContent = `${cp.value}%`; cp.nextElementSibling.classList.remove('unk'); };
    }
    root.querySelectorAll('.preset').forEach((b) => { b.onclick = () => toast(`Preview "${PRESETS[b.dataset.p].name}": a change plan opens before anything is sent.`); });
  }

  function pageOutput(root) {
    const id = S.outMix;
    const list = MIXES.filter((m) => ['main', 'mon1', 'mon2'].includes(m.id));
    const speed = 331.3 + 0.606 * S.calc.temp;
    const ms = (S.calc.metres / speed) * 1000;
    root.innerHTML = `
      <div class="page-head"><h1>Output<i lang="th">เอาต์พุต</i></h1>${mixButtons(id, null, list)}</div>
      <div class="out-grid">
        <section class="panel"><h2>GRAPHIC EQ · 9 BAND<span class="sp"></span><span class="note">± 15 dB · grey = not sent yet</span></h2>
          <div class="geq">${GEQ_HZ.map((hz, i) => `<div class="geq-band"><b>${S.geq[id][i] == null ? '--' : `${S.geq[id][i] > 0 ? '+' : ''}${S.geq[id][i]}`}</b><div class="well" data-i="${i}" role="slider" tabindex="0" aria-label="${hz} Hz"><span class="slot"></span><span class="cap${S.geq[id][i] == null ? ' unk' : ''}" style="bottom:${(((S.geq[id][i] ?? 0) + 15) / 30) * 100}%"></span></div><small>${hz}</small></div>`).join('')}</div>
        </section>
        <div style="display:flex;flex-direction:column;gap:12px">
          <section class="panel"><h2>LIMITER<span class="sp"></span><span class="prov ${S.limiter[id].prov}">${PROV[S.limiter[id].prov]}</span></h2>
            <div class="row"><label for="lim">THRESHOLD</label><input id="lim" type="range" min="-30" max="0" value="${known(S.limiter[id]) ? S.limiter[id].value : -30}" class="${known(S.limiter[id]) ? '' : 'unk-range'}"><span class="v${known(S.limiter[id]) ? '' : ' unk'}">${known(S.limiter[id]) ? `${S.limiter[id].value} dB` : '--'}</span></div>
          </section>
          <section class="panel calc"><h2>DELAY CALCULATOR</h2>
            <div class="row"><label for="dm">DISTANCE</label><input id="dm" type="number" min="0" max="200" step="0.5" value="${S.calc.metres}"><span class="note">metres from the main speakers</span></div>
            <div class="row"><label for="dt">AIR TEMP</label><input id="dt" type="number" min="-10" max="45" value="${S.calc.temp}"><span class="note">°C · ${speed.toFixed(1)} m/s</span></div>
            <div class="result"><b>${ms.toFixed(1)} ms</b><p class="note" style="margin:4px 0 0">Set this on the output delay of the fill speakers. The app calculates only; it does not send delay.</p></div>
          </section>
        </div>
      </div>`;
    wireMix(root, (m) => { S.outMix = m; render(); });
    root.querySelectorAll('.geq .well').forEach((w) => {
      let start = null;
      w.onpointerdown = (e) => { if (S.locked) return; w.setPointerCapture(e.pointerId); start = { y: e.clientY, g: S.geq[id][w.dataset.i] ?? 0 }; };
      w.onpointermove = (e) => { if (!start) return; S.geq[id][w.dataset.i] = Math.max(-15, Math.min(15, Math.round(start.g + ((start.y - e.clientY) / w.clientHeight) * 30 / (S.fine ? 4 : 1)))); };
      w.onpointerup = () => { start = null; render(); };
    });
    const lim = root.querySelector('#lim');
    lim.oninput = () => { lim.classList.remove('unk-range'); S.limiter[id] = { value: +lim.value, prov: 'COMMANDED' }; lim.nextElementSibling.textContent = `${lim.value} dB`; lim.nextElementSibling.classList.remove('unk'); };
    root.querySelector('#dm').oninput = (e) => { S.calc.metres = Math.max(0, +e.target.value || 0); pageOutputKeep(root, '#dm'); };
    root.querySelector('#dt').oninput = (e) => { S.calc.temp = +e.target.value || 0; pageOutputKeep(root, '#dt'); };
  }
  function pageOutputKeep(root, focusSel) { const pos = root.querySelector(focusSel).selectionStart; pageOutput(root); const el = root.querySelector(focusSel); el.focus(); try { el.setSelectionRange(pos, pos); } catch (_) { /* number inputs have no selection */ } }

  function pageFx(root) {
    root.innerHTML = `
      <div class="page-head"><h1>FX<i lang="th">เอฟเฟกต์</i></h1><span class="sp"></span>
        <span class="note">Preset names as the FLOW app shows them. MIDI channel for FX is awaiting a hardware test.</span></div>
      <div class="fx-grid">${['fx1', 'fx2'].map((id) => {
        const st = S.fx[id];
        return `<section class="panel"><h2>${id === 'fx1' ? 'FX 1 · REVERB' : 'FX 2 · DELAY / MOD'}<span class="sp"></span><span class="prov ${st.preset.prov}">${known(st.preset) ? `${PROV[st.preset.prov]} · ${FX_NAMES[id][st.preset.value - 1]}` : PROV.UNSYNCED}</span></h2>
          <div class="presets16">${FX_NAMES[id].map((n, i) => `<button type="button" data-fx="${id}" data-p="${i + 1}" aria-pressed="${known(st.preset) && st.preset.value === i + 1}">${n}<small>${i + 1}</small></button>`).join('')}</div>
          <div class="row" style="margin-top:8px"><label for="${id}-p1">PARAM 1</label><input id="${id}-p1" type="range" min="0" max="100" value="${st.p1.value}" class="${known(st.p1) ? '' : 'unk-range'}"><span class="v${known(st.p1) ? '' : ' unk'}">${known(st.p1) ? `${st.p1.value}%` : '--'}</span></div>
          <div class="row"><span class="k">VARIANT</span><div class="seg" role="group">${['A', 'B'].map((x, i) => `<button type="button" data-v="${id}:${i}" aria-pressed="${known(st.p2) && st.p2.value === i}">${x}</button>`).join('')}</div>
            <span class="lockline" style="margin-left:auto"><span class="chip lock">TAP</span><span class="chip lock">FX MUTE</span>locked</span></div>
        </section>`;
      }).join('')}</div>`;
    root.querySelectorAll('[data-fx]').forEach((b) => { b.onclick = () => { if (S.locked) return; S.fx[b.dataset.fx].preset = { value: +b.dataset.p, prov: 'COMMANDED' }; render(); }; });
    root.querySelectorAll('[data-v]').forEach((b) => { b.onclick = () => { if (S.locked) return; const [id, i] = b.dataset.v.split(':'); S.fx[id].p2 = { value: +i, prov: 'COMMANDED' }; render(); }; });
    ['fx1', 'fx2'].forEach((id) => { const r = root.querySelector(`#${id}-p1`); r.oninput = () => { r.classList.remove('unk-range'); S.fx[id].p1 = { value: +r.value, prov: 'COMMANDED' }; r.nextElementSibling.textContent = `${r.value}%`; r.nextElementSibling.classList.remove('unk'); }; });
  }

  function pageShow(root) {
    const next = S.cues[S.cueNow + 1];
    const ALL = ['Levels', 'Mutes', 'FX sends', 'EQ', 'Gain', '+48V'];
    root.innerHTML = `
      <div class="page-head"><h1>Show<i lang="th">คิวงาน</i></h1><span class="sp"></span><span class="note">App-side cues. A cue never touches gain or +48V.</span></div>
      <div class="show">
        <div class="cues">${S.cues.map((c, i) => `<button type="button" class="cuecard${i === S.cueNow ? ' now' : ''}${i === S.cueNow + 1 ? ' next' : ''}" data-i="${i}"><span class="n">${i + 1}</span><span><b>${esc(c.name)}</b><p>${esc(c.note)}</p></span><span class="prov ${i === S.cueNow ? 'OBSERVED' : 'COMMANDED'}">${i === S.cueNow ? 'NOW' : i === S.cueNow + 1 ? 'NEXT' : ''}</span></button>`).join('')}</div>
        <div style="display:flex;flex-direction:column;gap:12px">
          <section class="panel"><h2>GO</h2>
            <button type="button" class="go" id="go" ${next ? '' : 'disabled'}>${next ? `GO · ${esc(next.name)}` : 'END OF LIST'}<small>${next ? 'Opens the change plan. Nothing is sent until you confirm.' : ''}</small></button>
            ${next ? `<div class="scope">${ALL.map((k) => `<span class="${next.scope.includes(k) ? '' : 'off'}">${k}</span>`).join('')}</div>` : ''}
          </section>
          <section class="panel"><h2>SHOW MODES</h2>
            <p class="note" style="margin:0">MC and BAND stay as one-hold changeovers (cuts run before raises, undo stays on screen for 8 s).</p>
          </section>
        </div>
      </div>`;
    root.querySelectorAll('.cuecard').forEach((b) => { b.onclick = () => { S.cueNow = +b.dataset.i; render(); }; });
    const go = root.querySelector('#go');
    if (go) go.onclick = () => { if (!next || S.locked) return; const prev = S.cueNow; S.cueNow += 1; remember('cue', () => { S.cueNow = prev; }); render(); toast(`Cue ${S.cueNow + 1}: ${next.name}`); };
  }

  // Musician view: one monitor mix, "me" first and big, everyone else small.
  function pageStage(root) {
    const me = chById(S.me);
    root.innerHTML = `
      <div class="page-head"><h1>My Mon<i lang="th">มอนิเตอร์ของฉัน</i></h1>${mixButtons('mon1', null, MIXES.filter((m) => m.id.startsWith('mon')))}<span class="sp"></span>
        <span class="note">For a musician on stage: only sends to this monitor. No mutes, no EQ, no main mix.</span></div>
      <div class="mymon">
        <div class="me">
          <div class="note">I am</div>
          ${S.channels.filter((c) => c.n <= 6).map((c) => `<button type="button" class="big" data-me="${c.n}" aria-pressed="${c.n === S.me}">${esc(c.name)}</button>`).join('')}
        </div>
        <div class="others"></div>
      </div>`;
    wireMix(root, () => toast('Prototype: MON 2 works the same way.'));
    root.querySelectorAll('[data-me]').forEach((b) => { b.onclick = () => { S.me = +b.dataset.me; render(); }; });
    const box = root.querySelector('.others');
    const order = [me, ...S.channels.filter((c) => c.n !== me.n)];
    order.forEach((c) => box.appendChild(stripEl({
      num: c.n === me.n ? 'ME' : String(c.n).padStart(2, '0'), name: c.name, prov: c.level.mon1.prov, color: 'var(--mix-mon)', sel: c.n === me.n,
      get: () => c.level.mon1, set: (x) => { c.level.mon1 = x; }, sid: c.n,
    })));
    box.appendChild(stripEl({ num: 'MON 1', name: 'My level', prov: S.master.mon1.prov, color: 'var(--mix-mon)', master: true, get: () => S.master.mon1, set: (x) => { S.master.mon1 = x; }, sid: 'm' }));
  }

  function pageSafety(root) {
    const L = [
      ['Preamp gain', 'Set on the FLOW 8 itself. A gain change moves every send at once, so it is never remote or automated.'],
      ['+48V phantom', 'Host PC only, one confirmation per switch. Never in undo, presets, cues or show modes.'],
      ['Mixer snapshots 1–15', 'Recall shares MIDI channel 16 with Program Change 16, which resets the mixer. Locked until the numbering is tested safely.'],
      ['Mixer reset', 'Program Change 16 on channel 16. Forbidden everywhere.'],
      ['FX mute · tap tempo', 'Channel 16 as well. Locked with the snapshots.'],
      ['EQ frequency and Q', 'Two other apps say the FLOW 8 accepts these. Not yet tested on this mixer.', true],
      ['FX MIDI channels', 'Manual says 13/14, a tested third-party chart says 14/15. One short test decides it.', true],
    ];
    root.innerHTML = `
      <div class="page-head"><h1>Safety<i lang="th">สิ่งที่ล็อกไว้</i></h1><span class="sp"></span><span class="note">Every lock is enforced on the host PC, not only on this screen.</span></div>
      <div class="locks">${L.map(([t, d, test]) => `<div class="lockcard${test ? ' test' : ''}"><b>${t}</b><p>${d}</p></div>`).join('')}</div>`;
  }

  // ---------- Actions ----------
  function toggleMute(c) {
    if (S.locked) return;
    const before = { ...c.mute };
    c.mute = { value: known(c.mute) ? !c.mute.value : true, prov: 'COMMANDED' };
    remember('mute', () => { c.mute = before; });
    render();
  }
  function toggleGroup(i) {
    if (S.locked) return;
    const g = S.groups[i];
    g.on = !g.on;
    // A channel stays muted while any active group holds it.
    S.channels.forEach((c) => {
      if (!g.members.includes(c.n)) return;
      const held = S.groups.some((x) => x.on && x.members.includes(c.n));
      c.mute = { value: held, prov: 'COMMANDED' };
    });
    remember(`group ${g.name}`, () => toggleGroup(i));
    render();
  }

  function hold(btn, ms, done) {
    let t = null;
    btn.style.setProperty('--hold', `${ms}ms`);
    const cancel = () => { clearTimeout(t); btn.classList.remove('holding'); };
    btn.onpointerdown = () => { btn.classList.add('holding'); t = setTimeout(() => { cancel(); done(); }, ms); };
    btn.onpointerup = cancel; btn.onpointerleave = cancel; btn.onpointercancel = cancel;
    btn.onkeydown = (e) => { if ((e.key === 'Enter' || e.key === ' ') && !e.repeat) { e.preventDefault(); btn.onpointerdown(); } };
    btn.onkeyup = (e) => { if (e.key === 'Enter' || e.key === ' ') cancel(); };
  }
  hold($('#btn-lock'), 800, () => {
    S.locked = !S.locked;
    $('#btn-lock').setAttribute('aria-pressed', S.locked);
    $('#btn-lock').lastChild.textContent = S.locked ? 'LOCKED' : 'LOCK';
    document.body.classList.toggle('locked', S.locked);
    toast(S.locked ? 'Controls locked. Hold LOCK to unlock.' : 'Controls unlocked.');
  });
  hold($('#btn-muteall'), 600, () => {
    if (S.locked) return toast('Locked. Hold LOCK to unlock first.');
    S.allMuted = !S.allMuted;
    if (S.allMuted) { S.restore = S.channels.map((c) => ({ ...c.mute })); S.channels.filter((c) => c.n <= 6).forEach((c) => { c.mute = { value: true, prov: 'COMMANDED' }; }); }
    else if (S.restore) { S.channels.forEach((c, i) => { c.mute = S.restore[i]; }); }
    $('#btn-muteall').setAttribute('aria-pressed', S.allMuted);
    toast(S.allMuted ? 'Inputs 1–8 muted. USB/BT keeps playing.' : 'Mutes restored to how they were.');
    render();
  });
  $('#btn-fine').onclick = () => { S.fine = !S.fine; $('#btn-fine').setAttribute('aria-pressed', S.fine); toast(S.fine ? 'Fine: a quarter of the travel.' : 'Fine off.'); };
  $('#btn-night').onclick = () => { S.night = !S.night; $('#btn-night').setAttribute('aria-pressed', S.night); document.body.classList.toggle('night', S.night); };
  $('#btn-undo').onclick = () => { const u = S.undo.pop(); if (!u) return toast('Nothing to undo.'); u.undoFn(); render(); toast(`Undid ${u.label}.`); };
  $('#link').onclick = () => toast('Host PC reachable · FLOW 8 on USB MIDI · meters from USB audio.');

  // ---------- Render ----------
  const PAGE_FN = { mix: pageMix, sends: pageSends, channel: pageChannel, output: pageOutput, fx: pageFx, show: pageShow, stage: pageStage, safety: pageSafety };
  function render() {
    renderRail();
    renderCue();
    const stage = $('#stage');
    stage.innerHTML = '<div class="page"></div>';
    PAGE_FN[S.page](stage.firstChild);
  }

  // Mock meters: only channels with a known, unmuted level move, so silence reads as silence.
  const lvl = {};
  function meters() {
    document.querySelectorAll('.meter').forEach((m) => {
      const sid = m.dataset.sid;
      const c = sid === 'm' ? null : chById(+sid);
      const live = c ? known(c.level.main) && c.level.main.value > 0 && !(known(c.mute) && c.mute.value) : true;
      const target = live ? 0.45 + Math.random() * 0.35 : 0;
      lvl[sid] = (lvl[sid] ?? 0) * 0.7 + target * 0.3;
      m.firstChild.style.setProperty('--clip', `${(1 - lvl[sid]) * 100}%`);
    });
    setTimeout(() => requestAnimationFrame(meters), 60);
  }

  let resizeT;
  window.addEventListener('resize', () => { clearTimeout(resizeT); resizeT = setTimeout(render, 150); });
  render();
  meters();
})();
