'use strict';
(() => {
  const KEY = 'serial-story-studio-ui-v3';
  const metaTag = document.querySelector('meta[name="studio-token"]');
  const token = metaTag ? metaTag.content : '';
  const metaOf = (name) => { const m = document.querySelector('meta[name="' + name + '"]'); return m ? m.content : ''; };
  const BASE = metaOf('studio-base');
  const SERIES_TITLE = metaOf('studio-series');
  const HOME = Boolean(metaOf('studio-home'));
  const $ = (id) => document.getElementById(id);
  if (HOME) {
    $('home-btn').hidden = false;
    if (SERIES_TITLE) document.title = SERIES_TITLE + ' \u00b7 Serial Story Studio';
  }
  const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const reduced = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
  const BATCH = 6;
  const LENGTH_MIN = 100;
  const LENGTH_MAX = 3000;
  const MAX_EPISODES = 100;
  const KIND_TABS = [['all', 'All'], ['knowledge', 'Knows'], ['belief', 'Believes'], ['testimony', 'Said'], ['promise', 'Promised'], ['event', 'Happened'], ['summary', 'Summary'], ['relationship', 'Ties']];
  const KIND_LABEL = { event: 'happened', testimony: 'said', belief: 'believes', knowledge: 'knows', relationship: 'ties', promise: 'promised', summary: 'summary' };
  const VALID = { unknown: 'Not settled', true_in_story: 'True in the story', false_in_story: 'False in the story' };
  const PAUSE = {
    basis_changed: 'An earlier episode was edited after a later one was drafted.',
    not_sent: 'The writing service was not asked, so nothing was charged. Resume to try again.',
    incomplete: 'The writer stopped part way. The partial draft was set aside and nothing was charged beyond what the writer used.',
    target_accepted: 'That episode was approved while a replacement was being written. The replacement was set aside.',
    waiting_predecessor: 'An earlier episode has no draft yet.',
    accounting_uncertain: 'A drafting request has no confirmed result. It will not be retried.',
    unusable_answer: "The writer's answer was cut off or could not be used. It was billed and discarded. Trying again is safe.",
    open_conflict: 'An episode is flagged by an edit to an earlier one.',
    interrupted: 'The desk was closed while drafting. Resume to carry on from the last finished episode.',
    over_length: 'A draft ran past the length limit and was set aside.',
    secret_in_input: 'A secret word would have reached the writer, so nothing was sent.',
  };
  const COMMON = new Set(('about above after again against all also always and any are because been before being below between both but can come could did does done down during each either else even ever every few for from get gets give going gone good great had has have her here him his how into its just know last like long made make many may more most much must never new next not now off often once one only other our out over own said same see she should since some still such take than that the their them then there these they this those through too under until upon very was way well were what when where which while who why will with without would year years your story stories world people time thing things place night day').split(' '));

  let S = null, ctx = null, busy = false, offline = false, problem = null, note = null, retryTimer = 0;
  let storageOk = true;
  let pending = null, pollTimer = 0, tickTimer = 0, pulsePill = false, arrive = false;
  let ui = { theme: 'system', edits: {}, kept: {}, forms: {}, composer: '', chat: [], seen: {}, scope: 'story', scopeMode: 'auto', staged: [], focus: false };
  try {
    const st = JSON.parse(localStorage.getItem(KEY) || 'null');
    if (st && typeof st === 'object') ui = { ...ui, ...st, forms: st.forms || {}, edits: {}, kept: { ...(st.kept || {}), ...(st.edits || {}) }, chat: (st.chat || []).filter((m) => m && m.text).map((m, i) => ({ id: m.id || 'm0' + i, who: m.who === 'me' ? 'me' : m.who === 'event' ? 'event' : 'reply', kind: m.kind, failed: Boolean(m.failed), why: m.why || '', read: Array.isArray(m.read) ? m.read.map(String) : [], para: m.para || 0, text: String(m.text), scope: m.scope || 'story', ts: m.ts || 0, used: m.used || [] })), staged: Array.isArray(st.staged) ? st.staged : [], seen: st.seen || {} };
  } catch (_) { /* a corrupt value is simply ignored */ }
  try { localStorage.setItem(KEY + '-probe', '1'); localStorage.removeItem(KEY + '-probe'); } catch (_) { storageOk = false; }
  const route = { room: 'write', ep: 0, person: 'all', studio: null };
  const mem = { kind: 'all', q: '', shown: 80, sel: null, eps: new Set(), gsel: null, correcting: null };
  const sess = { edit: null, suggesting: null, sel: null, dismissed: [], sheet: null, paste: null, lineNote: {}, fresh: [], studioRoom: null, needsOpen: false, saving: false, savingUntil: 0, receipt: '', tourStep: 0, pane: 'book', pick: {}, chatSel: null, thinking: null, call: null, dock: 'peek', chatDot: false, menu: null, fly: null, kbd: false, fin: null };

  function persist() {
    try { localStorage.setItem(KEY, JSON.stringify(ui)); if (!storageOk) { storageOk = true; renderBanner(); } }
    catch (_) { if (storageOk) { storageOk = false; renderBanner(); } }
  }

  // ---------- theme ----------
  function applyTheme() {
    const dark = ui.theme === 'dark' || (ui.theme === 'system' && matchMedia('(prefers-color-scheme: dark)').matches);
    document.documentElement.dataset.theme = dark ? 'dark' : 'light';
  }
  applyTheme();
  matchMedia('(prefers-color-scheme: dark)').addEventListener('change', applyTheme);

  // ---------- helpers ----------
  const form = (key, fallback) => (ui.forms[key] !== undefined ? ui.forms[key] : fallback);
  const textOf = (id) => {
    if (ui.forms[id] !== undefined) return String(ui.forms[id]).trim();
    const node = document.querySelector(`[data-form="${id}"]`) || $(id);
    return node ? node.value.trim() : '';
  };
  const btn = (action, label, o = {}) => {
    const bare = o.html && o.html.replace(/<[^>]*>/g, '').trim().length <= 2 && !/aria-label/.test(o.extra || '');
    return `<button type="button" data-action="${action}"${o.cls ? ` class="${o.cls}"` : ''}${o.disabled ? ' disabled' : ''}${o.extra ? ' ' + o.extra : ''}${bare ? ` aria-label="${esc(label)}"` : ''}>${o.html || esc(label)}</button>`;
  };
  const CLOSE_SVG = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M4 4l8 8M12 4l-8 8" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>';
  const money = (v) => '$' + Number(v || 0).toFixed(2);
  const money4 = (v) => '$' + Number(v || 0).toFixed(4);
  const rich = (t) => esc(t).replace(/\*([^*\n]+)\*/g, '<em>$1</em>');
  const plural = (n, one, many) => `${n} ${n === 1 ? one : many || one + 's'}`;
  const range = (a, b) => (a === b ? 'episode ' + a : `episodes ${a} to ${b}`);
  const live = () => Boolean(S && S.provider && S.provider.live);
  const arcN = () => (S && S.governing && S.governing.arc ? S.governing.arc.content.intentions.length : 0);
  const cursor = () => (S && S.canon ? S.canon.length : 0);
  const ep = (n) => (S && S.episodes ? S.episodes.find((e) => e.ordinal === n) : null);
  const eps = () => (S && S.episodes ? S.episodes.filter((e) => e.ordinal <= arcN()) : []);
  const intention = (n) => (S.governing.arc ? S.governing.arc.content.intentions[n - 1] || '' : '');
  const privateOf = (n) => (S.governing.arc && S.governing.arc.content.private_intentions ? S.governing.arc.content.private_intentions[n - 1] || '' : '');
  const stripListMark = (s) => s.replace(/^\s*(?:[-*]\s+|(?:episode|ep)?\s*\d{1,3}\s*[.):]\s*)/i, '');
  const titleOf = (n) => {
    const t = stripListMark(intention(n)).split(/[.,;:]/)[0].split(/\s+/).filter(Boolean);
    return t.length > 6 ? t.slice(0, 6).join(' ') + '...' : t.join(' ') || 'Episode ' + n;
  };
  const flaggedList = () => eps().filter((e) => e.open_impacts > 0 && !e.accepted);
  const waitingMemory = () => eps().filter((e) => e.accepted && e.memory_state === 'waiting');
  const nextUndrafted = () => eps().find((e) => !e.accepted && !e.selection);
  const nextToApprove = () => ep(cursor() + 1);
  const lastCommission = () => (S && S.commissions && S.commissions.length ? S.commissions[S.commissions.length - 1] : null);
  const pausedCommission = () => { const c = lastCommission(); return c && c.status === 'paused' ? c : null; };
  const inFirstRun = () => !S || !S.story || !S.governing.skeleton;
  const planCount = () => Math.min(MAX_EPISODES, Math.max(2, Number(form('count', 30)) || 30));
  function currentEp() {
    if (!arcN()) return null;
    const n = route.ep && route.ep <= arcN() ? route.ep : (nextToApprove() || ep(arcN()) || { ordinal: 1 }).ordinal;
    return ep(n);
  }
  function findBlock(id) {
    for (const e of S ? S.episodes : []) { const b = e.blocks.find((x) => x.block_id === id); if (b) return { e, b }; }
    return null;
  }
  const dirtyBlocks = (e) => (e ? e.blocks.filter((b) => ui.edits[b.block_id] && ui.edits[b.block_id].text !== b.text) : []);
  const dirtyCount = () => Object.keys(ui.edits).filter((id) => { const f = findBlock(id); return f ? ui.edits[id].text !== f.b.text : true; }).length;
  const keptCount = () => Object.keys(ui.kept).filter((id) => findBlock(id)).length;
  function approveBlock(e) {
    if (!e || !e.selection) return 'This episode has no draft yet.';
    if (e.accepted) return 'This episode is already approved.';
    if (e.open_impacts > 0) return 'An earlier edit may have changed this episode. Check it first.';
    if (e.ordinal !== cursor() + 1) return `Approve episode ${cursor() + 1} first. Episodes are approved in order.`;
    if (S.uncertain.length) return 'A drafting request has no confirmed result. Settle it first.';
    return '';
  }
  function knotState(e) {
    if (e.accepted) return 'approved';
    if (e.open_impacts > 0) return 'flagged';
    if (e.selection) return 'drafted';
    if (pending) {
      const low = eps().find((x) => x.ordinal >= pending.first && x.ordinal <= pending.last && !x.selection);
      if (low && low.ordinal === e.ordinal) return 'drafting';
    }
    const c = pausedCommission();
    if (c) {
      const low = eps().find((x) => x.ordinal >= c.first_slot && x.ordinal <= c.last_slot && !x.selection);
      if (low && low.ordinal === e.ordinal) return 'paused';
    }
    return 'planned';
  }
  function knotWords(e) {
    const st = knotState(e);
    const base = { approved: e.memory_state === 'read' ? 'approved, facts saved' : 'approved, facts not saved', flagged: 'may no longer fit', drafted: 'draft, not approved', drafting: 'being written now', paused: 'drafting paused', planned: 'not drafted' }[st];
    return base;
  }
  const originOf = (e) => (e.selection && e.selection.selected_by === 'author' ? 'Edited by you' : 'Drafted');

  // ---------- announcements ----------
  function say(text) {
    const s = $('status');
    s.textContent = '';
    requestAnimationFrame(() => { s.textContent = text; });
  }
  function setSave(text, state) {
    const el = $('save');
    if (!el) return;
    if (el.dataset.state === state && el.textContent === text) return;
    el.dataset.state = state;
    el.textContent = text;
    if (!reduced() && el.animate) el.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 120, easing: 'ease-out' });
  }
  function flash(text) {
    sess.receipt = text;
    say(text);
    renderSave();
    clearTimeout(flash.t);
    flash.t = setTimeout(() => { sess.receipt = ''; renderSave(); }, 4200);
  }
  function renderSave() {
    if (sess.receipt) return setSave(sess.receipt, 'receipt');
    if (sess.saving || Date.now() < sess.savingUntil) return setSave('Saving', 'saving');
    if (!storageOk && (dirtyCount() || ui.composer)) return setSave('Not kept on this device', 'bad');
    if (dirtyCount() || keptCount()) return setSave('Not saved yet, kept on this device', 'unsaved');
    return setSave(S ? 'Saved' : 'Not connected', 'saved');
  }
  function setSaving(on) {
    sess.saving = on;
    if (on) sess.savingUntil = Date.now() + 600;
    renderSave();
    if (!on) setTimeout(renderSave, Math.max(0, sess.savingUntil - Date.now()) + 20);
  }

  // ---------- server ----------
  async function api(command, payload, expected) {
    let response;
    try {
      response = await fetch(BASE + '/api/v1/' + command, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Studio-Token': token },
        body: JSON.stringify(expected ? { payload: payload || {}, expected } : { payload: payload || {} }) });
    } catch (_) { throw { network: true }; }
    let data = null;
    try { data = await response.json(); } catch (_) { data = null; }
    if (!response.ok) throw { status: response.status, code: data && data.code, message: data && data.message, detail: data && data.detail };
    return data;
  }
  async function getJson(path) {
    let response;
    try { response = await fetch(path); } catch (_) { throw { network: true }; }
    let data = null;
    try { data = await response.json(); } catch (_) { data = null; }
    if (!response.ok) throw { status: response.status, code: data && data.code, message: data && data.message, detail: data && data.detail };
    return data;
  }
  function cleanEdits() {
    if (!S) return;
    [ui.edits, ui.kept].forEach((bag) => Object.keys(bag).forEach((id) => { if (!findBlock(id)) delete bag[id]; }));
    ui.staged = ui.staged.filter((s) => {
      if (s.kind === 'para') { const f = findBlock(s.block); return Boolean(f && !f.e.accepted); }
      if (s.kind === 'line') { const e = ep(s.index + 1); return !(e && e.accepted); }
      return true;
    });
  }
  async function refresh() {
    try {
      S = await getJson(BASE + '/api/v1/state');
      if (offline) { offline = false; say('Back in touch with your story.'); }
    } catch (e) {
      if (e.network) { goOffline(); }
      throw e;
    }
    ctx = null;
    if (S.story && S.canon.length) {
      try { ctx = await getJson(BASE + '/api/v1/context?boundary=' + S.canon.length); } catch (e) { ctx = e.network ? null : { blocked: e.message || 'The next episode cannot be prepared yet.', code: e.code }; }
    }
    cleanEdits();
    render();
  }
  function goOffline() {
    if (!offline) { offline = true; renderBanner(); renderDock(); }
    clearTimeout(retryTimer);
    retryTimer = setTimeout(() => { refresh().catch(() => {}); }, 5000);
  }

  const NAV = (to, label) => [`data-nav="${to}"`, label];
  const RELOAD = ['data-action="reload-state"', 'Refresh'];
  const RELOAD_PAGE = ['data-action="reload-page"', 'Reload page'];
  const EXPLAIN = {
    stale_pointer: ['This changed since you opened it', 'It may have changed in another tab. Nothing was overwritten and your words are kept here. Refresh, then try again.', [RELOAD]],
    overlap: ['That passage changed in the meantime', 'Nothing was written. Compare the versions, then choose what to keep.', []],
    direction_missing: ['Adopt a direction and a plan first', 'Drafting needs an adopted direction and an adopted plan.', [NAV('plan', 'Open the plan')]],
    open_conflict: ['An episode needs a check first', 'An earlier episode was edited after a later one was drafted. Check it, then try again.', [NAV('write', 'Open the episodes')]],
    accounting_uncertain: ['A drafting request has no confirmed result', 'The desk will not retry it. Settle it once you are sure, then continue.', [NAV('studio/money', 'Open Money')]],
    basis_changed: ['An earlier episode has no draft yet', 'Draft the earlier episodes first, in order.', []],
    prefix_invalid: ['That episode cannot be approved yet', 'Approve episodes in order, using the draft you currently see. Refresh to see what is ready.', [RELOAD]],
    polish_refused: ['That asks for a story change', 'Better wording only smooths the words. Describe a wording change such as "tighten the rhythm". Story changes belong in the plan.', []],
    invalid_range: ['That paragraph is no longer in the text', 'The paragraph changed or was removed. Refresh, then ask again.', [RELOAD]],
    not_found: ['The desk could not find that', 'It may already have been used or replaced. Refresh to see what is current.', [RELOAD]],
    accepted: ['Approved text is locked', 'Approved episodes change only through a staged change, which this desk does not offer yet.', []],
    ambiguous_block: ['That paragraph does not belong to this text', 'Refresh and edit again.', [RELOAD]],
    not_revertible: ['That change cannot be undone here', 'Approved text changes only through a staged change.', []],
    invalid_claim: ['Someone has to say it', 'A statement made by a person needs a speaker. Add who says it, or pick another kind.', []],
    unreadable_extraction: ['The story changes could not be read', 'The reading came back in a form the desk cannot use. Nothing was saved. Try again.', []],
    canary_already_visible: ['That word is already in the story', 'The writer has already seen that trigger word. Pick a word only this secret would bring in, such as a name.', []],
    invalid_secret: ['That secret needs more', 'Give it a short name, the secret, and trigger words of four or more letters that are not common words.', []],
    invalid_style_sheet: ['That voice cannot be saved', 'Keep the notes under 4,000 characters and the never-use list under 40 items.', []],
    commission_closed: ['That drafting run is finished', 'Start a new run to draft those episodes again. Your edits were not touched.', []],
    plan_below_approved: ['The plan is shorter than your approved episodes', 'Approved episodes cannot be dropped. Keep at least as many episodes as you have approved.', []],
    invalid_slots: ['That episode is not in the plan', 'Choose episodes that are in the adopted plan.', []],
    secret_in_message: ['Nothing was sent', 'That text names a protected secret word. Say it another way, or ask without it.', [NAV('studio/secrets', 'Open Secrets')]],
    secret_in_input: ['Drafting stopped', 'A secret would have reached the writer. Remove the trigger word from the plan, the voice notes or earlier episodes, or change the reveal episode.', [NAV('studio/secrets', 'Open Secrets')]],
    provider_not_sent: ['The writer was not asked', 'Nothing was sent and nothing was charged. The limit may be reached, or the writing service refused the request.', []],
    provider_unverified: ['The writing service gave no clear answer', 'It may or may not have charged. The desk will not try again by itself. Check Money for this charge.', [NAV('studio/money', 'Open Money')]],
    unusable_answer: ["The writer's answer was cut off", 'It was billed and discarded. Nothing changed; ask again when you are ready.', []],
    answer_unusable: ["The writer's answer was cut off", 'It was billed and discarded. Nothing changed; ask again when you are ready.', []],
  };
  function explain(e) {
    if (e.network) return { title: 'The desk did not confirm', text: 'We cannot tell whether that was saved. Your unsent text is kept here. Reload the page to check before you try again.', actions: [RELOAD_PAGE] };
    if (e.status === 403) return { title: 'This page is out of date', text: 'The desk was restarted, so it refused that action. It was not saved. Your unsent text is kept. Reload the page, then try again.', actions: [RELOAD_PAGE] };
    const known = EXPLAIN[e.code];
    if (known) return { title: known[0], text: known[1], actions: known[2], hard: e.code === 'secret_in_input' };
    return { title: 'That did not finish', text: (e.message || 'The desk could not finish that action.') + ' Nothing is lost. Refresh before trying again.', actions: [RELOAD] };
  }
  function report(e) {
    problem = { ...explain(e), id: 'p' + Date.now() };
    say(problem.title + '. ' + problem.text);
    renderBanner();
    if (e.code === 'overlap' && e.detail) openOverlap(e.detail);
  }
  async function run(label, work) {
    if (busy) { say('Still saving the last step. Try again in a moment.'); return { ok: false }; }
    busy = true;
    problem = null; note = null;
    setSaving(true);
    try {
      const out = await work();
      try { await refresh(); } catch (_) { /* offline banner already shows */ }
      return { ok: true, out };
    } catch (e) {
      try { await refresh(); } catch (_) { /* the failure message still applies */ }
      report(e);
      return { ok: false, err: e };
    } finally {
      busy = false; setSaving(false);
    }
  }

  function pauseText(c) {
    const d = c.pause_detail;
    if (c.pause_reason === 'over_length' && d && ep(d.ordinal) && ep(d.ordinal).selection) return `You chose to use the long draft of episode ${d.ordinal}. Resume to carry on after it.`;
    if (c.pause_reason === 'over_length' && d && d.within_limit) return `Episode ${d.ordinal} ran to ${d.words} words. It was set aside under an earlier, stricter limit. It is inside the current limit of ${d.limit}, so you can use it.`;
    if (c.pause_reason === 'over_length' && d) return `Episode ${d.ordinal} ran to ${d.words} words. The limit is ${d.limit}. It was set aside, not used. You can read it.`;
    return PAUSE[c.pause_reason] || 'It stopped early.';
  }

  // ---------- banner ----------
  let bannerKey = '';
  function computeBanner() {
    if (problem) return { sev: problem.hard ? 'bad' : 'warn', title: problem.title, text: problem.text, actions: problem.actions || [], dismiss: true, alert: Boolean(problem.hard) };
    if (offline) return { sev: 'warn', text: "Can't reach your story right now. What you type is kept on this device. Trying again.", actions: [RELOAD_PAGE] };
    if (S && S.story) {
      const c = pausedCommission();
      if (c && !S.uncertain.length) {
        const low = eps().find((x) => x.ordinal >= c.first_slot && x.ordinal <= c.last_slot && !x.selection);
        const retry = c.pause_reason === 'unusable_answer';
        return { sev: 'warn', text: `Drafting paused${low ? ' at episode ' + low.ordinal : ''}. ${pauseText(c)}`,
                 actions: retry ? [[`data-action="resume-commission" data-commission="${esc(c.commission_id)}"`, 'Try again'], ['data-action="see-why"', 'See why']] : [['data-action="see-why"', 'See why']] };
      }
      if (live() && S.provider.left_usd <= 0) return { sev: 'warn', text: 'Limit reached. Raise it to keep drafting.', actions: [NAV('studio/money', 'Open Money')] };
    }
    if (!storageOk) return { sev: 'warn', text: 'This browser is not keeping your unsent text. Save it or copy it before you reload.', actions: [['data-action="copy-unsent"', 'Copy unsent text']] };
    return null;
  }
  function renderBanner() {
    if (route.studio !== null && S) renderStudio();
    const b = computeBanner();
    const el = $('banner');
    const k = b ? (b.title || '') + b.text + b.sev : '';
    if (!b) { el.hidden = true; bannerKey = ''; return; }
    el.hidden = false;
    el.setAttribute('role', b.alert ? 'alert' : 'status');
    el.dataset.sev = b.sev;
    el.innerHTML = `<div class="banner-in"><p>${b.title ? `<strong>${esc(b.title)}.</strong> ` : ''}${esc(b.text)}</p><div class="banner-actions">${(b.actions || []).map(([attr, label]) => `<button type="button" ${attr}>${esc(label)}</button>`).join('')}${b.dismiss ? btn('dismiss-problem', 'Dismiss') : ''}</div></div>`;
    if (k !== bannerKey && !reduced() && el.animate) el.animate([{ transform: 'translateY(-100%)', opacity: 0 }, { transform: 'none', opacity: 1 }], { duration: 240, easing: 'cubic-bezier(.23,1,.32,1)' });
    bannerKey = k;
  }

  // ---------- needs you ----------
  function needs() {
    const out = [];
    if (!S || !S.story || inFirstRun()) return out;
    S.uncertain.forEach(() => out.push({ key: 'unc', text: 'Settle an unconfirmed charge', attr: 'data-nav="studio/money"' }));
    const c = pausedCommission();
    if (c && !S.uncertain.length) {
      const low = eps().find((x) => x.ordinal >= c.first_slot && x.ordinal <= c.last_slot && !x.selection);
      out.push({ key: 'paused', text: `Batch paused${low ? ' at episode ' + low.ordinal : ''}`, attr: 'data-action="see-why"' });
    }
    flaggedList().forEach((e) => out.push({ key: 'flag' + e.ordinal, text: `Check episode ${e.ordinal}, it may not fit`, attr: `data-nav="write/${e.ordinal}"` }));
    waitingMemory().forEach((e) => out.push({ key: 'save' + e.ordinal, text: `Save story changes for episode ${e.ordinal}`, attr: `data-action="open-finish" data-ordinal="${e.ordinal}"` }));
    const nx = nextToApprove();
    if (nx && nx.selection && !approveBlock(nx)) out.push({ key: 'ready' + nx.ordinal, text: `Read episode ${nx.ordinal}, it's ready`, attr: `data-nav="write/${nx.ordinal}"` });
    if (live() && S.provider.left_usd > 0 && S.provider.left_usd < 0.1) out.push({ key: 'limit', text: `Nearly at your limit (${money(S.provider.left_usd)} left)`, attr: 'data-nav="studio/money"' });
    if (ui.staged.length) out.push({ key: 'sug', text: `${plural(ui.staged.length, 'suggestion')} waiting`, attr: 'data-action="stage-show"' });
    return out;
  }
  let needsKeys = null;
  function renderNeeds() {
    const list = needs();
    const keys = list.map((n) => n.key).join('|');
    const pill = $('needs-btn');
    pill.hidden = !list.length;
    $('needs-count').textContent = String(list.length);
    pill.setAttribute('aria-label', `Needs you, ${list.length} waiting`);
    const grew = needsKeys !== null && list.some((n) => !needsKeys.includes(n.key));
    if ((grew || pulsePill) && list.length) pulse(pill);
    pulsePill = false;
    needsKeys = list.map((n) => n.key);
    const pop = $('needs');
    if (!list.length && sess.needsOpen) setNeeds(false);
    const showAll = Boolean(ui.seen.needsAll);
    const rows = showAll ? list : list.slice(0, 5);
    pop.innerHTML = `<h2>Needs you</h2><ul>${rows.map((n) => `<li><button type="button" ${n.attr}><span>${esc(n.text)}</span><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M6 3l5 5-5 5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg></button></li>`).join('')}</ul>${list.length > 5 && !showAll ? btn('needs-all', `See all ${list.length}`, { cls: 'plain' }) : ''}`;
    void keys;
  }
  function pulse(el) {
    const ring = el.querySelector('.ring');
    if (!ring || reduced() || !ring.animate) { el.classList.add('dot'); return; }
    ring.animate([{ transform: 'scale(1)', opacity: 0.6 }, { transform: 'scale(1.6)', opacity: 0 }], { duration: 600, easing: 'cubic-bezier(.23,1,.32,1)' });
  }
  function setNeeds(open) {
    sess.needsOpen = open;
    const pop = $('needs');
    $('needs-btn').setAttribute('aria-expanded', String(open));
    if (open) {
      pop.hidden = false;
      if (!reduced() && pop.animate) pop.animate([{ transform: 'scale(.96)', opacity: 0 }, { transform: 'none', opacity: 1 }], { duration: 200, easing: 'cubic-bezier(.23,1,.32,1)' });
      const first = pop.querySelector('button');
      if (first) first.focus({ preventScroll: true });
    } else if (!pop.hidden) {
      pop.hidden = true;
    }
  }

  // ---------- bar and rooms ----------
  function checkpoint() {
    if (!S) return 'Not connected';
    if (inFirstRun()) return 'Start your story';
    if (!S.governing.arc) return 'Plan the episodes';
    if (route.room === 'plan') return `${plural(arcN(), 'episode')}, ${cursor()} approved`;
    if (route.room === 'memory') return plural(S.memory.accepted.length, 'fact');
    const e = currentEp();
    const word = { approved: 'approved', flagged: 'may not fit', drafted: 'draft, not approved', drafting: 'being written', paused: 'paused', planned: 'not drafted' }[knotState(e)];
    return `Episode ${e.ordinal} of ${arcN()} · ${word}`;
  }
  let lastMemNum = '', roomsHtml = '';
  function renderBar() {
    $('where').textContent = (SERIES_TITLE ? SERIES_TITLE + ' \u00b7 ' : '') + checkpoint();
    const rooms = [['plan', 'Plan'], ['write', 'Write'], ['memory', 'Memory']];
    const count = S && S.memory ? S.memory.accepted.length : 0;
    const tabs = isPhone();
    const inChat = tabs && sess.pane === 'chat';
    const nStaged = ui.staged.length;
    const chatTab = tabs ? `<button type="button" id="pane-chat" data-action="switch-pane" data-pane="chat" aria-pressed="${inChat}" aria-label="${sess.chatDot ? 'Chat, new reply' : 'Chat'}">Chat${sess.chatDot ? '<i class="chatdot"></i>' : ''}</button>` : '';
    const html = chatTab + rooms.map(([id, l]) => {
      const here = route.room === id && !route.studio;
      const badge = tabs && here && nStaged ? `<span class="tabbadge" id="tabbadge">${nStaged}</span>` : '';
      const name = badge ? ` aria-label="${l}, ${plural(nStaged, 'suggestion')} waiting"` : '';
      return `<button type="button" data-nav="${id}"${here && !inChat ? ' aria-current="page"' : ''}${tabs && here ? ' id="pane-book"' : ''}${name}>${l}${id === 'memory' && count ? ` <span class="num" id="memnum">${count}</span>` : ''}${badge}</button>`;
    }).join('');
    if (html !== roomsHtml) { $('rooms').innerHTML = html; roomsHtml = html; }
    const mn = $('memnum');
    if (mn) { if (lastMemNum && lastMemNum !== String(count) && !reduced() && mn.animate) mn.animate([{ transform: 'translateY(60%)', opacity: 0 }, { transform: 'none', opacity: 1 }], { duration: 200, easing: 'cubic-bezier(.23,1,.32,1)' }); lastMemNum = String(count); }
  }

  // ---------- thread ----------
  const prevKnots = {};
  let threadKey = '';
  function threadModel() {
    if (S && S.story && S.governing.arc) return { adopted: true, list: eps().map((e) => ({ n: e.ordinal, st: knotState(e), saved: e.memory_state === 'read', title: e.title || titleOf(e.ordinal), words: knotWords(e), facts: S.memory.accepted.filter((c) => c.narrative_ordinal === e.ordinal).length })) };
    const n = inFirstRun() && (ui.fr || 1) < 3 ? 1 : planCount();
    return { adopted: false, list: Array.from({ length: n }, (_, i) => ({ n: i + 1, st: 'planned', saved: false, title: '', words: 'not written yet', facts: 0 })) };
  }
  let winNow = { start: 1, w: 7 }, winN = 0, winCur = 0;
  function threadWin(n, cur) {
    const tw = $('track') ? $('track').clientWidth : 0;
    const w = !tw ? Math.min(n, 7) : Math.min(n, Math.max(3, Math.floor(tw / 44)));
    const c = cur || sess.twinC || Math.min(n, cursor() + 1) || 1;
    return { w, start: Math.max(1, Math.min(c - Math.floor(w / 2), n - w + 1)) };
  }
  function renderThread() {
    const wrap = $('threadwrap');
    const m = threadModel();
    const n = m.list.length;
    const cur = route.room === 'write' && !route.studio && m.adopted && currentEp() ? currentEp().ordinal : 0;
    if (!cur && route.room === 'write') sess.twinC = 0;
    winN = n; winCur = cur;
    winNow = threadWin(n, cur);
    const vis = m.list.slice(winNow.start - 1, winNow.start - 1 + winNow.w);
    const heat = route.room === 'memory' && m.adopted;
    wrap.dataset.mode = heat ? 'memory' : route.room;
    wrap.dataset.adopted = String(m.adopted);
    const list = $('knots');
    const key = n + ':' + m.adopted + ':' + winNow.start + ':' + winNow.w;
    const first = key !== threadKey;
    if (first) {
      list.innerHTML = vis.map((k) => `<button type="button" role="option" class="knot" data-n="${k.n}"><i class="k"></i><span class="kn" aria-hidden="true">${k.n}</span></button>`).join('');
      $('track-in').style.setProperty('--n', String(vis.length));
      list.querySelectorAll('.knot').forEach((b, i) => {
        if (reduced() || !b.animate) return;
        if (!threadKey || threadKey.split(':')[1] === 'false') b.animate([{ opacity: 0, transform: 'scale(.6)' }, { opacity: 1, transform: 'none' }], { duration: 200, delay: Math.min(i * 12, 160 - 12), easing: 'cubic-bezier(.23,1,.32,1)', fill: 'backwards' });
      });
      threadKey = key;
    }
    const maxFacts = Math.max(1, ...m.list.map((k) => k.facts));
    const knots = list.querySelectorAll('.knot');
    vis.forEach((k, i) => {
      const b = knots[i];
      const prev = m.list[k.n - 2], next = m.list[k.n];
      const tex = (x, y) => (!x || !y ? 'none' : !m.adopted ? 'dash' : y.st === 'approved' ? 'lock' : 'dot');
      b.dataset.st = k.st;
      b.dataset.saved = k.saved ? 'yes' : 'no';
      b.dataset.in = tex(prev, k);
      b.dataset.out = tex(k, next);
      b.dataset.heat = heat ? String(k.facts ? 1 + Math.min(3, Math.floor((k.facts / maxFacts) * 3.99)) : 0) : '';
      b.setAttribute('aria-selected', String(k.n === cur));
      b.tabIndex = k.n === cur || (!cur && i === 0) ? 0 : -1;
      const label = m.adopted ? `Episode ${k.n}, ${k.title}, ${k.words}${heat ? ', ' + plural(k.facts, 'fact') : ''}` : `Episode ${k.n}, ${k.words}`;
      if (b.getAttribute('aria-label') !== label) b.setAttribute('aria-label', label);
      b.dataset.title = k.title;
      b.title = `${k.n}${k.title ? ' · ' + k.title : ''}`;
      const filtered = heat && mem.eps.size > 0 && mem.eps.has(k.n);
      b.dataset.pick = filtered ? 'yes' : 'no';
      const was = prevKnots[k.n];
      if (was && was !== k.st && !reduced()) {
        const dot = b.querySelector('.k');
        if (dot && dot.animate) dot.animate([{ transform: 'scale(.6)', opacity: 0.2 }, { transform: 'scale(1)', opacity: 1 }], { duration: k.st === 'approved' ? 480 : 320, easing: 'cubic-bezier(.34,1.35,.64,1)' });
      }
      prevKnots[k.n] = k.st;
    });
    const diamond = $('tstory');
    diamond.dataset.on = S && S.governing && S.governing.skeleton ? 'yes' : 'no';
    $('cap').hidden = !m.adopted;
    $('tprev').disabled = cur ? cur <= 1 : winNow.start <= 1;
    $('tnext').disabled = cur ? cur >= n : winNow.start + winNow.w > n;
    wrap.hidden = !S || !S.story || (!inFirstRun() && !S.governing.skeleton);
    if (inFirstRun() && S && !S.story) wrap.hidden = false;
    requestAnimationFrame(layoutThread);
    return first;
  }
  let lastScrollKey = '';
  function layoutThread() {
    const track = $('track'), list = $('knots');
    if (!track || !list) return;
    if (winN) {
      const w = threadWin(winN, winCur);
      if (w.start !== winNow.start || w.w !== winNow.w) { renderThread(); return; }
    }
    const knots = list.querySelectorAll('.knot');
    if (!knots.length) return;
    const inner = $('track-in');
    const sel = list.querySelector('[aria-selected="true"]');
    const center = (b) => b.offsetLeft + b.offsetWidth / 2;
    const ph = $('playhead');
    ph.hidden = !sel;
    if (sel) inner.style.setProperty('--ph', center(sel) + 'px');
    const target = list.querySelector('[data-st="drafting"]');
    const arc = $('arc');
    arc.hidden = !target;
    if (target) {
      const prev = target.previousElementSibling;
      inner.style.setProperty('--arc-from', (prev ? center(prev) : target.offsetLeft) - 12 + 'px');
      inner.style.setProperty('--arc-to', center(target) - 12 + 'px');
    }
    const cap = $('cap');
    inner.style.setProperty('--cap-l', center(knots[0]) + 'px');
    inner.style.setProperty('--cap-w', Math.max(0, center(knots[knots.length - 1]) - center(knots[0])) + 'px');
    void cap;
  }

  // ---------- dock ----------
  function dockPrimary() {
    if (!S || !S.story || inFirstRun()) return null;
    if (route.room === 'plan') return planPrimary();
    if (route.room === 'memory') {
      const w = waitingMemory();
      return w.length ? { label: 'Save story changes', action: 'open-finish', extra: `data-ordinal="${w[0].ordinal}"`, cls: 'btn moss' } : null;
    }
    if (!arcN()) return { label: 'Plan the episodes', action: 'go-plan', cls: 'btn tonal' };
    const e = currentEp();
    if (pending) return { label: `Drafting episode ${pending.first}`, busy: true, cls: 'btn busy' };
    const dirty = dirtyBlocks(e);
    if (dirty.length) return { label: dirty.length === 1 ? 'Save your edit' : `Save ${dirty.length} edits`, action: 'save-edits', cls: 'btn tonal' };
    if (S.uncertain.length) return { label: 'Settle the charge', action: 'go-money', cls: 'btn tonal' };
    if (pausedCommission() && !e.selection) return { label: 'See why', action: 'see-why', cls: 'btn tonal' };
    if (e.selection && !e.accepted) {
      if (e.open_impacts > 0) return { label: 'It still fits', action: 'revalidate-slot', extra: `data-slot="${e.ordinal}"`, cls: 'btn tonal' };
      return { label: 'Approve this episode', action: 'open-finish', extra: `data-ordinal="${e.ordinal}"`, cls: 'btn sealbar' };
    }
    if (e.accepted && e.memory_state === 'waiting') return { label: 'Save story changes', action: 'open-finish', extra: `data-ordinal="${e.ordinal}"`, cls: 'btn moss' };
    const nu = nextUndrafted();
    if (nu) { const r = spendRun(); const k = Math.min(3, r ? r.max : 1); return { label: k > 1 ? `Draft next ${k}` : `Draft episode ${nu.ordinal}`, action: 'open-spend', cls: 'btn spend' }; }
    const nx = nextToApprove();
    if (nx && nx.ordinal !== e.ordinal) return { label: 'Read on', nav: `write/${nx.ordinal}`, cls: 'btn tonal' };
    return { label: 'Plan more episodes', nav: 'plan', cls: 'btn tonal' };
  }
  function renderDock() {
    const dock = $('dock');
    const p = dockPrimary();
    dock.hidden = !S || !S.story || inFirstRun();
    $('spendchip').hidden = !live();
    if (live()) $('spendchip').textContent = `${money(S.provider.left_usd)} left`;
    $('practice').hidden = live() || !S;
    const main = $('dock-main');
    let html = '';
    if (p) {
      const attrs = p.nav ? `data-nav="${p.nav}"` : p.action ? `data-action="${p.action}"` : '';
      html = `${p.sentence ? `<span class="consequence">${esc(p.sentence)}</span>` : ''}<button type="button" class="${p.cls}" ${attrs}${p.extra ? ' ' + p.extra : ''}${p.busy ? ' disabled aria-disabled="true"' : ''}>${p.busy ? orbHtml('working', 'sm') : ''}${esc(p.label)}${p.chip ? `<span class="chip">${esc(p.chip)}</span>` : ''}</button>`;
    } else if (route.room === 'plan' && S && S.governing && S.governing.arc) {
      html = '<span class="adopted-tag">Adopted</span>';
    }
    if (main.dataset.key !== html) { main.innerHTML = html; main.dataset.key = html; }
    renderSave();
  }

  // ---------- icons ----------
  const ICON = {
    lock: '<svg viewBox="0 0 16 16" aria-hidden="true"><rect x="3.5" y="7" width="9" height="6.5" rx="1.5" fill="currentColor"/><path d="M5.5 7V5.2a2.5 2.5 0 015 0V7" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>',
    pencil: '<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M4 16l.8-3.4L13.6 3.8a1.4 1.4 0 012 0l.6.6a1.4 1.4 0 010 2L7.4 15.2z" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/></svg>',
    wand: '<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M4 16L13 7M12 4v3M16 8h-3M15 3.5v2M10 3v1.5" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>',
    chat: '<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M4 5.5A1.5 1.5 0 015.5 4h9A1.5 1.5 0 0116 5.5v6a1.5 1.5 0 01-1.5 1.5H9l-3.5 3v-3h0A1.5 1.5 0 014 11.5z" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/></svg>',
    read: '<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M3 5.5C5 4 7.5 4 10 5.6 12.5 4 15 4 17 5.5V15c-2-1.5-4.5-1.5-7 0-2.5-1.5-5-1.5-7 0z" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/><path d="M10 5.6V15" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>',
    dots: '<svg viewBox="0 0 20 20" aria-hidden="true"><circle cx="4.5" cy="10" r="1.4" fill="currentColor"/><circle cx="10" cy="10" r="1.4" fill="currentColor"/><circle cx="15.5" cy="10" r="1.4" fill="currentColor"/></svg>',
    bracket: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M5 3H3.5v10H5M11 3h1.5v10H11" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>',
    stack: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M2 5l6-3 6 3-6 3zM2 8.5l6 3 6-3M2 11.5l6 3 6-3" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/></svg>',
    key: '<svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="5" cy="8" r="2.6" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M7.6 8H14M12 8v2.4" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>',
  };

  // ---------- views: first run ----------
  const SAMPLE = {
    skeleton: { premise: 'Leena Vale is a court interpreter who speaks as the witness, in the first person, and cannot always tell afterward whose memory is whose.', spine: 'She exposes the coercion behind a trial; useful lies give way to accountable uncertainty.', private: 'The witness is real. The man everyone says died in the fire is alive.' },
    arc: { purpose: 'Make Darin suspect that the witness was prepared by someone', intentions: ['Leena interprets a witness whose answers are being steered, and feels the cost of speaking as him.', 'Darin hears the witness name a courier who supposedly died in a fire.', 'Darin finds a ledger entry that predates the alleged death.'], private_intentions: ['', 'Do not confirm the courier is alive yet.', ''] },
  };
  function firstRunHtml() {
    const step = Math.min(3, Math.max(1, ui.fr || 1));
    const premise = form('premise', ''), spine = form('spine', '');
    const err = sess.frError ? `<p class="field-err" role="alert">${esc(sess.frError)}</p>` : '';
    if (step === 1) {
      const priv = sess.privOpen || form('private-note', '');
      return `<section class="fr" data-step="1"><p class="sr" role="status">Step 1 of 3</p><h1>What is your story about?</h1>
<label class="sr" for="premise">Your story</label><textarea id="premise" data-form="premise" maxlength="4000" rows="5" placeholder="A lighthouse keeper's daughter finds the logbook her mother hid..." aria-describedby="fr-hint">${esc(premise)}</textarea>
<div class="fr-meta"><p id="fr-hint" class="hint">Who is in it, and what do they want.</p><span class="count" id="premise-count">${premise.length}/4000</span></div>${err}
${priv ? `<label for="private-note" class="hint">Private note. The writer never sees it.</label><textarea id="private-note" data-form="private-note" rows="2">${esc(form('private-note', ''))}</textarea>` : btn('open-private', 'Add a private note', { cls: 'link' })}
<div class="fr-actions">${btn('fr-next', 'Continue', { cls: 'btn adopt' })}${HOME ? '<a class="link" href="/">See the sample on your shelf</a>' : btn('start-sample', 'Try the sample story', { cls: 'link' })}</div></section>`;
    }
    if (step === 2) {
      return `<section class="fr" data-step="2"><p class="sr" role="status">Step 2 of 3</p><h1>Where does it go?</h1>
<label class="sr" for="spine">The spine</label><textarea id="spine" data-form="spine" maxlength="4000" rows="5" placeholder="Grief becomes a search; the search becomes a choice..." aria-describedby="fr-hint">${esc(spine)}</textarea>
<div class="fr-meta"><p id="fr-hint" class="hint">The big turns, in your words.</p><span class="count" id="spine-count">${spine.length}/4000</span></div>${err}
<div class="fr-actions">${btn('fr-next', 'Continue', { cls: 'btn adopt' })}${btn('fr-back', 'Go back', { cls: 'link' })}</div></section>`;
    }
    const n = planCount();
    return `<section class="fr" data-step="3"><p class="sr" role="status">Step 3 of 3</p><h1>How many episodes?</h1>
<div class="stepper" role="group" aria-label="Number of episodes">${btn('count-dec', 'Ten fewer episodes', { cls: 'icon ten', html: '<span aria-hidden="true">-10</span>', extra: 'data-step="10" aria-label="Ten fewer episodes"', disabled: n <= 2 })}${btn('count-dec', 'Fewer episodes', { cls: 'icon', html: '<span aria-hidden="true">-</span>', extra: 'data-step="1"', disabled: n <= 2 })}<output id="count-out" aria-live="polite">${n}</output>${btn('count-inc', 'More episodes', { cls: 'icon', html: '<span aria-hidden="true">+</span>', extra: 'data-step="1"', disabled: n >= MAX_EPISODES })}${btn('count-inc', 'Ten more episodes', { cls: 'icon ten', html: '<span aria-hidden="true">+10</span>', extra: 'data-step="10" aria-label="Ten more episodes"', disabled: n >= MAX_EPISODES })}</div>
<p class="hint">${live() ? 'The live writer is connected. Drafting spends a few cents.' : 'Try it first. Nothing is sent, nothing is charged.'}</p>
<div class="seal"><p class="seal-text">${esc(premise)}</p><p class="seal-text spine">${esc(spine)}</p><div class="seal-row">${btn('adopt-first', 'Adopt this direction', { cls: 'btn adopt', html: `${ICON.bracket}<span>Adopt this direction</span>` })}<span class="consequence">Drafts will follow it.</span></div></div>${err}
<div class="fr-actions">${btn('fr-back', 'Go back', { cls: 'link' })}</div></section>`;
  }

  // ---------- views: plan ----------
  function planBase() {
    const head = S.directions.arc, gov = S.governing.arc;
    return head ? head.content : gov ? gov.content : { purpose: '', intentions: [], private_intentions: [] };
  }
  const planCountVal = () => (S.governing.arc ? Math.min(MAX_EPISODES, Math.max(cursor() || 1, Number(form('count', planBase().intentions.length || arcN())) || arcN())) : planCount());
  const lineVal = (i) => form('int' + i, (planBase().intentions || [])[i] || '');
  const lineNote = (i) => form('pint' + i, (planBase().private_intentions || [])[i] || '');
  function planChanged() {
    const gov = S.governing.arc;
    if (!gov) return true;
    const g = gov.content, n = planCountVal();
    if (n !== g.intentions.length) return true;
    if (form('purpose', planBase().purpose || '').trim() !== (g.purpose || '').trim()) return true;
    for (let i = 0; i < n; i += 1) {
      if (lineVal(i).trim() !== (g.intentions[i] || '').trim()) return true;
      if (lineNote(i).trim() !== ((g.private_intentions || [])[i] || '').trim()) return true;
    }
    const head = S.directions.arc;
    return Boolean(head && head.revision_id !== gov.revision_id);
  }
  function planPrimary() {
    if (!S.governing.skeleton) return null;
    if (!S.governing.arc || planChanged()) return { label: 'Adopt this plan', action: 'adopt-plan', cls: 'btn adopt', sentence: 'Drafts will follow this plan.' };
    const nu = nextUndrafted();
    if (nu) { const r = spendRun(); const k = Math.min(3, r ? r.max : 1); return { label: k > 1 ? `Draft next ${k}` : `Draft episode ${nu.ordinal}`, action: 'open-spend', cls: 'btn spend' }; }
    return null;
  }
  function directionHtml() { return directionCard() + stagedDirHtml(); }
  function directionCard() {
    const head = S.directions.skeleton, gov = S.governing.skeleton;
    const unused = head && gov && gov.revision_id !== head.revision_id;
    const base = head ? head.content : gov.content;
    const editing = sess.edit === 'direction';
    if (!editing) {
      return `<section class="card dir" data-adopted="yes"><header><h2>Direction</h2><span class="tag">adopted</span>${btn('edit-direction', 'Edit direction', { cls: 'plain' })}</header>
<dl class="kv" data-open="${Boolean(sess.dirOpen)}"><dt>Premise</dt><dd class="wrap">${esc(gov.content.premise)}</dd><dt>Spine</dt><dd class="wrap">${esc(gov.content.spine)}</dd>${gov.content.private ? `<dt>Private</dt><dd class="wrap">${esc(gov.content.private)}</dd>` : ''}</dl>
${(gov.content.premise + gov.content.spine + (gov.content.private || '')).length > 360 ? btn('toggle-dir', sess.dirOpen ? 'Show less' : 'Show all', { cls: 'plain', extra: `aria-expanded="${Boolean(sess.dirOpen)}"` }) : ''}
<p class="mono">Episodes: ${S.length.low} to ${S.length.high} words, aim ${S.length.target}. ${btn('nav-studio-length', 'Change', { cls: 'link' })}</p>
${unused ? `<p class="line-note">A newer saved direction is not adopted. ${btn('adopt-saved', 'Adopt saved direction', { cls: 'plain', extra: 'data-layer="skeleton"' })}</p>` : ''}</section>`;
    }
    return `<section class="card dir" data-adopted="no"><header><h2>Direction</h2><span class="tag open">editing</span></header>
<label for="premise">Premise</label><textarea id="premise" rows="3" data-form="premise" maxlength="4000">${esc(form('premise', base.premise || ''))}</textarea>
<label for="spine">Spine</label><textarea id="spine" rows="3" data-form="spine" maxlength="4000">${esc(form('spine', base.spine || ''))}</textarea>
<label for="private-note">Private note. The writer never sees it.</label><textarea id="private-note" rows="2" data-form="private-note">${esc(form('private-note', base.private || ''))}</textarea>
<div class="seal-row">${btn('adopt-direction', 'Adopt this direction', { cls: 'btn adopt', html: `${ICON.bracket}<span>Adopt this direction</span>` })}${btn('cancel-edit-direction', 'Cancel', { cls: 'plain' })}<span class="consequence">Drafts will follow this.</span></div></section>`;
  }
  function lineHtml(i, count) {
    const n = i + 1, e = ep(n);
    const locked = Boolean(e && e.accepted);
    const val = lineVal(i), pn = lineNote(i);
    const open = sess.lineNote[i] !== undefined ? sess.lineNote[i] : Boolean(pn);
    const st = e ? knotState(e) : 'planned';
    return `<li class="line${locked ? ' locked' : ''}" data-n="${n}"><span class="ln"><i class="kd" data-st="${st}"></i>${n}</span><div class="lf">
${locked ? `<p class="locked-text wrap">${esc(val)}</p>` : `<label class="sr" for="intention-${i}">Plan line for episode ${n}</label><textarea id="intention-${i}" rows="1" data-form="int${i}" data-line="${i}" placeholder="Type a line">${esc(val)}</textarea>`}
${locked ? '' : stagedLine(i)}
${open && !locked ? `<label for="pint-${i}" class="hint">Private note. The writer never sees it.</label><textarea id="pint-${i}" rows="1" data-form="pint${i}">${esc(pn)}</textarea>` : ''}</div>
<div class="la">${locked ? `<span class="lockmark" title="Approved and locked">${ICON.lock}<span class="sr">Approved and locked</span></span>` : `<button type="button" class="keybtn" data-action="toggle-line-note" data-line="${i}" aria-pressed="${open}" data-filled="${Boolean(pn)}" aria-label="Private note for episode ${n}">${ICON.key}</button>`}</div></li>`;
  }
  const lockedRun = () => { let k = 0; while (ep(k + 1) && ep(k + 1).accepted) k += 1; return k; };
  function planHtml() {
    const base = planBase();
    const count = planCountVal();
    const head = S.directions.arc, gov = S.governing.arc;
    const unused = head && gov && gov.revision_id !== head.revision_id;
    let paste = '';
    if (sess.paste) {
      const p = sess.paste;
      const end = Math.min(MAX_EPISODES, p.from + p.lines.length);
      paste = `<div class="pastebar" role="group" aria-label="Paste preview"><p>Fill lines ${p.from + 1} to ${end} with ${plural(Math.min(p.lines.length, end - p.from), 'line')}?</p><div>${btn('paste-fill', 'Fill lines', { cls: 'btn tonal' })}${btn('paste-cancel', 'Cancel', { cls: 'plain' })}</div></div>`;
    }
    const stepper = sess.countOpen ? `<span class="stepper small" role="group" aria-label="Number of episodes">${btn('plan-dec', 'Ten fewer episodes', { cls: 'icon ten', html: '<span aria-hidden="true">-10</span>', extra: 'data-step="10" aria-label="Ten fewer episodes"', disabled: count <= Math.max(2, cursor()) })}${btn('plan-dec', 'Fewer episodes', { cls: 'icon', html: '<span aria-hidden="true">-</span>', extra: 'data-step="1"', disabled: count <= Math.max(2, cursor()) })}<output>${count}</output>${btn('plan-inc', 'More episodes', { cls: 'icon', html: '<span aria-hidden="true">+</span>', extra: 'data-step="1"', disabled: count >= MAX_EPISODES })}${btn('plan-inc', 'Ten more episodes', { cls: 'icon ten', html: '<span aria-hidden="true">+10</span>', extra: 'data-step="10" aria-label="Ten more episodes"', disabled: count >= MAX_EPISODES })}</span>` : '';
    return `<div class="plan"><h1 class="sr">Plan</h1>${directionHtml()}
<section class="purpose"><label for="purpose">Purpose of this stretch</label><textarea id="purpose" rows="2" data-form="purpose">${esc(form('purpose', base.purpose || ''))}</textarea>${stagedPurpose()}</section>
<div class="plan-head"><h2>Episodes</h2><button type="button" class="chipbtn" data-action="toggle-count" aria-expanded="${Boolean(sess.countOpen)}">${count} episodes</button>${stepper}${count > 10 ? '<label class="sr" for="plan-jump">Go to episode number</label><input id="plan-jump" class="jump-n" type="number" inputmode="numeric" min="1" max="' + count + '" placeholder="Go to #" autocomplete="off">' : ''}</div>
${unused ? `<p class="line-note">A newer saved plan is not adopted. ${btn('adopt-saved', 'Adopt saved plan', { cls: 'plain', extra: 'data-layer="arc"' })}</p>` : ''}${paste}
<ol class="lines">${(() => {
      const run = Math.min(lockedRun(), count);
      const row = (i) => lineHtml(i, count);
      if (run < 3) return Array.from({ length: count }, (_, i) => row(i)).join('');
      const folded = `<li class="lgroup"><details id="lockgroup"${sess.lockOpen ? ' open' : ''}><summary>Episodes 1 to ${run} are approved</summary><ol class="lines">${Array.from({ length: run }, (_, i) => row(i)).join('')}</ol></details></li>`;
      return folded + Array.from({ length: count - run }, (_, i) => row(run + i)).join('');
    })()}</ol>
${(base.intentions || []).filter((t) => t && t.trim()).length < 2 ? '<p class="fine">Paste a list into any line to fill the lines below it.</p>' : ''}</div>`;
  }

  // ---------- views: write ----------
  function proseHtml(text, hits) {
    if (!hits || !hits.length) return rich(text);
    const re = new RegExp('(' + hits.map((h) => h.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|') + ')', 'gi');
    return text.split(re).map((seg, i) => (i % 2 ? `<mark class="nu">${esc(seg)}</mark>` : rich(seg))).join('');
  }
  function wordDiff(oldText, newText) {
    const a = oldText.split(/\s+/).filter(Boolean), b = newText.split(/(\s+)/);
    const bw = b.map((t, i) => [t, i]).filter(([t]) => t.trim());
    const dp = Array.from({ length: a.length + 1 }, () => new Array(bw.length + 1).fill(0));
    for (let i = a.length - 1; i >= 0; i -= 1) for (let j = bw.length - 1; j >= 0; j -= 1) dp[i][j] = a[i] === bw[j][0] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
    const same = new Set();
    let i = 0, j = 0;
    while (i < a.length && j < bw.length) { if (a[i] === bw[j][0]) { same.add(bw[j][1]); i += 1; j += 1; } else if (dp[i + 1][j] >= dp[i][j + 1]) i += 1; else j += 1; }
    return b.map((t, idx) => (!t.trim() || same.has(idx) ? esc(t) : `<u>${esc(t)}</u>`)).join('');
  }
  function paragraphHtml(e, b, i) {
    const n = i + 1;
    const edit = ui.edits[b.block_id];
    const kept = ui.kept[b.block_id];
    const cand = S.candidates.find((c) => c.ordinal === e.ordinal && c.block_id === b.block_id && !sess.dismissed.includes(c.candidate_id));
    const stale = edit && edit.base !== b.sha256;
    let body;
    if (edit && !e.accepted) {
      body = `<label class="sr" for="edit-${i}">Edit paragraph ${n}</label><textarea id="edit-${i}" class="prose-edit" data-edit="${esc(b.block_id)}">${esc(edit.text)}</textarea>
${stale ? `<p class="warn-line">This paragraph changed after you began editing.</p><div class="compare one"><div><span class="mono">Saved now</span><p>${esc(b.text)}</p></div></div>` : ''}
<div class="erow">${btn('save-para', stale ? 'Keep editing on the new text' : 'Save edit', { cls: 'btn tonal', extra: `data-block="${esc(b.block_id)}"` })}${btn('cancel-edit', 'Cancel', { cls: 'plain', extra: `data-block="${esc(b.block_id)}"` })}<span class="mono hint-keys">Esc cancels. Ctrl Enter saves.</span></div>`;
    } else {
      body = `<p lang="en">${proseHtml(b.text, e.style_hits)}</p>`;
      if (sess.suggesting === b.block_id) body += `<div class="ask-row">${sess.call && sess.call.block === b.block_id ? statusHtml('reasoning', 'sm', sess.call.text) : ''}<label for="reason-${i}">What should change?</label><input id="reason-${i}" data-form="reason" value="${esc(form('reason', 'tighten the rhythm'))}"><div>${btn('get-suggestion', 'Get better wording', { cls: 'btn tonal', extra: `data-block="${esc(b.block_id)}" data-sha="${esc(b.sha256)}"` })}${btn('cancel-suggest', 'Cancel', { cls: 'plain' })}</div></div>`;
    }
    if (cand && !edit) {
      body += `<div class="cand"><p class="mono">Wording only. The story does not change.</p><div class="compare"><div><span class="mono">Now</span><p>${esc(b.text)}</p></div><div><span class="mono">New</span><p>${wordDiff(b.text, cand.replacement)}</p></div></div><div class="erow">${btn('apply-candidate', 'Use this wording', { cls: 'btn tonal', extra: `data-cand="${esc(cand.candidate_id)}"` })}${btn('dismiss-candidate', 'Keep mine', { cls: 'plain', extra: `data-cand="${esc(cand.candidate_id)}"` })}</div></div>`;
    }
    if (!edit && !e.accepted) body += stagedPara(b);
    const tools = e.accepted ? '' : `<div class="ptools" role="group" aria-label="Paragraph ${n} tools">${btn('edit-para', 'Edit', { cls: 'tool', html: ICON.pencil, extra: `data-block="${esc(b.block_id)}" title="Edit" aria-label="Edit paragraph ${n}"` })}${btn('suggest-para', 'Better wording', { cls: 'tool', html: ICON.wand, extra: `data-block="${esc(b.block_id)}" title="Better wording" aria-label="Better wording for paragraph ${n}"` })}${btn('ask-para', 'Ask', { cls: 'tool', html: ICON.chat, extra: `data-block="${esc(b.block_id)}" title="Ask about this" aria-label="Ask about paragraph ${n}"` })}</div>`;
    void kept;
    return `<div class="para${sess.sel === b.block_id ? ' sel' : ''}${edit && !e.accepted ? ' editing' : ''}" data-block="${esc(b.block_id)}" id="para-${e.ordinal}-${n}" tabindex="0" aria-label="Paragraph ${n}">${tools}${body}</div>`;
  }
  function gaugeHtml(e) {
    const [lo, , hi] = S.word_band || [550, 700, 900];
    const pos = Math.max(0, Math.min(1, (e.words - lo) / (hi - lo)));
    const where = e.words < lo ? 'under' : e.words > hi ? 'over' : 'in';
    return `<span class="gauge" role="img" aria-label="${e.words} words. This series is written to ${lo} to ${hi} words." data-where="${where}" data-pos="${pos.toFixed(3)}" tabindex="0" title="${e.words} of ${lo} to ${hi}"><i></i></span>`;
  }
  function writingHtml(e) {
    const active = pending && eps().find((x) => x.ordinal >= pending.first && x.ordinal <= pending.last && !x.selection);
    const mine = active && active.ordinal === e.ordinal;
    const total = pending ? pending.last - pending.first + 1 : 1;
    const lead = mine ? `<div class="orbrow">${orbHtml('working', 'lg')}<div><p class="wmsg" role="status">Writing episode ${e.ordinal}${total > 1 ? `, ${e.ordinal - pending.first + 1} of ${total}` : ''}</p><p class="mono">Elapsed <span class="timer" data-timer>0:00</span></p></div></div>` : '<p class="wmsg">Waiting for the earlier episode.</p>';
    return `<div class="writing" data-active="${mine}">${lead}
<p class="mono">Usually 30 to 45 seconds. You can leave this page.</p><p class="mono slow" data-slow hidden>Taking longer than usual. Still working.</p>
<div class="ghostlines" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i></div></div>`;
  }
  function pageHtml() {
    const e = currentEp();
    if (!e) return `<div class="empty"><h1>No episodes yet</h1>${btn('go-plan', 'Plan the episodes', { cls: 'btn adopt' })}</div>`;
    const n = e.ordinal;
    const savedEp = e.accepted && e.memory_state === 'read';
    const factN = S.memory.accepted.filter((c) => c.narrative_ordinal === n).length;
    const states = e.accepted ? `<span class="state" data-s="approved">${GLYPH.seal}Approved</span>${savedEp ? `<span class="state" data-s="saved">${GLYPH.thread}Saved to memory (${factN})</span>` : '<span class="state" data-s="waiting"><i class="wdot"></i>Facts waiting</span>'}` : '';
    const head = `<header class="ph"><div class="ptitle"><h1>Episode ${n}${e.title ? ` · ${esc(e.title)}` : ''}</h1>${btn('toggle-reading', sess.reading ? 'Leave focus reading' : 'Focus on reading', { cls: 'tool', html: ICON.read, extra: `aria-pressed="${Boolean(sess.reading)}" title="Focus on reading"` })}${btn('episode-menu', 'Episode options', { cls: 'tool', html: ICON.dots, extra: 'aria-haspopup="dialog" title="Episode options"' })}</div>${states ? `<div class="eno">${states}</div>` : ''}${e.selection && intention(n) ? `<p class="isub wrap">${esc(stripListMark(intention(n)))}</p>` : ''}</header>`;
    if (!e.selection) {
      const inRange = pending && n >= pending.first && n <= pending.last;
      const aside = !inRange && e.alternatives.length ? e.alternatives[e.alternatives.length - 1] : null;
      if (aside) return `<article class="page" data-st="aside" id="page">${head}<p class="planline wrap">${esc(intention(n))}</p>${asideHtml(e, aside)}</article>`;
      return `<article class="page" data-st="planned" id="page">${head}${inRange ? writingHtml(e) : `<p class="planline wrap">${esc(intention(n))}</p><p class="mono">Not drafted yet.</p>`}</article>`;
    }
    const lines = [];
    if (sess.fromMem && sess.fromMem.ep === n) {
      const f = S.memory.accepted.find((x) => x.claim_id === sess.fromMem.claim);
      lines.push(`<div class="pnote memback"><p>From Memory${f ? ': ' + esc(headline(f)) : ''}</p><div class="erow">${btn('back-memory', 'Back to the fact', { cls: 'link' })}${btn('dismiss-memback', 'Dismiss', { cls: 'link' })}</div></div>`);
    }
    if (e.open_impacts > 0 && !e.accepted) {
      const up = upstreamChange(n);
      lines.push(`<p class="pnote warn">Episode ${n} may no longer fit. ${up ? `Episode ${up} changed. ${btn('nav-ep', `Read the change in episode ${up}`, { cls: 'link', extra: `data-ep="${up}"` })}` : 'An earlier episode changed.'}</p>`);
    }
    const keptHere = e.blocks.filter((b) => ui.kept[b.block_id]);
    if (keptHere.length) {
      const b = keptHere[0], i = e.blocks.indexOf(b);
      lines.push(`<div class="pnote"><p>We kept your unsaved edit to paragraph ${i + 1}. Restore it or discard it.</p><div class="erow">${btn('restore-kept', 'Restore edit', { cls: 'btn tonal', extra: `data-block="${esc(b.block_id)}"` })}${btn('discard-kept', 'Discard edit', { cls: 'plain', extra: `data-block="${esc(b.block_id)}"` })}</div></div>`);
    }
    if (e.accepted) {
      const stray = e.blocks.filter((b) => ui.edits[b.block_id] && ui.edits[b.block_id].text !== b.text);
      if (stray.length) lines.push(`<div class="pnote warn"><p>An unsaved edit is not part of the approved words. It is kept on this device only.</p><div class="erow">${btn('discard-edits', 'Discard unsaved edit', { cls: 'plain' })}</div></div>`);
    }
    if (e.secret_hits.length) lines.push(`<p class="pnote bad">A secret is in this text: ${esc(e.secret_hits.join(', '))}.</p>`);
    if (e.style_hits.length) lines.push(`<p class="pnote">${plural(e.style_hits.length, 'word')} from your never-use list. ${btn('show-hit', 'Show me', { cls: 'link' })}</p>`);
    if (e.length_warning) lines.push(`<p class="pnote">Outside this series' range of ${S.length.low} to ${S.length.high} words.</p>`);
    if (!e.accepted && e.new_names && e.new_names.length) lines.push(`<p class="pnote">New names in this draft: ${esc(e.new_names.slice(0, 8).join(', '))}${e.new_names.length > 8 ? ` and ${e.new_names.length - 8} more` : ''}. Check they fit your story.</p>`);
    if (note) lines.push(`<p class="pnote" id="noteline">${esc(note.text)} ${note.eventId && canUndoId(note.eventId) ? btn('undo', 'Undo', { cls: 'link', extra: `data-event="${esc(note.eventId)}"` }) : ''}</p>`);
    const origin = `${originOf(e)} · ${words(e)}`;
    return `<article class="page${e.accepted ? ' locked' : ''}" data-st="${e.accepted ? 'approved' : 'drafted'}"${savedEp ? ' data-saved="yes"' : ''} id="page">${head}${lines.join('')}
<div class="prose">${e.blocks.map((b, i) => paragraphHtml(e, b, i)).join('')}</div>
<footer class="pf"><span class="mono">${esc(origin)}</span>${gaugeHtml(e)}</footer>${sess.fin === n ? finishPanel(n) : ''}</article>`;
  }
  const words = (e) => plural(e.words, 'word');
  function asideHtml(e, alt) {
    const limit = S.word_limit || 1080;
    const why = alt.detached_reason === 'over_length' ? (alt.words <= limit ? `This draft ran to ${alt.words} words. It was set aside under an earlier, stricter limit. It is inside the current limit of ${limit}.` : `This draft ran to ${alt.words} words. The limit is ${limit}, so it was set aside and not used.`)
      : alt.detached_reason === 'incomplete' ? 'The writer stopped part way, so this draft was set aside and not used.' : 'This draft was set aside and not used.';
    const paras = String(alt.text).split(/\n{2,}/).filter((x) => x.trim());
    return `<p class="pnote warn">${esc(why)} It is yours to read. If you use it, you can trim it like any draft.</p>
<div class="erow">${btn('use-draft', 'Use this draft', { cls: 'btn tonal', extra: `data-ordinal="${e.ordinal}" data-rev="${esc(alt.revision_id)}"` })}</div>
<div class="prose aside" aria-label="Set-aside draft">${paras.map((x, i) => `<div class="para" id="aside-${e.ordinal}-${i + 1}"><p lang="en">${esc(x)}</p></div>`).join('')}</div>
<footer class="pf"><span class="mono">Set aside · ${plural(alt.words, 'word')}</span></footer>`;
  }
  function upstreamChange(n) {
    const h = (S.history || []).find((x) => ['save', 'rewrite_apply', 'redo'].includes(x.action) && !x.undone && (() => { const q = epByArtifact(x.artifact_id); return q && q.ordinal < n; })());
    return h ? epByArtifact(h.artifact_id).ordinal : 0;
  }
  const epByArtifact = (id) => S.episodes.find((e) => e.artifact_id === id);
  function canUndo(h) { const e = epByArtifact(h.artifact_id); return !!e && !e.accepted && ['save', 'rewrite_apply', 'redo'].includes(h.action) && !h.undone; }
  function canRedo(h) { const e = epByArtifact(h.artifact_id); return !!e && !e.accepted && ['save', 'rewrite_apply'].includes(h.action) && h.undone && !S.history.some((x) => x.action === 'redo' && x.revert_of === h.event_id); }
  function canUndoId(id) { const h = S.history.find((x) => x.event_id === id); return !!h && canUndo(h); }

  // ---------- views: memory ----------
  const normName = (s) => String(s || '').toLowerCase().replace(/^(the|a|an)\s+/, '').replace(/[^\p{L}\p{N}\s'-]/gu, '').trim();
  const capFirst = (s) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : s);
  const memo = { src: null, people: [], of: new Map() };
  function buildPeople() {
    const claims = S.memory.accepted;
    if (memo.src === claims) return memo;
    const raws = new Map();
    claims.forEach((c) => { const p = c.speaker || c.holder; if (p) { const k = normName(p); if (!k) return; const m = raws.get(k) || new Map(); const r = p.trim().replace(/^(the|a|an)\s+/i, ''); m.set(r, (m.get(r) || 0) + 1); raws.set(k, m); } });
    const names = [...raws.keys()].sort((a, b) => b.length - a.length);
    const res = names.map((k) => [k, new RegExp('(^|[^\\p{L}\\p{N}])' + k.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '(?![\\p{L}\\p{N}])', 'iu')]);
    const of = new Map();
    const counts = new Map();
    claims.forEach((c) => {
      let k = normName(c.speaker || c.holder);
      if (!k) { const hit = res.find(([, re]) => re.test(c.subject || '')); k = hit ? hit[0] : '_story'; }
      of.set(c.claim_id, k);
      counts.set(k, (counts.get(k) || 0) + 1);
    });
    const people = [...counts.entries()].map(([k, v]) => {
      const m = raws.get(k);
      const label = k === '_story' ? 'The story' : capFirst(m ? [...m.entries()].sort((a, b) => b[1] - a[1])[0][0] : k);
      return { key: k, label, count: v };
    }).sort((a, b) => (a.key === '_story') - (b.key === '_story') || b.count - a.count || a.label.localeCompare(b.label));
    memo.src = claims; memo.people = people; memo.of = of; memo.res = res;
    return memo;
  }
  const personSlug = (k) => encodeURIComponent(k);
  const STOPWORDS = new Set(['a', 'an', 'the', 'to', 'of', 'my', 'me', 'i', 'is', 'it', 'in', 'on', 'for', 'and', 'or', 'do', 'did', 'does', 'what', 'who', 'how', 'about', 'that', 'this', 'with']);
  function tokens(q) { return String(q || '').toLowerCase().split(/[^\p{L}\p{N}]+/u).filter((t) => t && !STOPWORDS.has(t)); }
  function matched(hay, toks) {
    let n = 0;
    toks.forEach((t) => { const stem = t.length > 4 ? t.slice(0, t.length - 1) : t; if (hay.includes(t) || (t.length > 3 && hay.includes(stem)) || (t === 'say' && hay.includes('said')) || (t === 'says' && hay.includes('said'))) n += 1; });
    return n;
  }
  const headline = (c) => (c.prior_claim_id && c.note ? c.note : c.subject || c.quote);
  function memFiltered() {
    const { of } = buildPeople();
    const toks = tokens(mem.q);
    const need = toks.length ? Math.max(1, Math.ceil(toks.length * 0.6)) : 0;
    const out = [];
    S.memory.accepted.forEach((c) => {
      if (route.person && route.person !== 'all' && of.get(c.claim_id) !== route.person) return;
      if (mem.kind !== 'all' && c.kind !== mem.kind) return;
      if (mem.eps.size && !mem.eps.has(c.narrative_ordinal)) return;
      let score = 0;
      if (toks.length) {
        const hay = (headline(c) + ' ' + (c.subject || '') + ' ' + c.quote + ' ' + (c.speaker || '') + ' ' + (c.holder || '') + ' ' + (KIND_LABEL[c.kind] || '')).toLowerCase();
        score = matched(hay, toks);
        if (score < need) return;
      }
      out.push([c, score]);
    });
    if (toks.length) out.sort((a, b) => b[1] - a[1] || a[0].narrative_ordinal - b[0].narrative_ordinal);
    return out.map((x) => x[0]);
  }
  function factRow(c) {
    const said = c.kind === 'testimony' || c.kind === 'belief';
    const who = c.speaker || c.holder || '';
    const text = headline(c);
    const selected = mem.sel === c.claim_id;
    const inner = said
      ? `<span class="fwho">${esc(who ? capFirst(who) : 'Someone')} ${c.kind === 'belief' ? 'believes' : 'said'}</span><q class="fq">${esc(text)}</q>`
      : `<span class="ftxt">${esc(text)}</span>`;
    const glyph = said ? '<i class="truth" data-v="said" aria-hidden="true"></i>' : `<i class="truth" data-v="${c.world_validity === 'true_in_story' ? 'true' : c.world_validity === 'false_in_story' ? 'false' : 'unknown'}" aria-hidden="true"></i>`;
    const aria = `${said ? (c.kind === 'belief' ? 'Believed, not fact. ' : 'Said, not fact. ') : VALID[c.world_validity] + '. '}${text}. Episode ${c.narrative_ordinal}.`;
    return `<li><button type="button" class="fact" data-k="${said ? 'said' : 'plain'}" data-claim="${esc(c.claim_id)}" aria-pressed="${selected}" aria-label="${esc(aria)}">${glyph}<span class="fbody">${inner}</span><span class="fmeta"><span class="kind">${esc(KIND_LABEL[c.kind] || c.kind)}</span>${c.prior_claim_id ? '<span class="kind corr">corrected</span>' : ''}</span></button></li>`;
  }
  function sourceHtml() {
    const c = mem.sel ? S.memory.accepted.find((x) => x.claim_id === mem.sel) : null;
    if (!c) return '<div class="src-empty"><p class="hint">Pick a fact to see where it came from.</p></div>';
    const e = ep(c.narrative_ordinal);
    const bi = e ? e.blocks.findIndex((b) => b.block_id === c.block_id) : -1;
    const block = bi >= 0 ? e.blocks[bi] : null;
    let para = '';
    if (block) {
      const idx = block.text.indexOf(c.quote);
      para = idx >= 0 ? `${rich(block.text.slice(0, idx))}<mark class="src">${esc(c.quote)}</mark>${rich(block.text.slice(idx + c.quote.length))}` : `<mark class="src">${esc(c.quote)}</mark>`;
    } else para = `<mark class="src">${esc(c.quote)}</mark>`;
    const said = c.kind === 'testimony' || c.kind === 'belief';
    const corrected = c.prior_claim_id && c.note;
    const form1 = mem.correcting === c.claim_id ? `<div class="correct"><label for="corr-text">What should it say?</label><textarea id="corr-text" rows="3" data-form="corr_text">${esc(form('corr_text', headline(c)))}</textarea>
<div class="two"><div><label for="corr-kind">Kind</label><select id="corr-kind" data-form="corr_kind">${KIND_TABS.filter(([k]) => k !== 'all' && k !== 'relationship').map(([k, l]) => `<option value="${k}"${form('corr_kind', c.kind) === k ? ' selected' : ''}>${l}</option>`).join('')}</select></div>
<div><label for="corr-valid">In the story</label><select id="corr-valid" data-form="corr_valid">${Object.entries(VALID).map(([k, l]) => `<option value="${k}"${form('corr_valid', c.world_validity) === k ? ' selected' : ''}>${l}</option>`).join('')}</select></div></div>
<label for="corr-speaker">Who says or believes it (if a person)</label><input id="corr-speaker" data-form="corr_speaker" value="${esc(form('corr_speaker', c.speaker || ''))}">
<div class="erow">${btn('save-correction', 'Save correction', { cls: 'btn tonal', extra: `data-claim="${esc(c.claim_id)}"` })}${btn('cancel-correction', 'Cancel', { cls: 'plain' })}</div><p class="mono">The original stays on record.</p></div>` : '';
    return `<div class="src"><div class="src-head"><h2 id="src-title" tabindex="-1">Source</h2>${btn('close-source', 'Close', { cls: 'closebtn src-close', html: CLOSE_SVG + '<span>Close</span>' })}</div>
<p class="mono">Ep ${c.narrative_ordinal}${bi >= 0 ? ' · ¶' + (bi + 1) : ''} · ${esc(KIND_LABEL[c.kind] || c.kind)}</p>
<p class="src-statement${said ? ' said' : ''}">${said ? '&ldquo;' + esc(headline(c)) + '&rdquo;' : esc(headline(c))}</p>
${corrected ? `<p class="mono">Corrected. Was: ${esc(c.subject)}</p>` : ''}
<p class="mono">${said ? 'Whether it is true: ' : 'In the story: '}${esc(VALID[c.world_validity] || c.world_validity)}</p>
<div class="erow">${btn('go-paragraph', 'Go to paragraph', { cls: 'btn tonal', extra: `data-ep="${c.narrative_ordinal}" data-block="${esc(c.block_id)}" data-claim="${esc(c.claim_id)}"` })}${mem.correcting ? '' : btn('correct-memory', 'Correct this', { cls: 'plain', extra: `data-claim="${esc(c.claim_id)}"` })}</div>${form1}
<blockquote class="src-quote">${para}</blockquote></div>`;
  }
  const GW = 640, GH = 420;
  const nodeR = (n) => 16 + Math.min(18, Math.sqrt(n) * 2.6);
  function layoutGraph(nodes, edges) {
    const n = nodes.length;
    const maxN = Math.max(1, ...edges.map((e) => e.n));
    const P = nodes.map((p, i) => { const a = (2 * Math.PI * i) / n - Math.PI / 2; return { k: p.key, r: nodeR(p.count), x: GW / 2 + Math.cos(a) * GW * 0.27, y: GH / 2 + Math.sin(a) * GH * 0.27, vx: 0, vy: 0 }; });
    const ix = new Map(P.map((p, i) => [p.k, i]));
    for (let it = 0; it < 400; it += 1) {
      const cool = 1 - it / 400;
      for (let i = 0; i < n; i += 1) for (let k = i + 1; k < n; k += 1) {
        let dx = P[k].x - P[i].x, dy = P[k].y - P[i].y; const d = Math.hypot(dx, dy) || 0.01;
        dx /= d; dy /= d;
        const min = P[i].r + P[k].r + 50;
        const f = 9000 / (d * d) + (d < min ? (min - d) * 0.6 : 0);
        P[i].vx -= dx * f; P[i].vy -= dy * f; P[k].vx += dx * f; P[k].vy += dy * f;
      }
      edges.forEach((e) => {
        const A = P[ix.get(e.a)], B = P[ix.get(e.b)];
        let dx = B.x - A.x, dy = B.y - A.y; const d = Math.hypot(dx, dy) || 0.01;
        dx /= d; dy /= d;
        const ideal = 230 - 120 * (e.n / maxN);
        const f = (d - ideal) * 0.03 * (0.4 + e.n / maxN);
        A.vx += dx * f; A.vy += dy * f; B.vx -= dx * f; B.vy -= dy * f;
      });
      P.forEach((p) => {
        p.vx += (GW / 2 - p.x) * 0.006; p.vy += (GH / 2 - p.y) * 0.006;
        p.x += Math.max(-18, Math.min(18, p.vx * cool)); p.y += Math.max(-18, Math.min(18, p.vy * cool));
        p.vx *= 0.55; p.vy *= 0.55;
        p.x = Math.max(70, Math.min(GW - 70, p.x)); p.y = Math.max(44, Math.min(GH - 52, p.y));
      });
    }
    return P;
  }
  function graphModel() {
    const bp = buildPeople();
    const sig = [...mem.eps].sort((a, b) => a - b).join(',');
    if (memo.gm && memo.gm.src === bp.src && memo.gm.sig === sig) return memo.gm;
    const claims = S.memory.accepted.filter((c) => !mem.eps.size || mem.eps.has(c.narrative_ordinal));
    const label = new Map(bp.people.filter((p) => p.key !== '_story').map((p) => [p.key, p.label]));
    const own = new Map();
    claims.forEach((c) => { const k = bp.of.get(c.claim_id); if (label.has(k)) own.set(k, (own.get(k) || 0) + 1); });
    const pairs = new Map();
    claims.forEach((c) => {
      const keys = new Set();
      const k0 = bp.of.get(c.claim_id); if (label.has(k0)) keys.add(k0);
      [c.speaker, c.holder].forEach((w) => { const k = normName(w || ''); if (label.has(k)) keys.add(k); });
      const text = [c.subject, c.quote, c.note].filter(Boolean).join(' ');
      (bp.res || []).forEach(([k, re]) => { if (label.has(k) && re.test(text)) keys.add(k); });
      const ks = [...keys].sort();
      for (let i = 0; i < ks.length; i += 1) for (let x = i + 1; x < ks.length; x += 1) {
        const id = ks[i] + '|' + ks[x];
        const e = pairs.get(id) || { a: ks[i], b: ks[x], claims: [] };
        e.claims.push(c); pairs.set(id, e);
      }
    });
    let edges = [...pairs.values()].map((e) => ({ ...e, n: e.claims.length })).sort((a, b) => b.n - a.n);
    const linked = new Set(); edges.forEach((e) => { linked.add(e.a); linked.add(e.b); });
    const ranked = [...linked].map((k) => ({ key: k, label: label.get(k), count: own.get(k) || 0 })).sort((a, b) => b.count - a.count || a.label.localeCompare(b.label));
    const nodes = ranked.slice(0, 14);
    const keep = new Set(nodes.map((p) => p.key));
    edges = edges.filter((e) => keep.has(e.a) && keep.has(e.b));
    if (edges.length > 45) edges = edges.filter((e) => e.n > 1);
    const others = [...own.entries()].filter(([k]) => !keep.has(k)).map(([k, n]) => ({ label: label.get(k), n })).sort((a, b) => b.n - a.n);
    const pos = nodes.length ? layoutGraph(nodes, edges) : [];
    pos.forEach((p, i) => { nodes[i].x = p.x; nodes[i].y = p.y; nodes[i].r = p.r; });
    memo.gm = { src: bp.src, sig, nodes, edges, others, byKey: new Map(nodes.map((p) => [p.key, p])), maxN: Math.max(1, ...edges.map((e) => e.n)) };
    return memo.gm;
  }
  function graphHtml() {
    const m = graphModel();
    if (m.nodes.length < 2) return `<div class="empty small"><p class="hint">${mem.eps.size ? 'No two people are named together in the episodes you picked.' : 'Connections appear once at least two people share a fact. Save a few episodes first.'}</p></div>`;
    const gs = mem.gsel;
    const pairSel = gs && gs.b ? m.edges.find((e) => e.a === gs.a && e.b === gs.b) : null;
    const g = gs && m.byKey.has(gs.a) && (!gs.b || pairSel) ? gs : null;
    const near = new Set();
    if (g && !g.b) m.edges.forEach((e) => { if (e.a === g.a) near.add(e.b); if (e.b === g.a) near.add(e.a); });
    const edgeOn = (e) => Boolean(g) && (g.b ? e.a === g.a && e.b === g.b : e.a === g.a || e.b === g.a);
    const nodeOn = (k) => Boolean(g) && (k === g.a || k === g.b || near.has(k));
    const at = (k) => m.byKey.get(k);
    const lines = m.edges.map((e) => {
      const A = at(e.a), B = at(e.b);
      return `<line class="mlink${edgeOn(e) ? ' on' : g ? ' dim' : ''}" x1="${A.x.toFixed(1)}" y1="${A.y.toFixed(1)}" x2="${B.x.toFixed(1)}" y2="${B.y.toFixed(1)}" stroke-opacity="${(0.3 + 0.55 * e.n / m.maxN).toFixed(2)}" stroke-width="${(1 + 2.6 * e.n / m.maxN).toFixed(1)}"/>`;
    }).join('');
    const hits = m.edges.map((e) => {
      const A = at(e.a), B = at(e.b);
      return `<line class="mhit" x1="${A.x.toFixed(1)}" y1="${A.y.toFixed(1)}" x2="${B.x.toFixed(1)}" y2="${B.y.toFixed(1)}" data-action="g-edge" data-a="${esc(e.a)}" data-b="${esc(e.b)}"><title>${esc(A.label)} and ${esc(B.label)}: ${plural(e.n, 'fact')}</title></line>`;
    }).join('');
    const counts = m.edges.filter(edgeOn).map((e) => { const A = at(e.a), B = at(e.b); return `<text class="mcount" x="${((A.x + B.x) / 2).toFixed(1)}" y="${((A.y + B.y) / 2 + 4).toFixed(1)}" text-anchor="middle">${e.n}</text>`; }).join('');
    const dots = m.nodes.map((p) => {
      const deg = m.edges.filter((e) => e.a === p.key || e.b === p.key).length;
      const sel = Boolean(g) && (p.key === g.a || p.key === g.b);
      const short = p.label.length > 16 ? p.label.slice(0, 15) + '\u2026' : p.label;
      return `<g class="mnode${sel ? ' sel' : ''}${g && !nodeOn(p.key) ? ' dim' : ''}" data-action="g-node" data-key="${esc(p.key)}" tabindex="0" role="button" aria-pressed="${sel}" aria-label="${esc(p.label)}, ${plural(p.count, 'fact')}, connected to ${deg} ${deg === 1 ? 'person' : 'people'}"><title>${esc(p.label)}</title><circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="${p.r.toFixed(1)}"/><text class="mnum" x="${p.x.toFixed(1)}" y="${(p.y + 4).toFixed(1)}" text-anchor="middle">${p.count}</text><text class="mname" x="${p.x.toFixed(1)}" y="${(p.y + p.r + 15).toFixed(1)}" text-anchor="middle">${esc(short)}</text></g>`;
    }).join('');
    const connRow = (e, from) => {
      const text = from ? at(e.a === from ? e.b : e.a).label : at(e.a).label + ' and ' + at(e.b).label;
      return `<li><button type="button" class="connrow" data-action="g-edge" data-a="${esc(e.a)}" data-b="${esc(e.b)}"><span>${esc(text)}</span><span class="num">${plural(e.n, 'fact')} together</span></button></li>`;
    };
    let detail;
    if (!g) {
      detail = `<p class="hint">Tap a person to see who they are connected to. Tap a line to see the facts those two share. A line means both are named in the same fact or in the sentence it came from. A thicker line means more shared facts.</p><h3>Strongest connections</h3><ul class="rows tight conn">${m.edges.slice(0, 10).map((e) => connRow(e)).join('')}</ul>`;
    } else if (!g.b) {
      const p = at(g.a);
      const mine = m.edges.filter((e) => e.a === g.a || e.b === g.a);
      detail = `<div class="gdetail"><div class="ghead"><h3 tabindex="-1">${esc(p.label)}</h3><span class="mono">${plural(p.count, 'fact')}</span></div><div class="erow">${btn('g-open', 'Show all of ' + p.label + '\u2019s facts', { cls: 'btn tonal', extra: `data-key="${esc(p.key)}"` })}${btn('g-clear', 'Clear', { cls: 'plain' })}</div>${mine.length ? `<ul class="rows tight conn">${mine.map((e) => connRow(e, g.a)).join('')}</ul>` : '<p class="hint">No one else is named in their facts yet.</p>'}</div>`;
    } else {
      const A = at(g.a), B = at(g.b);
      const list = pairSel.claims.slice().sort((x, y) => x.narrative_ordinal - y.narrative_ordinal);
      let rows = '', last = 0;
      list.slice(0, 24).forEach((c) => { if (c.narrative_ordinal !== last) { last = c.narrative_ordinal; rows += `<li class="eh"><span>Episode ${last}</span></li>`; } rows += factRow(c); });
      detail = `<div class="gdetail"><div class="ghead"><h3 tabindex="-1">${esc(A.label)} and ${esc(B.label)}</h3><span class="mono">${plural(list.length, 'fact')} name both</span></div><div class="erow">${btn('g-back', 'Back to ' + A.label, { cls: 'plain' })}${btn('g-clear', 'Clear', { cls: 'plain' })}</div><ul class="facts">${rows}</ul>${list.length > 24 ? `<p class="mono">Showing 24 of ${list.length}. Use List to see the rest.</p>` : ''}</div>`;
    }
    const others = m.others.length ? `<p class="fine">Not connected to anyone here: ${m.others.slice(0, 8).map((o) => esc(o.label) + ' (' + o.n + ')').join(', ')}${m.others.length > 8 ? ' and ' + (m.others.length - 8) + ' more' : ''}.</p>` : '';
    return `<div class="mgraph"><svg viewBox="0 0 ${GW} ${GH}" role="group" aria-label="Who is connected to whom. The list below says the same thing.">${lines}${hits}${counts}${dots}</svg>${detail}${others}</div>`;
  }
  function memoryHtml() {
    if (!S.memory.accepted.length) return `<div class="empty"><h1>Nothing remembered yet</h1><p class="hint">Facts appear after you approve and save an episode.</p>${btn('go-write', 'Open the episode', { cls: 'btn tonal' })}</div>`;
    const { people } = buildPeople();
    const list = memFiltered();
    const shown = list.slice(0, mem.shown);
    const person = route.person && route.person !== 'all' ? people.find((p) => p.key === route.person) : null;
    const base = S.memory.accepted;
    const kindCounts = {};
    base.forEach((c) => { if (!person || buildPeople().of.get(c.claim_id) === person.key) kindCounts[c.kind] = (kindCounts[c.kind] || 0) + 1; });
    const view = route.person === '' ? 'home' : 'entity';
    const peopleList = `<ul class="plist"><li><button type="button" data-person="all" ${!person && route.person !== '' ? 'aria-current="true"' : ''}><span>Everyone</span><span class="num">${base.length}</span></button></li>${people.map((p) => `<li><button type="button" data-person="${esc(personSlug(p.key))}" ${person && person.key === p.key ? 'aria-current="true"' : ''}><span>${esc(p.label)}</span><span class="num">${p.count}</span></button></li>`).join('')}</ul>`;
    let rows = '', lastEp = 0;
    shown.forEach((c) => { if (c.narrative_ordinal !== lastEp) { lastEp = c.narrative_ordinal; rows += `<li class="eh"><span>Episode ${lastEp}</span></li>`; } rows += factRow(c); });
    const filter = mem.eps.size ? `<button type="button" class="chipbtn" data-action="clear-mem-range">${(mem.eps.size === 1 ? 'Episode ' : 'Episodes ') + [...mem.eps].sort((a, b) => a - b).join(', ')}<span aria-hidden="true"> x</span><span class="sr"> Clear</span></button>` : '';
    return `<section class="mem" data-view="${view}" data-source="${mem.sel ? 'open' : 'closed'}">
<div class="mem-side"><h1 class="sr">Memory</h1><label class="sr" for="mem-search">Search facts</label><div class="searchbox"><input id="mem-search" type="search" data-form="memq" placeholder="Search facts" value="${esc(mem.q)}" autocomplete="off"><kbd aria-hidden="true">/</kbd></div><h2 class="sr">People</h2>${peopleList}</div>
<div class="mem-main"><div class="memtool">${btn('mem-home', 'Back to people', { cls: 'plain mem-back' })}<label class="sr" for="mem-search2">Search facts</label><div class="searchbox"><input id="mem-search2" type="search" data-form="memq" placeholder="Search facts" value="${esc(mem.q)}" autocomplete="off"></div></div><header class="mem-head"><h1>${esc(mem.view === 'graph' ? 'Connections' : person ? person.label : 'Everyone')}</h1><div class="memview" role="group" aria-label="How to look at the facts"><button type="button" data-action="mem-view" data-v="list" aria-pressed="${mem.view !== 'graph'}">List</button><button type="button" data-action="mem-view" data-v="graph" aria-pressed="${mem.view === 'graph'}">Connections</button></div><p class="mono">${mem.view === 'graph' ? '' : plural(person ? person.count : base.length, 'fact')}</p></header>
${mem.view === 'graph' ? '' : `<div class="ktabs" role="group" aria-label="Kind of fact">${KIND_TABS.filter(([k]) => k === 'all' || kindCounts[k]).map(([k, l]) => `<button type="button" data-kind="${k}" aria-pressed="${mem.kind === k}">${l}${k === 'all' ? '' : ` <span class="num">${kindCounts[k]}</span>`}</button>`).join('')}</div>`}
${(() => { const withFacts = [...new Set(base.map((c) => c.narrative_ordinal))].sort((a, b) => a - b); return withFacts.length > 1 ? `<div class="ktabs eps" role="group" aria-label="Facts from episodes. Pick one or more."><button type="button" data-action="mem-ep" data-n="0" aria-pressed="${!mem.eps.size}">All</button>${withFacts.map((n) => `<button type="button" data-action="mem-ep" data-n="${n}" aria-pressed="${mem.eps.has(n)}">Ep ${n}</button>`).join('')}</div>` : ''; })()}
${filter ? `<div class="filters">${filter}</div>` : ''}
${mem.view === 'graph' ? graphHtml() : (shown.length ? `<ul class="facts">${rows}</ul>` : `<div class="empty small"><p class="hint">No facts match.</p>${btn('clear-mem', 'Clear filters', { cls: 'plain' })}</div>`)}
${mem.view === 'graph' ? '' : (list.length > shown.length ? `<div class="more">${btn('more-facts', `Show ${Math.min(20, list.length - shown.length)} more`, { cls: 'btn tonal' })}<span class="mono">${shown.length} of ${list.length}</span></div>` : '')}</div>
<aside class="mem-src" aria-label="Source" id="srcpane">${sourceHtml()}</aside></section>`;
  }

  // ---------- dialogs ----------
  function showDialog(d) {
    if (d.open) return;
    d._from = sess.invoker && sess.invoker.isConnected && !sess.invoker.closest('dialog') ? sess.invoker : document.activeElement;
    d.showModal();
  }
  function backFocus(d) {
    const el = d._from; d._from = null;
    if (!el || el === document.body || !el.isConnected) return false;
    setTimeout(() => el.focus({ preventScroll: true }), 0);
    return true;
  }
  function hideDialog(d) {
    if (!d.open) return;
    if (reduced()) { d.close(); return; }
    d.classList.add('out');
    clearTimeout(d._t);
    d._t = setTimeout(() => { d.classList.remove('out'); if (d.open) d.close(); }, 170);
  }
  function openSheet(spec, trigger) {
    const t = trigger || document.activeElement;
    sess.sheet = { ...spec, back: sess.sheet ? sess.sheet.back : keyOf(t) };
    $('sheet').dataset.kind = spec.kind;
    renderSheet(true);
    showDialog($('sheet'));
    const title = $('sheet-title');
    title.focus({ preventScroll: true });
  }
  function closeSheet() { hideDialog($('sheet')); }
  function sheetTitle(s) {
    return { finish: `Finish episode ${s.n}`, unsaved: 'Unsaved edits', spend: 'Start drafting', paused: 'Drafting paused', menu: `Episode ${s.n}`, tour: 'How this works', keys: 'Keyboard', overlap: 'The passage changed', shown: `What episode ${s.n} was written from` }[s.kind] || '';
  }
  function renderSheet(force) {
    const s = sess.sheet;
    const d = $('sheet');
    if (!s || (!d.open && !force)) return;
    const body = $('sheet-body');
    const top = body.scrollTop;
    const act = document.activeElement;
    const key = act && body.contains(act) ? keyOf(act) : null;
    const open = [...body.querySelectorAll('details')].map((x) => x.open);
    $('sheet-title').textContent = sheetTitle(s);
    const html = { finish: () => finishHtml(s.n), unsaved: () => unsavedHtml(s.n), spend: spendHtml, paused: pausedHtml, menu: () => menuHtml(s.n), tour: tourHtml, keys: keysHtml, overlap: () => s.html, shown: () => s.html }[s.kind]();
    if (body.dataset.html !== html) {
      body.innerHTML = html; body.dataset.html = html;
      body.querySelectorAll('details').forEach((x, i) => { if (open[i] !== undefined && x.dataset.keep) x.open = open[i]; });
      body.scrollTop = top;
      if (key) { const t = document.querySelector(key); if (t && t !== document.activeElement) t.focus({ preventScroll: true }); }
    }
    body.querySelectorAll('[data-pct]').forEach((m) => m.style.setProperty('--p', m.dataset.pct));
    d.dataset.tour = s.kind === 'tour' ? String(sess.tourStep) : '';
    $('threadwrap').dataset.tour = s.kind === 'tour' ? String(sess.tourStep) : '';
  }
  function openOverlap(d) {
    const parts = d.before !== undefined || d.ai !== undefined ? [['Before', d.before], ['Suggested', d.ai], ['Now', d.now]] : [['The change you would undo', d.expected], ['Now', d.now]];
    openSheet({ kind: 'overlap', html: `<p>Nothing was written. The words below differ, so the desk will not overwrite the newer text.</p><div class="compare">${parts.map(([h, t]) => `<div><span class="mono">${h}</span><p>${t == null ? '(removed)' : esc(t)}</p></div>`).join('')}</div><div class="erow">${btn('close-sheet', 'Keep current text', { cls: 'btn tonal' })}</div>` });
  }

  // ---------- finish sheet ----------
  function whoFor(c) {
    const p = c.speaker || c.holder;
    if (p) return capFirst(p.trim().replace(/^(the|a|an)\s+/i, ''));
    const s = c.subject || '';
    for (const pe of buildPeople().people) {
      if (pe.key === '_story') continue;
      if (new RegExp('(^|[^\\p{L}\\p{N}])' + pe.key.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '(?![\\p{L}\\p{N}])', 'iu').test(s)) return pe.label;
    }
    const m = s.match(/^([A-Z][\p{L}'-]+)/u);
    return m ? m[1] : 'The story';
  }
  function previewRead(e) {
    return Boolean(S.extractions && e.selection && S.extractions.some((r) => r.mode === 'preview' && r.revision_id === e.selection.revision_id && r.outcome === 'read'));
  }
  function provisionalFor(e) { return [...(S.memory.provisional || []), ...(S.memory.awaiting || [])].filter((c) => c.narrative_ordinal === e.ordinal && e.selection && c.revision_id === e.selection.revision_id); }
  function finRow(c, e) {
    const said = c.kind === 'testimony' || c.kind === 'belief';
    const i = e.blocks.findIndex((b) => b.block_id === c.block_id);
    const who = c.speaker || c.holder || '';
    const text = headline(c);
    const body = said ? `<span class="fwho">${esc(capFirst(who || 'Someone'))} ${c.kind === 'belief' ? 'believes' : 'said'}</span><q class="fq">${esc(text)}</q>` : `<span class="ftxt">${esc(text)}</span>`;
    const glyph = said ? 'said' : c.world_validity === 'true_in_story' ? 'true' : c.world_validity === 'false_in_story' ? 'false' : 'unknown';
    return `<li class="frow" data-k="${said ? 'said' : 'plain'}" data-block="${esc(c.block_id)}" tabindex="0"><i class="truth" data-v="${glyph}" aria-hidden="true"></i><div class="fbody">${body}<span class="fquote">${esc(c.quote)}</span><span class="mono">${esc(KIND_LABEL[c.kind] || c.kind)} · ${esc(VALID[c.world_validity] || '')}${i >= 0 ? ' · ¶' + (i + 1) : ''}</span></div></li>`;
  }
  function factGroupsHtml(facts, e) {
    const groups = new Map();
    facts.forEach((c) => { const w = whoFor(c); if (!groups.has(w)) groups.set(w, []); groups.get(w).push(c); });
    return [...groups.entries()].map(([w, list], gi) => {
      const open = sess.finGroups && sess.finGroups[w] !== undefined ? sess.finGroups[w] : gi === 0;
      const all = sess.finAll && sess.finAll[w];
      const shown = all ? list : list.slice(0, 5);
      return `<details class="fgroup" data-who="${esc(w)}"${open ? ' open' : ''}><summary><span>${esc(w)}</span><span class="num">${list.length}</span></summary><ul>${shown.map((c) => finRow(c, e)).join('')}</ul>${list.length > 5 && !all ? btn('fin-all', `Show all ${list.length}`, { cls: 'plain', extra: `data-who="${esc(w)}"` }) : ''}</details>`;
    }).join('');
  }
  function finishHtml(n) {
    const e = ep(n);
    if (!e || !e.selection) return '<p>This episode has no draft yet.</p>';
    if (dirtyBlocks(e).length && !e.accepted) return unsavedHtml(n);
    const block = approveBlock(e);
    const approved = e.accepted;
    const saved = approved && e.memory_state === 'read';
    const prov = saved ? [] : provisionalFor(e);
    const savedFacts = saved ? S.memory.accepted.filter((c) => c.narrative_ordinal === n) : [];
    const read = previewRead(e);
    const seen = Boolean(sess.finSeen && sess.finSeen[n]);
    const firstOut = !approved && n !== cursor() + 1 && n > cursor() + 1;
    let step1;
    if (approved) step1 = '<p class="receipt" role="status">Approved and locked.</p>';
    else step1 = `<p>Approve locks these exact words.</p>${block ? `<p class="reason" id="why1">${esc(block)}</p>${firstOut ? btn('nav-ep', `Go to episode ${cursor() + 1}`, { cls: 'plain', extra: `data-ep="${cursor() + 1}"` }) : ''}` : ''}
<button type="button" class="btn approve" id="btn-approve" data-action="confirm-approve" data-ordinal="${n}"${block ? ' aria-disabled="true" aria-describedby="why1"' : ''}>${ICON.lock}<span>Approve episode ${n}</span></button>`;
    let step2;
    if (saved) step2 = `<p class="receipt" role="status">Saved. The story remembers ${plural(savedFacts.length, 'more thing')}.</p><div class="erow">${btn('close-fin', 'Done', { cls: 'btn tonal' })}</div>`;
    else {
      const callMine = sess.call && sess.call.n === n ? statusHtml('compacting', 'sm', sess.call.text) : '';
      let review;
      if (prov.length && approved) review = `<details class="fwrap" id="fin-review"${seen ? ' open' : ''}><summary>Review ${plural(prov.length, 'change')} before saving</summary><div class="facts-fin" id="fin-facts">${factGroupsHtml(prov, e)}</div></details>`;
      else if (prov.length) review = `<div class="facts-fin" id="fin-facts">${factGroupsHtml(prov, e)}</div>`;
      else if (read) review = '<p class="hint">Nothing new found in this episode.</p>';
      else review = `<p class="hint">${live() ? 'Showing them first costs about a fifth of a cent.' : 'Showing them first is free.'}</p>${btn('read-facts', 'Show what it adds first', { cls: 'plain', extra: `data-ordinal="${n}"` })}`;
      const ready = approved && (prov.length ? seen : read);
      const why = !approved ? 'Locked until step 1 is done.' : !ready ? (prov.length ? 'Open the list of changes first.' : 'Show what it adds first.') : '';
      const wait = ready && !callMine ? `<p>${statusHtml('waiting', 'sm', 'Waiting for you to save')}</p>` : '';
      step2 = `${callMine}${review}${prov.length ? '<p class="mono">Saving adds all of these.</p>' : ''}${why ? `<p class="reason" id="why2">${why}</p>` : ''}
${wait}<button type="button" class="btn save" id="btn-save" data-action="confirm-save" data-ordinal="${n}"${!ready ? ' aria-disabled="true" aria-describedby="why2"' : ''}>${ICON.stack}<span>${prov.length ? `Save ${plural(prov.length, 'story change')}` : 'Save story changes'}</span></button>${approved ? `<div class="erow">${btn('close-fin', 'Not yet', { cls: 'plain' })}</div>` : `<div class="erow">${btn('close-fin', 'Cancel', { cls: 'plain' })}</div>`}`;
    }
    return `<p class="mono sub">${esc(words(e))}</p><section class="step" data-done="${approved}"><h3><span class="sn">1</span>Approve</h3>${step1}</section>
<section class="step" data-done="${saved}" data-inert="${!approved}"><h3><span class="sn">2</span>${saved ? 'Saved' : 'Save to memory'}</h3>${step2}</section>`;
  }
  function unsavedHtml(n) {
    const e = ep(n);
    const c = dirtyBlocks(e).length;
    return `<p>You have ${plural(c, 'unsaved edit')} in this episode. Finish uses saved words only.</p><div class="erow col">${btn('save-edits-continue', 'Save edits and continue', { cls: 'btn tonal', extra: `data-ordinal="${n}"` })}${btn('discard-edits-continue', 'Discard edits', { cls: 'plain', extra: `data-ordinal="${n}"` })}${btn('close-fin', 'Cancel', { cls: 'plain' })}</div>`;
  }
  function finishPanel(n) {
    return `<section class="finish" id="finish" aria-labelledby="fin-h"><h2 id="fin-h" tabindex="-1">Finish episode ${n}</h2>${finishHtml(n)}</section>`;
  }
  function openFinish(n, trigger) {
    const e = ep(n);
    if (!e || !e.selection) return;
    sess.finGroups = {}; sess.finAll = {};
    sess.fin = n; sess.finFrom = keyOf(trigger || document.activeElement);
    route.studio = null; route.room = 'write'; route.ep = n;
    render();
    requestAnimationFrame(() => {
      const p = $('finish');
      if (!p) return;
      p.scrollIntoView({ block: 'center', behavior: 'auto' });
      $('fin-h').focus({ preventScroll: true });
      if (!reduced() && p.animate) p.animate([{ opacity: 0, transform: 'translateY(8px)' }, { opacity: 1, transform: 'none' }], { duration: 240, easing: 'cubic-bezier(0.2,0,0,1)' });
    });
  }

  // ---------- spend and paused ----------
  function spendRun() {
    const first = nextUndrafted();
    if (!first) return null;
    let max = 0;
    for (let k = first.ordinal; k <= arcN() && max < BATCH; k += 1) { const x = ep(k); if (x && !x.selection && !x.accepted) max += 1; else break; }
    const count = Math.min(Math.max(1, Number(sess.spendCount) || Math.min(3, max)), max);
    return { first: first.ordinal, max, count, last: first.ordinal + count - 1 };
  }
  function cents(lo, hi) { return hi >= 100 ? `${money(lo / 100)} to ${money(hi / 100)}` : `${lo} to ${hi} cents`; }
  function spendHtml() {
    const r = spendRun();
    if (!r) return '<p>Every episode has a draft.</p>';
    const lo = r.count * 3, hi = r.count * 5;
    const left = live() ? S.provider.left_usd : null;
    const blocked = live() && hi / 100 > left;
    return `<h3>Draft ${range(r.first, r.last)}</h3>
<div class="stepper" role="group" aria-label="How many episodes">${btn('spend-dec', 'Fewer episodes', { cls: 'icon', html: '<span aria-hidden="true">-</span>', disabled: r.count <= 1 })}<output>${r.count}</output>${btn('spend-inc', 'More episodes', { cls: 'icon', html: '<span aria-hidden="true">+</span>', disabled: r.count >= r.max })}</div>
<p>${live() ? `About ${cents(lo, hi)}. You have ${money(left)} left.` : 'Practice writer. Nothing is sent and nothing is charged.'}</p>
<p class="mono">Each takes about 30 to 45 seconds. You can leave while it works.</p><p class="mono">Episodes are written to ${(S.word_band || [550, 700, 900])[0]} to ${(S.word_band || [550, 700, 900])[2]} words. A draft a little over is kept and marked. One past ${S.word_limit || 1080} is set aside for you to read, and drafting stops there.</p>${blocked ? '<p class="reason">The most this could cost is above what is left. Draft fewer episodes.</p>' : ''}
<div class="erow">${btn('confirm-spend', 'Start drafting', { cls: 'btn spend', disabled: blocked, html: `<span>Start drafting</span><span class="chip">${live() ? 'about ' + cents(lo, hi) : 'free'}</span>`, extra: `data-first="${r.first}" data-count="${r.count}"` })}${btn('close-sheet', 'Cancel', { cls: 'plain' })}</div>`;
  }
  function openSpend(trigger) {
    if (!nextUndrafted()) return;
    if (pending) { say('Drafting is already running.'); return; }
    sess.spendCount = 0;
    openSheet({ kind: 'spend' }, trigger);
  }
  function pausedHtml() {
    const c = pausedCommission();
    if (!c) return '<p>Nothing is paused.</p>';
    const low = eps().find((x) => x.ordinal >= c.first_slot && x.ordinal <= c.last_slot && !x.selection);
    const left = live() ? S.provider.left_usd : null;
    const aside = c.pause_detail ? ep(c.pause_detail.ordinal) : null;
    const read = aside && aside.alternatives.length ? `<p>${btn('nav-ep', `Read episode ${aside.ordinal}`, { cls: 'link', extra: `data-ep="${aside.ordinal}"` })}. Use it and trim it by hand, or resume to have it written again.</p>` : '';
    const scope = low ? `Resuming carries on from episode ${low.ordinal}. Episodes already drafted are kept as they are.` : 'Episodes already drafted are kept as they are.';
    return `<p>${low ? `Stopped at episode ${low.ordinal}. ` : ''}${esc(pauseText(c))}</p>${read}<p class="mono">${esc(scope)} ${live() ? `Resuming spends more, ${money(left)} left.` : 'Practice writer. Nothing is sent and nothing is charged.'}</p>
<div class="erow">${btn('resume-commission', 'Resume drafting', { cls: 'btn spend', html: `<span>Resume drafting</span><span class="chip">${live() ? 'costs money' : 'free'}</span>`, extra: `data-commission="${esc(c.commission_id)}"` })}${btn('close-sheet', 'Not now', { cls: 'plain' })}</div>`;
  }

  // ---------- menu, tour, keys ----------
  function menuHtml(n) {
    const e = ep(n);
    if (!e) return '';
    const hist = S.history.filter((h) => h.artifact_id === e.artifact_id && ['save', 'rewrite_apply', 'revert', 'redo'].includes(h.action));
    const decided = [];
    if (S.governing.skeleton) decided.push('Adopted the direction.');
    if (S.governing.arc) decided.push('Adopted the plan.');
    if (e.accepted) decided.push(`Approved episode ${n}.`);
    if (e.accepted && e.memory_state === 'read') decided.push(`Saved story changes from episode ${n}.`);
    S.history.filter((h) => h.artifact_id === e.artifact_id && h.action === 'revalidate').forEach(() => decided.push(`Said episode ${n} still fits.`));
    const reads = (S.extractions || []).filter((r) => e.selection && r.revision_id === e.selection.revision_id);
    return `<section><h3>Edits</h3>${hist.length ? `<ul class="rows">${hist.slice(0, 10).map((h) => `<li><span>${esc(eventLabel(h))}${h.undone ? ', undone' : ''}</span><span>${canUndo(h) ? btn('undo', 'Undo', { cls: 'plain', extra: `data-event="${esc(h.event_id)}"` }) : ''}${canRedo(h) ? btn('redo', 'Redo', { cls: 'plain', extra: `data-event="${esc(h.event_id)}"` }) : ''}</span></li>`).join('')}</ul>` : '<p class="hint">No edits yet.</p>'}</section>
<section><h3>What I decided</h3><ul class="rows">${decided.map((t) => `<li><span>${esc(t)}</span></li>`).join('')}</ul></section>
${e.selection ? `<section><h3>Details</h3><dl class="kv"><dt>Version</dt><dd class="mono wrap">${esc(e.selection.revision_id)}</dd><dt>Fingerprint</dt><dd class="mono wrap">${esc(e.selection.sha256)}</dd><dt>Set-aside drafts</dt><dd>${e.alternatives.length}</dd>${reads.map((r) => `<dt>${r.mode === 'preview' ? 'Before approval' : 'After approval'}</dt><dd>found ${r.returned} · exact quotes ${r.anchored_exact} · set aside ${r.quarantined + r.duplicates}</dd>`).join('')}</dl></section>` : ''}
${e.open_impacts > 0 && !e.accepted ? `<div class="erow">${btn('revalidate-slot', 'It still fits', { cls: 'btn tonal', extra: `data-slot="${n}"` })}</div>` : ''}`;
  }
  function eventLabel(h) {
    const e = epByArtifact(h.artifact_id);
    const where = e ? ` episode ${e.ordinal}` : '';
    const map = { save: 'You edited', rewrite_apply: 'Used better wording in', revert: 'Undid a change to', redo: 'Redid a change to', adopt: h.artifact_id === 'arc' ? 'Adopted the plan' : 'Adopted the direction', commission_start: 'Started drafting', commission_pause: 'Drafting paused', commission_resume: 'Drafting resumed',
      select: 'Chose a draft for', result_detached: 'Set aside a draft for', result_imported: 'Added a draft for', accept: 'Approved episodes', revalidate: 'Said it still fits:', interpret: 'Corrected a fact', resolve_uncertain: 'Settled a charge', secret_add: 'Kept a secret', secret_retire: 'Retired a secret', style_sheet: 'Saved a voice version' };
    const base = map[h.action] || 'Updated the story';
    return e && /^(You edited|Used|Undid|Redid|Chose|Set aside|Added|Said)/.test(base) ? base + where : base;
  }
  const TOUR = [
    ['You decide the direction.', 'plan'],
    ['Plan the episodes, one line each.', 'plan'],
    ['The writer drafts. You read.', 'draft'],
    ['Nothing becomes the story until you press Approve.', 'approve'],
    ['Each knot is an episode. Shape and line show where it stands.', 'legend'],
  ];
  function tourHtml() {
    const i = sess.tourStep;
    const [text] = TOUR[i];
    const legend = i === 4 ? '<ul class="legend"><li><i class="k" data-st="planned"></i>Planned</li><li><i class="k" data-st="drafted"></i>Drafted</li><li><i class="k" data-st="flagged"></i>May not fit</li><li><i class="k" data-st="approved"></i>Approved</li></ul>' : '';
    return `<p class="mono">${i + 1} of ${TOUR.length}</p><p class="tour-text">${esc(text)}</p>${legend}<div class="erow">${i > 0 ? btn('tour-prev', 'Back', { cls: 'plain' }) : ''}${i < TOUR.length - 1 ? btn('tour-next', 'Next', { cls: 'btn tonal' }) : btn('close-sheet', 'Done', { cls: 'btn tonal' })}</div>`;
  }
  function keysHtml() {
    const rows = [['Ctrl K', 'Find or do anything'], ['1 2 3', 'Plan, Write, Memory'], ['Left, Right', 'Previous or next episode'], ['J, K', 'Next or previous episode'], [',', 'Open Studio'], ['/', 'Search facts'], ['Esc', 'Close or cancel']];
    return `<dl class="keys">${rows.map(([k, t]) => `<dt><kbd>${esc(k)}</kbd></dt><dd>${esc(t)}</dd>`).join('')}</dl>`;
  }

  // ---------- studio ----------
  const STUDIO = [['voice', 'Voice'], ['length', 'Length'], ['secrets', 'Secrets'], ['money', 'Money'], ['models', 'Models'], ['history', 'History'], ['how', 'How it works'], ['details', 'Support']];
  function avoidList() {
    const raw = form('style-avoid', S && S.style_sheet ? S.style_sheet.avoid.join('\n') : '');
    return raw.split('\n').map((x) => x.trim()).filter(Boolean);
  }
  function voiceHtml() {
    const sheet = S.style_sheet;
    const avoid = avoidList();
    return `<h2>How should it sound?</h2><label class="sr" for="style-body">Voice notes</label><textarea id="style-body" rows="6" data-form="style-body" placeholder="Plain, warm, short sentences...">${esc(form('style-body', sheet ? sheet.body : ''))}</textarea>
<h3>Never use</h3><ul class="chiplist">${avoid.map((w, i) => `<li><span class="wrap">${esc(w)}</span><button type="button" data-action="avoid-remove" data-i="${i}" aria-label="Remove ${esc(w)}">x</button></li>`).join('')}</ul>
<div class="addrow"><label class="sr" for="avoid-add">Add a word, phrase or mark</label><input id="avoid-add" placeholder="Add a word, phrase or mark" autocomplete="off">${btn('avoid-add', 'Add', { cls: 'btn tonal neutral' })}</div>
<p class="fine">The app flags these in drafts. It never rewrites them silently.</p>
<p class="mono">${sheet ? `Voice, version ${sheet.version}` : 'No voice saved yet'}</p><div class="erow">${btn('save-style', 'Save voice', { cls: 'btn tonal' })}</div>`;
  }
  const LENGTH_PRESETS = [['Short', [250, 350, 450]], ['Usual', [550, 700, 900]], ['Long', [900, 1200, 1500]]];
  const lenVal = (k) => form('len-' + k, String(S.length[k]));
  const lenLimit = () => { const h = Number(lenVal('high')); return Number.isInteger(h) && h > 0 ? Math.floor(h * 6 / 5) : '?'; };
  function lengthHtml() {
    const L = S.length;
    const field = (k, label) => `<div class="lenf"><label for="len-${k}">${label}</label><input id="len-${k}" inputmode="numeric" data-form="len-${k}" value="${esc(lenVal(k))}" autocomplete="off"${invalid('len-' + k)}>${fieldErr('len-' + k)}</div>`;
    return `<h2>How long is an episode?</h2>
<p class="hint">The writer is told these numbers for every episode. A draft a little past the longest is kept and marked. A draft longer than <span id="len-limit">${lenLimit()}</span> words (a fifth past the longest, with the numbers below) is set aside for you to read.</p>
<div class="chiprow" role="group" aria-label="Start from">${LENGTH_PRESETS.map(([name, v]) => btn('len-preset', `${name}, ${v[0]} to ${v[2]}`, { cls: 'btn tonal neutral', extra: `data-v="${v.join(',')}"` })).join('')}</div>
<div class="lengrid">${field('low', 'Shortest (words)')}${field('target', 'Aim for (words)')}${field('high', 'Longest (words)')}</div>
<p class="fine">Applies to drafts from now on. Drafts you already have do not change. Between ${LENGTH_MIN} and ${LENGTH_MAX} words.</p>
<p class="mono">${L.custom ? 'Set for this series' : 'The usual length, not changed yet'}</p>
<div class="erow">${btn('save-length', 'Save length', { cls: 'btn tonal' })}</div>`;
  }
  const SECRET_MAX = 80;
  const fieldErr = (id) => (sess.studioErr && sess.studioErr.field === id ? `<p class="field-err" id="${id}-err" role="alert">${esc(sess.studioErr.text)}</p>` : '');
  const invalid = (id) => (sess.studioErr && sess.studioErr.field === id ? ` aria-invalid="true" aria-describedby="${id}-err"` : '');
  function studioErr(text, field) {
    sess.studioErr = { text, field };
    $('sroom').dataset.html = '';
    renderStudio();
    const el = field && $(field);
    if (el) el.focus();
    say(text);
  }
  function studioAlertHtml() {
    const b = problem || offline ? computeBanner() : null;
    if (!b) return '';
    return `<div class="studio-alert" role="alert" data-sev="${b.sev}"><p>${b.title ? `<strong>${esc(b.title)}.</strong> ` : ''}${esc(b.text)}</p><div class="banner-actions">${(b.actions || []).map(([attr, label]) => `<button type="button" ${attr}>${esc(label)}</button>`).join('')}${b.dismiss ? btn('dismiss-problem', 'Dismiss') : ''}</div></div>`;
  }
  function secretsHtml() {
    const secrets = S.secrets || [];
    const label = form('secret-label', '');
    return `<h2>Things you know and the writer must not.</h2>
${secrets.length ? `<ul class="slist">${secrets.map((s) => `<li><div><strong class="wrap">${esc(s.label)}</strong><p class="wrap">${esc(s.body)}</p><p class="mono wrap">triggers: ${esc(s.canaries.join(', '))}${s.reveal_ordinal ? ` · may appear from episode ${s.reveal_ordinal}` : ''}${s.status === 'retired' ? ' · retired' : ''}</p></div>${s.status !== 'retired' ? btn('retire-secret', 'Retire', { cls: 'plain', extra: `data-secret="${esc(s.secret_id)}"` }) : ''}</li>`).join('')}</ul>` : '<p class="hint">No secrets yet.</p>'}
<h3>Add a secret</h3><label for="secret-label">Name</label><input id="secret-label" data-form="secret-label" value="${esc(label)}" autocomplete="off" aria-describedby="label-count"${invalid('secret-label')}><p class="mono" id="label-count" data-over="${label.length > SECRET_MAX}">${label.length} of ${SECRET_MAX}</p>${fieldErr('secret-label')}
<label for="secret-body">The secret</label><textarea id="secret-body" rows="3" data-form="secret-body"${invalid('secret-body')}>${esc(form('secret-body', ''))}</textarea>${fieldErr('secret-body')}
<label for="secret-words">Words that would give it away</label><input id="secret-words" data-form="secret-words" value="${esc(form('secret-words', ''))}" autocomplete="off" aria-describedby="words-hint${sess.studioErr && sess.studioErr.field === 'secret-words' ? ' secret-words-err' : ''}"${sess.studioErr && sess.studioErr.field === 'secret-words' ? ' aria-invalid="true"' : ''}><p class="fine" id="words-hint">Separate with commas. Four or more letters each, and not common words.</p>${fieldErr('secret-words')}
<label for="secret-reveal">Earliest episode (optional)</label><input id="secret-reveal" inputmode="numeric" data-form="secret-reveal" value="${esc(form('secret-reveal', ''))}" autocomplete="off">
<div class="erow">${btn('add-secret', 'Add a secret', { cls: 'btn tonal' })}</div>`;
  }
  function moneyHtml() {
    const p = S.provider || {};
    if (!live()) return `<h2>Money</h2><p>Practice mode. The writer is scripted, so nothing is sent and nothing is charged.</p>
<p class="hint">When the desk runs live, each draft and chat reply costs a small amount. This page then shows three things: what has been spent, what is set aside for calls still running, and your limit. The desk never goes past the limit.</p>`;
    const pct = p.cap_usd ? Math.min(1, p.spent_usd / p.cap_usd) : 0;
    const calls = (p.calls || []).slice(-8).reverse();
    const held = p.held_usd || 0;
    const near = p.left_usd <= 0 ? 'Limit reached. Raise it to keep drafting.' : p.left_usd < p.cap_usd * 0.2 ? 'Nearly at your limit.' : '';
    return `<h2>Money</h2><div class="trio"><div><span class="big">${money(p.spent_usd)}</span><span class="mono">spent</span></div><div><span class="big">${money(p.left_usd)}</span><span class="mono">left</span></div><div><span class="big">${money(p.cap_usd)}</span><span class="mono">your limit</span></div></div>${held > 0 ? `<p class="fine">${money(held)} is set aside for calls still running. It is released when they finish.</p>` : ''}
<div class="numline" role="img" aria-label="${money(p.spent_usd)} spent of ${money(p.cap_usd)}"><i data-pct="${pct}"></i></div>${near ? `<p class="reason">${near}</p>` : ''}
<p class="fine">The limit is set when the desk starts. It counts everything ever spent on this story.</p>${uncertainHtml()}
<h3>Recent paid calls</h3><p class="hint">One row per request to the writer. "Read" and "written" are amounts of text the model handled; cached text was reused and costs less.</p>${calls.length ? `<ul class="calls">${calls.map((c) => `<li><span>${esc(({ sequential_draft: 'Draft', promotion: 'Story changes', converse: 'Ask' }[c.recipe]) || c.recipe)}${c.outcome !== 'ok' ? ' · ' + esc(String(c.outcome).replace(/_/g, ' ')) : ''}</span><span class="mono wrap">${esc((c.model || '').split('/').pop())}</span><span class="mono">${c.prompt_tokens ?? 0} read · ${c.cached_tokens ?? 0} cached · ${c.completion_tokens ?? 0} written</span><span>${c.cost_usd == null ? '' : money4(c.cost_usd)}</span></li>`).join('')}</ul>` : '<p class="hint">No paid calls yet.</p>'}`;
  }
  function uncertainHtml() {
    return (S.uncertain || []).map((id) => `<div class="unc"><h3>Settle a charge</h3><p>A drafting request has no confirmed result. It will not be retried.</p><label for="settle-${esc(id)}">Why is it safe to settle?</label><input id="settle-${esc(id)}" data-form="settle-${esc(id)}" value="${esc(form('settle-' + id, ''))}" autocomplete="off"><div class="erow">${btn('resolve-uncertain', 'Mark as settled', { cls: 'btn tonal', extra: `data-job="${esc(id)}"` })}</div></div>`).join('');
  }
  function modelsHtml() {
    const roster = '<ul class="rows"><li><span>Drafting and chat</span><span>Claude Sonnet 5.5</span></li><li><span>Planning ideas</span><span>Claude Opus 5.5</span></li><li><span>Reading facts</span><span>GPT-6 Luna</span></li></ul>';
    const note = live()
      ? '<p class="hint">These are the models behind the desk right now. The split keeps the expensive model for planning and uses the cheaper ones for the rest.</p>'
      : '<p>Practice mode uses a scripted writer that stands in for all three models, so nothing is sent or charged. When the desk runs live, this is the crew:</p>';
    return `<h2>Models</h2>${note}${roster}${live() ? '' : uncertainHtml()}`;
  }
  function howHtml() { return window.StudioGuide ? window.StudioGuide.logic({ length: S.length, live: live() }) : '<p>The guide could not be loaded. Reload the page.</p>'; }
  function historyHtml() {
    const hist = S.history.filter((h) => h.action !== 'job_frozen');
    return `<h2>History</h2><p class="hint">Your edits, newest first.</p>${hist.length ? `<ul class="rows">${hist.slice(0, 30).map((h) => `<li><span>${esc(eventLabel(h))}${h.undone ? ', undone' : ''}</span><span>${canUndo(h) ? btn('undo', 'Undo', { cls: 'plain', extra: `data-event="${esc(h.event_id)}"` }) : ''}${canRedo(h) ? btn('redo', 'Redo', { cls: 'plain', extra: `data-event="${esc(h.event_id)}"` }) : ''}</span></li>`).join('')}</ul>` : '<p class="hint">Nothing yet.</p>'}`;
  }
  function exportManuscript() {
    const done = eps().filter((e) => e.accepted && e.blocks);
    if (!done.length) { say('No approved episodes to download yet.'); return; }
    const title = (S.story && S.story.title) || 'Manuscript';
    const parts = [`# ${title}`, ...done.map((e) => `## Episode ${e.ordinal}\n\n${e.blocks.map((b) => b.text).join('\n\n')}`)];
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([parts.join('\n\n') + '\n'], { type: 'text/markdown' }));
    a.download = title.replace(/[^\w-]+/g, '-').toLowerCase() + '.md';
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    say(`Downloaded ${plural(done.length, 'episode')}.`);
  }
  function epFor(revisionId) {
    const c = S.canon.find((x) => x.revision_id === revisionId);
    if (c) return c.ordinal;
    const e = S.episodes.find((x) => x.selection && x.selection.revision_id === revisionId);
    return e ? e.ordinal : null;
  }
  function shownHtml(r) {
    if (!r.job) return '<p class="hint">No request has been sent for this episode.</p>';
    const blocks = r.parts.map((p) => (p.kind === 'episode'
      ? `<p class="sentrow"><span>${esc(p.label)}</span><span class="mono">${plural(p.words, 'word')}</span></p>`
      : `<details class="support"><summary>${esc(p.label)}</summary><pre class="sent">${esc(p.text)}</pre></details>`)).join('');
    const where = live() ? 'This is what was sent.' : 'Practice mode sends nothing anywhere. This is what the writer would be sent.';
    return `<p class="hint">${where} Earlier episodes go in whole, in order. The story facts you saved in Memory are not part of the request.</p>${blocks}<p class="mono wrap">Fingerprint ${esc(r.fingerprint)}</p><p class="hint">The fingerprint is a short signature of the request. If you ever ask for help, quoting it proves both sides are looking at the same request.</p>`;
  }
  function detailsHtml() {
    const ex = S.extractions || [];
    const withDraft = eps().filter((e) => e.selection);
    return `<h2>Support details</h2><p class="hint">For when you ask for help. Nothing here needs action.</p>
<details class="support"><summary>Version IDs, for support</summary><p class="hint">Every draft has an ID and a fingerprint. If something looks wrong, copy the ID of that episode and send it with your question. That is all these are for.</p>${withDraft.length ? `<ul class="rows tight">${withDraft.map((e) => `<li><span>Episode ${e.ordinal}</span><span class="mono wrap">${esc(e.selection.revision_id)}</span>${btn('copy', 'Copy', { cls: 'plain', extra: `data-text="${esc(e.selection.revision_id)}" aria-label="Copy version of episode ${e.ordinal}"` })}</li><li><span class="mono">Fingerprint</span><span class="mono wrap">${esc(e.selection.sha256)}</span>${btn('copy', 'Copy', { cls: 'plain', extra: `data-text="${esc(e.selection.sha256)}" aria-label="Copy fingerprint of episode ${e.ordinal}"` })}</li>`).join('')}</ul>` : '<p class="hint">No drafts yet.</p>'}</details>
<details class="support"><summary>What the writer was shown</summary>${withDraft.length ? `<p class="hint">The exact request for each draft: your direction, your voice notes and the earlier episodes. Private notes and secrets are not part of it.</p><ul class="rows tight">${withDraft.map((e) => `<li><span>Episode ${e.ordinal}</span>${btn('show-sent', 'Show', { cls: 'plain', extra: `data-n="${e.ordinal}" aria-label="Show what the writer was shown for episode ${e.ordinal}"` })}</li>`).join('')}</ul>` : '<p class="hint">No drafts yet.</p>'}</details>
<details class="support"><summary>How each episode was read</summary><p class="hint">After you approve an episode, the desk reads it and pulls out facts for Memory. "Found" is how many it proposed. "Exact quotes" is how many matched the text word for word. "Set aside" is how many were dropped for not matching, or for saying something already known.</p>${ex.length ? `<ul class="rows tight">${ex.map((r) => `<li><span>Episode ${epFor(r.revision_id) ?? '?'}</span><span>${r.mode === 'preview' ? 'Before approval' : 'After approval'}${r.outcome !== 'read' ? ', failed' : ''}</span><span class="mono">found ${r.returned} · exact quotes ${r.anchored_exact} · set aside ${r.quarantined + r.duplicates}</span></li>`).join('')}</ul>` : '<p class="hint">No episode has been read yet.</p>'}</details>
<p class="fine">${S.style_sheet ? 'Voice version ' + S.style_sheet.version + ' is in use. ' : ''}Drafts, chat messages and rewrite requests are checked for your secret trigger words before anything is sent. The check finds the words, not the idea, so keep the secret itself out of the plan.</p>`;
  }
  function renderStudio() {
    const d = $('studio');
    if (route.studio === null) { if (d.open) hideDialog(d); return; }
    if (!S || !S.story) { return; }
    const room = route.studio || '';
    d.dataset.view = room ? 'room' : 'list';
    $('srooms').innerHTML = STUDIO.map(([id, l]) => `<li><button type="button" data-studio="${id}" ${room === id || (!room && id === 'voice' && matchMedia('(min-width:700px)').matches) ? 'aria-current="true"' : ''}><span>${l}</span><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M6 3l5 5-5 5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg></button></li>`).join('');
    const eff = room || (matchMedia('(min-width:700px)').matches ? 'voice' : '');
    const fn = { voice: voiceHtml, length: lengthHtml, secrets: secretsHtml, money: moneyHtml, models: modelsHtml, history: historyHtml, how: howHtml, details: detailsHtml }[eff];
    const body = $('sroom');
    const html = fn ? `${btn('studio-back', 'Studio', { cls: 'plain sback' })}${studioAlertHtml()}${fn()}` : '';
    if (body.dataset.html !== html || d.dataset.eff !== eff) {
      const act = document.activeElement;
      const key = act && body.contains(act) ? keyOf(act) : null;
      const top = body.scrollTop;
      body.innerHTML = html; body.dataset.html = html; d.dataset.eff = eff;
      body.scrollTop = top;
      if (key) { const t = document.querySelector(key); if (t) t.focus({ preventScroll: true }); }
    }
    body.querySelectorAll('[data-pct]').forEach((m) => m.style.setProperty('--p', m.dataset.pct));
    document.querySelectorAll('[data-theme-set]').forEach((b) => b.setAttribute('aria-pressed', String(ui.theme === b.dataset.themeSet)));
    if (!d.open) { sess.studioFrom = keyOf(document.activeElement); showDialog(d); $('studio-title').focus({ preventScroll: true }); }
  }

  // ---------- palette ----------
  let palItems = [], palSel = 0;
  function buildPalette() {
    const it = [];
    const add = (label, hint, kw, fn) => it.push({ label, hint, kw: `${label} ${hint} ${kw}`.toLowerCase(), fn });
    if (!S || !S.story || inFirstRun()) {
      if (HOME) add('All series', 'Back to your shelf, where the sample lives', 'home shelf series library sample demo example', () => { location.href = '/'; });
      else add('Try the sample story', 'Three episodes, practice writer', 'sample demo example', () => actions['start-sample']());
      add('How this works', `${TOUR.length} short cards`, 'help tour how guide learn', () => openTour());
      return it;
    }
    const e = currentEp();
    if (nextUndrafted()) add('Draft next episode', 'Shows the cost first', 'draft write next chapter generate spend money cost', () => openSpend());
    if (e && e.selection && !e.accepted) add(`Finish episode ${e.ordinal}`, 'Approve the words', 'finish approve accept lock final', () => openFinish(e.ordinal));
    if (waitingMemory().length) add('Save story changes', 'Add facts to memory', 'save memory facts story changes', () => openFinish(waitingMemory()[0].ordinal));
    add('Go to Plan', 'Direction and episode lines', 'plan direction premise spine adopt lines', () => navTo('plan'));
    add('Go to Write', 'Read and edit', 'write read edit prose page', () => navTo('write'));
    add('Go to Memory', 'What the story knows', 'memory facts story knows why a fact is here source people', () => navTo('memory'));
    add('Open Secrets', 'Things the writer must not know', 'secret secrets hide twist canary reveal private', () => navTo('studio/secrets'));
    add('How it works', 'The logic, with diagrams', 'how works logic diagram guide explain end to end', () => navTo('studio/how'));
    add('Open Length', 'Words per episode', 'length words long short episode size aim', () => navTo('studio/length'));
    add('Open Money', 'Spent, left, limit', 'money cost spend spent spending limit paid budget cents dollars price how much', () => navTo('studio/money'));
    add('Open Voice', 'How it sounds', 'voice style sound never use words tone', () => navTo('studio/voice'));
    add('Open Models', 'Who writes and who reads', 'model models writer writing practice live which who writes reads engine', () => navTo('studio/models'));
    add('Open History', 'Undo and redo your edits', 'history undo redo take back edit rewrite revert', () => navTo('studio/history'));
    add('Open Support details', 'Versions and how episodes were read', 'support details technical help version fingerprint read', () => navTo('studio/details'));
    add('Ask about the story', 'Ideas only, nothing changes', 'ask chat idea talk question discuss who knows what why', () => focusChat());
    add('Download the manuscript', 'Approved episodes as text', 'export download manuscript save text markdown file copy', () => exportManuscript());
    add('Needs you', 'Decisions waiting for you', 'needs waiting todo check', () => setNeeds(true));
    if (HOME) add('All series', 'Back to your shelf', 'home shelf series library switch', () => { location.href = '/'; });
    add('Use dark mode', 'Night theme', 'dark theme night screen appearance', () => setTheme('dark'));
    add('Use light mode', 'Day theme', 'light theme day screen appearance', () => setTheme('light'));
    add('Match my computer', 'Follow system theme', 'system theme auto appearance', () => setTheme('system'));
    add('How this works', `${TOUR.length} short cards`, 'help tour how guide learn legend', () => openTour());
    add('Keyboard shortcuts', 'Keys', 'keys shortcuts keyboard help', () => openSheet({ kind: 'keys' }));
    add('Review the writing logic', 'How the writer decides', 'logic writing review prompt', () => { location.href = '/logic'; });
    eps().forEach((x) => add(`Go to episode ${x.ordinal}`, titleOf(x.ordinal), `episode ${x.ordinal} ${intention(x.ordinal)}`, () => navTo('write/' + x.ordinal)));
    return it;
  }
  function renderPalette() {
    const q = $('pal-input').value;
    const toks = tokens(q);
    const all = buildPalette();
    let out;
    if (!toks.length) out = all.filter((i) => !/^Go to episode/.test(i.label)).slice(0, 9);
    else {
      const need = Math.max(1, Math.ceil(toks.length * 0.5));
      out = all.map((i, idx) => {
        const labelWords = i.label.toLowerCase();
        const m = matched(i.kw, toks);
        const bonus = toks.reduce((s, t) => s + (labelWords.includes(t) ? 2 : 0), 0);
        return { i, idx, m, score: m * 3 + bonus };
      }).filter((x) => x.m >= need).sort((a, b) => b.m - a.m || b.score - a.score || a.idx - b.idx).map((x) => x.i).slice(0, 12);
    }
    if (q.trim() && S && S.story && S.memory.accepted.length) out.push({ label: `Search facts for "${q.trim()}"`, hint: 'Memory', kw: '', fn: () => { mem.q = q.trim(); mem.kind = 'all'; mem.eps.clear(); mem.shown = 80; mem.sel = null; route.person = 'all'; navTo('memory/all'); } });
    const num = q.match(/(?:^|\s)(?:go to |open |show )?(?:episode|ep|chapter)?\s*(\d{1,3})\s*$/i);
    if (num && S && S.story && !inFirstRun()) {
      const want = Number(num[1]);
      out = out.filter((i) => { const m = /^Go to episode (\d+)$/.exec(i.label); return !m || Number(m[1]) === want; });
      const exact = all.find((i) => i.label === `Go to episode ${want}`);
      if (exact && !out.includes(exact)) out.unshift(exact);
      else if (exact) { out.splice(out.indexOf(exact), 1); out.unshift(exact); }
    }
    if (q.trim() && out.every((i) => /^Search facts for/.test(i.label)) && S && S.story && !inFirstRun()) {
      out = [
        ...out,
        { label: `Ask the chat: "${q.trim().slice(0, 40)}"`, hint: 'Ideas only', kw: '', fn: () => focusChat(q.trim()) },
        ...all.filter((i) => /^Go to (Plan|Write|Memory)$|^Open Money$/.test(i.label)),
      ];
    }
    palItems = out;
    palSel = Math.min(palSel, Math.max(0, out.length - 1));
    $('pal-list').innerHTML = out.map((i, k) => `<li role="option" id="pal-${k}" data-pal="${k}" aria-selected="${k === palSel}"><span>${esc(i.label)}</span><small>${esc(i.hint)}</small></li>`).join('');
    $('pal-input').setAttribute('aria-activedescendant', out.length ? 'pal-' + palSel : '');
    $('pal-empty').hidden = Boolean(out.length);
  }
  function openPalette() {
    sess.palFrom = keyOf(document.activeElement);
    $('pal-input').value = ''; palSel = 0;
    renderPalette();
    showDialog($('palette'));
    $('pal-input').focus();
  }
  function runPalette(k) { const i = palItems[k]; if (!i) return; $('palette')._from = null; hideDialog($('palette')); setTimeout(() => i.fn(), reduced() ? 0 : 60); }
  function openTour() { sess.tourStep = 0; openSheet({ kind: 'tour' }); }
  function setTheme(t) { ui.theme = t; render(); say(t === 'system' ? 'Matching your computer.' : t === 'dark' ? 'Dark mode on.' : 'Light mode on.'); }

  // ---------- chat ----------
  const CHAT_MAX = 80;
  const newId = (p) => p + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
  const isPhone = () => matchMedia('(max-width:599px), (max-height:599px) and (max-width:1023px)').matches;
  const isTablet = () => matchMedia('(min-width:600px) and (max-width:1023px) and (min-height:600px)').matches;
  function autoTarget() {
    if (!S || !S.story || inFirstRun()) return 'story';
    if (route.room === 'plan') return 'arc';
    if (route.room === 'memory') return 'story';
    const e = currentEp();
    return e ? 'episode:' + e.ordinal : 'story';
  }
  function chatTarget() {
    const m = ui.scopeMode;
    if (!m || m === 'auto') return autoTarget();
    if (m === 'episode') { const e = currentEp(); return e ? 'episode:' + e.ordinal : 'story'; }
    return m;
  }
  function scopeLabel(t) {
    if (t === 'skeleton') return 'the direction';
    if (t === 'arc') return 'the plan';
    if (t && t.startsWith('episode:')) return 'episode ' + t.split(':')[1];
    return 'the whole story';
  }
  const thinkLabel = (t) => (t && t.startsWith('episode:') ? 'Episode ' + t.split(':')[1] : scopeLabel(t));
  function setPane(p) {
    sess.pane = p;
    if (p === 'chat') sess.chatDot = false;
    renderChat();
    if (p === 'book') requestAnimationFrame(() => { layoutThread(); layoutWide(); });
    else requestAnimationFrame(() => scrollNewest(true));
  }
  function setDock(h) { sess.dock = h; renderChat(); if (h !== 'peek') requestAnimationFrame(() => scrollNewest(true)); }
  function layoutWide() {
    const w = $('book') ? $('book').clientWidth : 0;
    document.body.dataset.wide = w >= 1100 ? 'yes' : 'no';
    renderChat();
  }

  // ---------- orb: the model's presence, shown only while a call is pending ----------
  const orbHtml = (state, size) => `<span class="orb${size === 'lg' ? ' lg' : ''}" data-s="${state}" aria-hidden="true"><i class="o-r"></i><i class="o-a"></i><i class="o-c"></i><i class="o-g"></i></span>`;
  const statusHtml = (state, size, text) => `<span class="orbwrap" role="status">${orbHtml(state, size)}<span class="otext">${esc(text)}</span></span>`;
  async function withCall(kind, text, extra, fn) {
    sess.call = { kind, text, start: Date.now(), ...extra };
    render();
    try { return await fn(); } finally { sess.call = null; render(); }
  }
  function renderCall() {
    const cw = $('chatwarn');
    const warn = !storageOk ? 'This browser is not keeping your unsent text. Copy it before you reload.' : offline ? "Can't reach your story. What you type is kept on this device." : '';
    cw.hidden = !warn;
    if (warn && cw.dataset.t !== warn) { cw.dataset.t = warn; cw.innerHTML = `<p>${esc(warn)}</p>${!storageOk ? btn('copy-unsent', 'Copy unsent text', { cls: 'plain' }) : ''}`; }
    const chip = $('memchip');
    const c = sess.call;
    const on = Boolean(c && (c.kind === 'save' || c.kind === 'read'));
    chip.hidden = !on;
    if (on && $('memchip-text').textContent !== c.text) $('memchip-text').textContent = c.text;
  }

  // ---------- one marker to Memory, invoker tracking, keyboard viewport ----------
  function flyMarker(from, k) {
    const tab = document.querySelector('#rooms [data-nav="memory"]');
    if (!from || !tab || reduced() || !tab.animate) return;
    const to = tab.getBoundingClientRect();
    const g = document.createElement('div');
    g.className = 'flyobj marker mono';
    g.textContent = `+${k}`;
    g.style.setProperty('left', from.left + from.width / 2 - 20 + 'px'); g.style.setProperty('top', from.top + from.height / 2 - 14 + 'px');
    $('flight').appendChild(g);
    const dx = to.left + to.width / 2 - (from.left + from.width / 2), dy = to.top + to.height / 2 - (from.top + from.height / 2);
    const a = g.animate([{ transform: 'translate(0,0)', opacity: 0 }, { transform: 'translate(0,-4px)', opacity: 1, offset: 0.2 }, { transform: `translate(${dx}px,${dy}px)`, opacity: 1, offset: 0.85 }, { transform: `translate(${dx}px,${dy}px)`, opacity: 0 }], { duration: 400, easing: 'cubic-bezier(0.2,0,0,1)', fill: 'forwards' });
    a.onfinish = () => { g.remove(); tab.animate([{ transform: 'scale(1.08)' }, { transform: 'none' }], { duration: 240, easing: 'cubic-bezier(0.2,0,0,1)' }); };
    a.oncancel = () => g.remove();
  }
  document.addEventListener('keydown', () => { sess.invoker = null; }, true);
  document.addEventListener('click', (ev) => { const b = ev.target.closest && ev.target.closest('button, a, [role="button"]'); if (b) sess.invoker = b; }, true);
  if (window.visualViewport) {
    const vv = () => document.documentElement.style.setProperty('--vvh', window.visualViewport.height + 'px');
    window.visualViewport.addEventListener('resize', vv); window.visualViewport.addEventListener('scroll', vv); vv();
  }

  // ---------- events and glyphs ----------
  const GLYPH = {
    slip: '<svg viewBox="0 0 12 12" aria-hidden="true"><rect x="1.5" y="2.5" width="9" height="7" rx="1" fill="none" stroke="currentColor" stroke-width="1.2" stroke-dasharray="2 1.6"/></svg>',
    adopt: '<svg viewBox="0 0 12 12" aria-hidden="true"><circle cx="6" cy="6" r="3" fill="currentColor"/></svg>',
    seal: '<svg viewBox="0 0 12 12" aria-hidden="true"><circle cx="6" cy="6" r="4.6" fill="none" stroke="currentColor" stroke-width="1.2"/><circle cx="6" cy="6" r="2" fill="currentColor"/></svg>',
    thread: '<svg viewBox="0 0 12 12" aria-hidden="true"><path d="M6 1v10" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/><circle cx="6" cy="3.5" r="1.4" fill="currentColor"/><circle cx="6" cy="8.5" r="1.4" fill="currentColor"/></svg>',
    back: '<svg viewBox="0 0 12 12" aria-hidden="true"><path d="M8.5 3L4 6l4.5 3" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    draft: '<svg viewBox="0 0 12 12" aria-hidden="true"><path d="M2.5 3.5h7M2.5 6h7M2.5 8.5h4" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/></svg>',
  };
  function chatEvent(kind, text) {
    ui.chat.push({ id: newId('e'), who: 'event', kind, text, ts: Date.now() });
    if (ui.chat.length > CHAT_MAX) ui.chat = ui.chat.slice(-CHAT_MAX);
    persist(); renderChat();
  }
  const itemName = (it) => {
    if (it.kind === 'para') return `Paragraph ${it.n} wording`;
    if (it.kind === 'line') return `Plan line ${it.index + 1}`;
    return { premise: 'Premise', spine: 'Spine', private: 'Private note', purpose: 'Purpose' }[it.kind];
  };

  // ---------- composer and log ----------
  let chatTick = 0;
  function chipAct(act, label, m, extra) {
    return `<button type="button" class="chipact" data-action="${act}" data-msg="${m.id}"${extra ? ' ' + extra : ''}>${esc(label)}</button>`;
  }
  function actionsHtml(m) {
    const bits = [chipAct('copy-msg', 'Copy', m), chipAct('ask-again', 'Ask again', m)];
    return `<div class="acts msgacts">${bits.join('')}</div>`;
  }
  function readLine(m) {
    if (m.read === undefined) return '';
    return `<p class="cread">${m.read.length ? 'Read: ' + esc(m.read.join(', ')) + '.' : 'Read: only your message.'}</p>`;
  }
  function msgParts(m) {
    if (m.who === 'event') return { outer: `<div class="crow event" data-id="${m.id}" data-kind="${esc(m.kind)}">${GLYPH[m.kind] || GLYPH.draft}<span>${esc(m.text)}</span></div>`, extra: null };
    if (m.who === 'me') {
      const err = m.failed ? (m.why === 'secret_in_message' ? '<p class="cerr" role="alert">That names a protected secret word, so nothing was sent. Say it another way.</p>' : `<p class="cerr" role="alert">That didn't come through. Nothing was changed. ${btn('retry-chat', 'Try again', { cls: 'link', extra: `data-msg="${m.id}"` })}</p>`) : '';
      const where = scopeLabel(m.scope) + (m.para ? `, paragraph ${m.para}` : '');
      return { outer: `<div class="crow me" data-id="${m.id}"><div class="cbub wrap">${esc(m.text)}</div><span class="mono cmeta">About ${esc(where)}</span><div class="rextra" aria-live="off"></div></div>`, extra: err };
    }
    const staged = ui.staged.filter((s) => s.msg === m.id);
    const used = (m.used || []).map((u) => `<p class="usedline mono">${esc(u.text)}</p>`).join('');
    const waiting = staged.map((s) => `<p class="usedline mono waiting">On the page: ${esc(itemName(s))}. ${btn('stage-show', 'Show it', { cls: 'link', extra: `data-stage="${s.id}"` })}</p>`).join('');
    return { outer: `<div class="crow reply" data-id="${m.id}"><span class="mono cwho">${live() ? 'Writer' : 'Practice writer'}</span><div class="rtext wrap" data-msg="${m.id}">${esc(m.text)}</div>${readLine(m)}<div class="rextra" aria-live="off"></div></div>`, extra: actionsHtml(m) + waiting + used };
  }
  const STARTERS = {
    first: ['Help me find my premise', 'What makes a strong spine?', 'Suggest a twist for the middle'],
    write: ['Where does this drag?', 'Does she know too much here?', 'Tighten the last paragraph'],
    plan: ['Suggest a stronger ending for the middle', 'Which episodes feel thin?', 'Give me three ways to open episode 2'],
    memory: ['Who knows about the ledger?', 'What did Mara promise?', 'Where could a secret hide?'],
  };
  const startKey = () => (inFirstRun() || !arcN() ? 'first' : route.room);
  const PLACEHOLDER = { write: 'Ask about the episode', plan: 'Shape the plan', memory: 'Ask about a person or fact' };
  const rowHtml = new WeakMap();
  let lastRows = 0;

  function chipsHtml() {
    const t = chatTarget();
    const manual = (ui.scopeMode || 'auto') !== 'auto';
    const lab = scopeLabel(t);
    let h = '';
    if (manual) h += btn('chip-follow', 'Follow the room', { cls: 'cchip-btn' });
    const f = sess.sel && route.room === 'write' && t.startsWith('episode:') ? findBlock(sess.sel) : null;
    if (f && f.e.ordinal === Number(t.split(':')[1])) {
      const n = f.e.blocks.indexOf(f.b) + 1, w = f.b.text.split(/\s+/).filter(Boolean).length;
      h += `<span class="cchip">Paragraph ${n}, ${plural(w, 'word')}<button type="button" class="cx" data-action="chip-sel-clear" aria-label="Stop using paragraph ${n}"><svg viewBox="0 0 12 12" aria-hidden="true"><path d="M3 3l6 6M9 3L3 9" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg></button></span>`;
    }
    return h;
  }

  const SCOPES = [
    ['auto', 'Follows the room', 'Talks about whatever you have open: the plan in Plan, an episode in Write, the whole story in Memory.'],
    ['story', 'The whole story', 'Sends your premise and spine, the plan with one line per episode, the text of your approved episodes (the latest ones if there are many) and the last few messages.'],
    ['skeleton', 'The direction', 'Sends your premise and spine and the last few messages. Nothing else.'],
    ['arc', 'The plan', 'Sends the premise, the spine, the purpose of this stretch, every episode line and the last few messages. No episode text.'],
    ['episode', 'The current episode', "Sends the premise and spine, this episode's job, its full text and the last few messages."],
  ];
  const CHECK_SVG = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3.5 8.5l3 3 6-7" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  function scopeOptions() { return SCOPES.filter(([v]) => v !== 'episode' || (S && S.story && arcN())); }
  function renderScope() {
    const mode = ui.scopeMode || 'auto';
    const opts = scopeOptions();
    const cur = opts.find((o) => o[0] === mode) || opts[0];
    const key = opts.map((o) => o[0]).join('|') + '#' + cur[0];
    const btnEl = $('scope-btn');
    if (btnEl.dataset.k === key) return;
    btnEl.dataset.k = key;
    $('scope-label').textContent = cur[1];
    btnEl.title = cur[2] + ' Click to change what this chat sends.';
    btnEl.setAttribute('aria-label', 'What this chat sends: ' + cur[1] + '. ' + cur[2]);
    $('scopemenu').innerHTML = opts.map(([v, l, d]) => `<button type="button" class="sopt" role="option" data-action="scope-pick" data-v="${v}" aria-selected="${v === cur[0]}"><b>${esc(l)}</b>${CHECK_SVG}<span>${esc(d)}</span></button>`).join('')
      + '<p class="snote">Private notes are never included. Under each reply you can see what was read.</p>';
  }
  function setScopeOpen(open) {
    const menu = $('scopemenu'), b = $('scope-btn');
    menu.hidden = !open;
    b.setAttribute('aria-expanded', String(open));
    if (open) { const sel = menu.querySelector('[aria-selected="true"]') || menu.querySelector('.sopt'); if (sel) sel.focus({ preventScroll: true }); }
  }
  function renderChat() {
    renderCall();
    const phone = isPhone(), tablet = isTablet();
    document.body.dataset.chat = ui.focus ? 'off' : 'on';
    document.body.dataset.pane = sess.pane;
    document.body.dataset.dock = sess.dock || 'peek';
    document.body.dataset.reading = sess.reading ? 'yes' : 'no';
    renderBar();
    const solo = phone && sess.pane === 'chat';
    $('chat').setAttribute('role', solo ? 'main' : 'complementary');
    $('chat-h1').hidden = !solo;
    const dockBtn = $('dock-cycle');
    dockBtn.setAttribute('aria-label', (sess.dock || 'peek') === 'peek' ? 'Open chat' : (sess.dock === 'half' ? 'Make chat taller' : 'Shrink chat'));
    renderScope();
    $('chat-hide').setAttribute('aria-pressed', String(Boolean(ui.focus)));
    $('chat-open').hidden = !ui.focus;
    $('chat-title').textContent = 'Chat about ' + scopeLabel(chatTarget());
    $('writerchip').textContent = live() ? 'Writer: live' : 'Writer: practice';
    const chips = chipsHtml();
    if ($('chips').dataset.h !== chips) {
      const had = $('chips').contains(document.activeElement);
      $('chips').innerHTML = chips; $('chips').dataset.h = chips;
      if (had) { const f = $('chips').querySelector('button'); (f || $('composer')).focus({ preventScroll: true }); }
    }
    const composer = $('composer');
    $('send').disabled = Boolean(sess.thinking);
    if (document.activeElement !== composer && composer.value !== (ui.composer || '')) { composer.value = ui.composer || ''; growComposer(); }
    composer.placeholder = inFirstRun() || !arcN() ? 'Think out loud about your story...' : PLACEHOLDER[route.room] || PLACEHOLDER.write;
    const log = $('chatlog'), box = $('chatscroll');
    const nearEnd = box.scrollHeight - box.scrollTop - box.clientHeight < 140;
    const tpl = document.createElement('template');
    let empty = $('chatempty');
    if (!ui.chat.length && !sess.thinking) {
      if (!empty) { empty = document.createElement('div'); empty.id = 'chatempty'; empty.className = 'empty-chat'; log.prepend(empty); }
      const k = startKey();
      if (empty.dataset.k !== k) {
        empty.dataset.k = k;
        empty.innerHTML = `<div class="acts">${STARTERS[k].map((s) => `<button type="button" class="chipact starter" data-action="starter" data-text="${esc(s)}">${esc(s)}</button>`).join('')}</div>`;
      }
    } else if (empty) { empty.remove(); empty = null; }
    let prev = empty;
    const ids = new Set();
    ui.chat.forEach((m) => {
      const p = msgParts(m);
      ids.add(m.id);
      let el = log.querySelector(`[data-id="${m.id}"]`);
      if (!el) { tpl.innerHTML = p.outer; el = tpl.content.firstElementChild; }
      if (p.extra !== null) {
        const x = el.querySelector('.rextra');
        if (rowHtml.get(x) !== p.extra && !(document.activeElement && document.activeElement.tagName === 'SELECT' && x.contains(document.activeElement))) { x.innerHTML = p.extra; rowHtml.set(x, p.extra); }
      }
      if (m.who === 'reply') { const rt = el.querySelector('.rtext'); if (rt) rt.classList.toggle('slipped', ui.staged.some((s) => s.msg === m.id)); }
      const want = prev ? prev.nextElementSibling : log.firstElementChild;
      if (want !== el) log.insertBefore(el, want);
      prev = el;
    });
    [...log.children].forEach((c) => { if (c.id !== 'chatempty' && c.id !== 'thinking' && !ids.has(c.dataset.id)) c.remove(); });
    let think = $('thinking');
    if (sess.thinking) {
      if (!think) {
        think = document.createElement('div'); think.id = 'thinking'; think.className = 'crow reply thinking';
        think.innerHTML = `<span class="mono cwho">${live() ? 'Writer' : 'Practice writer'}</span><p class="think">${orbHtml('reasoning', 'sm')}<span>Thinking about ${esc(thinkLabel(sess.thinking.target))}</span></p><p class="mono" data-cslow hidden>Still working. You can keep reading.</p>`;
      }
      log.appendChild(think);
    } else if (think) think.remove();
    const lastReply = [...ui.chat].reverse().find((m) => m.who === 'reply');
    const peek = $('peekline');
    peek.textContent = sess.thinking ? 'Thinking...' : lastReply ? lastReply.text.replace(/\s+/g, ' ').slice(0, 120) : 'Open chat';
    peek.hidden = !tablet;
    markSel();
    const rows = ui.chat.length + (sess.thinking ? 1 : 0);
    if (rows > lastRows && lastRows !== 0 && (nearEnd || sess.thinking)) scrollNewest(false);
    if (!lastRows && rows) requestAnimationFrame(() => scrollNewest(true));
    lastRows = rows;
    updateJump();
  }
  function growComposer() {
    const c = $('composer');
    c.style.setProperty('height', 'auto');
    c.style.setProperty('height', Math.min(c.scrollHeight, 160) + 'px');
  }
  function scrollNewest(instant) {
    const box = $('chatscroll');
    box.scrollTo({ top: box.scrollHeight, behavior: instant || reduced() ? 'auto' : 'smooth' });
  }
  function updateJump() {
    const box = $('chatscroll');
    $('jump').hidden = box.scrollHeight - box.scrollTop - box.clientHeight < 160;
  }
  function markSel() { /* selection tracking only feeds Copy now */ }
  function startChatTimer() {
    clearInterval(chatTick);
    chatTick = setInterval(() => {
      if (!sess.thinking) { clearInterval(chatTick); return; }
      const s = Math.floor((Date.now() - sess.thinking.start) / 1000);
      document.querySelectorAll('[data-cslow]').forEach((t) => { t.hidden = s < 8; });
    }, 1000);
  }
  document.addEventListener('selectionchange', () => {
    const s = getSelection();
    if (!s || s.isCollapsed || !s.rangeCount) return;
    const node = s.anchorNode && (s.anchorNode.nodeType === 1 ? s.anchorNode : s.anchorNode.parentElement);
    const r = node && node.closest ? node.closest('.rtext') : null;
    if (r && r.contains(s.focusNode)) {
      const text = s.toString().trim();
      if (text) { sess.chatSel = { id: r.dataset.msg, text, rect: s.getRangeAt(0).getBoundingClientRect() }; markSel(); }
    }
  });
  document.addEventListener('pointerdown', (ev) => {
    const t = ev.target.closest ? ev.target : ev.target.parentElement;
    if (sess.chatSel && !(t.closest && t.closest('.chipact, .rtext, .picker'))) { sess.chatSel = null; markSel(); }
    if (!$('scopemenu').hidden && !(t.closest && t.closest('#scopemenu, #scope-btn'))) setScopeOpen(false);
  });
  document.addEventListener('click', (ev) => { sess.kbd = ev.detail === 0; }, true);

  async function sendChat(textIn) {
    const el = $('composer');
    const text = String(textIn !== undefined ? textIn : el.value).trim();
    if (!text || sess.thinking) { if (!text) el.focus(); return; }
    let target = chatTarget();
    const mention = text.match(/\bepisode\s+(\d{1,2})\b/i);
    if ((ui.scopeMode || 'auto') === 'auto' && mention && S && S.story && ep(Number(mention[1]))) target = 'episode:' + Number(mention[1]);
    let para = 0, sent = text;
    if (target.startsWith('episode:') && sess.sel && route.room === 'write') {
      const f = findBlock(sess.sel);
      if (f && f.e.ordinal === Number(target.split(':')[1])) { para = f.e.blocks.indexOf(f.b) + 1; sent = `About paragraph ${para}: "${f.b.text.slice(0, 240)}"\n${text}`; }
    }
    const mine = { id: newId('m'), who: 'me', text, scope: target, para, ts: Date.now() };
    ui.chat.push(mine);
    ui.composer = ''; el.value = ''; growComposer();
    sess.menu = null;
    sess.thinking = { start: Date.now(), target };
    if (isTablet() && (sess.dock || 'peek') === 'peek') sess.dock = 'half';
    persist(); renderChat(); scrollNewest(false); startChatTimer(); say('Sent. Thinking.');
    try {
      if (!S || !S.story) { await api('create_story', {}); S = await getJson(BASE + '/api/v1/state'); render(); }
      const out = await api('converse', { target, text: sent });
      ui.chat.push({ id: newId('m'), who: 'reply', text: out.text, scope: target, ts: Date.now(), used: [], read: Array.isArray(out.read) ? out.read : [] });
      if (ui.chat.length > CHAT_MAX) ui.chat = ui.chat.slice(-CHAT_MAX);
      if (isPhone() && sess.pane === 'book') sess.chatDot = true;
      say('Reply from the writer. Your story did not change.');
    } catch (e) {
      mine.failed = true;
      mine.why = e && e.code === 'secret_in_message' ? 'secret_in_message' : '';
      say(mine.why ? 'Nothing was sent. That names a protected secret word.' : "That didn't come through. Nothing was changed.");
    } finally {
      sess.thinking = null; clearInterval(chatTick);
      persist(); renderChat(); scrollNewest(false);
    }
  }
  function focusChat(prefill) {
    if (ui.focus) { ui.focus = false; render(); }
    if (isPhone()) setPane('chat');
    else if (isTablet()) setDock('half');
    if (prefill) { ui.composer = prefill; $('composer').value = prefill; persist(); growComposer(); }
    const c = $('composer');
    setTimeout(() => { c.focus(); c.setSelectionRange(c.value.length, c.value.length); }, 30);
  }

  // ---------- slips ----------
  function replyText(m) {
    if (sess.chatSel && sess.chatSel.id === m.id && sess.chatSel.text) return sess.chatSel.text;
    return m.text.trim();
  }
  function sourceRect(m, btnEl) {
    if (sess.chatSel && sess.chatSel.id === m.id && sess.chatSel.rect && sess.chatSel.rect.width) return sess.chatSel.rect;
    const r = document.querySelector(`.rtext[data-msg="${m.id}"]`);
    return (r || btnEl).getBoundingClientRect();
  }
  const stagedFor = (kind, key) => ui.staged.filter((s) => s.kind === kind && (key === undefined || s.index === key || s.block === key));
  function diffPair(oldT, newT) {
    const a = oldT.split(/(\s+)/), b = newT.split(/(\s+)/);
    const aw = a.map((t, i) => [t, i]).filter(([t]) => t.trim()), bw = b.map((t, i) => [t, i]).filter(([t]) => t.trim());
    const dp = Array.from({ length: aw.length + 1 }, () => new Array(bw.length + 1).fill(0));
    for (let i = aw.length - 1; i >= 0; i -= 1) for (let j = bw.length - 1; j >= 0; j -= 1) dp[i][j] = aw[i][0] === bw[j][0] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
    const sa = new Set(), sb = new Set();
    let i = 0, j = 0;
    while (i < aw.length && j < bw.length) {
      if (aw[i][0] === bw[j][0]) { sa.add(aw[i][1]); sb.add(bw[j][1]); i += 1; j += 1; } else if (dp[i + 1][j] >= dp[i][j + 1]) i += 1; else j += 1;
    }
    return [a.map((t, k) => (!t.trim() || sa.has(k) ? esc(t) : `<s>${esc(t)}</s>`)).join(''), b.map((t, k) => (!t.trim() || sb.has(k) ? esc(t) : `<u>${esc(t)}</u>`)).join('')];
  }
  function stagedHtml(it, now) {
    const para = it.kind === 'para';
    const head = 'Suggestion for ' + (para ? `Paragraph ${it.n}` : it.kind === 'line' ? `line ${it.index + 1}` : { premise: 'premise', spine: 'spine', private: 'private note', purpose: 'purpose' }[it.kind]);
    const noArc = (it.kind === 'purpose' || it.kind === 'line') && !(S.governing && S.governing.arc);
    const main = para ? btn('use-staged-wording', 'Adopt', { cls: 'btn adopt slipbtn', extra: `data-stage="${it.id}"` })
      : btn('adopt-staged', noArc ? 'Put in plan' : 'Adopt', { cls: 'btn adopt slipbtn', extra: `data-stage="${it.id}" aria-label="Adopt ${esc(head.replace('Suggestion for ', ''))}"` });
    const stale = para && it.base && (() => { const f = findBlock(it.block); return f && f.b.sha256 !== it.base; })();
    const [o, n] = diffPair(now || '', it.text);
    const same = (now || '').trim() === it.text.trim();
    const old = Date.now() - (it.ts || Date.now()) > 864e5;
    return `<div class="slip${para ? ' proseish' : ''}" id="stage-${it.id}" data-stage="${it.id}" data-kind="${it.kind}"${old ? ' data-old="yes"' : ''} role="group" aria-labelledby="slh-${it.id}"><p class="slip-h" id="slh-${it.id}">${esc(head)}</p>
<div class="slip-body"><p class="wrap sug">${n}</p>${same ? '<p class="mono">Same as now.</p>' : ''}${now && !same ? `<details class="cmp"><summary>Compare</summary><p class="wrap now">${o}</p></details>` : ''}</div>
${stale ? '<p class="warn-line">This paragraph changed since the suggestion.</p>' : ''}<div class="erow">${main}${btn('keep-staged', 'Put back', { cls: 'btn plain slipbtn', extra: `data-stage="${it.id}"` })}${btn('show-source', 'From chat', { cls: 'link', extra: `data-msg="${it.msg}"` })}</div></div>`;
  }
  function stagedDirHtml() {
    const gov = S.governing.skeleton;
    if (!gov) return '';
    return ['premise', 'spine', 'private'].flatMap((k) => stagedFor(k).map((it) => stagedHtml(it, gov.content[k] || ''))).join('');
  }
  const stagedPurpose = () => stagedFor('purpose').map((it) => stagedHtml(it, S.governing.arc ? S.governing.arc.content.purpose : form('purpose', ''))).join('');
  const stagedLine = (i) => stagedFor('line', i).map((it) => stagedHtml(it, lineVal(i))).join('');
  const stagedPara = (b) => stagedFor('para', b.block_id).map((it) => stagedHtml(it, b.text)).join('');

  function flySlip(from, el) {
    if (!el) return;
    const body = el.querySelector('.slip-body');
    if (!from || reduced() || !el.animate) {
      el.classList.add('ring');
      if (el.animate) el.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 160, easing: 'cubic-bezier(0.2,0,0,1)' });
      setTimeout(() => el.classList.remove('ring'), 1200);
      return;
    }
    const to = el.getBoundingClientRect();
    const dx = from.left - to.left, dy = from.top - to.top;
    el.classList.add('flying');
    const std = 'cubic-bezier(0.2,0,0,1)', emph = 'cubic-bezier(0.3,0,0,1)';
    const a = el.animate([
      { transform: `translate(${dx}px,${dy}px)`, opacity: 0, offset: 0, easing: emph },
      { transform: 'translate(0,0)', opacity: 1, offset: 0.35, easing: std },
      { transform: 'translate(0,0)', opacity: 1, offset: 1 },
    ], { duration: 360, fill: 'backwards' });
    if (body) body.animate([{ opacity: 0, offset: 0 }, { opacity: 0, offset: 0.7 }, { opacity: 1, offset: 1 }], { duration: 360, easing: 'linear', fill: 'backwards' });
    sess.fly = a;
    const done = () => { el.classList.remove('flying'); if (sess.fly === a) sess.fly = null; el.classList.add('landed'); setTimeout(() => el.classList.remove('landed'), 700); };
    a.onfinish = done;
    a.oncancel = () => { el.classList.remove('flying'); if (sess.fly === a) sess.fly = null; };
  }
  function flyDot(from) {
    const tab = $('pane-book');
    if (!from || !tab) return;
    const to = tab.getBoundingClientRect();
    if (reduced() || !tab.animate) return;
    const g = document.createElement('div');
    g.className = 'flyobj';
    g.style.setProperty('left', from.left + 'px'); g.style.setProperty('top', from.top + 'px');
    g.style.setProperty('width', Math.max(120, Math.min(from.width, 300)) + 'px');
    $('flight').appendChild(g);
    const dx = to.left + to.width / 2 - from.left - 10, dy = to.top + to.height / 2 - from.top - 10;
    const a = g.animate([
      { transform: 'translate(0,-4px) scale(1)', opacity: 0, offset: 0 },
      { transform: 'translate(0,-4px) scale(1)', opacity: 1, offset: 0.21 },
      { transform: `translate(${dx}px,${dy}px) scale(.08)`, opacity: 1, offset: 0.9 },
      { transform: `translate(${dx}px,${dy}px) scale(.08)`, opacity: 0, offset: 1 },
    ], { duration: 560, easing: 'cubic-bezier(0.3,0,0,1)', fill: 'forwards' });
    a.onfinish = () => g.remove();
    a.oncancel = () => g.remove();
  }
  function revealStaged(it, from, show) {
    const phone = isPhone();
    if (show && phone) setPane('book');
    if (isTablet()) setDock('peek');
    route.studio = null;
    if (it.kind === 'para') { route.room = 'write'; route.ep = it.ep; } else route.room = 'plan';
    render();
    if (phone && !show) { flyDot(from); return; }
    requestAnimationFrame(() => {
      const el = $('stage-' + it.id);
      if (!el) return;
      const r = el.getBoundingClientRect();
      window.scrollTo({ top: Math.max(0, window.scrollY + r.top - window.innerHeight * 0.4), behavior: 'instant' });
      flySlip(show ? null : from, el);
      if (sess.kbd) { const b = el.querySelector('.btn.adopt'); if (b) b.focus({ preventScroll: true }); }
    });
  }
  function removeStaged(id) { ui.staged = ui.staged.filter((s) => s.id !== id); persist(); }
  function finishStaged(it, where) {
    removeStaged(it.id);
    const m = ui.chat.find((x) => x.id === it.msg);
    if (m) { m.used = m.used || []; m.used.push({ text: 'Used in ' + where + '.', at: Date.now() }); }
    ui.chat.push({ id: newId('e'), who: 'event', kind: 'adopt', text: `Adopted: ${itemName(it)}.`, ts: Date.now() });
    persist(); renderChat(); render();
    flash('Used in ' + where + '.');
  }
  const chatActions = {
    'toggle-focus': () => {
      ui.focus = !ui.focus; render(); layoutWide();
      const f = ui.focus ? $('chat-open') : $('composer');
      if (f) f.focus({ preventScroll: true });
    },
    'switch-pane': (t) => setPane(t.dataset.pane),
    'dock-cycle': () => setDock({ peek: 'half', half: 'full', full: 'peek' }[sess.dock || 'peek']),
    'dock-set': (t) => { setDock(t.dataset.h || 'half'); $('composer').focus(); },
    'ask-open': () => focusChat(),
    'ask-para': (t) => {
      sess.sel = t.dataset.block;
      ui.scopeMode = 'auto';
      focusChat();
      render();
    },
    starter: (t) => sendChat(t.dataset.text),
    send: () => sendChat(),
    jump: () => scrollNewest(false),
    'copy-msg': async (t) => {
      const m = ui.chat.find((x) => x.id === t.dataset.msg);
      if (!m) return;
      try { await navigator.clipboard.writeText(replyText(m)); flash('Copied.'); } catch (_) { flash('Select the text and copy it.'); }
    },
    'ask-again': (t) => {
      const i = ui.chat.findIndex((x) => x.id === t.dataset.msg);
      const q = ui.chat.slice(0, i).reverse().find((x) => x.who === 'me');
      if (q) sendChat(q.text);
    },
    'retry-chat': (t) => {
      const m = ui.chat.find((x) => x.id === t.dataset.msg);
      if (!m) return;
      ui.chat = ui.chat.filter((x) => x.id !== m.id);
      persist(); sendChat(m.text);
    },
    'scope-toggle': () => { setScopeOpen($('scopemenu').hidden); },
    'scope-pick': (t) => { ui.scopeMode = t.dataset.v; persist(); setScopeOpen(false); $('scope-btn').focus({ preventScroll: true }); renderChat(); },
    'chip-detach': () => { ui.scopeMode = 'story'; persist(); renderChat(); },
    'chip-follow': () => { ui.scopeMode = 'auto'; persist(); renderChat(); },
    'chip-sel-clear': () => { sess.sel = null; document.querySelectorAll('.para.sel').forEach((p) => p.classList.remove('sel')); renderChat(); },
    'stage-show': (t) => {
      const id = t.dataset.stage || (ui.staged[0] && ui.staged[0].id);
      const it = ui.staged.find((s) => s.id === id);
      if (it) revealStaged(it, null, true);
    },
    'show-source': (t) => {
      if (isPhone()) setPane('chat'); else if (isTablet()) setDock('half');
      requestAnimationFrame(() => {
        const row = document.querySelector(`#chatlog [data-id="${t.dataset.msg}"]`);
        if (!row) { flash('That message is no longer in the chat.'); return; }
        row.scrollIntoView({ block: 'center', behavior: 'auto' });
        row.classList.add('hl'); setTimeout(() => row.classList.remove('hl'), 1400);
      });
    },
    'keep-staged': (t) => {
      const id = t.dataset.stage;
      const el = $('stage-' + id);
      const finish = () => {
        removeStaged(id);
        chatEvent('back', 'Put back. Nothing changed.');
        render();
        flash('Put back. Nothing changed.');
        const c = $('composer'); if (sess.kbd && c) c.focus({ preventScroll: true });
      };
      if (el && el.animate && !reduced()) {
        const a = el.animate([{ transform: 'translateX(0)', opacity: 1 }, { transform: 'translateX(-8px)', opacity: 0 }], { duration: 200, easing: 'cubic-bezier(0.4,0,1,1)', fill: 'forwards' });
        a.onfinish = finish;
      } else finish();
    },
    'adopt-staged': async (t) => {
      const it = ui.staged.find((s) => s.id === t.dataset.stage);
      if (!it) return;
      if (['premise', 'spine', 'private'].includes(it.kind)) {
        const gov = S.governing.skeleton;
        const content = { ...gov.content };
        if (it.kind === 'private') content.private = it.text; else content[it.kind] = it.text;
        const r = await run('Adopting the direction', () => adoptLayer('skeleton', content));
        if (r.ok) {
          delete ui.forms[it.kind === 'private' ? 'private-note' : it.kind];
          finishStaged(it, 'the direction, as the ' + (it.kind === 'private' ? 'private note' : it.kind));
        }
        return;
      }
      const gov = S.governing.arc;
      if (!gov) {
        if (it.kind === 'purpose') ui.forms.purpose = it.text;
        else { ui.forms['int' + it.index] = it.text; if (it.index + 1 > planCountVal()) ui.forms.count = it.index + 1; }
        finishStaged(it, it.kind === 'purpose' ? 'the plan draft, as its purpose' : `the plan draft, episode ${it.index + 1}`);
        return;
      }
      const content = JSON.parse(JSON.stringify(gov.content));
      if (it.kind === 'purpose') content.purpose = it.text;
      else {
        const e = ep(it.index + 1);
        if (e && e.accepted) { flash(`Episode ${it.index + 1} is approved and locked.`); return; }
        content.intentions[it.index] = it.text;
      }
      const r = await run('Adopting the plan', () => adoptLayer('arc', content));
      if (r.ok) {
        if (it.kind === 'purpose') delete ui.forms.purpose; else { delete ui.forms['int' + it.index]; }
        finishStaged(it, it.kind === 'purpose' ? 'the plan, as its purpose' : `the plan, episode ${it.index + 1}`);
      }
    },
    'use-staged-wording': async (t) => {
      const it = ui.staged.find((s) => s.id === t.dataset.stage);
      if (!it) return;
      const f = findBlock(it.block);
      if (!f || f.e.accepted) { removeStaged(it.id); render(); flash('That paragraph is locked or gone.'); return; }
      const e = f.e;
      if (dirtyBlocks(e).length) { flash('Save or discard your unsaved edits first.'); return; }
      const blocks = e.blocks.map((b) => ({ block_id: b.block_id, text: b.block_id === it.block ? it.text : b.text }));
      const r = await run('Using the wording', () => api('save_revision', { ordinal: e.ordinal, base_revision_id: e.selection.revision_id, blocks }, { selection_cas: e.selection.cas }));
      if (!r.ok) return;
      const flagged = r.out.flagged || [];
      note = { text: 'Adopted.' + (flagged.length ? ` ${capFirst(epList(flagged))} may no longer fit.` : ''), eventId: r.out.event_id };
      const mine = note;
      setTimeout(() => { if (note === mine) { note = null; const el = $('noteline'); if (el) el.remove(); } }, 12000);
      sess.pulseBlocks = [it.block];
      finishStaged(it, `episode ${e.ordinal}, paragraph ${f.e.blocks.findIndex((b) => b.block_id === it.block) + 1}`);
    },
  };

  document.addEventListener('keydown', (ev) => {
    if (ev.altKey && ev.key === '3') {
      const b = document.querySelector('#main .slip .btn.adopt');
      if (b) { ev.preventDefault(); if (isPhone()) setPane('book'); b.focus(); b.scrollIntoView({ block: 'center' }); }
      return;
    }
    if ((ev.ctrlKey || ev.metaKey) && ev.key === '/') { ev.preventDefault(); focusChat(); return; }
    if ((ev.ctrlKey || ev.metaKey) && ev.key === '.') {
      ev.preventDefault();
      if (isPhone()) setPane(sess.pane === 'chat' ? 'book' : 'chat');
      else if (isTablet()) setDock((sess.dock || 'peek') === 'peek' ? 'half' : 'peek');
      else chatActions['toggle-focus']();
      return;
    }
    if (ev.key === 'Escape') {
      if (sess.fly) { sess.fly.finish(); return; }
    }
  });

  // ---------- render ----------
  let focusNext = null, lastView = '', stepFast = false;
  function keyOf(el) {
    if (!el || el === document.body || el === document.documentElement) return null;
    if (el.id) return '#' + el.id;
    const parts = [el.tagName.toLowerCase()];
    for (const [k, v] of Object.entries(el.dataset)) parts.push(`[data-${k.replace(/[A-Z]/g, (m) => '-' + m.toLowerCase())}="${String(v).replace(/"/g, '\\"')}"]`);
    return parts.length > 1 ? parts.join('') : null;
  }
  function viewKey() {
    if (!S) return 'down';
    if (inFirstRun()) return 'first' + (ui.fr || 1);
    if (route.room === 'write') { const e = currentEp(); return 'write' + (e ? e.ordinal : 0) + (sess.fromMem ? ':mb' + sess.fromMem.ep : ''); }
    return route.room + (route.room === 'memory' ? ':' + route.person + ':' + (mem.view || 'list') : '');
  }
  function mainHtml() {
    if (!S) return `<div class="empty"><h1>The desk is not answering</h1><p class="hint">Your story lives on the desk, not on this page. Nothing here was lost.</p>${btn('reload-state', 'Try again', { cls: 'btn tonal' })}</div>`;
    if (inFirstRun()) return firstRunHtml();
    if (route.room === 'plan') return planHtml();
    if (route.room === 'memory') return memoryHtml();
    return pageHtml();
  }
  function render() {
    const act = document.activeElement;
    const key = keyOf(act);
    const caret = act && (act.tagName === 'TEXTAREA' || act.tagName === 'INPUT') && act.closest('#main') ? [act.selectionStart, act.selectionEnd] : null;
    persist(); applyTheme();
    document.body.dataset.mode = !S || inFirstRun() ? 'first' : 'app';
    document.body.dataset.room = route.room;
    renderBar();
    const main = $('main');
    const vk = viewKey();
    const entering = vk !== lastView;
    const firstPaint = lastView === '';
    const scrollY = window.scrollY;
    main.innerHTML = `<div class="view">${mainHtml()}</div>`;
    lastView = vk;
    renderThread();
    renderChat();
    renderDock(); renderBanner(); renderNeeds(); renderSheet(); renderStudio();
    syncHash();
    document.querySelectorAll('[data-theme-set]').forEach((b) => b.setAttribute('aria-pressed', String(ui.theme === b.dataset.themeSet)));
    const view = main.firstElementChild;
    if (entering) {
      window.scrollTo(0, 0);
      if (!reduced() && view.animate && !firstPaint) view.animate(stepFast ? [{ opacity: 0 }, { opacity: 1 }] : [{ opacity: 0, transform: 'translateY(6px)' }, { opacity: 1, transform: 'none' }], { duration: stepFast ? 120 : 200, easing: 'cubic-bezier(.23,1,.32,1)' });
    } else window.scrollTo(0, scrollY);
    if (arrive) {
      arrive = false;
      if (!reduced() && view.animate) view.animate([{ opacity: 0, transform: 'translateY(8px)' }, { opacity: 1, transform: 'none' }], { duration: 320, easing: 'cubic-bezier(.23,1,.32,1)' });
    }
    stepFast = false;
    const target = focusNext ? document.querySelector(focusNext) : key ? document.querySelector(key) : null;
    focusNext = null;
    if (target && target !== document.activeElement) {
      target.focus({ preventScroll: true });
      if (caret && target.setSelectionRange && key && key === keyOf(target)) { try { target.setSelectionRange(caret[0], caret[1]); } catch (_) { /* some input types have no selection */ } }
    }
    main.querySelectorAll('.gauge').forEach((g) => g.style.setProperty('--pos', g.dataset.pos));
    if (sess.highlight) {
      const hit = main.querySelector(`.para[data-block="${CSS.escape(sess.highlight)}"]`);
      sess.highlight = null;
      if (hit) { hit.scrollIntoView({ block: 'center', behavior: reduced() ? 'auto' : 'smooth' }); hit.classList.add('flash'); setTimeout(() => hit.classList.remove('flash'), 1000); }
    }
    const fresh = sess.pulseBlocks;
    if (fresh && fresh.length) {
      sess.pulseBlocks = [];
      fresh.forEach((id) => { const p = main.querySelector(`.para[data-block="${CSS.escape(id)}"]`); if (p) { p.classList.add('flash'); setTimeout(() => p.classList.remove('flash'), 950); } });
    }
    updateTimers();
  }
  function hashFor() {
    if (route.studio !== null) return 'studio' + (route.studio ? '/' + route.studio : '');
    if (route.room === 'write') { const e = currentEp(); return e ? 'write/' + e.ordinal : 'write'; }
    if (route.room === 'memory') return 'memory' + (route.person === '' ? '' : '/' + personSlug(route.person));
    return 'plan';
  }
  function syncHash() {
    if (!S || inFirstRun()) return;
    const want = '#' + hashFor();
    if (location.hash !== want) history.replaceState(null, '', want);
  }
  function parseHash() {
    const parts = location.hash.replace(/^#\/?/, '').split('/');
    let b;
    try { b = parts[1] === undefined ? undefined : decodeURIComponent(parts[1]); } catch (_) { b = parts[1]; }
    return { a: parts[0] || '', b };
  }
  function applyRoute() {
    const { a, b } = parseHash();
    if (a === 'studio') route.studio = STUDIO.some(([id]) => id === b) ? b : '';
    else {
      route.studio = null;
      if (a === 'plan') route.room = 'plan';
      else if (a === 'memory') { route.room = 'memory'; route.person = b === undefined ? '' : b; }
      else { route.room = 'write'; if (b) route.ep = Number(b) || 0; }
    }
    sess.needsOpen && setNeeds(false);
    render();
  }
  function navTo(str) {
    if ($('sheet').open && (sess.sheet || {}).kind !== 'overlap') closeSheet();
    if ($('palette').open) hideDialog($('palette'));
    if (location.hash === '#' + str) applyRoute(); else location.hash = str;
  }
  function closeStudio() {
    route.studio = null;
    const h = hashFor();
    if (location.hash === '#' + h) applyRoute(); else location.hash = h;
  }
  function stepEpisode(d) {
    const e = currentEp();
    if (!e) return;
    const n = Math.min(arcN(), Math.max(1, e.ordinal + d));
    if (n !== e.ordinal) { stepFast = true; navTo('write/' + n); }
  }

  // ---------- timers and polling ----------
  const fmt = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
  function updateTimers() {
    if (!pending) return;
    const s = Math.floor((Date.now() - pending.startedAt) / 1000);
    document.querySelectorAll('[data-timer]').forEach((t) => { t.textContent = fmt(s); });
    document.querySelectorAll('[data-slow]').forEach((t) => { t.hidden = s < 90; });
  }
  function startWatching() {
    clearInterval(tickTimer); clearInterval(pollTimer);
    tickTimer = setInterval(updateTimers, 1000);
    pollTimer = setInterval(async () => {
      if (!pending) return;
      try { const next = await getJson(BASE + '/api/v1/state'); if (pending) { S = next; render(); } } catch (_) { /* the final refresh reports any failure */ }
    }, 3000);
  }
  function stopWatching() { clearInterval(tickTimer); clearInterval(pollTimer); }
  // Changes made outside this page (another window, a script) show up when the tab is looked at again and every so often.
  const stateKey = (s) => [s.story && s.story.canon_seq, (s.history[0] || {}).seq, s.commissions.map((c) => c.status + c.pause_reason).join(), s.provider && s.provider.spent_usd,
    s.episodes.map((e) => (e.selection ? e.selection.revision_id : '') + e.alternatives.length).join(), s.length && s.length.target].join('|');
  let quietBusy = false;
  async function quietRefresh() {
    if (quietBusy || pending || busy || offline || !S || !S.story || document.hidden) return;
    const a = document.activeElement;
    if (a && /^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName)) return;
    quietBusy = true;
    try {
      const next = await getJson(BASE + '/api/v1/state');
      if (!pending && !busy && stateKey(next) !== stateKey(S)) await refresh();
    } catch (_) { /* a failed look is not worth a banner */ } finally { quietBusy = false; }
  }
  document.addEventListener('visibilitychange', quietRefresh);
  window.addEventListener('focus', quietRefresh);
  setInterval(quietRefresh, 15000);
  async function runDraft(label, first, last, work) {
    pending = { first, last, startedAt: Date.now() };
    route.room = 'write'; route.studio = null; route.ep = first;
    if (location.hash !== '#write/' + first) history.replaceState(null, '', '#write/' + first);
    render();
    startWatching();
    say(`Writing ${range(first, last)}.`);
    let out = null, err = null;
    try { out = await work(); } catch (e) { err = e; }
    stopWatching();
    pending = null;
    const here = route.room === 'write' && !route.studio && currentEp() && currentEp().ordinal >= first && currentEp().ordinal <= last;
    arrive = Boolean(here);
    try { await refresh(); } catch (_) { /* offline banner shows */ }
    if (err) report(err);
    else if (out && out.status === 'complete') { if (!here) pulsePill = true; flash(`Draft ready: ${range(first, last)}.`); chatEvent('draft', `${capFirst(range(first, last))} drafted.`); }
    else flash('Drafting paused. See why from the banner.');
    render();
    void label;
  }
  const e0approved = (n) => { const x = ep(n); return Boolean(x && x.accepted); };
  const epList = (list) => (list.length === 1 ? 'episode ' + list[0] : 'episodes ' + list.slice(0, -1).join(', ') + ' and ' + list[list.length - 1]);

  // ---------- actions ----------
  async function adoptLayer(layer, content) {
    const rev = await api('save_direction', { layer, content });
    const gov = S.governing[layer];
    await api('adopt', { revision_id: rev.revision_id }, { governing: gov ? gov.revision_id : null });
  }
  function ringFx(rect) {
    if (reduced() || !rect) return;
    const ring = document.createElement('div');
    ring.className = 'ringfx';
    ring.style.setProperty('left', rect.left + 'px'); ring.style.setProperty('top', rect.top + 'px');
    ring.style.setProperty('width', rect.width + 'px'); ring.style.setProperty('height', rect.height + 'px');
    $('flight').appendChild(ring);
    const a = ring.animate([{ transform: 'scale(1)', opacity: 0.4 }, { transform: 'scale(1.8)', opacity: 0 }], { duration: 480, easing: 'cubic-bezier(.23,1,.32,1)' });
    a.onfinish = () => ring.remove();
  }
  function flyList(clone, rect) {
    const target = document.querySelector('#rooms [data-nav="memory"]');
    if (!clone || !rect || !target || reduced() || !clone.animate) { if (clone) clone.remove(); return; }
    const to = target.getBoundingClientRect();
    clone.classList.add('flightclone');
    ['left', 'top', 'width'].forEach((p, i) => clone.style.setProperty(p, [rect.left, rect.top, rect.width][i] + 'px'));
    clone.style.setProperty('height', Math.min(rect.height, window.innerHeight * 0.5) + 'px');
    $('flight').appendChild(clone);
    const dx = to.left + to.width / 2 - rect.left - rect.width * 0.1, dy = to.top + to.height / 2 - rect.top;
    const a = clone.animate([{ transform: 'translate(0,0) scale(1)', opacity: 1, offset: 0 }, { opacity: 1, offset: 0.72 }, { transform: `translate(${dx}px,${dy}px) scale(.2)`, opacity: 0, offset: 1 }], { duration: 420, easing: 'cubic-bezier(.77,0,.175,1)', fill: 'forwards' });
    a.onfinish = () => clone.remove();
    a.oncancel = () => clone.remove();
  }
  function snapshotTexts(e) { const m = {}; if (e) e.blocks.forEach((b) => { m[b.block_id] = b.text; }); return m; }
  function markChanged(before) {
    const e = currentEp();
    if (!e || !before) return;
    sess.pulseBlocks = e.blocks.filter((b) => before[b.block_id] !== undefined && before[b.block_id] !== b.text).map((b) => b.block_id);
  }
  async function saveEdits(e) {
    const dirty = dirtyBlocks(e);
    if (!dirty.length) return true;
    if (dirty.some((b) => !ui.edits[b.block_id].text.trim())) { flash('A paragraph cannot be empty. Cancel the edit to keep the old words.'); return false; }
    if (dirty.some((b) => ui.edits[b.block_id].base !== b.sha256)) { flash('A paragraph changed after you began editing. Keep editing on the new text first.'); return false; }
    const blocks = e.blocks.map((b) => ({ block_id: b.block_id, text: ui.edits[b.block_id] && ui.edits[b.block_id].text !== b.text ? ui.edits[b.block_id].text : b.text }));
    const ids = dirty.map((b) => b.block_id);
    const r = await run('Saving your edit', () => api('save_revision', { ordinal: e.ordinal, base_revision_id: e.selection.revision_id, blocks }, { selection_cas: e.selection.cas }));
    if (!r.ok) return false;
    ids.forEach((id) => { delete ui.edits[id]; });
    const flagged = r.out.flagged || [];
    note = { text: 'Edited.' + (flagged.length ? ` ${capFirst(epList(flagged))} may no longer fit.` : ''), eventId: r.out.event_id };
    const mine = note;
    setTimeout(() => { if (note === mine) { note = null; const el = $('noteline'); if (el) el.remove(); } }, 6000);
    sess.pulseBlocks = ids;
    render();
    say(note.text);
    return true;
  }
  const actions = {
    ...chatActions,
    'reload-state': async () => { problem = null; try { await refresh(); flash('Refreshed.'); } catch (e) { report(e); } renderBanner(); },
    'reload-page': () => { persist(); location.reload(); },
    'dismiss-problem': () => { problem = null; renderBanner(); renderStudio(); },
    'copy-unsent': async () => {
      const parts = [];
      Object.entries(ui.edits).forEach(([id, ed]) => { const f = findBlock(id); parts.push(`Edit to paragraph ${f ? f.e.blocks.indexOf(f.b) + 1 : '?'}:\n${ed.text}`); });
      if (ui.composer) parts.push('Message:\n' + ui.composer);
      Object.entries(ui.forms).forEach(([k, v]) => { if (/^(premise|spine|private-note|purpose|int\d+|pint\d+|style-body|secret-body)$/.test(k) && v) parts.push(`${k}:\n${v}`); });
      try { await navigator.clipboard.writeText(parts.join('\n\n') || 'Nothing unsent.'); flash('Copied your unsent text.'); } catch (_) { flash('Could not copy. Select the text and copy it by hand.'); }
    },
    copy: async (t) => { try { await navigator.clipboard.writeText(t.dataset.text); flash('Copied.'); } catch (_) { flash('Could not copy.'); } },
    'open-private': () => { sess.privOpen = true; focusNext = '#private-note'; render(); },
    'fr-next': () => {
      const step = ui.fr || 1;
      const v = textOf(step === 1 ? 'premise' : 'spine');
      if (!v) { sess.frError = step === 1 ? 'Write a sentence or two first.' : 'Write where it goes first.'; render(); return; }
      sess.frError = ''; ui.fr = step + 1;
      focusNext = step === 1 ? '#spine' : '[data-action="count-dec"]';
      render();
    },
    'fr-back': () => { sess.frError = ''; ui.fr = Math.max(1, (ui.fr || 1) - 1); focusNext = ui.fr === 1 ? '#premise' : '#spine'; render(); },
    'count-dec': (t) => { const s = Number(t.dataset.step) || 1; ui.forms.count = Math.max(2, planCount() - s); focusNext = `[data-action="count-dec"][data-step="${s}"]`; render(); },
    'count-inc': (t) => { const s = Number(t.dataset.step) || 1; ui.forms.count = Math.min(MAX_EPISODES, planCount() + s); focusNext = `[data-action="count-inc"][data-step="${s}"]`; render(); },
    'start-sample': async () => {
      const r = await run('Setting up the sample story', async () => {
        if (!S.story) await api('create_story', {});
        S = await getJson(BASE + '/api/v1/state');
        await adoptLayer('skeleton', SAMPLE.skeleton);
        S = await getJson(BASE + '/api/v1/state');
        await adoptLayer('arc', SAMPLE.arc);
      });
      if (r.ok) { ui.fr = 1; route.room = 'write'; route.ep = 1; navTo('write/1'); flash('The sample story is ready. Draft episode 1 when you like.'); }
    },
    'adopt-first': async () => {
      const premise = textOf('premise'), spine = textOf('spine'), priv = textOf('private-note');
      const r = await run('Adopting the direction', async () => {
        if (!S.story) await api('create_story', {});
        S = await getJson(BASE + '/api/v1/state');
        await adoptLayer('skeleton', priv ? { premise, spine, private: priv } : { premise, spine });
      });
      if (r.ok) {
        ['premise', 'spine', 'private-note'].forEach((k) => delete ui.forms[k]);
        ui.fr = 1; sess.privOpen = false;
        route.room = 'plan'; navTo('plan');
        flash('Direction adopted. Drafts will follow it.');
        chatEvent('adopt', 'Direction adopted.');
        const d = $('tstory');
        if (d && d.animate && !reduced()) d.animate([{ transform: 'scale(.6)' }, { transform: 'scale(1)' }], { duration: 320, easing: 'cubic-bezier(.34,1.35,.64,1)' });
      } else { render(); }
    },
    'edit-direction': () => { sess.edit = 'direction'; focusNext = '#premise'; render(); },
    'cancel-edit-direction': () => { sess.edit = null; ['premise', 'spine', 'private-note'].forEach((k) => delete ui.forms[k]); focusNext = '[data-action="edit-direction"]'; render(); },
    'adopt-direction': async () => {
      const gov = S.governing.skeleton;
      const premise = textOf('premise') || gov.content.premise, spine = textOf('spine') || gov.content.spine, priv = textOf('private-note');
      const r = await run('Adopting the direction', () => adoptLayer('skeleton', priv ? { premise, spine, private: priv } : { premise, spine }));
      if (r.ok) { ['premise', 'spine', 'private-note'].forEach((k) => delete ui.forms[k]); sess.edit = null; focusNext = '[data-action="edit-direction"]'; render(); flash('Direction adopted. Drafts will follow it.'); chatEvent('adopt', 'Direction adopted.'); }
    },
    'adopt-saved': async (t) => {
      const layer = t.dataset.layer, head = S.directions[layer], gov = S.governing[layer];
      const r = await run('Adopting the saved version', () => api('adopt', { revision_id: head.revision_id }, { governing: gov ? gov.revision_id : null }));
      if (r.ok) { flash(layer === 'arc' ? 'Plan adopted. Drafts will follow it.' : 'Direction adopted. Drafts will follow it.'); chatEvent('adopt', layer === 'arc' ? 'Plan adopted.' : 'Direction adopted.'); }
    },
    'toggle-dir': () => { sess.dirOpen = !sess.dirOpen; focusNext = '[data-action="toggle-dir"]'; render(); },
    'toggle-count': () => { sess.countOpen = !sess.countOpen; focusNext = '[data-action="toggle-count"]'; render(); },
    'plan-dec': (t) => { const s = Number(t.dataset.step) || 1; ui.forms.count = Math.max(2, cursor(), planCountVal() - s); focusNext = `[data-action="plan-dec"][data-step="${s}"]`; render(); },
    'plan-inc': (t) => { const s = Number(t.dataset.step) || 1; ui.forms.count = Math.min(MAX_EPISODES, planCountVal() + s); focusNext = `[data-action="plan-inc"][data-step="${s}"]`; render(); },
    'toggle-line-note': (t) => { const i = Number(t.dataset.line); const cur = sess.lineNote[i] !== undefined ? sess.lineNote[i] : Boolean(lineNote(i)); sess.lineNote[i] = !cur; focusNext = cur ? `[data-action="toggle-line-note"][data-line="${i}"]` : `#pint-${i}`; render(); },
    'paste-fill': () => {
      const p = sess.paste;
      if (!p) return;
      const need = Math.min(MAX_EPISODES, p.from + p.lines.length);
      if (need > planCountVal()) ui.forms.count = need;
      p.lines.slice(0, need - p.from).forEach((l, k) => { ui.forms['int' + (p.from + k)] = l; });
      sess.paste = null; focusNext = `#intention-${p.from}`; render(); flash('Lines filled.');
    },
    'paste-cancel': () => { const p = sess.paste; sess.paste = null; focusNext = p ? `#intention-${p.from}` : null; render(); },
    'adopt-plan': async () => {
      const count = planCountVal();
      const purpose = textOf('purpose') || form('purpose', planBase().purpose || '').trim();
      const intentions = Array.from({ length: count }, (_, i) => lineVal(i).trim());
      if (!purpose) { focusNext = '#purpose'; render(); flash('Say what this stretch is for.'); return; }
      const miss = intentions.findIndex((t) => !t);
      if (miss >= 0) { focusNext = `#intention-${miss}`; render(); flash(`Add a line for episode ${miss + 1}.`); return; }
      const notes = Array.from({ length: count }, (_, i) => lineNote(i).trim());
      const content = notes.some(Boolean) ? { purpose, intentions, private_intentions: notes } : { purpose, intentions };
      const first = !S.governing.arc;
      const r = await run('Adopting the plan', () => adoptLayer('arc', content));
      if (r.ok) {
        Object.keys(ui.forms).filter((k) => /^(int\d+|pint\d+|purpose|count)$/.test(k)).forEach((k) => delete ui.forms[k]);
        sess.countOpen = false; sess.lineNote = {};
        flash('Plan adopted. Drafts will follow it.');
        chatEvent('adopt', `Plan adopted. ${plural(count, 'episode')}.`);
        const cap = $('cap');
        if (first && cap && cap.animate && !reduced()) cap.animate([{ transform: 'scaleX(0)' }, { transform: 'scaleX(1)' }], { duration: 480, easing: 'cubic-bezier(.23,1,.32,1)' });
      }
    },
    'go-plan': () => navTo('plan'),
    'nav-studio-length': () => navTo('studio/length'),
    'go-write': () => navTo('write'),
    'go-home': () => { location.href = '/'; },
    'go-money': () => navTo('studio/money'),
    'step-ep': (t) => { const d = Number(t.dataset.d); if (route.room === 'write') stepEpisode(d); else { sess.twinC = Math.max(1, Math.min(arcN() || 1, (sess.twinC || winNow.start + Math.floor(winNow.w / 2)) + d * Math.max(1, winNow.w - 1))); renderThread(); } },
    'open-spend': (t) => openSpend(t),
    'spend-dec': () => { const r = spendRun(); sess.spendCount = Math.max(1, r.count - 1); renderSheet(); const b = document.querySelector('[data-action="spend-dec"]'); if (b) b.focus(); },
    'spend-inc': () => { const r = spendRun(); sess.spendCount = Math.min(r.max, r.count + 1); renderSheet(); const b = document.querySelector('[data-action="spend-inc"]'); if (b) b.focus(); },
    'confirm-spend': (t) => {
      const first = Number(t.dataset.first), count = Number(t.dataset.count), last = first + count - 1;
      closeSheet();
      runDraft('Drafting', first, last, () => api('commission_arc', { slots: [first, last], progression: 'provisional_chain' }));
    },
    'see-why': (t) => openSheet({ kind: 'paused' }, t),
    'use-draft': async (t) => {
      const r = await run('Using this draft', () => api('use_draft', { ordinal: Number(t.dataset.ordinal), revision_id: t.dataset.rev }, { selection_cas: 0 }));
      if (r.ok) flash('This draft is now episode ' + t.dataset.ordinal + '. Trim it if you like, then resume drafting.');
    },
    'resume-commission': (t) => {
      const id = t.dataset.commission, c = S.commissions.find((x) => x.commission_id === id);
      closeSheet(); setNeeds(false);
      const low = c ? eps().find((x) => x.ordinal >= c.first_slot && x.ordinal <= c.last_slot && !x.selection) : null;
      runDraft('Resuming', low ? low.ordinal : (c ? c.first_slot : 1), c ? c.last_slot : 1, () => api('resume_commission', { commission_id: id }));
    },
    'resolve-uncertain': async (t) => {
      const reason = textOf('settle-' + t.dataset.job);
      if (!reason) { flash('Write why it is safe to settle this charge.'); return; }
      const r = await run('Settling the charge', () => api('resolve_uncertain', { job_id: t.dataset.job, reason }));
      if (r.ok) flash('Settled. You can continue drafting.');
    },
    'edit-para': (t) => {
      const f = findBlock(t.dataset.block);
      if (!f) return;
      ui.edits[f.b.block_id] = ui.kept[f.b.block_id] || { text: f.b.text, base: f.b.sha256 };
      delete ui.kept[f.b.block_id];
      focusNext = `textarea[data-edit="${CSS.escape(f.b.block_id)}"]`; render();
    },
    'cancel-edit': (t) => { delete ui.edits[t.dataset.block]; focusNext = `.para[data-block="${CSS.escape(t.dataset.block)}"]`; render(); flash('Edit cancelled. Nothing was lost.'); },
    'save-para': async (t) => {
      const f = findBlock(t.dataset.block);
      if (!f) return;
      const ed = ui.edits[f.b.block_id];
      if (ed && ed.base !== f.b.sha256) { ed.base = f.b.sha256; render(); flash('Now editing on the new text. Save when ready.'); return; }
      await saveEdits(f.e);
    },
    'save-edits': async () => { await saveEdits(currentEp()); },
    'restore-kept': (t) => { const id = t.dataset.block; ui.edits[id] = ui.kept[id]; delete ui.kept[id]; focusNext = `textarea[data-edit="${CSS.escape(id)}"]`; render(); },
    'discard-kept': (t) => { delete ui.kept[t.dataset.block]; render(); flash('Discarded.'); },
    'discard-edits': () => { ui.edits = {}; render(); flash('Discarded.'); },
    'show-hit': () => { const m = document.querySelector('mark.nu'); if (m) { m.scrollIntoView({ block: 'center', behavior: reduced() ? 'auto' : 'smooth' }); m.classList.add('flash'); setTimeout(() => m.classList.remove('flash'), 1000); } },
    'suggest-para': (t) => { sess.suggesting = t.dataset.block; focusNext = 'input[data-form="reason"]'; render(); },
    'cancel-suggest': () => { sess.suggesting = null; render(); },
    'get-suggestion': async (t) => {
      const reason = textOf('reason');
      if (!reason) { flash('Say what should change, for example "tighten the rhythm".'); return; }
      const e = currentEp();
      const r = await withCall('suggest', 'Looking for better wording', { block: t.dataset.block }, () => run('Asking for better wording', () => api('request_rewrite', { ordinal: e.ordinal, block_id: t.dataset.block, intent: 'polish', reason }, { block_sha256: t.dataset.sha })));
      if (!r.ok) return;
      sess.suggesting = null; focusNext = `[data-action="apply-candidate"][data-cand="${r.out.candidate_id}"]`; render();
      flash('Better wording is ready. Compare it.');
    },
    'dismiss-candidate': (t) => { sess.dismissed.push(t.dataset.cand); render(); flash('Kept your version.'); },
    'apply-candidate': async (t) => {
      const e = currentEp();
      const before = snapshotTexts(e);
      const r = await run('Using the wording', () => api('apply_candidate', { candidate_id: t.dataset.cand }, { selection_cas: e.selection.cas }));
      if (!r.ok) return;
      const flagged = r.out.flagged || [];
      note = { text: 'Wording used.' + (flagged.length ? ` ${capFirst(epList(flagged))} may no longer fit.` : ''), eventId: r.out.event_id };
      markChanged(before); render(); say(note.text);
    },
    undo: async (t) => {
      const before = snapshotTexts(currentEp());
      const r = await run('Undoing the change', () => api('revert_event', { event_id: t.dataset.event }));
      if (r.ok) { note = null; markChanged(before); render(); flash('Undone.'); }
    },
    redo: async (t) => {
      const before = snapshotTexts(currentEp());
      const r = await run('Redoing the change', () => api('redo_event', { event_id: t.dataset.event }));
      if (r.ok) { note = null; markChanged(before); render(); flash('Redone.'); }
    },
    'revalidate-slot': async (t) => {
      const n = Number(t.dataset.slot);
      const notch = document.querySelector(`.knot[data-n="${n}"] .k`);
      const r = await run('Recording your decision', () => api('revalidate', { ordinal: n }));
      if (r.ok) flash(`Episode ${n} kept as is.`);
      void notch;
    },
    'toggle-reading': () => { sess.reading = !sess.reading; renderChat(); render(); say(sess.reading ? 'Focus reading on. The button is at the top of the episode.' : 'Focus reading off.'); },
    'show-sent': async (t) => {
      const n = Number(t.dataset.n);
      try { openSheet({ kind: 'shown', n, html: shownHtml(await api('draft_inspection', { ordinal: n })) }, t); } catch (e) { report(e); }
    },
    'episode-menu': (t) => { const e = currentEp(); if (e) openSheet({ kind: 'menu', n: e.ordinal }, t); },
    'open-finish': (t) => openFinish(Number(t.dataset.ordinal), t),
    'close-fin': () => { sess.fin = null; focusNext = '#dock-main button'; render(); },
    'save-edits-continue': async (t) => {
      const n = Number(t.dataset.ordinal), e = ep(n);
      if (await saveEdits(e)) openFinish(n);
    },
    'discard-edits-continue': (t) => { const n = Number(t.dataset.ordinal); const e = ep(n); dirtyBlocks(e).forEach((b) => delete ui.edits[b.block_id]); render(); openFinish(n, t); },
    'nav-ep': (t) => navTo('write/' + t.dataset.ep),
    'fin-all': (t) => { sess.finAll = sess.finAll || {}; sess.finAll[t.dataset.who] = true; renderSheet(); },
    'read-facts': async (t) => {
      const n = Number(t.dataset.ordinal);
      const r = await withCall('read', 'Reading the episode for story changes', { n }, () => run('Reading the episode', () => api('read_provisional', { ordinal: n })));
      if (r.ok) { sess.finSeen = sess.finSeen || {}; if (e0approved(n)) sess.finSeen[n] = true; flash(`Found ${plural(r.out.imported, 'story change')}. Review them.`); render(); }
    },
    'confirm-approve': async (t) => {
      const n = Number(t.dataset.ordinal), e = ep(n);
      if (t.getAttribute('aria-disabled') === 'true') { const why = $('why1'); say(why ? why.textContent : 'Not ready yet.'); return; }
      if (dirtyBlocks(e).length) { openFinish(n); return; }
      const rect = t.getBoundingClientRect();
      const sawList = provisionalFor(e).length > 0;
      const label = t.querySelector('span');
      if (label) label.textContent = 'Approving';
      t.setAttribute('aria-busy', 'true');
      const r = await run(`Approving episode ${n}`, () => api('accept_prefix', { episodes: [{ ordinal: n, revision_id: e.selection.revision_id, sha256: e.selection.sha256 }] }, { canon_seq: S.story.canon_seq }));
      if (!r.ok) { render(); return; }
      if (sawList) { sess.finSeen = sess.finSeen || {}; sess.finSeen[n] = true; }
      ringFx(rect);
      chatEvent('seal', `Episode ${n} approved. Final words locked.`);
      const pg = $('page');
      if (pg) { pg.classList.add('lock-in'); setTimeout(() => pg.classList.remove('lock-in'), 700); }
      focusNext = '#btn-save';
      render();
      const firstEver = !ui.seen.approved;
      ui.seen.approved = true; persist();
      flash(firstEver ? 'Locked. This is the story now.' : `Approved. Episode ${n} is locked.`);
      const b = $('btn-save'); if (b) b.focus({ preventScroll: true });
    },
    'confirm-save': async (t) => {
      const n = Number(t.dataset.ordinal);
      if (t.getAttribute('aria-disabled') === 'true') { const why = $('why2'); say(why ? why.textContent : 'Not ready yet.'); return; }
      const rect = t.getBoundingClientRect();
      const lab = t.querySelector('span'); if (lab) lab.textContent = 'Saving';
      const r = await withCall('save', 'Saving to story memory', { n }, () => run('Saving story changes', () => api('update_memory', {})));
      if (!r.ok) { render(); return; }
      const k = S.memory.accepted.filter((c) => c.narrative_ordinal === n).length;
      flyMarker(rect, k);
      const firstSave = !ui.seen.saved; ui.seen.saved = true; persist();
      flash(firstSave ? `Your story now remembers ${k} things.` : `Saved. The story now remembers ${plural(k, 'more thing')}.`);
      focusNext = null;
      render();
      const pgs = $('page'); if (pgs) { pgs.classList.add('thread-in'); setTimeout(() => pgs.classList.remove('thread-in'), 700); }
      chatEvent('thread', `${plural(k, 'fact')} saved from Episode ${n}.`);
      const knot = document.querySelector(`.knot[data-n="${n}"]`);
      if (knot && knot.animate && !reduced()) knot.animate([{ opacity: 0.4 }, { opacity: 1 }], { duration: 320, easing: 'cubic-bezier(.23,1,.32,1)' });
    },
    'correct-memory': (t) => { mem.correcting = t.dataset.claim; focusNext = '#corr-text'; render(); },
    'cancel-correction': () => { mem.correcting = null; render(); },
    'save-correction': async (t) => {
      const c = S.memory.accepted.find((x) => x.claim_id === t.dataset.claim);
      const text = textOf('corr_text');
      const kind = form('corr_kind', c.kind), valid = form('corr_valid', c.world_validity);
      const speaker = textOf('corr_speaker') || (kind === 'testimony' ? (c.speaker || '') : '');
      if (!text) { flash('Say what the fact should be.'); return; }
      const holds = kind === 'belief' || kind === 'knowledge' ? (textOf('corr_speaker') || c.holder || '') : '';
      const r = await run('Saving your correction', () => api('interpret', { claim_id: c.claim_id, kind, speaker: speaker || null, holder: holds || null, world_validity: valid, note: text }));
      if (r.ok) {
        mem.correcting = null;
        ['corr_text', 'corr_kind', 'corr_valid', 'corr_speaker'].forEach((k) => delete ui.forms[k]);
        const fix = S.memory.accepted.find((x) => x.prior_claim_id === c.claim_id);
        mem.sel = fix ? fix.claim_id : null;
        render(); flash('Corrected. The original stays on record.');
      }
    },
    'clear-mem': () => { mem.kind = 'all'; mem.q = ''; mem.eps.clear(); route.person = 'all'; navTo('memory/all'); },
    'clear-mem-range': () => { mem.eps.clear(); render(); },
    'more-facts': () => { mem.shown += 20; render(); },
    'mem-home': () => navTo('memory'),
    'close-source': () => { mem.sel = null; mem.correcting = null; render(); },
    'go-paragraph': (t) => { sess.fromMem = { claim: t.dataset.claim || '', ep: Number(t.dataset.ep) }; sess.highlight = t.dataset.block; navTo('write/' + t.dataset.ep); },
    'back-memory': () => { const f = sess.fromMem; sess.fromMem = null; if (f) mem.sel = f.claim || null; navTo('memory/all'); },
    'dismiss-memback': () => { sess.fromMem = null; render(); },
    'mem-ep': (t) => { const n = Number(t.dataset.n); if (!n) mem.eps.clear(); else if (mem.eps.has(n)) mem.eps.delete(n); else mem.eps.add(n); mem.shown = 80; render(); },
    'g-node': (t) => { const k = t.dataset.key; mem.gsel = mem.gsel && !mem.gsel.b && mem.gsel.a === k ? null : { a: k }; focusNext = '.mnode[data-key="' + CSS.escape(k) + '"]'; render(); },
    'g-edge': (t) => { mem.gsel = { a: t.dataset.a, b: t.dataset.b }; focusNext = '.gdetail h3'; render(); },
    'g-back': () => { mem.gsel = mem.gsel ? { a: mem.gsel.a } : null; focusNext = '.gdetail h3'; render(); },
    'g-clear': () => { mem.gsel = null; render(); },
    'g-open': (t) => { mem.gsel = null; mem.shown = 80; mem.view = 'list'; navTo('memory/' + personSlug(t.dataset.key)); },
    'mem-view': (t) => { mem.view = t.dataset.v === 'graph' ? 'graph' : 'list'; render(); },
    'len-preset': (t) => {
      const [lo, mid, hi] = t.dataset.v.split(',');
      ui.forms['len-low'] = lo; ui.forms['len-target'] = mid; ui.forms['len-high'] = hi;
      sess.studioErr = null; $('sroom').dataset.html = ''; renderStudio();
    },
    'save-length': async () => {
      const raw = { low: textOf('len-low'), target: textOf('len-target'), high: textOf('len-high') };
      const num = {};
      for (const [k, label] of [['low', 'shortest'], ['target', 'aim'], ['high', 'longest']]) {
        if (!/^\d{1,5}$/.test(raw[k])) { studioErr(`Give the ${label} as a whole number of words.`, 'len-' + k); return; }
        num[k] = Number(raw[k]);
        if (num[k] < LENGTH_MIN || num[k] > LENGTH_MAX) { studioErr(`The ${label} must be between ${LENGTH_MIN} and ${LENGTH_MAX} words.`, 'len-' + k); return; }
      }
      if (num.low > num.target) { studioErr('The shortest cannot be more than the aim.', 'len-low'); return; }
      if (num.target > num.high) { studioErr('The aim cannot be more than the longest.', 'len-target'); return; }
      sess.studioErr = null;
      const r = await run('Saving the length', () => api('set_length', num));
      if (r.ok) { ['low', 'target', 'high'].forEach((k) => delete ui.forms['len-' + k]); $('sroom').dataset.html = ''; render(); flash(`Length saved: ${num.low} to ${num.high} words, aim ${num.target}. It applies to drafts from now on.`); }
    },
    'save-style': async () => {
      const body = textOf('style-body');
      const avoid = avoidList();
      const r = await run('Saving the voice', () => api('save_style_sheet', { body, avoid }));
      if (r.ok) { delete ui.forms['style-body']; delete ui.forms['style-avoid']; render(); flash(`Voice saved, version ${r.out.version}.`); }
    },
    'avoid-add': () => {
      const el = $('avoid-add'); const v = el ? el.value.trim() : '';
      if (!v) return;
      const list = avoidList();
      if (!list.includes(v)) list.push(v);
      ui.forms['style-avoid'] = list.join('\n');
      focusNext = '#avoid-add'; render();
    },
    'avoid-remove': (t) => { const list = avoidList(); list.splice(Number(t.dataset.i), 1); ui.forms['style-avoid'] = list.join('\n'); focusNext = '#avoid-add'; render(); },
    'add-secret': async () => {
      const label = textOf('secret-label'), body = textOf('secret-body');
      const canaries = textOf('secret-words').split(',').map((x) => x.trim()).filter(Boolean);
      const reveal = textOf('secret-reveal');
      if (!label) { studioErr('Give the secret a name.', 'secret-label'); return; }
      if (!body) { studioErr('Write the secret itself.', 'secret-body'); return; }
      if (!canaries.length) { studioErr('Add at least one word that would give it away.', 'secret-words'); return; }
      if (label.length > SECRET_MAX) { studioErr(`Name must be ${SECRET_MAX} characters or fewer. It is ${label.length}.`, 'secret-label'); return; }
      const bad = canaries.find((w) => w.replace(/[^\p{L}\p{N}]/gu, '').length < 4);
      if (bad) { studioErr(`"${bad}" is too short. Use four or more letters.`, 'secret-words'); return; }
      const common = canaries.find((w) => COMMON.has(w.toLowerCase()));
      if (common) { studioErr(`"${common}" is a common word and would stop ordinary drafts. Pick something only this secret would bring in.`, 'secret-words'); return; }
      sess.studioErr = null;
      const payload = { label, body, canaries };
      if (reveal) payload.reveal_ordinal = Number(reveal);
      const r = await run('Keeping the secret', () => api('add_secret', payload));
      if (r.ok) { ['secret-label', 'secret-body', 'secret-words', 'secret-reveal'].forEach((k) => delete ui.forms[k]); render(); flash('Secret kept. Anything sent to the writer is checked for its trigger words first.'); }
    },
    'retire-secret': async (t) => { const r = await run('Retiring the secret', () => api('retire_secret', { secret_id: t.dataset.secret })); if (r.ok) flash('Secret retired.'); },
    'needs-all': () => { ui.seen.needsAll = true; renderNeeds(); },
    'tour-next': () => { sess.tourStep = Math.min(TOUR.length - 1, sess.tourStep + 1); renderSheet(); focusNext = null; const b = document.querySelector('[data-action="tour-next"],[data-action="close-sheet"]'); if (b) b.focus(); },
    'tour-prev': () => { sess.tourStep = Math.max(0, sess.tourStep - 1); renderSheet(); const b = document.querySelector('[data-action="tour-next"]'); if (b) b.focus(); },
    'close-sheet': () => closeSheet(),
    'close-studio': () => closeStudio(),
    'studio-back': () => navTo('studio'),
    'open-palette': () => openPalette(),
    'open-studio': () => navTo('studio' + (route.studio ? '/' + route.studio : '')),
    'toggle-needs': () => setNeeds(!sess.needsOpen),
  };

  // ---------- thread pointer handling ----------
  let scrub = null, suppressClick = false;
  function knotAt(x) {
    const list = [...document.querySelectorAll('#knots .knot')];
    let best = null, bd = 1e9;
    list.forEach((k) => { const r = k.getBoundingClientRect(); const d = Math.abs(r.left + r.width / 2 - x); if (d < bd) { bd = d; best = k; } });
    return best;
  }
  function openKnot(n) {
    if (route.room === 'memory' && S && S.governing.arc) {
      if (mem.eps.has(n)) mem.eps.delete(n); else mem.eps.add(n);
      mem.shown = 80; render();
      return;
    }
    if (!S || !S.governing.arc) return;
    navTo('write/' + n);
  }
  function showBubble(k, x) {
    const b = $('bubble');
    const w = $('threadwrap').getBoundingClientRect();
    b.hidden = false;
    b.textContent = `${k.dataset.n} · ${k.dataset.title || ''}`;
    b.style.setProperty('--bx', Math.min(w.width - 60, Math.max(60, x - w.left)) + 'px');
  }

  // ---------- events ----------
  document.addEventListener('click', (ev) => {
    if (suppressClick) { suppressClick = false; ev.preventDefault(); return; }
    const raw = ev.target;
    const knot = raw.closest && raw.closest('.knot');
    if (knot) { openKnot(Number(knot.dataset.n)); return; }
    const para = raw.closest && raw.closest('.para');
    if (para && !raw.closest('button, textarea, input, a, label, select') && !para.classList.contains('editing')) {
      const on = !para.classList.contains('sel');
      document.querySelectorAll('.para.sel').forEach((p) => p.classList.remove('sel'));
      para.classList.toggle('sel', on); sess.sel = on ? para.dataset.block : null; renderChat();
    }
    const t = raw.closest && raw.closest('[data-action],[data-nav],[data-studio],[data-person],[data-kind],[data-claim],[data-theme-set],[data-pal]');
    if (!t || t.disabled) {
      if (sess.needsOpen && !(raw.closest && raw.closest('#needs, #needs-btn'))) setNeeds(false);
      return;
    }
    const d = t.dataset;
    if (d.action) { if (sess.needsOpen && d.action !== 'toggle-needs') setNeeds(false); const fn = actions[d.action]; if (fn) fn(t); return; }
    if (d.nav) { setNeeds(false); if (isPhone() && sess.pane === 'chat') setPane('book'); navTo(d.nav); return; }
    if (d.studio) { navTo('studio/' + d.studio); return; }
    if (d.person !== undefined) { mem.shown = 80; mem.view = 'list'; navTo('memory/' + d.person); return; }
    if (d.pal !== undefined) { runPalette(Number(d.pal)); return; }
    if (d.themeSet) { setTheme(d.themeSet); return; }
    if (d.kind) { mem.kind = d.kind; mem.shown = 80; render(); return; }
    if (d.claim) { mem.sel = d.claim; mem.correcting = null; if (matchMedia('(max-width:899px)').matches) focusNext = '#src-title'; render(); return; }
  });
  document.addEventListener('keydown', (ev) => {
    const g = ev.target && ev.target.closest ? ev.target.closest('.mnode') : null;
    if (g && (ev.key === 'Enter' || ev.key === ' ')) { ev.preventDefault(); g.dispatchEvent(new MouseEvent('click', { bubbles: true })); }
  });
  document.addEventListener('input', (ev) => {
    const t = ev.target;
    if (t.id === 'pal-input') { palSel = 0; renderPalette(); return; }
    sess.receipt = '';
    if (sess.studioErr && t.closest && t.closest('#studio')) { sess.studioErr = null; document.querySelectorAll('#studio .field-err').forEach((x) => x.remove()); $('sroom').dataset.html = ''; }
    if (t.dataset && t.dataset.form === 'memq') {
      mem.q = t.value; mem.shown = 80;
      clearTimeout(actions.memT);
      actions.memT = setTimeout(() => { focusNext = '#mem-search'; render(); }, 180);
      return;
    }
    if (t.dataset && t.dataset.form) {
      ui.forms[t.dataset.form] = t.value; persist();
      if (t.id === 'premise') { const c = $('premise-count'); if (c) c.textContent = `${t.value.length}/4000`; }
      if (t.id === 'spine') { const c = $('spine-count'); if (c) c.textContent = `${t.value.length}/4000`; }
      if (t.id === 'len-high') { const c = $('len-limit'); if (c) c.textContent = String(lenLimit()); }
      if (t.id === 'secret-label') { const c = $('label-count'); if (c) { c.textContent = `${t.value.length} of ${SECRET_MAX}`; c.dataset.over = String(t.value.length > SECRET_MAX); } }
      if (t.dataset.line !== undefined || t.id === 'purpose') renderDock();
      renderSave();
    } else if (t.dataset && t.dataset.edit && ui.edits[t.dataset.edit]) {
      ui.edits[t.dataset.edit].text = t.value; persist(); renderDock(); renderSave();
    } else if (t.id === 'composer') { ui.composer = t.value; persist(); renderSave(); growComposer(); }
  });
  document.addEventListener('change', (ev) => {
    const t = ev.target;
    if (t.dataset && t.dataset.pick) { sess.pick[t.dataset.pick] = t.value; }
    else if (t.dataset && t.dataset.form && t.tagName === 'SELECT') { ui.forms[t.dataset.form] = t.value; persist(); }
  });
  document.addEventListener('paste', (ev) => {
    const t = ev.target;
    if (!t || t.dataset === undefined || t.dataset.line === undefined) return;
    const text = (ev.clipboardData || window.clipboardData).getData('text');
    const lines = text.split(/\r?\n/).map((l) => stripListMark(l.trim()).trim()).filter(Boolean);
    if (lines.length < 2) return;
    ev.preventDefault();
    sess.paste = { from: Number(t.dataset.line), lines: lines.slice(0, MAX_EPISODES) };
    render();
    const b = document.querySelector('[data-action="paste-fill"]'); if (b) b.focus({ preventScroll: false });
  });
  document.addEventListener('toggle', (ev) => {
    const t = ev.target;
    if (t.classList && t.classList.contains('fgroup')) { sess.finGroups = sess.finGroups || {}; sess.finGroups[t.dataset.who] = t.open; }
    if (t.id === 'lockgroup') sess.lockOpen = t.open;
    if (t.id === 'fin-review' && t.open && sess.fin) { sess.finSeen = sess.finSeen || {}; if (!sess.finSeen[sess.fin]) { sess.finSeen[sess.fin] = true; focusNext = '#fin-review summary'; render(); } }
  }, true);
  document.addEventListener('mouseover', (ev) => { const r = ev.target.closest && ev.target.closest('.frow'); if (r) tint(r.dataset.block); });
  document.addEventListener('focusin', (ev) => { const r = ev.target.closest && ev.target.closest('.frow'); if (r) tint(r.dataset.block); });
  document.addEventListener('mouseout', (ev) => { if (ev.target.closest && ev.target.closest('.frow')) tint(null); });
  document.addEventListener('focusout', (ev) => { if (ev.target.closest && ev.target.closest('.frow')) tint(null); });
  function tint(block) {
    document.querySelectorAll('.para.tint').forEach((p) => p.classList.remove('tint'));
    if (!block) return;
    const p = document.querySelector(`#main .para[data-block="${CSS.escape(block)}"]`);
    if (p) p.classList.add('tint');
  }
  const typing = (t) => t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.tagName === 'SELECT' || t.isContentEditable);
  document.addEventListener('keydown', (ev) => {
    const t = ev.target;
    if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === 'k') { ev.preventDefault(); openPalette(); return; }
    if (t.id === 'composer' && ev.key === 'Enter' && !ev.shiftKey && !ev.isComposing) { ev.preventDefault(); sendChat(); return; }
    if ((ev.ctrlKey || ev.metaKey) && ev.key === 'Enter') {
      if (t.dataset && t.dataset.edit) { ev.preventDefault(); saveEdits(currentEp()); return; }
    }
    if (ev.key === 'Escape') {
      if (scrub) { scrub = null; $('bubble').hidden = true; return; }
      if (sess.needsOpen) { setNeeds(false); $('needs-btn').focus(); return; }
      if (t.dataset && t.dataset.edit) { ev.preventDefault(); actions['cancel-edit']({ dataset: { block: t.dataset.edit } }); return; }
      if (sess.suggesting && t.closest && t.closest('main')) { sess.suggesting = null; render(); return; }
      if (mem.sel && route.room === 'memory' && !document.querySelector('dialog[open]')) { mem.sel = null; mem.correcting = null; render(); return; }
    }
    if (t.id === 'pal-input') {
      if (ev.key === 'ArrowDown') { ev.preventDefault(); palSel = Math.min(palSel + 1, palItems.length - 1); renderPalette(); }
      else if (ev.key === 'ArrowUp') { ev.preventDefault(); palSel = Math.max(palSel - 1, 0); renderPalette(); }
      else if (ev.key === 'Enter') { ev.preventDefault(); runPalette(palSel); }
      return;
    }
    if (t.id === 'plan-jump' && ev.key === 'Enter') {
      ev.preventDefault();
      const n = Math.max(1, Math.min(Number(t.value) || 1, planCountVal()));
      if (n <= lockedRun()) { sess.lockOpen = true; render(); }
      const li = document.querySelector(`.line[data-n="${n}"]`);
      if (li) { li.setAttribute('tabindex', '-1'); li.scrollIntoView({ block: 'center' }); (li.querySelector('textarea') || li).focus(); }
      return;
    }
    if (t.closest && t.closest('#knots')) {
      const list = [...document.querySelectorAll('#knots .knot')];
      const i = list.indexOf(t.closest('.knot'));
      let j = -1;
      if (ev.key === 'ArrowRight') j = Math.min(list.length - 1, i + 1);
      else if (ev.key === 'ArrowLeft') j = Math.max(0, i - 1);
      else if (ev.key === 'Home') j = 0;
      else if (ev.key === 'End') j = list.length - 1;
      if (j >= 0) { ev.preventDefault(); list.forEach((k) => { k.tabIndex = -1; }); list[j].tabIndex = 0; list[j].focus(); }
      return;
    }
    if (t.closest && t.closest('.para') && !typing(t) && (ev.key === 'Enter' || ev.key === ' ') && t.classList.contains('para')) { ev.preventDefault(); sess.sel = sess.sel === t.dataset.block ? null : t.dataset.block; t.classList.toggle('sel', sess.sel === t.dataset.block); return; }
    if (typing(t) || ev.ctrlKey || ev.metaKey || ev.altKey || document.querySelector('dialog[open]')) return;
    if (!S || !S.story || inFirstRun()) return;
    if (ev.key === '1') navTo('plan');
    else if (ev.key === '2') navTo('write');
    else if (ev.key === '3') navTo('memory');
    else if (ev.key === ',') navTo('studio');
    else if (ev.key === '/' && route.room === 'memory') { ev.preventDefault(); const s = $('mem-search'); if (s) s.focus(); }
    else if (ev.key === '?') openSheet({ kind: 'keys' });
    else if ((ev.key === 'ArrowRight' || ev.key === 'j') && route.room === 'write' && !(t.closest && t.closest('#threadwrap'))) stepEpisode(1);
    else if ((ev.key === 'ArrowLeft' || ev.key === 'k') && route.room === 'write' && !(t.closest && t.closest('#threadwrap'))) stepEpisode(-1);
  });
  $('track').addEventListener('pointerdown', (ev) => {
    if (ev.pointerType === 'touch' || ev.button !== 0 || !S || !S.governing || !S.governing.arc) return;
    scrub = { x: ev.clientX, moved: false };
  });
  window.addEventListener('pointermove', (ev) => {
    if (!scrub) return;
    if (!scrub.moved && Math.abs(ev.clientX - scrub.x) < 6) return;
    scrub.moved = true;
    $('threadwrap').classList.add('scrubbing');
    const k = knotAt(ev.clientX);
    if (k) { showBubble(k, ev.clientX); $('track-in').style.setProperty('--ph', k.offsetLeft + k.offsetWidth / 2 + 'px'); }
  });
  window.addEventListener('pointerup', (ev) => {
    if (!scrub) return;
    const s = scrub; scrub = null;
    $('bubble').hidden = true; $('threadwrap').classList.remove('scrubbing');
    if (s.moved) { const k = knotAt(ev.clientX); suppressClick = true; setTimeout(() => { suppressClick = false; }, 0); if (k) openKnot(Number(k.dataset.n)); }
  });
  $('sheet').addEventListener('cancel', (ev) => { ev.preventDefault(); closeSheet(); });
  $('studio').addEventListener('cancel', (ev) => { ev.preventDefault(); closeStudio(); });
  $('palette').addEventListener('cancel', (ev) => { ev.preventDefault(); hideDialog($('palette')); });
  [['studio', () => closeStudio()], ['sheet', () => closeSheet()], ['palette', () => hideDialog($('palette'))]].forEach(([id, close]) => {
    const d = $(id); let down = false;
    const outside = (ev) => { if (ev.target !== d) return false; const r = d.getBoundingClientRect(); return ev.clientX < r.left || ev.clientX > r.right || ev.clientY < r.top || ev.clientY > r.bottom; };
    d.addEventListener('pointerdown', (ev) => { down = outside(ev); });
    d.addEventListener('click', (ev) => { const was = down; down = false; if (was && outside(ev)) close(); });
  });
  $('sheet').addEventListener('close', () => {
    const fromEl = backFocus($('sheet'));
    const key = fromEl ? null : sess.sheet && sess.sheet.back;
    sess.sheet = null; $('sheet-body').dataset.html = ''; $('threadwrap').dataset.tour = '';
    const target = key ? document.querySelector(key) : null;
    (target && !target.closest('[hidden]') ? target : $('main')).focus({ preventScroll: true });
  });
  $('studio').addEventListener('close', () => {
    if (route.studio !== null) closeStudio();
    if (backFocus($('studio'))) return;
    const key = sess.studioFrom;
    const target = key ? document.querySelector(key) : null;
    (target || $('main')).focus({ preventScroll: true });
  });
  $('palette').addEventListener('close', () => {
    if (backFocus($('palette'))) return;
    const key = sess.palFrom;
    const target = key ? document.querySelector(key) : null;
    if (target) target.focus({ preventScroll: true });
  });
  $('sheet').addEventListener('click', (ev) => { if (ev.target === $('sheet')) closeSheet(); });
  $('palette').addEventListener('click', (ev) => { if (ev.target === $('palette')) hideDialog($('palette')); });
  window.addEventListener('hashchange', applyRoute);
  window.addEventListener('online', () => { refresh().catch(() => {}); });
  let resizeT = 0;
  window.addEventListener('resize', () => { clearTimeout(resizeT); resizeT = setTimeout(() => { lastScrollKey = ''; layoutThread(); layoutWide(); }, 120); });
  $('chatscroll').addEventListener('scroll', updateJump, { passive: true });
  if (window.ResizeObserver) new ResizeObserver(() => layoutThread()).observe($('track'));

  $('scopemenu').addEventListener('keydown', (ev) => {
    const items = [...$('scopemenu').querySelectorAll('.sopt')];
    const i = items.indexOf(document.activeElement);
    if (ev.key === 'ArrowDown') { ev.preventDefault(); items[(i + 1) % items.length].focus(); }
    else if (ev.key === 'ArrowUp') { ev.preventDefault(); items[(i - 1 + items.length) % items.length].focus(); }
    else if (ev.key === 'Home') { ev.preventDefault(); items[0].focus(); }
    else if (ev.key === 'End') { ev.preventDefault(); items[items.length - 1].focus(); }
    else if (ev.key === 'Escape') { ev.preventDefault(); ev.stopPropagation(); setScopeOpen(false); $('scope-btn').focus(); }
    else if (ev.key === 'Tab') setScopeOpen(false);
  });
  $('scope-btn').addEventListener('keydown', (ev) => {
    if ((ev.key === 'ArrowUp' || ev.key === 'ArrowDown') && $('scopemenu').hidden) { ev.preventDefault(); setScopeOpen(true); }
  });

  // Drag the line between chat and book. Width is kept on this device.
  (() => {
    const bar = $('resizer'), root = document.documentElement;
    const MIN = 300, KEY = 'sss-chat-width';
    const wide = () => matchMedia('(min-width:1024px) and (min-height:600px)').matches;
    const top = () => Math.max(MIN + 40, Math.min(760, Math.round(innerWidth * 0.6)));
    function set(px, save) {
      const w = Math.max(MIN, Math.min(top(), Math.round(px)));
      root.style.setProperty('--chatw', w + 'px');
      bar.setAttribute('aria-valuenow', String(w)); bar.setAttribute('aria-valuemax', String(top()));
      if (save) { try { localStorage.setItem(KEY, String(w)); } catch (_) { /* width is not kept */ } }
      return w;
    }
    try { const kept = Number(localStorage.getItem(KEY)); if (kept) set(kept, false); } catch (_) { /* default width */ }
    bar.addEventListener('pointerdown', (ev) => {
      if (!wide() || ev.button > 0) return;
      ev.preventDefault();
      bar.setPointerCapture(ev.pointerId);
      document.body.classList.add('resizing');
      const left = $('shell').getBoundingClientRect().left;
      let last = 0;
      const move = (e) => { last = set(e.clientX - left, false); };
      const done = () => {
        bar.removeEventListener('pointermove', move); bar.removeEventListener('pointerup', done); bar.removeEventListener('pointercancel', done);
        document.body.classList.remove('resizing');
        if (last) set(last, true);
      };
      bar.addEventListener('pointermove', move); bar.addEventListener('pointerup', done); bar.addEventListener('pointercancel', done);
    });
    bar.addEventListener('dblclick', () => {
      root.style.removeProperty('--chatw'); bar.setAttribute('aria-valuenow', '340');
      try { localStorage.removeItem(KEY); } catch (_) { /* nothing kept */ }
    });
    bar.addEventListener('keydown', (ev) => {
      const now = $('chat').getBoundingClientRect().width;
      if (ev.key === 'ArrowLeft') { ev.preventDefault(); set(now - 24, true); }
      else if (ev.key === 'ArrowRight') { ev.preventDefault(); set(now + 24, true); }
      else if (ev.key === 'Home') { ev.preventDefault(); set(MIN, true); }
      else if (ev.key === 'End') { ev.preventDefault(); set(top(), true); }
      else if (ev.key === 'Enter') { ev.preventDefault(); bar.dispatchEvent(new MouseEvent('dblclick')); }
    });
    window.addEventListener('resize', () => { const w = $('chat').getBoundingClientRect().width; if (wide() && w > top()) set(top(), false); });
  })();

  // ---------- boot ----------
  persist();
  (() => {
    const { a, b } = parseHash();
    if (a === 'studio') route.studio = STUDIO.some(([id]) => id === b) ? b : '';
    else if (a === 'plan') route.room = 'plan';
    else if (a === 'memory') { route.room = 'memory'; route.person = b === undefined ? '' : b; }
    else if (a === 'write' && b) route.ep = Number(b) || 0;
  })();
  refresh().catch((e) => { if (e && e.stack) console.error(e.stack); S = null; render(); if (!e.network) report(e); })
    .finally(() => { $('main').setAttribute('aria-busy', 'false'); });
})();
