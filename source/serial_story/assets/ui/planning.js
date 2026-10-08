import {append, button, heading, node, paragraph, table} from './dom.js';

export function planningView(stage, story, state, actions) {
  stage.append(heading('Intentions are not history.',
    'Browse planned intentions alongside recorded episodes. A plan is not evidence that an event happened.'));
  const plan = story.plan?.content;
  if (!plan || !Array.isArray(plan.beats) || !plan.beats.length) {
    stage.append(heading('The story needs an episode plan',
      'Create and review a plan in the local workflow, then refresh. This review cannot add a plan.'));
    return;
  }
  if (story.fixture_only) stage.append(paragraph('Offline workflow-test planning contains placeholders, not a developed serial.', 'small'));
  const toolbar = node('div', undefined, 'toolbar');
  const rangeLabel = node('label', 'Episode range');
  rangeLabel.setAttribute('for', 'beat-range');
  const range = node('select');
  range.id = 'beat-range';
  range.dataset.focusKey = 'beat-range';
  const arcs = Array.isArray(plan.arcs) && plan.arcs.length ? plan.arcs
    : [{start: Math.min(...plan.beats.map(beat => beat.episode)), end: Math.max(...plan.beats.map(beat => beat.episode))}];
  const allRange = `${Math.min(...arcs.map(arc => arc.start))}:${Math.max(...arcs.map(arc => arc.end))}`;
  const choices = [{value: allRange, text: 'All planned episodes'}, ...arcs.map(arc => ({
    value: `${arc.start}:${arc.end}`, text: `Episodes ${arc.start}–${arc.end}`,
  }))];
  if (!choices.some(choice => choice.value === state.beatRange)) state.beatRange = choices[1]?.value || allRange;
  for (const choice of choices) {
    const option = node('option', choice.text);
    option.value = choice.value;
    option.selected = choice.value === state.beatRange;
    range.append(option);
  }
  range.value = state.beatRange;
  const searchLabel = node('label', 'Find a planned intention');
  searchLabel.setAttribute('for', 'beat-search');
  const search = node('input');
  search.id = 'beat-search';
  search.type = 'search';
  search.value = state.beatSearch;
  search.dataset.focusKey = 'beat-search';
  const rows = node('section');
  const count = paragraph('', 'small');
  function clearFilters() {
    state.beatSearch = '';
    state.beatRange = allRange;
    search.value = '';
    range.value = allRange;
    updateRows();
    search.focus();
  }
  function updateRows() {
    const [from, to] = state.beatRange.split(':').map(Number);
    const beats = plan.beats.filter(beat => beat.episode >= from && beat.episode <= to
      && String(beat.intention).toLowerCase().includes(state.beatSearch.toLowerCase()));
    count.textContent = `${beats.length} of ${plan.beats.length} planned intentions shown.`;
    rows.replaceChildren();
    if (!beats.length) {
      rows.append(heading('No intentions match these filters', 'Clear filters to inspect all planned episodes.'),
        button('Clear filters', clearFilters, undefined, 'clear-planning'));
      return;
    }
    rows.append(table(['Episode', 'Planned intention', 'Recorded prose'], beats.map(beat => {
      const revisions = story.episodes.filter(episode => episode.number === beat.episode);
      const latest = revisions.find(episode => episode.status === 'accepted') || revisions.at(-1);
      return [beat.episode, beat.intention, latest
        ? button(latest.status === 'accepted' ? 'Read accepted prose' : `Read ${latest.status} revision`,
          () => actions.select(latest.id), undefined, `beat-${beat.episode}`) : 'Not written'];
    })));
  }
  range.addEventListener('change', () => { state.beatRange = range.value; updateRows(); });
  search.addEventListener('input', () => { state.beatSearch = search.value; updateRows(); });
  append(toolbar, append(node('div', undefined, 'field'), rangeLabel, range),
    append(node('div', undefined, 'field'), searchLabel, search));
  append(stage, toolbar, count, rows);
  updateRows();
  const directions = story.directions.filter(direction => direction.status === 'active');
  stage.append(node('h2', 'Author’s active directions'));
  if (!directions.length) stage.append(paragraph('No future directions are recorded. Add them in the local workflow, then refresh.', 'muted'));
  for (const direction of directions) {
    stage.append(append(node('section', undefined, 'direction-row'), paragraph(direction.text),
      paragraph(`Episodes ${direction.start_episode}–${direction.end_episode}. Intention only, not an event.`, 'small')));
  }
}
