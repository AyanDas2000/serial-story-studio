import {append, button, entityName, heading, node, paragraph} from './dom.js';

export function evidenceProse(episode, fact) {
  const prose = node('div', episode.prose, 'prose');
  if (!fact || episode.status !== 'accepted' || fact.source_revision_id !== episode.id) return prose;
  // SQLite/Python evidence offsets count Unicode code points, not UTF-16 units.
  const characters = Array.from(episode.prose);
  const start = fact.evidence_start;
  const end = fact.evidence_end;
  const exact = Number.isInteger(start) && Number.isInteger(end)
    && start >= 0 && end > start && end <= characters.length
    && characters.slice(start, end).join('') === fact.evidence;
  if (!exact) return prose;
  const mark = node('mark', fact.evidence);
  mark.id = 'evidence-passage';
  mark.tabIndex = -1;
  prose.replaceChildren(document.createTextNode(characters.slice(0, start).join('')),
    mark, document.createTextNode(characters.slice(end).join('')));
  return prose;
}

export function factState(fact) {
  return fact.superseded_by ? 'superseded' : fact.status;
}

export function sourceButton(story, fact, inspect) {
  const episode = story.episodes.find(item => item.id === fact.source_revision_id);
  const control = button(episode ? `Inspect episode ${episode.number}'s source` : 'Source revision unavailable',
    () => inspect(fact, control), 'source', `source-${fact.id}`);
  control.disabled = !episode;
  return control;
}

export function factRow(story, fact, inspect) {
  return append(node('section', undefined, 'fact-row'),
    paragraph(`${entityName(story, fact.subject_id)} · ${fact.predicate}: ${fact.value}`),
    paragraph(`${factState(fact)} interpretation`, 'small'), node('blockquote', fact.evidence),
    sourceButton(story, fact, inspect));
}

export function memoryView(stage, story, state, actions) {
  stage.append(heading('Trace an interpretation back to prose.',
    'Confirmed interpretations, proposals and earlier interpretations stay distinct. Inspect a source to see its exact passage.'));
  const toolbar = node('div', undefined, 'toolbar');
  const label = node('label', 'Memory state');
  const select = node('select');
  select.id = 'memory-state';
  select.dataset.focusKey = 'memory-state';
  label.setAttribute('for', select.id);
  for (const [value, text] of [['current', 'Current confirmed'], ['proposed', 'Proposed'],
    ['rejected', 'Rejected'], ['superseded', 'Superseded'], ['all', 'All states']]) {
    const option = node('option', text);
    option.value = value;
    option.selected = state.memoryFilter === value;
    select.append(option);
  }
  select.value = state.memoryFilter;
  const rows = node('div');
  const count = paragraph('', 'small');
  function updateRows() {
    const facts = story.facts.filter(fact => state.memoryFilter === 'all'
      || (state.memoryFilter === 'current' ? factState(fact) === 'confirmed' : factState(fact) === state.memoryFilter));
    count.textContent = `${facts.length} of ${story.facts.length} interpretations shown. This review cannot confirm or reject them.`;
    rows.replaceChildren();
    if (!facts.length) {
      rows.append(heading(story.facts.length ? 'No interpretations match this state' : 'Memory begins with accepted evidence',
        story.facts.length ? 'Choose another state or clear the filter to see all recorded interpretations.'
          : 'Record interpretations in the local writing workflow, then refresh this read-only review.'));
      if (story.facts.length) rows.append(button('Clear filter', () => {
        state.memoryFilter = 'all';
        select.value = 'all';
        updateRows();
        select.focus();
      }, undefined, 'clear-memory'));
    }
    for (const fact of facts) rows.append(factRow(story, fact, actions.inspect));
  }
  select.addEventListener('change', () => { state.memoryFilter = select.value; updateRows(); });
  append(toolbar, label, select);
  append(stage, toolbar, count, rows);
  updateRows();
  const details = node('details', undefined, 'graph-details');
  details.open = Boolean(state.graphOpen);
  details.append(node('summary', 'Explore the source-linked memory graph'));
  const graphStatus = paragraph('The graph shows current and earlier confirmed interpretations, registered cast, situations and future directions. Proposed and rejected interpretations appear only in the list.', 'small');
  details.append(graphStatus);
  function loadGraph() {
    state.graphOpen = details.open;
    if (!details.open || details.querySelector('iframe')) return;
    graphStatus.textContent = 'Opening the recorded memory graph. List filters do not change this graph.';
    const frame = node('iframe');
    frame.title = 'Source-linked confirmed story memory and future directions';
    frame.src = '/graph?revision=' + encodeURIComponent(story.revision);
    frame.addEventListener('load', () => { graphStatus.textContent = 'Graph document opened. If it reports a read failure, refresh the review and reopen it.'; });
    frame.addEventListener('error', () => { graphStatus.textContent = 'The graph could not be opened. Refresh the review and reopen it.'; });
    details.append(frame);
  }
  details.addEventListener('toggle', loadGraph);
  stage.append(details);
  loadGraph();
}
