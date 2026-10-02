/* Presentation only. The authoring module retains ownership of every form and action. */
(function () {
 'use strict';
 document.addEventListener('DOMContentLoaded', function () {
  var links = Array.from(document.querySelectorAll('[data-view]'));
  var panels = Array.from(document.querySelectorAll('[data-workspace]'));
  var names = ['plan', 'write', 'continuity', 'models'];
  var chosen = Boolean(window.location.hash);
  var restored = false;
  var navigation = links.filter(function (link) { return link.id.indexOf('nav-') === 0 || link.parentElement && link.parentElement.tagName === 'NAV'; });
  function show(name) {
   if (names.indexOf(name) < 0) name = 'plan';
   panels.forEach(function (panel) { panel.hidden = panel.id !== 'view-' + name; });
   links.forEach(function (link) {
    if (link.dataset.view === name) link.setAttribute('aria-current', 'page');
    else link.removeAttribute('aria-current');
   });
  }
  links.forEach(function (link) {
   link.addEventListener('click', function () {
    chosen = true; show(link.dataset.view); window.scrollTo(0, 0);
    if (navigation.indexOf(link) < 0) document.getElementById('workspace').focus({preventScroll:true});
   });
  });
  navigation.forEach(function (link, index) {
   link.addEventListener('keydown', function (event) {
    var next = index;
    if (event.key === 'ArrowRight' || event.key === 'ArrowDown') next = (index + 1) % navigation.length;
    else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') next = (index + navigation.length - 1) % navigation.length;
    else if (event.key === 'Home') next = 0;
    else if (event.key === 'End') next = navigation.length - 1;
    else return;
    event.preventDefault(); chosen = true; show(navigation[next].dataset.view); navigation[next].focus(); window.scrollTo(0, 0);
   });
  });
  function id(name) { return document.getElementById(name); }
  function text(name, value) { if (id(name).textContent !== value) id(name).textContent = value; }
  function reflect() {
   var saved = null;
   try { saved = JSON.parse(id('remote-copy').textContent); } catch (_) { /* The first saved copy is still loading. */ }
   var unavailable = id('manuscript-panel').hidden;
   if (saved && !restored) {
    restored = true;
    if (!chosen && !unavailable) show('write');
   }
   id('write-prerequisite').hidden = !unavailable;
   id('continuity-prerequisite').hidden = id('setup-section').hidden;
   id('models-prerequisite').hidden = id('setup-section').hidden;
   var plan = saved && saved.plan;
   var pending = saved && saved.pending;
   var beat = plan && plan.future && plan.future.find(function (b) { return !pending || b.episode === pending.number; });
   id('approved-intention').hidden = unavailable || !plan || plan.status !== 'approved';
   text('intention-text', beat ? beat.intention : 'No intention is recorded for this episode. Review Plan before drafting.');
   var prose = id('manuscript').value;
   text('editor-save-state', unavailable ? '' : pending ?
    (prose === pending.text ? 'Saved manuscript: text version ' + pending.text_version : 'Unsaved manuscript: save before accepting') :
    (prose ? 'Unsaved manuscript: save as a draft first' : 'No saved draft: write or paste your manuscript'));
  }
  // Observe only core-owned output. No extra fetches, writes, value assignments or access to private state.
  var observer = new MutationObserver(reflect);
  ['remote-copy', 'manuscript-panel', 'setup-section'].forEach(function (name) {
   observer.observe(id(name), {childList:true, subtree:true, characterData:true, attributes:true, attributeFilter:['hidden']});
  });
  id('manuscript').addEventListener('input', reflect);
  show(window.location.hash.slice(1));
  reflect();
 });
})();
