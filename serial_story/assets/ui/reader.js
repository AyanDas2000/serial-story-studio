import {append, button, heading, node, paragraph, revisionLabel} from './dom.js';
import {evidenceProse, factRow} from './evidence.js';

export function readerView(stage, story, state, actions) {
  if (!story.episodes.length) {
    stage.append(heading('Your first episode will appear here',
      'Propose and review a draft in the local writing workflow, then refresh. This review does not generate or approve text.'));
    return;
  }
  const episode = story.episodes.find(item => item.id === state.selected) || story.episodes.at(-1);
  state.selected = episode.id;
  const reader = node('div', undefined, 'reader');
  const index = node('aside', undefined, 'episode-index');
  index.setAttribute('aria-label', 'Episode revisions');
  const label = node('label', 'Choose an episode revision');
  label.setAttribute('for', 'episode-revision');
  const select = node('select');
  select.id = 'episode-revision';
  select.dataset.focusKey = 'episode-revision';
  for (const revision of story.episodes) {
    const option = node('option', revisionLabel(revision));
    option.value = String(revision.id);
    option.selected = revision.id === episode.id;
    select.append(option);
  }
  select.value = String(episode.id);
  select.addEventListener('change', () => actions.select(Number(select.value)));
  const revisions = node('div', undefined, 'revision-list');
  for (const revision of story.episodes) {
    const control = button(revisionLabel(revision), () => actions.select(revision.id),
      undefined, `revision-${revision.id}`);
    if (revision.id === episode.id) control.setAttribute('aria-current', 'true');
    revisions.append(control);
  }
  append(index, label, select, revisions);
  const article = node('article');
  append(article, node('h2', `Episode ${episode.number}`),
    paragraph(`Revision ${episode.revision ?? episode.id} · ${episode.status} · ${episode.words} words`, 'revision-meta'),
    paragraph(episode.status === 'accepted' ? 'Accepted final prose, part of recorded history.'
      : episode.status === 'pending' ? 'Awaiting author review, not accepted history.'
        : episode.status === 'rejected' ? 'Rejected revision, not accepted history.' : 'Not accepted history.', 'small'));
  if (state.evidence) {
    article.append(button(`Return to ${state.returnLabel || 'memory'}`, actions.returnSource,
      'source-return', 'source-return'));
  }
  const prose = evidenceProse(episode, state.evidence);
  if (state.evidence && !prose.querySelector('mark')) {
    article.append(paragraph('The recorded quote does not match this accepted revision’s exact offsets. The prose is shown without a highlight.', 'notice'));
  }
  article.append(prose);
  const evidence = node('aside', undefined, 'evidence');
  append(evidence, node('h2', 'What this passage supports'),
    paragraph('A quote locates an interpretation. It does not make every character’s claim true.', 'small'));
  const facts = story.facts.filter(fact => fact.source_revision_id === episode.id);
  if (!facts.length) {
    evidence.append(paragraph(episode.status === 'accepted'
      ? 'No interpretations are recorded for this episode. This is not a completed memory review.'
      : 'Only accepted final prose can support confirmed memory.', 'small'));
  }
  for (const fact of facts) evidence.append(factRow(story, fact, actions.inspect));
  append(reader, index, article, evidence);
  stage.append(reader);
}
