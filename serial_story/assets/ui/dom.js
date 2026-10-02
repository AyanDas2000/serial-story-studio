// Small shared building blocks. Story content always enters a text sink.
export function node(tag, text, className) {
  const element = document.createElement(tag);
  if (text !== undefined) element.textContent = String(text ?? '');
  if (className) element.className = className;
  return element;
}

export function append(parent, ...children) {
  parent.append(...children);
  return parent;
}

export function paragraph(text, className) {
  return node('p', text, className);
}

export function button(text, action, className, focusKey) {
  const element = node('button', text, className);
  element.type = 'button';
  if (focusKey) element.dataset.focusKey = focusKey;
  element.addEventListener('click', action);
  return element;
}

export function heading(title, explanation) {
  return append(node('section', undefined, 'section-intro'),
    node('h2', title), paragraph(explanation, 'muted'));
}

export function table(headers, rows) {
  const head = node('thead');
  const labels = node('tr');
  for (const label of headers) {
    const cell = node('th', label);
    cell.setAttribute('scope', 'col');
    labels.append(cell);
  }
  head.append(labels);
  const body = node('tbody');
  for (const values of rows) {
    const row = node('tr');
    for (const value of values) {
      const cell = node('td');
      cell.append(value instanceof Node ? value : document.createTextNode(String(value ?? 'Unknown')));
      row.append(cell);
    }
    body.append(row);
  }
  const wrap = append(node('div', undefined, 'table-wrap'), append(node('table'), head, body));
  wrap.tabIndex = 0;
  wrap.setAttribute('role', 'region');
  wrap.setAttribute('aria-label', headers.join(', ') + '. Scroll to see all columns.');
  return wrap;
}

export function entityName(story, id) {
  return story.entities.find(entity => entity.id === id)?.name || 'Unlisted character';
}

export function revisionLabel(episode) {
  return `Episode ${episode.number} · Revision ${episode.revision ?? episode.id} · ${episode.status}`;
}

export function focusHeading(stage) {
  const target = stage.querySelector('h2') || stage;
  target.tabIndex = -1;
  target.focus();
}

// Restore only the control that was already focused, never jump on polling.
export function rememberFocus(stage) {
  const active = document.activeElement;
  if (!stage.contains(active) || !active.dataset.focusKey) return null;
  return {
    key: active.dataset.focusKey,
    start: active.selectionStart,
    end: active.selectionEnd,
  };
}

export function restoreFocus(stage, saved) {
  if (!saved) return;
  const control = [...stage.querySelectorAll('[data-focus-key]')]
    .find(element => element.dataset.focusKey === saved.key);
  if (!control) return;
  control.focus({preventScroll: true});
  if (typeof saved.start === 'number' && control.type === 'search') {
    control.setSelectionRange(saved.start, saved.end);
  }
}
