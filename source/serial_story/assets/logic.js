"use strict";
(() => {
  const names = new Set(["writer", "memory", "current"]);
  const panels = [...document.querySelectorAll(".logic-panel")];
  const links = [...document.querySelectorAll(".logic-tabs a")];
  function select(focus) {
    const requested = location.hash.slice(1);
    const name = names.has(requested) ? requested : "writer";
    panels.forEach(panel => {
      panel.hidden = panel.id !== name;
      panel.classList.toggle("changed", panel.id === name);
    });
    links.forEach(link => link.setAttribute("aria-current", String(link.hash === "#" + name)));
    if (focus) document.getElementById(name + "-title").focus({preventScroll: true});
  }
  links.forEach(link => link.addEventListener("click", event => {
    event.preventDefault();
    history.pushState({}, "", link.hash);
    select(true);
  }));
  window.addEventListener("popstate", () => select(false));
  window.addEventListener("hashchange", () => select(false));
  select(false);
})();
