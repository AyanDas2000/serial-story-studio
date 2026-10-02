'use strict';
(() => {
  const KEY = 'borrowed-witness-writing-desk-fixture-v1';
  const token = document.querySelector('meta[name="studio-token"]').content;
  const $ = (id) => document.getElementById(id);
  const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const VIEWS = [['entry', 'Start here'], ['direction', 'Story direction'], ['arc', 'Episode plan'], ['batch', 'Drafts in order'],
    ['impact', 'Effects of edits'], ['acceptance', 'Approve final text'], ['memory', 'Story facts'], ['history', 'History']];
  const reduced = () => matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Server state is the only truth about the story. `ui` holds where the author was and
  // words they typed but have not saved yet; it is restored after a refresh.
  let S = null;
  let ctx = null;
  let busy = false;
  let problem = null;
  let note = null;
  let storageOk = true;
  let focusNext = null;
  let modalReturn = null;
  const arrived = new Set();
  let ui = { view: 'entry', episode: 1, scope: 'story', thread: [], forms: {}, edits: {}, dismissed: [], open: {},
    suggesting: null, correcting: null, acceptThrough: null, composer: '' };
  try {
    const stored = JSON.parse(localStorage.getItem(KEY) || 'null');
    if (stored && typeof stored === 'object') ui = { ...ui, ...stored, forms: stored.forms || {}, edits: stored.edits || {}, open: stored.open || {} };
  } catch (_) { storageOk = false; }
  function persist() {
    try { localStorage.setItem(KEY, JSON.stringify(ui)); storageOk = true; } catch (_) { storageOk = false; }
    $('storage-label').textContent = storageOk ? 'Saved by the desk' : 'Saved by the desk. Typing not yet saved is lost if you refresh';
  }

  // ---------- motion ----------
  function animateOnce(node, ms) {
    if (!node || !node.animate || reduced()) return;
    node.getAnimations().forEach((a) => a.cancel());
    const tokens = getComputedStyle(document.documentElement);
    node.animate([{ opacity: 0.55 }, { opacity: 1 }], { duration: parseFloat(tokens.getPropertyValue(ms)), easing: tokens.getPropertyValue('--ease').trim() });
  }
  function say(text, isError) {
    const status = $('status');
    status.textContent = text;
    status.classList.toggle('error', Boolean(isError));
    animateOnce(status, '--fast');
  }
  function arrive() {
    document.querySelectorAll('[data-arrive]').forEach((node) => {
      const id = node.dataset.arrive;
      if (arrived.has(id)) return;
      arrived.add(id);
      animateOnce(node, '--base');
    });
  }

  // ---------- server ----------
  async function api(command, payload, expected) {
    let response;
    try {
      response = await fetch('/api/v1/' + command, {
        method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Studio-Token': token },
        body: JSON.stringify(expected ? { payload: payload || {}, expected } : { payload: payload || {} }),
      });
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
  async function refresh() {
    S = await getJson('/api/v1/state');
    ctx = null;
    if (S.story && S.canon.length) {
      try { ctx = await getJson('/api/v1/context?boundary=' + S.canon.length); } catch (e) {
        ctx = e.network ? null : { blocked: e.message || 'The next episode cannot be prepared yet.', code: e.code };
      }
    }
    render();
  }

  // ---------- helpers ----------
  const arcN = () => (S && S.governing.arc ? S.governing.arc.content.intentions.length : 0);
  const cursor = () => S.canon.length;
  const ep = (n) => S.episodes.find((e) => e.ordinal === n);
  const eps = () => S.episodes.filter((e) => e.ordinal <= arcN());
  const epByArtifact = (id) => S.episodes.find((e) => e.artifact_id === id);
  const intention = (n) => (S.governing.arc ? S.governing.arc.content.intentions[n - 1] || '' : '');
  const shortTitle = (n) => { const w = intention(n).split(/\s+/).filter(Boolean); return w.length > 6 ? w.slice(0, 6).join(' ') + '…' : w.join(' '); };
  const epState = (e) => (e.accepted ? 'Approved' : e.open_impacts > 0 ? 'Needs a check' : e.selection ? 'Drafted, not approved' : 'Not drafted');
  const flaggedList = () => eps().filter((e) => e.open_impacts > 0 && !e.accepted);
  const form = (key, fallback) => (ui.forms[key] !== undefined ? ui.forms[key] : fallback);
  const btn = (action, label, o = {}) => `<button type="button" data-action="${action}"${o.primary ? ' class="primary"' : ''}${o.disabled ? ' disabled' : ''}${o.extra ? ' ' + o.extra : ''}>${esc(label)}</button>`;
  const nums = (list) => (list.length === 1 ? 'Episode ' + list[0] : 'Episodes ' + list.slice(0, -1).join(', ') + ' and ' + list[list.length - 1]);
  const words = (e) => `${e.words} word${e.words === 1 ? '' : 's'}`;
  const bandText = () => { const b = S.word_band || [550, 700, 900]; return `${b[0]}–${b[2]} (aim ${b[1]})`; };
  const lengthNote = (e) => (e.length_warning ? `${words(e)}. Outside the usual ${bandText()}. You can still approve it.` : words(e));
  const toggleHtml = (key, dflt) => ((ui.open[key] === undefined ? dflt : ui.open[key]) ? ' open' : '');

  function keyOf(el) {
    if (!el || el === document.body || el === document.documentElement) return null;
    if (el.id) return '#' + el.id;
    const parts = [el.tagName.toLowerCase()];
    for (const [k, v] of Object.entries(el.dataset)) parts.push(`[data-${k.replace(/[A-Z]/g, (m) => '-' + m.toLowerCase())}="${String(v).replace(/"/g, '\\"')}"]`);
    return parts.length > 1 ? parts.join('') : null;
  }

  // ---------- failure explanations ----------
  const GO = (view, label) => [`data-view="${view}"`, label];
  const EXPLAIN = {
    stale_pointer: ['This changed since you opened it', 'It may have changed in another tab. Nothing was overwritten, and the words you typed are kept here. Reload the saved copy, then try again.', [['data-action="reload-state"', 'Reload the saved copy']]],
    overlap: ['That passage changed in the meantime', 'Nothing was written. Compare the versions, then choose what to keep.', []],
    direction_missing: ['Adopt a direction and a plan first', 'Drafting needs an adopted story direction and an adopted episode plan.', [GO('direction', 'Story direction'), GO('arc', 'Episode plan')]],
    open_conflict: ['An episode needs a check first', 'An earlier episode was edited after a later one was drafted. Check the effects, then try again.', [GO('impact', 'Check the effects')]],
    accounting_uncertain: ['A drafting request has no confirmed result', 'The desk will not retry it. Mark it as settled once you are sure, then continue.', [GO('batch', 'Open drafts')]],
    basis_changed: ['An earlier episode has no draft yet', 'Draft the earlier episodes first, in order.', [GO('batch', 'Open drafts')]],
    prefix_invalid: ['Those episodes cannot be approved together yet', 'Approve episodes in order, using the draft you currently see. Reload to see what is ready.', [['data-action="reload-state"', 'Reload the saved copy'], GO('acceptance', 'Approve final text')]],
    polish_refused: ['That asks for a story change', 'A suggestion here only smooths wording. Describe a wording change, such as "tighten the rhythm". Story changes belong in the episode plan.', []],
    invalid_range: ['That paragraph is no longer in the text', 'The paragraph changed or was removed. Reload the saved copy, then ask again.', [['data-action="reload-state"', 'Reload the saved copy']]],
    not_found: ['The desk could not find that', 'It may already have been used or replaced. Reload the saved copy to see what is current.', [['data-action="reload-state"', 'Reload the saved copy']]],
    accepted: ['Approved text is locked', 'Approved episodes change only through a staged change, which this desk does not offer yet.', []],
    ambiguous_block: ['That paragraph does not belong to this text', 'Reload the saved copy and edit again.', [['data-action="reload-state"', 'Reload the saved copy']]],
    not_revertible: ['That change cannot be undone here', 'Approved text changes only through a staged change.', []],
    invalid_claim: ['Someone has to say it', 'A statement made by a person needs a speaker. Add who says it, or pick another kind of reading.', []],
  };
  function explain(e) {
    if (e.network) return { title: 'The desk did not answer', text: 'Nothing was saved by that action. Check that the desk is still running, then reload the saved copy.', actions: [['data-action="reload-state"', 'Reload the saved copy']] };
    const known = EXPLAIN[e.code];
    if (known) return { title: known[0], text: known[1], actions: known[2] };
    if (e.status === 403) return { title: 'The desk would not accept that', text: 'This page may be out of date or the desk is read-only. Reload the page.', actions: [['data-action="reload-state"', 'Reload the saved copy']] };
    return { title: 'That did not finish', text: e.message || 'The desk could not finish that action. Reload the saved copy before trying again.', actions: [['data-action="reload-state"', 'Reload the saved copy']] };
  }
  function report(e, context) {
    const info = explain(e);
    problem = { ...info, context: context || '', id: 'p' + Date.now() };
    say(info.title + '. ' + info.text, true);
    render();
    if (e.code === 'overlap' && e.detail) openOverlap(e.detail);
  }

  async function run(label, work) {
    if (busy) { say('Still finishing the last step. Try again in a moment.'); return { ok: false }; }
    busy = true;
    $('main').setAttribute('aria-busy', 'true');
    problem = null;
    note = null;
    say(label + '…');
    try {
      const out = await work();
      try { await refresh(); } catch (_) { say('Done, but the desk could not be reloaded. Reload the page to see the saved copy.', true); return { ok: true, out }; }
      return { ok: true, out };
    } catch (e) {
      try { await refresh(); } catch (_) { /* the failure message below still applies */ }
      report(e);
      return { ok: false };
    } finally {
      busy = false;
      $('main').setAttribute('aria-busy', 'false');
    }
  }

  // ---------- rendering ----------
  function render() {
    const key = keyOf(document.activeElement);
    persist();
    renderChrome();
    $('main').innerHTML = problemHtml() + viewHtml();
    renderThread();
    arrive();
    const target = focusNext ? document.querySelector(focusNext) : key ? document.querySelector(key) : null;
    focusNext = null;
    if (target && target !== document.activeElement) target.focus({ preventScroll: true });
  }
  function renderChrome() {
    const live = S && S.provider && S.provider.live;
    $('offline').textContent = !S ? 'The desk is not answering.' : live ? 'Connected to a live writer. Drafts may cost money.' : 'Practice mode: drafts are written offline by a scripted writer. Nothing is sent anywhere and nothing is charged.';
    let line = 'No story yet';
    if (S && S.story) {
      const n = arcN();
      line = !n ? 'Story started. Choose a direction and a plan.'
        : ui.view === 'episode' ? `Following your direction and plan · episode ${ui.episode} of ${n}`
          : `Following your direction and plan · ${cursor()} of ${n} episodes approved`;
    } else if (!S) line = 'Not connected';
    $('checkpoint').textContent = line;
    const flagged = S && S.story ? flaggedList().length : 0;
    $('view-nav').innerHTML = VIEWS.map(([v, l]) => `<button type="button" data-view="${v}"${ui.view === v ? ' aria-current="page"' : ''}>${l}${v === 'impact' && flagged ? `<span class="count-badge">${flagged}</span>` : ''}</button>`).join('');
    $('episode-nav').innerHTML = S && S.story && arcN()
      ? eps().map((e) => `<button type="button" data-episode="${e.ordinal}"${ui.view === 'episode' && ui.episode === e.ordinal ? ' aria-current="page"' : ''}>Episode ${e.ordinal} <span class="sub">${epState(e)}</span></button>`).join('')
      : '<p class="meta">Episodes appear once you adopt a plan.</p>';
    $('index-basis').textContent = S && S.story && arcN() ? `${cursor()} of ${arcN()} approved · ${eps().filter((e) => e.selection).length} drafted` : '';
    $('chat-scope').value = ui.scope;
    if ($('composer') !== document.activeElement && $('composer').value !== (ui.composer || '')) $('composer').value = ui.composer || '';
    $('thread-note').textContent = ui.thread.length ? 'Messages are kept on this computer. The desk saves them but cannot list them back yet.' : '';
  }
  function renderThread() {
    $('thread').innerHTML = ui.thread.map((m) => `<div class="message"><span class="me">${m.who === 'me' ? 'You' : 'Practice writer'}:</span> <span class="${m.who === 'me' ? '' : 'reply'}">${esc(m.text)}</span></div>`).join('');
  }
  function problemHtml() {
    if (!problem) return '';
    return `<div class="problem" role="alert" data-arrive="${problem.id}"><strong>${esc(problem.title)}</strong><p>${esc(problem.text)}</p><div class="actions">${problem.actions.map(([attr, label]) => `<button type="button" ${attr}>${esc(label)}</button>`).join('')}${btn('dismiss-problem', 'Dismiss')}</div></div>`;
  }
  function noteHtml() {
    if (!note) return '';
    return `<div class="saved-note" data-arrive="${note.id}"><p><strong>${esc(note.text)}</strong></p><div class="actions">${note.eventId && canUndoId(note.eventId) ? btn('undo', 'Undo this change', { extra: `data-event="${esc(note.eventId)}"` }) : ''}${note.flagged && note.flagged.length ? `<button type="button" data-view="impact">Check the effects</button>` : ''}</div></div>`;
  }
  function viewHtml() {
    if (!S) return `<div class="kicker">Writing desk</div><h1>The desk is not answering</h1><p class="measure">Your story is stored by the desk, not by this page, so nothing here was lost. Check that the desk is running, then try again.</p><div class="actions">${btn('reload-state', 'Try again', { primary: true })}</div>`;
    if (!S.story && ui.view !== 'entry') ui.view = 'entry';
    switch (ui.view) {
      case 'direction': return directionView();
      case 'arc': return arcView();
      case 'batch': return batchView();
      case 'episode': return episodeView();
      case 'impact': return impactView();
      case 'acceptance': return acceptanceView();
      case 'memory': return memoryView();
      case 'history': return historyView();
      default: return entryView();
    }
  }

  // ---------- views ----------
  function nextStep() {
    if (!S.governing.skeleton) return { text: 'Write the idea your story stands on.', label: 'Write the story direction', view: 'direction' };
    if (!S.governing.arc) return { text: 'Say what each episode is for.', label: 'Plan the episodes', view: 'arc' };
    const flagged = flaggedList();
    if (flagged.length) return { text: `${nums(flagged.map((e) => e.ordinal))} ${flagged.length > 1 ? 'were' : 'was'} drafted from text that has since changed.`, label: 'Check the effects', view: 'impact' };
    const open = eps().filter((e) => !e.selection && !e.accepted);
    if (open.length) return { text: `${nums(open.map((e) => e.ordinal))} ${open.length > 1 ? 'have' : 'has'} no draft yet.`, label: 'Draft the episodes', view: 'batch' };
    if (readyList().length) return { text: 'Drafts are ready for you to read and approve.', label: 'Approve episodes', view: 'acceptance' };
    if (cursor() && !S.memory.accepted.length) return { text: 'Approved pages have not been read into the story facts yet.', label: 'Update story facts', view: 'memory' };
    return { text: cursor() >= arcN() ? 'Every episode in this plan is approved.' : 'Keep reading and editing.', label: 'Read an episode', view: 'episode' };
  }
  function entryView() {
    if (!S.story) {
      return `<div class="kicker">Start here</div><h1>Start a story at this desk</h1><p class="measure">The desk keeps your direction, every draft, and the exact pages you approve. Close the page whenever you like: it all comes back when you return.</p><div class="actions">${btn('create-story', 'Start the story', { primary: true })}</div>`;
    }
    const step = nextStep();
    const drafted = eps().filter((e) => e.selection).length;
    return `<div class="kicker">Start here</div><h1>Pick up where you left off</h1>
<div class="spine"><strong>Next step</strong><p>${esc(step.text)}</p><div class="actions">${step.view === 'episode' ? `<button type="button" class="primary" data-episode="${Math.min(cursor() + 1, arcN()) || 1}">${esc(step.label)}</button>` : `<button type="button" class="primary" data-view="${step.view}">${esc(step.label)}</button>`}</div></div>
<dl><dt>Story direction</dt><dd>${S.governing.skeleton ? 'In use' : 'Not chosen yet'}</dd><dt>Episode plan</dt><dd>${arcN() ? arcN() + ' episodes planned' : 'Not chosen yet'}</dd><dt>Drafts</dt><dd>${arcN() ? `${drafted} of ${arcN()} drafted` : 'None yet'}</dd><dt>Approved</dt><dd>${arcN() ? `${cursor()} of ${arcN()}` : cursor() + ''}</dd><dt>Story facts</dt><dd>${S.memory.accepted.length ? S.memory.accepted.length + ' readings from approved pages' : 'None yet'}</dd></dl>
<p class="meta">Choosing a draft is not approving it. Only the Approve page makes text final.</p>`;
  }
  function directionView() {
    const head = S.directions.skeleton;
    const gov = S.governing.skeleton;
    const base = head ? head.content : gov ? gov.content : {};
    const unused = head && (!gov || gov.revision_id !== head.revision_id);
    return `<div class="kicker">Story direction</div><h1>What is this story about?</h1>
<p class="measure">Two short statements are enough. You can change them later, and every change is kept.</p>
${gov ? `<div class="spine"><strong>In use now</strong><p>${esc(gov.content.premise)}</p><p>${esc(gov.content.spine)}</p></div>` : '<p class="notice">No direction is in use yet. Drafting waits for one.</p>'}
${unused ? `<p class="notice">A saved version is not in use yet. ${btn('adopt-saved', 'Use the saved version', { extra: 'data-layer="skeleton"' })}</p>` : ''}
<label for="premise">The premise: who and what</label><textarea id="premise" class="compact" data-form="premise">${esc(form('premise', base.premise || ''))}</textarea>
<label for="spine">The spine: where the story goes</label><textarea id="spine" class="compact" data-form="spine">${esc(form('spine', base.spine || ''))}</textarea>
<div class="actions">${btn('save-direction', 'Save and use this direction', { primary: true })}</div>
<p class="meta">Saving keeps a copy. Using it makes it the direction every draft follows.</p>`;
  }
  function arcView() {
    const head = S.directions.arc;
    const gov = S.governing.arc;
    const base = head ? head.content : gov ? gov.content : { purpose: '', intentions: [] };
    const count = Number(form('count', (base.intentions || []).length || 3));
    const unused = head && (!gov || gov.revision_id !== head.revision_id);
    const rows = Array.from({ length: count }, (_, i) => `<section class="row"><div class="row-head"><strong>Episode ${i + 1}</strong></div><label for="intention-${i}">Plan for episode ${i + 1}</label><textarea id="intention-${i}" class="compact" data-form="int${i}">${esc(form('int' + i, (base.intentions || [])[i] || ''))}</textarea></section>`).join('');
    return `<div class="kicker">Episode plan</div><h1>Give each episode a purpose</h1>
${!S.governing.skeleton ? `<p class="notice">Choose a story direction first. <button type="button" data-view="direction">Story direction</button></p>` : ''}
${gov ? `<p class="meta">In use now: ${gov.content.intentions.length} episodes.</p>` : '<p class="meta">No plan is in use yet.</p>'}
${unused ? `<p class="notice">A saved plan is not in use yet. ${btn('adopt-saved', 'Use the saved plan', { extra: 'data-layer="arc"' })}</p>` : ''}
<label for="purpose">What this stretch of the story is for</label><textarea id="purpose" class="compact" data-form="purpose">${esc(form('purpose', base.purpose || ''))}</textarea>
<label for="arc-count">Number of episodes</label><select id="arc-count">${[2, 3, 4, 5, 6].map((n) => `<option value="${n}"${n === count ? ' selected' : ''}>${n} episodes</option>`).join('')}</select>
${rows}
<div class="actions">${btn('save-arc', 'Save and use this plan', { primary: true, disabled: !S.governing.skeleton })}</div>
<p class="meta">Episodes you have already approved keep their place when you change the plan.</p>`;
  }
  const PAUSE = {
    basis_changed: 'An earlier episode was edited after a later one was drafted. Check the effects, then resume.',
    waiting_predecessor: 'An earlier episode has no draft yet.',
    accounting_uncertain: 'A drafting request has no confirmed result. It will not be retried.',
    open_conflict: 'An episode is flagged by an edit to an earlier one. Check the effects first.',
  };
  function batchView() {
    const n = arcN();
    const last = S.commissions[S.commissions.length - 1];
    const paused = last && last.status === 'paused';
    const ready = S.governing.skeleton && S.governing.arc;
    const left = n - cursor();
    const blocked = flaggedList().length > 0;
    let status = 'No drafting has started.';
    if (last) status = last.status === 'complete' ? 'The last run drafted every episode it was given.' : paused ? 'Drafting is paused: ' + (PAUSE[last.pause_reason] || 'it stopped for a reason the desk could not name.') : 'Drafting: ' + last.status + '.';
    const uncertain = S.uncertain.map((id) => `<section class="problem"><strong>Result unknown, charge held</strong><p>A drafting request has no confirmed result. It will not be retried. Say why you are settling it.</p><label for="settle-${esc(id)}">Why is it safe to settle?</label><input id="settle-${esc(id)}" data-form="settle-${esc(id)}" value="${esc(form('settle-' + id, ''))}"><div class="actions">${btn('resolve-uncertain', 'Mark as settled', { extra: `data-job="${esc(id)}"` })}</div></section>`).join('');
    return `<div class="kicker">Drafts in order</div><h1>Drafts, one after another</h1>
<p>${esc(status)}</p>
<div class="spine"><strong>Linked drafting</strong><p>Each draft is made from the earlier drafts you can see. Every draft is only a draft until you approve it.</p></div>
${uncertain}
<div class="actions">${btn('commission', left > 0 ? `Start drafting episode${left > 1 ? 's ' + (cursor() + 1) + '–' + n : ' ' + n}` : 'Start drafting', { primary: !paused, disabled: !ready || left <= 0 || paused || blocked })}${btn('resume-commission', 'Resume drafting', { primary: paused, disabled: !paused, extra: paused ? `data-commission="${esc(last.commission_id)}"` : '' })}</div>
${!ready ? `<p class="meta">To draft in order, first adopt a story direction and an episode plan. <button type="button" data-view="direction">Story direction</button> <button type="button" data-view="arc">Episode plan</button></p>` : ''}
${ready && left <= 0 ? '<p class="meta">Every episode in this plan is approved. Add more episodes on the Episode plan page.</p>' : ''}
${blocked ? '<p class="notice">Some drafts rely on text that changed. Check the effects before drafting more. <button type="button" data-view="impact">Check the effects</button></p>' : ''}
${eps().map((e) => `<section class="row"><div class="row-head"><strong>Episode ${e.ordinal} · ${esc(shortTitle(e.ordinal))}</strong><span class="tag">${epState(e)}</span></div><p class="meta">${e.selection ? esc(lengthNote(e)) : 'Not drafted yet'}${e.predecessors.length ? ` · made from ${nums(e.predecessors.map((_, i) => i + 1)).toLowerCase()}` : ''}</p><div class="actions"><button type="button" data-episode="${e.ordinal}">Open episode ${e.ordinal}</button></div></section>`).join('')}`;
  }

  function downstreamOf(e) {
    if (!e.selection) return [];
    return eps().filter((d) => d.ordinal > e.ordinal && d.predecessors.some((p) => p[0] === e.selection.revision_id)).map((d) => d.ordinal);
  }
  function eventLabel(h) {
    const e = epByArtifact(h.artifact_id);
    const where = e ? ` episode ${e.ordinal}` : '';
    const map = { save: e ? 'You edited' : 'You saved a working copy of the direction or plan', rewrite_apply: 'Applied a suggested rewrite to', revert: 'Undid a change to', redo: 'Redid a change to',
      adopt: h.artifact_id === 'arc' ? 'Adopted the episode plan' : 'Adopted the story direction', commission_start: 'Started drafting', commission_pause: 'Drafting paused', commission_resume: 'Drafting resumed',
      select: 'Draft chosen for', result_detached: 'Set aside a draft for', result_imported: 'Added a draft for', accept: 'Approved episodes', revalidate: 'Kept the text as is for', interpret: 'Corrected a reading', resolve_uncertain: 'Settled an unknown request' };
    const base = map[h.action] || h.action.replace(/_/g, ' ');
    return e && !/Adopted|Started|paused|resumed|Approved|Corrected|Settled|working copy/.test(base) ? base + where : base;
  }
  function canUndoId(id) { const h = S.history.find((x) => x.event_id === id); return !!h && canUndo(h); }
  function canUndo(h) { const e = epByArtifact(h.artifact_id); return !!e && !e.accepted && ['save', 'rewrite_apply', 'redo'].includes(h.action) && !h.undone; }
  function canRedo(h) { const e = epByArtifact(h.artifact_id); return !!e && !e.accepted && ['save', 'rewrite_apply'].includes(h.action) && h.undone && !S.history.some((x) => x.action === 'redo' && x.revert_of === h.event_id); }
  function changeRow(h) {
    return `<li><strong>${esc(eventLabel(h))}</strong><small>Change ${h.seq}${h.undone ? ' · undone' : ''}</small><div class="actions">${canUndo(h) ? btn('undo', 'Undo', { extra: `data-event="${esc(h.event_id)}"` }) : ''}${canRedo(h) ? btn('redo', 'Redo', { extra: `data-event="${esc(h.event_id)}"` }) : ''}</div></li>`;
  }

  function paragraphHtml(e, b, i) {
    const edit = ui.edits[b.block_id];
    const stale = edit && edit.base !== b.sha256;
    const cand = S.candidates.find((c) => c.ordinal === e.ordinal && c.block_id === b.block_id && !ui.dismissed.includes(c.candidate_id));
    const locked = e.accepted;
    let body;
    if (edit) {
      body = `<label for="edit-${i}">Edit paragraph ${i + 1}</label><textarea id="edit-${i}" class="edit" data-edit="${esc(b.block_id)}">${esc(edit.text)}</textarea>
${stale ? `<p class="notice">This paragraph changed after you began editing. Your words are kept above. Copy what you need, then discard your edit and start again.</p>` : ''}
<div class="actions">${btn('save-para', 'Save change', { primary: true, disabled: stale, extra: `data-block="${esc(b.block_id)}"` })}${btn('cancel-edit', stale ? 'Discard my edit' : 'Cancel', { extra: `data-block="${esc(b.block_id)}"` })}</div>`;
    } else {
      body = `<p class="prose">${esc(b.text)}</p>`;
      if (!locked) {
        body += `<div class="actions">${btn('edit-para', 'Edit paragraph', { extra: `data-block="${esc(b.block_id)}"` })}${btn('suggest-para', 'Suggest a better version', { extra: `data-block="${esc(b.block_id)}"` })}</div>`;
      }
      if (ui.suggesting === b.block_id) {
        body += `<div class="inline-field suggest-form"><div><label for="reason-${i}">What should change?</label><input id="reason-${i}" data-form="reason" value="${esc(form('reason', 'tighten the rhythm'))}"></div>${btn('get-suggestion', 'Get a suggestion', { primary: true, extra: `data-block="${esc(b.block_id)}" data-sha="${esc(b.sha256)}"` })}${btn('cancel-suggest', 'Cancel', { extra: `data-block="${esc(b.block_id)}"` })}</div>`;
      }
    }
    if (cand && !edit) {
      body += `<div class="cand" data-arrive="cand-${esc(cand.candidate_id)}"><h3>Suggested rewrite · ${esc(cand.reason)}</h3><div class="split"><section><h2>Now</h2><p class="prose">${esc(b.text)}</p></section><section><h2>Suggested</h2><p class="prose">${esc(cand.replacement)}</p></section></div><div class="actions">${btn('apply-candidate', 'Use this version', { primary: true, extra: `data-cand="${esc(cand.candidate_id)}"` })}${btn('dismiss-candidate', 'Keep my version', { extra: `data-cand="${esc(cand.candidate_id)}"` })}</div></div>`;
    }
    return `<section class="para" data-para="${i + 1}"><div class="para-head"><span class="meta">Paragraph ${i + 1}</span>${edit ? '<span class="tag">Unsaved edit</span>' : ''}</div>${body}</section>`;
  }
  function episodeView() {
    const n = ui.episode;
    const e = ep(n);
    if (!e || n > arcN()) return `<div class="kicker">Episode</div><h1>No such episode</h1><p class="empty">Pick an episode from the list, or adopt an episode plan first.</p>`;
    if (!e.selection) return `<div class="kicker">Episode ${n} of ${arcN()}</div><h1>Episode ${n}</h1><p class="measure">Plan: ${esc(intention(n))}</p><p class="empty">This episode has no draft yet. Drafts are made in order on the Drafts page.</p><div class="actions"><button type="button" class="primary" data-view="batch">Go to drafts</button></div>`;
    const down = downstreamOf(e);
    const recent = S.history.filter((h) => h.artifact_id === e.artifact_id && ['save', 'rewrite_apply', 'revert', 'redo'].includes(h.action)).slice(0, 4);
    return `<div class="kicker">Episode ${n} of ${arcN()} · ${epState(e)}</div><h1>Episode ${n}</h1>
<p class="measure">Plan: ${esc(intention(n))}</p>
<p class="meta">${esc(lengthNote(e))}${e.predecessors.length ? ` · made from ${nums(e.predecessors.map((_, i) => i + 1)).toLowerCase()} as ${e.predecessors.length > 1 ? 'they were' : 'it was'} when drafted` : ''}</p>
${e.open_impacts > 0 && !e.accepted ? `<p class="notice">Earlier text changed after this was drafted. <button type="button" data-view="impact">Check the effects</button></p>` : ''}
${e.accepted ? '<p class="notice">This episode is approved. Approved text changes only through a staged change, which this desk does not offer yet.</p>' : down.length ? `<p class="meta">Saving a change here will flag ${nums(down).toLowerCase()} for a check, because ${down.length > 1 ? 'they were' : 'it was'} drafted from this text.</p>` : ''}
${noteHtml()}
${e.blocks.map((b, i) => paragraphHtml(e, b, i)).join('')}
${recent.length ? `<h2>Recent changes to this episode</h2><ul class="history">${recent.map(changeRow).join('')}</ul>` : ''}
<details data-toggle="exact-${n}"${toggleHtml('exact-' + n, false)}><summary>Exact version details</summary><dl><dt>Version</dt><dd>${esc(e.selection.revision_id)}</dd><dt>Fingerprint</dt><dd>${esc(e.selection.sha256)}</dd><dt>Chosen by</dt><dd>${e.selection.selected_by === 'commission' ? 'The drafting run' : 'You'}</dd><dt>Set-aside drafts</dt><dd>${e.alternatives.length}</dd></dl></details>`;
  }
  function impactView() {
    const flagged = flaggedList();
    const last = S.commissions[S.commissions.length - 1];
    const paused = last && last.status === 'paused';
    if (!flagged.length) {
      return `<div class="kicker">Effects of edits</div><h1>Nothing to check</h1><p class="empty">This page fills in when you edit an earlier episode that later ones rely on.</p>${paused && !S.uncertain.length ? `<p class="notice">Drafting is paused. ${btn('resume-commission', 'Resume drafting', { primary: true, extra: `data-commission="${esc(last.commission_id)}"` })}</p>` : ''}`;
    }
    return `<div class="kicker">Effects of edits</div><h1>Your edit is kept. Check what relied on it.</h1>
<p class="measure">${esc(nums(flagged.map((e) => e.ordinal)))} ${flagged.length > 1 ? 'were' : 'was'} drafted from text you have since changed. Nothing was rewritten for you.</p>
${flagged.map((e) => `<section class="row"><div class="row-head"><strong>Episode ${e.ordinal}</strong><span class="tag">Needs a check</span></div><p class="meta">${esc(lengthNote(e))}</p><div class="actions"><button type="button" data-episode="${e.ordinal}">Read the text</button>${btn('revalidate-slot', 'It still fits', { primary: true, extra: `data-slot="${e.ordinal}"` })}</div></section>`).join('')}
<p class="meta">"It still fits" is your own judgment that the episode still agrees with the changed text. It does not rewrite anything.</p>
${paused ? `<div class="actions">${btn('resume-commission', 'Resume drafting', { extra: `data-commission="${esc(last.commission_id)}"` })}</div>` : ''}`;
  }
  function readyList() {
    const out = [];
    for (let n = cursor() + 1; n <= arcN(); n++) {
      const e = ep(n);
      if (!e || !e.selection || e.open_impacts > 0) break;
      out.push(e);
    }
    return out;
  }
  function chosenForAcceptance() {
    const ready = readyList();
    const through = Math.min(Math.max(Number(ui.acceptThrough) || ready.length, 1), ready.length || 1);
    return ready.slice(0, through);
  }
  function acceptanceView() {
    const ready = readyList();
    const chosen = chosenForAcceptance();
    const done = S.canon.map((c) => c.ordinal);
    const firstBlocked = ep(cursor() + ready.length + 1);
    let why = '';
    if (cursor() >= arcN() && arcN()) why = 'Every episode in this plan is approved.';
    else if (firstBlocked && firstBlocked.open_impacts > 0) why = `Episode ${firstBlocked.ordinal} needs a check before it can be approved.`;
    else if (cursor() + ready.length < arcN()) why = `Episode ${cursor() + ready.length + 1} has no draft yet.`;
    return `<div class="kicker">Approve final text</div><h1>Choosing a draft is not approving it</h1>
<p>Approved so far: <strong>${done.length ? nums(done) : 'none'}</strong>. Ready to approve next: <strong>${ready.length ? nums(ready.map((e) => e.ordinal)) : 'none'}</strong>.</p>
${why ? `<p class="notice">${esc(why)} ${firstBlocked && firstBlocked.open_impacts > 0 ? '<button type="button" data-view="impact">Check the effects</button>' : ''}</p>` : ''}
${ready.length ? `<label for="accept-through">Approve</label><select id="accept-through">${ready.map((e, i) => `<option value="${i + 1}"${chosen.length === i + 1 ? ' selected' : ''}>${i === 0 ? 'Episode ' + e.ordinal : 'Episodes ' + ready[0].ordinal + '–' + e.ordinal}</option>`).join('')}</select>` : ''}
${ready.map((e) => `<details data-toggle="read-${e.ordinal}"${toggleHtml('read-' + e.ordinal, true)}><summary>Episode ${e.ordinal} · ${esc(lengthNote(e))}</summary>${e.blocks.map((b) => `<p class="prose">${esc(b.text)}</p>`).join('')}</details>`).join('')}
<div class="actions">${btn('accept-prefix', chosen.some((e) => e.length_warning) ? 'Approve anyway' : chosen.length > 1 ? `Approve episodes ${chosen[0].ordinal}–${chosen[chosen.length - 1].ordinal}, these versions` : 'Approve this version', { primary: true, disabled: !ready.length })}</div>
${chosen.some((e) => e.length_warning) ? `<p class="notice">Outside the usual ${bandText()} words. The desk keeps a length note with the approval and never refuses on length.</p>` : ''}
${S.acceptances.length ? `<h2>Approvals so far</h2><ul class="history">${S.acceptances.map((a) => `<li><strong>Approval ${a.canon_seq}</strong>${a.warnings.length ? a.warnings.map((w) => `<small>Episode ${w.ordinal}: ${w.words} words, outside ${w.band[0]}–${w.band[2]}. Approved anyway.</small>`).join('') : '<small>Every episode was within the usual length.</small>'}</li>`).join('')}</ul>` : ''}`;
  }
  const KINDS = { summary: 'Summary', testimony: 'Something a person says', event: 'Something that happens', belief: 'Something someone believes', knowledge: 'Something someone knows' };
  const VALID = { unknown: 'Not known to be true', true_in_story: 'True in the story', false_in_story: 'False in the story' };
  function paragraphOf(c) {
    const e = ep(c.narrative_ordinal);
    const i = e ? e.blocks.findIndex((b) => b.block_id === c.block_id) : -1;
    return `Episode ${c.narrative_ordinal}${i >= 0 ? ', paragraph ' + (i + 1) : ''}`;
  }
  function claimHtml(c) {
    const open = ui.correcting === c.claim_id;
    return `<div class="claim" data-claim-row="${esc(c.claim_id)}"><div class="row-head"><span class="tag">${esc(KINDS[c.kind] || c.kind)}</span><span class="meta">${esc(paragraphOf(c))}</span></div><blockquote>${esc(c.quote)}</blockquote>
<p class="meta">${c.speaker ? 'Said by ' + esc(c.speaker) + ' · ' : ''}${esc(VALID[c.world_validity] || c.world_validity)}${c.prior_claim_id ? ' · corrected by you' + (c.note ? ': ' + esc(c.note) : '') : ''}</p>
${open ? `<div class="correct-form"><div class="grid-form"><div><label for="corr-kind">What kind of reading is it?</label><select id="corr-kind" data-form="corr_kind">${Object.entries(KINDS).slice(0, 3).map(([k, l]) => `<option value="${k}"${form('corr_kind', c.kind) === k ? ' selected' : ''}>${l}</option>`).join('')}</select></div><div><label for="corr-speaker">Who says it (if a person)</label><input id="corr-speaker" data-form="corr_speaker" value="${esc(form('corr_speaker', c.speaker || ''))}"></div><div><label for="corr-valid">Is it true in the story?</label><select id="corr-valid" data-form="corr_valid">${Object.entries(VALID).map(([k, l]) => `<option value="${k}"${form('corr_valid', c.world_validity) === k ? ' selected' : ''}>${l}</option>`).join('')}</select></div></div>
<label for="memory-correction">What should this reading say?</label><textarea id="memory-correction" class="compact" data-form="corr_note">${esc(form('corr_note', ''))}</textarea><div class="actions">${btn('save-correction', 'Save correction', { primary: true, extra: `data-claim="${esc(c.claim_id)}"` })}${btn('cancel-correction', 'Cancel', { extra: `data-claim="${esc(c.claim_id)}"` })}</div></div>` : `<div class="actions">${btn('correct-memory', 'Correct this reading', { extra: `data-claim="${esc(c.claim_id)}"` })}</div>`}</div>`;
  }
  function memoryView() {
    const claims = S.memory.accepted;
    const byEp = {};
    claims.forEach((c) => { (byEp[c.narrative_ordinal] = byEp[c.narrative_ordinal] || []).push(c); });
    let next = '';
    if (cursor()) {
      next = ctx && ctx.blocked ? `<p class="notice"><strong>The next episode cannot be prepared yet.</strong> ${esc(ctx.blocked)}${ctx.code === 'open_conflict' ? ' <button type="button" data-view="impact">Check the effects</button>' : ''}</p>`
        : ctx ? `<p class="notice"><strong>For the next episode:</strong> ${ctx.mode === 'indexed' ? 'the story facts below are up to date.' : esc(ctx.notice || 'Memory updating; using exact accepted pages.')}</p>` : '';
    }
    return `<div class="kicker">Story facts</div><h1>What the desk has read in your approved pages</h1>
<p class="measure">Only approved pages are read. Each reading quotes the exact words it came from, and you can correct any of them. A correction never erases the original.</p>
${!cursor() ? '<p class="empty">Nothing is approved yet, so there are no story facts. Approve an episode first. <button type="button" data-view="acceptance">Approve final text</button></p>' : `<div class="actions">${btn('update-memory', 'Update story facts', { primary: !claims.length })}</div>`}
${next}
${cursor() && !claims.length ? '<p class="meta">Not read yet. Update story facts to read the approved pages.</p>' : ''}
${Object.keys(byEp).sort((a, b) => a - b).map((k) => `<h2>Episode ${k}</h2>${byEp[k].map(claimHtml).join('')}`).join('')}`;
  }
  function historyView() {
    const rows = S.history.filter((h) => h.action !== 'job_frozen');
    return `<div class="kicker">History</div><h1>Pick up where you left off</h1>
<p class="measure">Everything below is stored by the desk, so it is still here after you refresh or come back later.</p>
<div class="spine"><strong>${cursor()} of ${arcN() || 0} episodes approved</strong><p>${nextStep().text}</p><div class="actions"><button type="button" data-view="${nextStep().view === 'episode' ? 'entry' : nextStep().view}">${esc(nextStep().label)}</button></div></div>
<h2>Recent changes</h2>${rows.length ? `<ul class="history">${rows.map(changeRow).join('')}</ul>` : '<p class="empty">No changes yet. Start anywhere in the room.</p>'}`;
  }

  // ---------- modal ----------
  function openModal(title, html, trigger) {
    modalReturn = keyOf(trigger || document.activeElement);
    $('modal-title').textContent = title;
    $('modal-body').innerHTML = html;
    const dlg = $('modal');
    if (!dlg.open) dlg.showModal();
  }
  function openOverlap(d) {
    const parts = [];
    if (d.before !== undefined || d.ai !== undefined) {
      parts.push(['Before', d.before], ['Suggested', d.ai], ['Now', d.now]);
    } else parts.push(['The change you would undo', d.expected], ['Now', d.now]);
    openModal('The passage changed since', `<p>Nothing was written. The words below differ, so the desk will not overwrite the newer text.</p><div class="compare">${parts.map(([h, t]) => `<section><h2>${h}</h2><p class="prose">${t == null ? '(removed)' : esc(t)}</p></section>`).join('')}</div><div class="actions">${btn('close-modal', 'Keep current text', { primary: true })}</div>`);
  }
  $('modal').addEventListener('close', () => {
    const key = modalReturn;
    modalReturn = null;
    const target = key ? document.querySelector(key) : null;
    (target || $('main')).focus({ preventScroll: true });
  });

  // ---------- actions ----------
  function go(view) {
    ui.view = view; note = null; problem = null;
    render();
    window.scrollTo(0, 0);
  }
  function openEpisode(n) {
    ui.view = 'episode'; ui.episode = n; note = null; problem = null;
    render();
    window.scrollTo(0, 0);
  }
  function textOf(id) {
    if (ui.forms[id] !== undefined) return String(ui.forms[id]).trim();
    const node = document.querySelector(`[data-form="${id}"]`) || $(id);
    return node ? node.value.trim() : '';
  }

  async function saveAndAdopt(layer, content, label) {
    const rev = await api('save_direction', { layer, content });
    const gov = S.governing[layer];
    await api('adopt', { revision_id: rev.revision_id }, { governing: gov ? gov.revision_id : null });
    return label;
  }
  const actions = {
    'reload-state': async () => { problem = null; try { await refresh(); say('Reloaded the saved copy.'); } catch (e) { report(e); } },
    'dismiss-problem': () => { problem = null; render(); },
    'create-story': async () => { const r = await run('Starting the story', () => api('create_story', {})); if (r.ok) { ui.view = 'direction'; render(); say('Story started. Choose its direction next.'); } },
    'save-direction': async () => {
      const premise = textOf('premise'), spine = textOf('spine');
      if (!premise || !spine) { say('Write both the premise and the spine first.', true); return; }
      const r = await run('Saving the direction', () => saveAndAdopt('skeleton', { premise, spine }));
      if (r.ok) { ui.forms.premise = undefined; ui.forms.spine = undefined; ui.view = 'arc'; render(); say('Direction saved and in use. Plan the episodes next.'); }
      else if (problem) { problem.text += ' Your words are kept in the boxes.'; render(); }
    },
    'save-arc': async () => {
      const count = Number(form('count', 3));
      const purpose = textOf('purpose');
      const intentions = Array.from({ length: count }, (_, i) => textOf('intention-' + i));
      if (!purpose || intentions.some((t) => !t)) { say('Give the plan a purpose and a line for every episode.', true); return; }
      const r = await run('Saving the plan', () => saveAndAdopt('arc', { purpose, intentions }));
      if (r.ok) { Object.keys(ui.forms).filter((k) => /^(int\d+|purpose|count)$/.test(k)).forEach((k) => delete ui.forms[k]); ui.view = 'batch'; render(); say(`Plan saved and in use: ${count} episodes. You can draft them now.`); }
    },
    'adopt-saved': async (t) => {
      const layer = t.dataset.layer;
      const head = S.directions[layer];
      const gov = S.governing[layer];
      const r = await run('Using the saved version', () => api('adopt', { revision_id: head.revision_id }, { governing: gov ? gov.revision_id : null }));
      if (r.ok) say('The saved version is now in use.');
    },
    commission: async () => {
      const first = cursor() + 1, last = arcN();
      const r = await run('Drafting the episodes', () => api('commission_arc', { slots: [first, last], progression: 'provisional_chain' }));
      if (!r.ok) return;
      const c = r.out;
      if (c.status === 'complete') { ui.view = 'episode'; ui.episode = first; render(); say(`Drafted ${nums(Array.from({ length: last - first + 1 }, (_, i) => first + i)).toLowerCase()}. Read them, then approve when you are happy.`); }
      else say('Drafting paused: ' + (PAUSE[c.pause_reason] || 'it stopped early.'), true);
    },
    'resume-commission': async (t) => {
      const r = await run('Resuming the drafts', () => api('resume_commission', { commission_id: t.dataset.commission }));
      if (!r.ok) return;
      say(r.out.status === 'complete' ? 'Drafting finished.' : 'Drafting paused again: ' + (PAUSE[r.out.pause_reason] || 'it stopped early.'), r.out.status !== 'complete');
    },
    'resolve-uncertain': async (t) => {
      const reason = textOf('settle-' + t.dataset.job);
      if (!reason) { say('Write why it is safe to settle this request.', true); return; }
      const r = await run('Settling the request', () => api('resolve_uncertain', { job_id: t.dataset.job, reason }));
      if (r.ok) say('Settled. You can continue drafting.');
    },
    'edit-para': (t) => {
      const e = ep(ui.episode); const b = e.blocks.find((x) => x.block_id === t.dataset.block);
      ui.edits[b.block_id] = { text: b.text, base: b.sha256 };
      focusNext = `textarea[data-edit="${b.block_id}"]`;
      render();
    },
    'cancel-edit': (t) => { delete ui.edits[t.dataset.block]; focusNext = `button[data-action="edit-para"][data-block="${t.dataset.block}"]`; render(); },
    'save-para': async (t) => {
      const e = ep(ui.episode); const id = t.dataset.block; const edit = ui.edits[id];
      if (!edit.text.trim()) { say('A paragraph cannot be empty. Cancel the edit to keep the old words.', true); return; }
      const blocks = e.blocks.map((b) => ({ block_id: b.block_id, text: b.block_id === id ? edit.text : b.text }));
      const r = await run('Saving your change', () => api('save_revision', { ordinal: e.ordinal, base_revision_id: e.selection.revision_id, blocks }, { selection_cas: e.selection.cas }));
      if (!r.ok) return;
      delete ui.edits[id];
      const flagged = r.out.flagged || [];
      note = { id: 'n' + r.out.event_id, text: 'Saved.' + (flagged.length ? ` ${nums(flagged)} ${flagged.length > 1 ? 'were' : 'was'} drafted from the old text and now ${flagged.length > 1 ? 'need' : 'needs'} a check.` : ''), eventId: r.out.event_id, flagged };
      focusNext = `button[data-action="edit-para"][data-block="${id}"]`;
      render();
      say(note.text);
    },
    'suggest-para': (t) => { ui.suggesting = t.dataset.block; focusNext = '.suggest-form input'; render(); },
    'cancel-suggest': (t) => { ui.suggesting = null; focusNext = `button[data-action="suggest-para"][data-block="${t.dataset.block}"]`; render(); },
    'get-suggestion': async (t) => {
      const reason = textOf('reason') || (document.querySelector('.suggest-form input') || {}).value || '';
      if (!reason.trim()) { say('Say what should change, for example "tighten the rhythm".', true); return; }
      const e = ep(ui.episode);
      const r = await run('Asking for a suggestion', () => api('request_rewrite', { ordinal: e.ordinal, block_id: t.dataset.block, intent: 'polish', reason }, { block_sha256: t.dataset.sha }));
      if (!r.ok) return;
      ui.suggesting = null;
      focusNext = `button[data-action="apply-candidate"][data-cand="${r.out.candidate_id}"]`;
      render();
      say('Suggestion ready. Compare it with your paragraph below.');
    },
    'dismiss-candidate': (t) => { ui.dismissed.push(t.dataset.cand); render(); say('Kept your version. The suggestion is set aside on this computer.'); },
    'apply-candidate': async (t) => {
      const e = ep(ui.episode);
      const r = await run('Using the suggestion', () => api('apply_candidate', { candidate_id: t.dataset.cand }, { selection_cas: e.selection.cas }));
      if (!r.ok) return;
      const flagged = r.out.flagged || [];
      note = { id: 'n' + r.out.event_id, text: 'Suggestion used.' + (flagged.length ? ` ${nums(flagged)} ${flagged.length > 1 ? 'need' : 'needs'} a check.` : ''), eventId: r.out.event_id, flagged };
      render();
      say(note.text);
    },
    undo: async (t) => {
      const r = await run('Undoing the change', () => api('revert_event', { event_id: t.dataset.event }));
      if (r.ok) { note = null; render(); say('Undone. The earlier words are back; your other edits are untouched.'); }
    },
    redo: async (t) => {
      const r = await run('Redoing the change', () => api('redo_event', { event_id: t.dataset.event }));
      if (r.ok) { note = null; render(); say('Redone.'); }
    },
    'revalidate-slot': async (t) => {
      const n = Number(t.dataset.slot);
      const r = await run('Recording your decision', () => api('revalidate', { ordinal: n }));
      if (r.ok) say(`Episode ${n} kept as is.` + (flaggedList().length ? '' : ' Nothing else needs a check.'));
    },
    'accept-prefix': (t) => {
      const chosen = chosenForAcceptance();
      if (!chosen.length) return;
      const list = chosen.map((e) => `<li><strong>Episode ${e.ordinal}</strong> · ${esc(lengthNote(e))}</li>`).join('');
      openModal('Approve these versions?', `<p>Approving makes the exact text you see now final. Later changes to approved text need a staged change.</p><ul>${list}</ul><div class="actions">${btn('confirm-accept', 'Approve', { primary: true })}${btn('close-modal', 'Cancel')}</div>`, t);
    },
    'confirm-accept': async () => {
      const chosen = chosenForAcceptance();
      const payload = { episodes: chosen.map((e) => ({ ordinal: e.ordinal, revision_id: e.selection.revision_id, sha256: e.selection.sha256 })) };
      const expected = { canon_seq: S.story.canon_seq };
      $('modal').close();
      const r = await run('Approving the episodes', () => api('accept_prefix', payload, expected));
      if (!r.ok) return;
      ui.acceptThrough = null;
      const w = r.out.warnings || [];
      render();
      say(`Approved ${nums(chosen.map((e) => e.ordinal)).toLowerCase()}.` + (w.length ? ` Length note kept for ${nums(w.map((x) => x.ordinal)).toLowerCase()}: outside ${bandText()}.` : '') + ' Update the story facts next.');
    },
    'update-memory': async () => {
      const r = await run('Reading the approved pages', () => api('update_memory', {}));
      if (r.ok) say(r.out.imported ? `Read ${r.out.imported} approved episode${r.out.imported > 1 ? 's' : ''}. ${S.memory.accepted.length} readings are ready to review.` : 'Nothing new to read. The story facts are up to date.');
    },
    'correct-memory': (t) => { ui.correcting = t.dataset.claim; focusNext = '#memory-correction'; render(); },
    'cancel-correction': (t) => { ui.correcting = null; focusNext = `button[data-action="correct-memory"][data-claim="${t.dataset.claim}"]`; render(); },
    'save-correction': async (t) => {
      const c = S.memory.accepted.find((x) => x.claim_id === t.dataset.claim);
      const kind = form('corr_kind', c.kind), valid = form('corr_valid', c.world_validity), speaker = textOf('corr_speaker') || (kind === 'testimony' ? (c.speaker || '') : '');
      const text = textOf('corr_note');
      if (!text) { say('Say what the reading should be, so the correction is clear later.', true); return; }
      const r = await run('Saving your correction', () => api('interpret', { claim_id: c.claim_id, kind, speaker: speaker || null, world_validity: valid, note: text }));
      if (r.ok) { ui.correcting = null; ['corr_kind', 'corr_speaker', 'corr_valid', 'corr_note'].forEach((k) => delete ui.forms[k]); render(); say('Correction saved. The original reading is kept in its history.'); }
    },
    send: async () => {
      const text = $('composer').value.trim();
      if (!text) { say('Write a question or an idea first.', true); return; }
      const target = ui.scope === 'episode' ? 'episode:' + ui.episode : ui.scope;
      const r = await run('Sending', () => api('converse', { target, text }));
      if (!r.ok) return;
      ui.thread.push({ who: 'me', text }, { who: 'reply', text: r.out.text });
      if (ui.thread.length > 40) ui.thread = ui.thread.slice(-40);
      ui.composer = ''; $('composer').value = '';
      render();
      say('Reply received. Your story did not change.');
    },
    talk: () => { $('composer').scrollIntoView({ block: 'center' }); $('composer').focus(); },
    'writing-focus': () => { $('main').focus(); window.scrollTo(0, 0); },
    history: () => go('history'),
    'close-modal': () => $('modal').close(),
  };

  document.addEventListener('click', (ev) => {
    const t = ev.target.closest('[data-action],[data-view],[data-episode]');
    if (!t || t.disabled) return;
    if (t.dataset.action) { const fn = actions[t.dataset.action]; if (fn) fn(t); return; }
    if (t.dataset.view) { go(t.dataset.view); return; }
    if (t.dataset.episode) openEpisode(Number(t.dataset.episode));
  });
  document.addEventListener('input', (ev) => {
    const t = ev.target;
    if (t.dataset && t.dataset.form) { ui.forms[t.dataset.form] = t.value; persist(); }
    else if (t.dataset && t.dataset.edit && ui.edits[t.dataset.edit]) { ui.edits[t.dataset.edit].text = t.value; persist(); }
    else if (t.id === 'composer') { ui.composer = t.value; persist(); }
  });
  document.addEventListener('change', (ev) => {
    const t = ev.target;
    if (t.id === 'arc-count') { ui.forms.count = Number(t.value); focusNext = '#arc-count'; render(); }
    else if (t.id === 'chat-scope') { ui.scope = t.value; persist(); }
    else if (t.id === 'accept-through') { ui.acceptThrough = Number(t.value); focusNext = '#accept-through'; render(); }
    else if (t.dataset && t.dataset.form && t.tagName === 'SELECT') { ui.forms[t.dataset.form] = t.value; persist(); }
  });
  document.addEventListener('toggle', (ev) => {
    const t = ev.target;
    if (t.dataset && t.dataset.toggle) { ui.open[t.dataset.toggle] = t.open; persist(); }
  }, true);
  $('main').addEventListener('keydown', (ev) => {
    if (ev.key !== 'Escape') return;
    const field = ev.target.closest('.suggest-form, .correct-form');
    if (!field) return;
    ev.preventDefault();
    if (field.classList.contains('suggest-form')) actions['cancel-suggest']({ dataset: { block: ui.suggesting } });
    else actions['cancel-correction']({ dataset: { claim: ui.correcting } });
  });

  persist();
  refresh().catch((e) => { S = null; render(); say(explain(e).title + '. ' + explain(e).text, true); })
    .finally(() => { $('main').setAttribute('aria-busy', 'false'); });
})();
