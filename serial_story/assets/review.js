import {focusHeading, heading, rememberFocus, restoreFocus} from './ui/dom.js';
import {readerView} from './ui/reader.js';
import {planningView} from './ui/planning.js';
import {memoryView} from './ui/evidence.js';
import {modelView, qualityView, receiptsView} from './ui/review-details.js';

const byId = id => document.getElementById(id);
const stage = byId('workspace');
const refreshButton = byId('refresh');
const views = new Set(['read', 'storyboard', 'memory', 'quality', 'receipts', 'model']);
const state = {selected: null, evidence: null, returnLabel: null,
  beatRange: '', beatSearch: '', memoryFilter: 'current', graphOpen: false};
let story = null;
let provider = null;
let providerStatus = 'loading';
let activeView = 'read';
let loading = false;
let lastRead = null;
let sourceReturn = null;

function updateNavigation() {
  for (const control of byId('nav').querySelectorAll('button')) {
    if (control.dataset.view === activeView) control.setAttribute('aria-current', 'page');
    else control.removeAttribute('aria-current');
  }
  byId('mobile-view').value = activeView;
}

function navigate(view, {focus = true, historyMode = 'push'} = {}) {
  activeView = views.has(view) ? view : 'read';
  const hash = '#' + activeView;
  if (location.hash !== hash) {
    history[historyMode === 'replace' ? 'replaceState' : 'pushState'](null, '', hash);
  }
  updateNavigation();
  render({focus});
}

const actions = {
  select(id) {
    state.selected = id;
    state.evidence = null;
    sourceReturn = null;
    navigate('read');
  },
  inspect(fact, control) {
    if (!story.episodes.some(episode => episode.id === fact.source_revision_id)) return;
    if (!state.evidence) sourceReturn = {view: activeView, selected: state.selected,
      focus: control ? {key: control.dataset.focusKey} : null};
    state.returnLabel = sourceReturn?.view === 'read' ? 'episode evidence' : sourceReturn?.view || 'memory';
    state.selected = fact.source_revision_id;
    state.evidence = fact;
    navigate('read');
    const passage = stage.querySelector('mark');
    if (passage) { passage.focus(); passage.scrollIntoView({block: 'center'}); }
  },
  returnSource() {
    const destination = sourceReturn;
    state.evidence = null;
    sourceReturn = null;
    if (destination) state.selected = destination.selected;
    navigate(destination?.view || 'memory', {focus: false});
    if (destination?.focus) restoreFocus(stage, destination.focus);
    else focusHeading(stage);
  },
};

function render({focus = false} = {}) {
  if (!story) return;
  const saved = rememberFocus(stage);
  stage.replaceChildren();
  stage.setAttribute('aria-busy', 'false');
  byId('scope').textContent = story.fixture_only
    ? 'Offline workflow-test material, not a generated serial. Generation and spending are off.'
    : 'Read-only on this device. Generation, editing, approvals and spending are off.';
  const renderers = {
    read: () => readerView(stage, story, state, actions),
    storyboard: () => planningView(stage, story, state, actions),
    memory: () => memoryView(stage, story, state, actions),
    quality: () => qualityView(stage, story),
    receipts: () => receiptsView(stage, story),
    model: () => modelView(stage, provider, providerStatus),
  };
  renderers[activeView]();
  if (focus) focusHeading(stage);
  else restoreFocus(stage, saved);
}

async function readJSON(url) {
  const response = await fetch(url, {cache: 'no-store', signal: AbortSignal.timeout(8000)});
  if (!response.ok) throw new Error('Review information unavailable');
  return response.json();
}

function hasProseSelection() {
  const selection = window.getSelection?.();
  return selection && !selection.isCollapsed && stage.contains(selection.anchorNode);
}

async function refresh(manual = false) {
  if (loading) return;
  loading = true;
  refreshButton.disabled = true;
  refreshButton.textContent = 'Reading review…';
  if (!story) stage.setAttribute('aria-busy', 'true');
  try {
    const data = await readJSON('/api/story');
    if (!data || !data.revision || !['episodes', 'facts', 'entities', 'directions', 'calls', 'reviews']
      .every(key => Array.isArray(data[key]))) throw new Error('Incomplete story observation');
    const changed = story?.revision !== data.revision;
    // Polling must not destroy selected prose. Apply on a later tick.
    const deferred = changed && !manual && hasProseSelection();
    if (!deferred) {
      story = data;
      if (state.evidence) state.evidence = story.facts.find(fact => fact.id === state.evidence.id) || null;
      if (changed) render();
    }
    lastRead = new Date().toLocaleTimeString();
    byId('error').hidden = true;
    byId('connection').textContent = deferred
      ? `Last checked ${lastRead}. New prose is waiting until you finish selecting. Refresh review to show it now.`
      : `Last read ${lastRead}. Checks every 3 seconds while visible.`;
  } catch {
    byId('connection').textContent = lastRead ? `Last read ${lastRead}. Latest check failed.` : 'Local review unavailable';
    byId('error').hidden = false;
    byId('error').textContent = story
      ? 'Could not refresh the story. Showing the last successful observation. Check the local review, then choose Refresh review.'
      : 'The story could not be opened. Check that the local review is running, then choose Refresh review to retry.';
    if (!story) stage.replaceChildren(heading('The story could not be opened',
      'Check the local review, then choose Refresh review above to retry. No story data was changed.'));
  } finally {
    stage.setAttribute('aria-busy', 'false');
    // Catalog failure is independent: the story stays usable.
    if (manual || providerStatus === 'loading') {
      providerStatus = 'loading';
      if (activeView === 'model' && story) render();
      try {
        const info = await readJSON('/api/provider');
        if (!info || typeof info !== 'object' || Array.isArray(info)) throw new Error('Invalid catalog');
        provider = info;
        providerStatus = 'loaded';
      } catch {
        provider = null;
        providerStatus = 'error';
      }
      if (activeView === 'model') render();
    }
    loading = false;
    refreshButton.disabled = false;
    refreshButton.textContent = 'Refresh review';
  }
}

refreshButton.addEventListener('click', () => refresh(true));
for (const control of byId('nav').querySelectorAll('button')) {
  control.addEventListener('click', () => navigate(control.dataset.view));
}
byId('mobile-view').addEventListener('change', event => navigate(event.target.value));
function followHash() {
  const view = location.hash.slice(1);
  if (view === 'workspace') return; // Native skip link, not a section switch.
  if (view !== activeView || !views.has(view)) navigate(view, {historyMode: 'replace', focus: Boolean(story)});
}
window.addEventListener('hashchange', followHash);
window.addEventListener('popstate', followHash);
followHash();
updateNavigation();
refresh();
setInterval(() => { if (!document.hidden) refresh(); }, 3000);
document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); });
