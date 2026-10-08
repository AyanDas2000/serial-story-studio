'use strict';
(() => {
  const KEY = 'serial-story-studio-ui-v3';
  const $ = (id) => document.getElementById(id);
  const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const token = (document.querySelector('meta[name="studio-token"]') || {}).content || '';
  const plural = (n, one, many) => `${n} ${n === 1 ? one : many || one + 's'}`;
  let busy = false;
  let caps = { live: false };
  const money = (n) => '$' + Number(n || 0).toFixed(2);

  try {
    const ui = JSON.parse(localStorage.getItem(KEY) || 'null') || {};
    const dark = ui.theme === 'dark' || ((ui.theme || 'system') === 'system' && matchMedia('(prefers-color-scheme: dark)').matches);
    document.documentElement.dataset.theme = dark ? 'dark' : 'light';
  } catch (_) { /* the default theme stays */ }

  function ago(iso) {
    const then = Date.parse(iso);
    if (!then) return '';
    const mins = Math.round((Date.now() - then) / 60000);
    if (mins < 1) return 'just now';
    if (mins < 60) return plural(mins, 'minute') + ' ago';
    const hours = Math.round(mins / 60);
    if (hours < 24) return plural(hours, 'hour') + ' ago';
    const days = Math.round(hours / 24);
    if (days < 14) return plural(days, 'day') + ' ago';
    return new Date(then).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
  }

  function threadHtml(s) {
    if (!s.planned) return '';
    const label = `${s.approved} of ${s.planned} episodes approved`;
    if (s.planned > 14) return `<progress class="sprog" max="${s.planned}" value="${Math.min(s.approved, s.planned)}" aria-label="${esc(label)}"></progress>`;
    const dots = Array.from({ length: s.planned }, (_, i) => `<i${i < s.approved ? ' data-on="1"' : ''}></i>`).join('');
    return `<div class="sdots" role="img" aria-label="${esc(label)}">${dots}</div>`;
  }

  function cardHtml(s) {
    const lines = s.started
      ? [s.planned ? `${s.approved} of ${plural(s.planned, 'episode')} approved` : 'No plan yet', [s.facts ? plural(s.facts, 'fact') + ' remembered' : '', s.touched ? 'Changed ' + ago(s.touched) : ''].filter(Boolean).join(' \u00b7 ')].filter(Boolean)
      : ['Not started. Open it to set the premise.'];
    const live = s.writer === 'live';
    const badge = live ? '<span class="sbadge live">Live writer</span>' : '<span class="sbadge quiet">Practice writer</span>';
    if (live) lines.push(s.available ? `${money(s.spent_usd)} spent of ${money(s.cap_usd)} limit` : 'This desk cannot run live writers. Start the live desk to open it.');
    const open = s.available ? `<a class="scard-link" href="/s/${esc(s.slug)}/">` : '<div class="scard-link">';
    const close = s.available ? '</a>' : '</div>';
    return `<li class="scard${s.available ? '' : ' off'}">${open}
<span class="sbadges">${s.sample ? '<span class="sbadge">Sample</span>' : ''}${badge}</span>
<h2 class="stitle">${esc(s.title)}</h2>
${s.premise ? `<p class="spremise">${esc(s.premise)}</p>` : ''}
${threadHtml(s)}
<p class="mono smeta">${lines.map((l) => `<span>${esc(l)}</span>`).join('')}</p>${close}</li>`;
  }

  function applyCaps(c) {
    caps = c && c.live ? c : { live: false };
    $('hwriter').hidden = !caps.live;
    $('hmode').textContent = caps.live ? 'Live writers are available. Each live series has its own spend limit.' : 'Practice writer. Nothing is sent or charged.';
    $('hintro-writer').textContent = caps.live
      ? 'Each series has one writer. A practice writer follows a script and costs nothing. A live writer uses real models and spends from that series\' own limit.'
      : 'The writer here is a practice writer. It follows a script, so nothing is sent anywhere and nothing is charged.';
    if (caps.live) {
      const cap = $('hnew-cap');
      cap.max = String(caps.max_cap);
      cap.value = String(caps.default_cap);
    }
  }

  function show(list) {
    const shelf = $('shelf');
    shelf.innerHTML = list.map(cardHtml).join('');
    $('hintro').hidden = list.some((s) => !s.sample);
    $('hmsg').hidden = list.length > 0;
    if (!list.length) $('hmsg').textContent = 'No series yet. Choose New series to start one.';
    $('main').setAttribute('aria-busy', 'false');
  }

  async function load() {
    try {
      const response = await fetch('/api/shelf');
      if (!response.ok) throw new Error('status ' + response.status);
      const body = await response.json();
      applyCaps(body);
      show(body.series || []);
    } catch (_) {
      $('shelf').innerHTML = '';
      $('hmsg').hidden = false;
      $('hmsg').textContent = 'Your series could not be loaded. Reload this page to try again.';
      $('main').setAttribute('aria-busy', 'false');
    }
  }

  function setForm(open) {
    $('hnew').hidden = !open;
    $('new-btn').setAttribute('aria-expanded', String(open));
    if (open) { $('hnew-title').focus(); } else { $('hnew-err').hidden = true; $('new-btn').focus(); }
  }

  async function create(ev) {
    ev.preventDefault();
    if (busy) return;
    const title = $('hnew-title').value.trim();
    const err = $('hnew-err');
    if (!title) { err.textContent = 'Give the series a name.'; err.hidden = false; $('hnew-title').setAttribute('aria-invalid', 'true'); $('hnew-title').focus(); return; }
    busy = true; $('hnew-go').disabled = true;
    try {
      const payload = { title };
      if (caps.live) {
        const writer = (document.querySelector('input[name="hwriter"]:checked') || {}).value || 'practice';
        payload.writer = writer;
        if (writer === 'live') {
          const cap = Number($('hnew-cap').value);
          if (!(cap > 0 && cap <= caps.max_cap)) { err.textContent = `Set a spend limit above $0 and at most ${money(caps.max_cap)}.`; err.hidden = false; $('hnew-cap').focus(); return; }
          payload.cap_usd = cap;
        }
      }
      const response = await fetch('/api/shelf/create', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Studio-Token': token }, body: JSON.stringify(payload) });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) { err.textContent = body.message || 'The series could not be created. Try again.'; err.hidden = false; $('hnew-title').setAttribute('aria-invalid', 'true'); return; }
      location.href = body.path;
    } catch (_) {
      err.textContent = 'The desk did not answer. Check that it is still running, then try again.'; err.hidden = false;
    } finally {
      busy = false; $('hnew-go').disabled = false;
    }
  }

  const dlg = $('start');
  let step = 0;
  const SEEN = 'serial-story-studio-start-seen';
  function drawStep() {
    const g = window.StudioGuide;
    const last = step === g.count - 1;
    $('start-count').textContent = `${step + 1} of ${g.count}`;
    $('start-h').textContent = g.steps[step].title;
    $('start-body').innerHTML = g.steps[step].html();
    $('start-back').hidden = step === 0;
    $('start-next').textContent = last ? 'Start a series' : 'Next';
    $('start-next').dataset.action = last ? 'start-finish' : 'start-next';
  }
  function openStart() {
    const msg = $('startmsg');
    if (!window.StudioGuide || !dlg.showModal) {
      msg.hidden = false;
      msg.textContent = window.StudioGuide
        ? 'This browser cannot show the walkthrough. Open Studio, then How it works, inside a series instead.'
        : 'The walkthrough did not load. An older copy of this program may still be running. Close every window of it, start it again, then reload this page.';
      return;
    }
    msg.hidden = true;
    step = 0; drawStep();
    if (!dlg.open) dlg.showModal();
    $('start-h').focus();
  }
  function closeStart() {
    if (dlg.open) dlg.close();
    $('start-btn').focus();
  }
  dlg.addEventListener('close', () => { try { localStorage.setItem(SEEN, '1'); } catch (_) { /* the walkthrough may show again */ } });
  dlg.addEventListener('click', (ev) => { if (ev.target === dlg) closeStart(); });
  try { if (!localStorage.getItem(SEEN)) setTimeout(openStart, 400); } catch (_) { /* no storage: do not nag */ }

  document.addEventListener('click', (ev) => {
    const t = ev.target.closest && ev.target.closest('[data-action]');
    if (!t) return;
    const act = t.dataset.action;
    if (act === 'new-open') setForm($('hnew').hidden);
    if (act === 'new-close') setForm(false);
    if (act === 'start-open') openStart();
    if (act === 'start-close') closeStart();
    if (act === 'start-next') { step = Math.min(window.StudioGuide.count - 1, step + 1); drawStep(); $('start-h').focus(); }
    if (act === 'start-back') { step = Math.max(0, step - 1); drawStep(); $('start-h').focus(); }
    if (act === 'start-finish') { closeStart(); setForm(true); }
  });
  document.addEventListener('keydown', (ev) => { if (ev.key === 'Escape' && !$('hnew').hidden) setForm(false); });
  $('hnew').addEventListener('submit', create);
  document.querySelectorAll('input[name="hwriter"]').forEach((r) => r.addEventListener('change', () => {
    $('hcap').hidden = (document.querySelector('input[name="hwriter"]:checked') || {}).value !== 'live';
    $('hnew-err').hidden = true;
  }));
  $('hnew-title').addEventListener('input', () => { $('hnew-err').hidden = true; $('hnew-title').removeAttribute('aria-invalid'); });
  window.addEventListener('pageshow', (ev) => { if (ev.persisted) load(); });
  load();
})();
