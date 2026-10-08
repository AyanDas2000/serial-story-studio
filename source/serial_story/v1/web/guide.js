'use strict';
/* The guide: a short walkthrough for a first visit, and the full "how it works" page with diagrams.
   Everything here is static text and drawings. It reads nothing from the story. */
(() => {
  const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const fmt = (n) => Number(n).toLocaleString('en-US');

  const lines = (x, y, rows, cls) => rows.map((t, i) => `<text class="${cls}" x="${x}" y="${y + i * 16}" text-anchor="middle">${esc(t)}</text>`).join('');
  const box = (x, y, w, h, title, sub, cls) => {
    const head = [].concat(title), rest = sub ? [].concat(sub) : [];
    const top = y + h / 2 - (head.length + rest.length) * 8 + 12;
    return `<g class="gb ${cls}"><rect x="${x}" y="${y}" width="${w}" height="${h}" rx="10"/>${lines(x + w / 2, top, head, 't')}${lines(x + w / 2, top + head.length * 16, rest, 'sub')}</g>`;
  };
  const arrow = (d, id) => `<path class="ga" d="${d}" marker-end="url(#${id})"/>`;
  const svg = (id, w, h, label, body) => `<div class="gfig"><svg class="gsvg" viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(label)}"><defs><marker id="${id}" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path class="gm" d="M0 1L9 5L0 9z"/></marker></defs>${body}</svg></div>`;
  const legend = (a, b) => `<p class="glegend"><span class="gk yu"></span>${esc(a)}<span class="gk tl"></span>${esc(b)}</p>`;
  const list = (items) => `<ol class="gtext">${items.map((t) => `<li>${esc(t)}</li>`).join('')}</ol>`;

  function loop() {
    const names = [['Direction', 'premise, spine', 'yu'], ['Plan', 'one line each', 'yu'], ['Draft', 'the writer', 'tl'], ['Read and edit', 'your words win', 'yu'], ['Approve', 'locks the words', 'yu'], ['Save', 'quoted facts', 'tl']];
    const parts = names.map(([t, s, c], i) => box(10 + i * 126, 40, 108, 64, t, s, c));
    const arrows = names.slice(1).map((_, i) => arrow(`M${118 + i * 126} 72H${136 + i * 126}`, 'gm-loop')).join('');
    const back = arrow('M688 104V170H64V104', 'gm-loop');
    const note = `<text class="gn" x="376" y="190" text-anchor="middle">Then the next episode</text>`;
    return svg('gm-loop', 760, 210, 'The loop for each episode: direction, plan, draft, read and edit, approve, save, then back to the next draft.', parts.join('') + arrows + back + note)
      + legend('You decide', 'The tool works') + list(['You write the direction: the premise and the spine.', 'You plan the episodes, one line each.', 'The writer drafts an episode.', 'You read it and edit it.', 'You approve it, which locks the exact words.', 'Saving reads the approved text for facts, each with a quote.', 'Then the next episode starts.']);
  }

  function who() {
    const you = ['Adopt the direction', 'Adopt the plan', 'Approve an episode', 'Save story changes'];
    const tool = ['Draft episodes', 'Suggest wording', 'Read it for facts', 'Answer in chat'];
    const row = (items, y, c) => items.map((t, i) => box(10 + i * 188, y, 172, 54, t, null, c)).join('');
    const body = `<text class="gn" x="10" y="26">You decide</text>${row(you, 36, 'yu')}
<path class="gdiv" d="M10 118H750"/>
<text class="gn" x="380" y="146" text-anchor="middle">Nothing below changes your story until something above says so.</text>
<text class="gn" x="10" y="184">The tool suggests</text>${row(tool, 194, 'tl')}`;
    return svg('gm-who', 760, 262, 'Two rows. You decide: adopt the direction, adopt the plan, approve an episode, save story changes. The tool suggests: drafts, better wording, reading for facts, chat replies. Nothing the tool does changes the story until you act.', body)
      + legend('Only you do these', 'The tool only suggests these')
      + list(['You decide four things: adopt the direction, adopt the plan, approve an episode, save story changes.', 'The tool drafts, suggests wording, reads for facts and answers in chat.', 'Nothing the tool does changes your story until you act.']);
  }

  function writer() {
    const sent = ['Standing rules: length and grounding', 'Premise and spine', 'Purpose of this stretch', 'Voice notes and never-use words', 'Every earlier episode, in full', "This episode's one line"];
    const never = ['Memory facts', 'Your private notes', 'Secrets and their trigger words', 'Chat messages'];
    const left = sent.map((t, i) => box(24, 52 + i * 38, 400, 30, t, null, 'yu')).join('');
    const right = never.map((t, i) => box(494, 52 + i * 38, 244, 30, t, null, 'never')).join('');
    const body = `<text class="gn" x="10" y="30">Sent to the writer for each episode</text>${left}<text class="gn" x="480" y="30">Never sent</text>${right}`;
    return svg('gm-writer', 760, 296, 'What the writer is sent: the standing rules, premise and spine, purpose, voice notes, every earlier episode in full, and this episode\'s one line. Never sent: memory facts, private notes, secrets, chat.', body)
      + list(['Sent: the standing rules about length and grounding, the premise and spine, the purpose of this stretch, voice notes, every earlier episode in full, and this episode\'s one line.', 'Never sent: memory facts, your private notes, your secrets and their trigger words, your chat messages.']);
  }

  function memory() {
    const body = box(10, 40, 150, 70, 'Draft', 'yours to edit', 'yu')
      + box(190, 40, 150, 70, 'Approved text', 'locked', 'yu')
      + box(370, 40, 170, 70, 'The reader', 'proposes facts with quotes', 'tl')
      + box(570, 40, 180, 70, 'The desk checks', 'is the quote in the text?', 'tl')
      + arrow('M160 75H186', 'gm-mem') + arrow('M340 75H366', 'gm-mem') + arrow('M540 75H566', 'gm-mem')
      + box(500, 160, 250, 56, 'Kept in Memory', 'with its source', 'yu')
      + box(190, 160, 250, 56, 'Set aside and counted', 'no matching quote, or already known', 'tl')
      + arrow('M690 110V156', 'gm-mem') + arrow('M630 110L440 164', 'gm-mem');
    return svg('gm-mem', 760, 240, 'From draft to memory: a draft you edit, approved locked text, the reader proposes facts with quotes, the desk checks each quote is in the text, then each fact is kept with its source or set aside and counted.', body)
      + legend('Yours', 'Done by the tool') + list(['You edit the draft.', 'You approve it and the words are locked.', 'The reader proposes facts, each with a quote.', 'The desk checks every quote is really in the text.', 'A fact that passes is kept in Memory with its source. One that fails is set aside and counted.']);
  }

  function length(L) {
    const a = L || { low: 550, target: 700, high: 900, limit: 1080 };
    const seg = [[10, 150, 'under', 'Short', 'allowed, marked'], [160, 330, 'normal', 'Your range', 'used as it is'], [490, 130, 'long', 'A bit long', 'kept, marked'], [620, 130, 'over', 'Too long', 'set aside']];
    const body = seg.map(([x, w, c, t, s]) => `<g class="gz ${c}"><rect x="${x}" y="56" width="${w}" height="52"/>${lines(x + w / 2, 78, [t], 't')}${lines(x + w / 2, 96, [s], 'sub')}</g>`).join('')
      + [[160, 'shortest', a.low], [325, 'aim', a.target], [490, 'longest', a.high], [620, 'longest + 20%', a.limit]].map(([x, t, n]) => `<path class="gdiv" d="M${x} 108V122"/>${lines(x, 138, [t], 'gn')}${lines(x, 156, [fmt(n) + ' words'], 'sub')}`).join('');
    return svg('gm-len', 760, 176, `Length bands for this series: under ${a.low} words allowed and marked, ${a.low} to ${a.high} used, up to ${a.limit} kept and marked, more than ${a.limit} set aside.`, body)
      + list([`Under ${fmt(a.low)} words: allowed, and marked.`, `${fmt(a.low)} to ${fmt(a.high)} words: used as it is. The aim is ${fmt(a.target)}.`, `Up to ${fmt(a.limit)} words: kept, and marked as long.`, `More than ${fmt(a.limit)} words: set aside. You can read it, use it and trim it, or ask for a new one.`]);
  }

  function money() {
    const body = box(10, 40, 150, 64, 'Your limit', 'set per series', 'yu')
      + box(190, 40, 170, 64, 'Is there room?', 'checked before each call', 'tl')
      + box(390, 40, 160, 64, 'Room is held', 'while it runs', 'tl')
      + box(580, 40, 170, 64, 'The writer answers', 'cost is settled', 'tl')
      + arrow('M160 72H186', 'gm-money') + arrow('M360 72H386', 'gm-money') + arrow('M550 72H576', 'gm-money')
      + box(190, 150, 200, 56, 'No room', 'nothing is sent, nothing charged', 'never')
      + box(420, 150, 330, 56, 'No clear answer', 'marked unconfirmed, never retried, you settle it', 'never')
      + arrow('M275 104V146', 'gm-money') + arrow('M665 104V146', 'gm-money');
    return svg('gm-money', 760, 230, 'Money: your limit, a room check before each call, room held while it runs, the cost settled. With no room nothing is sent. With no clear answer the call is marked unconfirmed and never retried.', body)
      + list(['Each live series has its own limit.', 'Before every call the desk checks there is room.', 'While the call runs that amount is held.', 'When the writer answers, the real cost is settled.', 'No room: nothing is sent and nothing is charged.', 'No clear answer: the call is marked unconfirmed. It is never retried. You settle it.']);
  }

  const sec = (id, h, text, figure) => `<section class="gsec" aria-labelledby="g-${id}"><h3 id="g-${id}">${esc(h)}</h3>${text.map((t) => `<p>${esc(t)}</p>`).join('')}${figure}</section>`;

  function logic(opts) {
    const o = opts || {};
    return `<div class="guide"><h2>How it works</h2>
<p class="hint">The whole idea, start to finish. You direct the future. Approved text is the past. Memory is a record beside both, and it never steers the writer by itself.</p>
${sec('who', 'Who decides', ['The tool can draft, suggest, read and reply. It cannot change your story.', 'Four actions are yours alone, and chat cannot do any of them.'], who())}
${sec('loop', 'The loop, episode by episode', ['Each episode goes the same way. You can stop at any step and come back.'], loop())}
${sec('writer', 'What the writer is shown', ['The writer gets the direction, your voice notes, and every earlier episode in full. It does not get Memory, so a wrong fact in Memory cannot leak into a draft.', 'Its standing instructions say to treat earlier episodes as fixed, keep track of who knows what, show where evidence comes from, and leave a fact vague when unsure. After each draft the desk lists any new names it introduced, so you can check they fit.', 'Studio, Support, "What the writer was shown" shows the exact request for any draft.'], writer())}
${sec('memory', 'From a draft to memory', ['Memory is built only from text you approved. Every fact carries a quote, and the desk keeps a fact only if the quote is really in the text.'], memory())}
${sec('length', 'Length', ['Each series has its own shortest, aim and longest, set in Studio, Length. The writer is told these numbers for every episode.'], length(o.length))}
${sec('money', 'Money and safety', [o.live ? 'This series uses a live writer. Every call counts against its limit, and the limit is never passed.' : 'This series uses the practice writer. Nothing leaves this computer and nothing is charged. A live writer works the way shown below.', 'Secrets: each has trigger words that are checked before anything is sent. The check finds words, not ideas, so keep the secret itself out of the plan.', 'History: your edits can be undone. Approved text changes only through an explicit change.'], money())}
</div>`;
  }

  const STEPS = [
    ['Welcome', () => `<p>Serial Story Studio is a desk for writing a serial one episode at a time. A writer drafts, you decide. It is meant to be careful, not clever.</p>${who()}`],
    ['Choose a writer', () => `<p>Each series has one writer, chosen when you create it.</p><ul class="gbul"><li><b>Practice writer.</b> Follows a script. Free. Nothing leaves your computer. Good for learning the desk.</li><li><b>Live writer.</b> Real models, through Merge. It needs a Merge key and has its own spend limit. Ask the person who sent you this for the key and the steps.</li></ul>${money()}`],
    ['Start a series', () => `<p>Make a series, then give it four things, in this order.</p><ol class="gbul"><li><b>Premise and spine.</b> Who and what the story is about, and where it is going. Keep any secret out of these.</li><li><b>A plan.</b> One line for each episode. You can plan a hundred and draft only a few.</li><li><b>Length.</b> Shortest, aim and longest for each episode. The usual is 550, 700 and 900 words.</li><li><b>Voice (optional).</b> Notes on how it should sound, and words never to use.</li></ol>`],
    ['The loop', () => `<p>Draft a few episodes, read them, fix what you want, approve what is right. Then draft the next.</p>${loop()}`],
    ['What it protects', () => `<p>Fewer invented facts, by design.</p>${writer()}`],
    ['Memory', () => `<p>Approve an episode, then save its story changes. You read the list before you save.</p>${memory()}`],
  ];

  window.StudioGuide = { logic, steps: STEPS.map(([title, html]) => ({ title, html })), count: STEPS.length };
})();
