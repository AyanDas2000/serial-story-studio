import {append, entityName, heading, node, paragraph, revisionLabel, table} from './dom.js';

export function qualityView(stage, story) {
  stage.append(heading('Quality needs your judgment.',
    'Length is checked. Narrative quality, contradictions and the long arc still need an author’s review.'));
  if (story.episodes.length) {
    stage.append(table(['Episode revision', 'Length', '400–700 words', 'Human decision'],
      story.episodes.map(episode => [revisionLabel(episode), `${episode.words} words`,
        episode.word_count_ok ? 'Within range' : 'Outside range', episode.status])));
  } else {
    stage.append(paragraph('Draft an episode in the local workflow, then refresh to inspect its actual word count.', 'muted'));
  }
  const checks = node('ol', undefined, 'checks');
  for (const text of [
    'Opening: is there a clear reason to keep reading?',
    'Continuity: do actions, locations, timing and character knowledge match accepted evidence?',
    'Voice and scene: are the characters distinct, the prose specific and the action understandable?',
    'Payoff and hook: does the episode deliver a change and leave a meaningful unresolved question?',
    'Memory: are established events separate from attributed claims and future intentions?',
    'Long arc: does the next episode follow the serial’s direction instead of repeating it?',
  ]) checks.append(node('li', text));
  append(stage, node('h2', 'Read with these questions'), checks,
    paragraph('These are unsaved review prompts, not scores. No automated critic has run.', 'small'));
}

export function receiptsView(stage, story) {
  stage.append(heading('See the recorded decisions.',
    'Receipts belong to this story. They do not certify a complete memory review or an account-wide spending limit.'));
  const spent = story.calls.reduce((total, call) => total + Number(call.spent_micro_usd || 0), 0);
  const reserved = story.calls.reduce((total, call) => total + Number(call.reserved_micro_usd || 0), 0);
  stage.append(paragraph(`Recorded calls: ${story.calls.length}. Recorded cost: $${(spent / 1e6).toFixed(6)}. Held for unresolved calls: $${(reserved / 1e6).toFixed(6)}.`, 'small'));
  if (story.fixture_only) stage.append(paragraph('These are offline workflow-test receipts, not measured real-model usage or savings.', 'small'));
  if (story.reviews.length) {
    stage.append(table(['Reviewed item', 'Decision', 'Recorded at'],
      story.reviews.map(review => [`${review.target_kind} ${review.target_id}`, review.decision, review.created_at])));
  } else {
    stage.append(paragraph('Author decisions appear here after they are saved by the local writing workflow.', 'muted'));
  }
  stage.append(node('h2', 'Material selected for earlier drafts'));
  if (!story.calls.length) stage.append(paragraph('No writing-call receipts are recorded. This review never makes model calls.', 'muted'));
  for (const call of story.calls) {
    const row = node('section', undefined, 'receipt-row');
    let manifest;
    try { manifest = JSON.parse(call.context_manifest); } catch { manifest = null; }
    const state = {succeeded: 'Completed', failed: 'Failed', reserved: 'Awaiting completion', uncertain: 'Outcome needs review'}[call.status] || 'Needs review';
    row.append(paragraph(`${call.episode === 0 ? 'Series planning' : 'Episode ' + call.episode} · ${state}`));
    if (!manifest || typeof manifest !== 'object' || Array.isArray(manifest)) manifest = {};
    const list = key => Array.isArray(manifest[key]) ? manifest[key].join(', ') || 'none' : 'not recorded';
    if (Array.isArray(manifest.included)) {
      row.append(paragraph(`Recent episodes included: ${list('included')}. Left out: ${list('omitted')}.`, 'small'));
    }
    if (Array.isArray(manifest.facts)) {
      row.append(paragraph(`Memory interpretations selected: ${list('facts')}. Future directions selected: ${list('directions')}.`, 'small'));
    }
    if (Array.isArray(manifest.active_cast)) {
      row.append(paragraph(`Focused cast: ${manifest.active_cast.map(id => entityName(story, id)).join(', ') || 'no specific cast selected'}.`, 'small'));
    }
    if (!Object.keys(manifest).length) row.append(paragraph('No material-selection receipt was recorded for this call.', 'small'));
    stage.append(row);
  }
}

export function modelView(stage, provider, status) {
  stage.append(heading('Writing is off.',
    'This is read-only catalog information, not a connected writing provider. Generation needs separate approval for model, access and spending.'));
  if (status === 'loading') {
    stage.append(heading('Opening model information', 'The review is checking locally attached catalog metadata. No inference is being requested.'));
    return;
  }
  if (status === 'error') {
    stage.append(heading('Model information could not be read', 'Choose Refresh review to retry. Story inspection remains available.'));
    return;
  }
  if (!provider?.model) {
    stage.append(heading('A writing model has not been selected', 'No model metadata is attached to this review. No credentials are stored in this page.'));
    return;
  }
  const streaming = provider.advertised_streaming === true ? 'Streaming is advertised'
    : provider.advertised_streaming === false ? 'Streaming is not advertised' : 'Streaming support is unknown';
  append(stage, paragraph(`${provider.display_name || 'Selected catalog model'} · ${provider.model}`),
    paragraph(`Catalog checked: ${provider.checked_at || 'date unknown'}. ${streaming}. Live inference has not been tested here.`, 'small'));
  const prices = provider.pricing || {};
  const price = key => {
    const value = prices[key];
    return (typeof value === 'number' && Number.isFinite(value) && value >= 0)
      || (typeof value === 'string' && value.trim() && Number.isFinite(Number(value)) && Number(value) >= 0)
      ? String(value) : 'Unknown';
  };
  stage.append(table(['Catalog rate', `${prices.currency || 'Currency unknown'} per million tokens`], [
    ['Ordinary input', price('input_per_million')], ['Output', price('output_per_million')],
    ['Reused input', price('cache_read_per_million')], ['First saved input', price('cache_write_per_million')],
  ]));
  append(stage, paragraph('Reused-input savings have not been verified. Supported provider controls and actual usage measurements are needed before claiming them.'),
    paragraph('No model calls, automatic inference retries or key changes are enabled by this review.', 'small'));
}
