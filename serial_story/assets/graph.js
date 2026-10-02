'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const labels = {character:'Character',location:'Location',fact:'Confirmed fact',situation:'Situation',episode:'Accepted episode',direction:'Future direction'};
  const relation = {about:'Concerns',relates_to:'Connects to',in_situation:'In this situation',evidenced_by:'Supported by',supersedes:'Replaces earlier fact',guides_future:'Guides'};
  const svgNS = 'http://www.w3.org/2000/svg';
  let graph, selected = null, source = null;
  const put = (parent, tag, text, attrs={}) => {
    const node = document.createElementNS(svgNS,tag);
    Object.entries(attrs).forEach(([key,value]) => node.setAttribute(key,String(value)));
    if (text !== null) node.textContent = text;
    parent.appendChild(node); return node;
  };
  const words = text => {
    const lines = [''];
    for (const word of String(text).split(/\s+/)) {
      let last = lines.length-1;
      if ((lines[last]+' '+word).trim().length > 25 && lines[last]) { lines.push(''); last++; }
      lines[last] = (lines[last]+' '+word).trim();
    }
    return [lines[0].slice(0,25), lines.length>1 ? lines[1].slice(0,23)+(lines.length>2 || lines[1].length>23 ? '…' : '') : ''];
  };
  const neighbors = id => new Set(graph.edges.filter(e=>e.source===id || e.target===id).flatMap(e=>[e.source,e.target]));
  function selectNode(node) {
    selected = node.id;
    $('selected-title').textContent = node.label;
    $('selected-status').textContent = node.status==='historical' ? 'Earlier fact, retained for the record' : node.kind==='direction' ? `Future intention · episodes ${node.start_episode}–${node.end_episode}` : node.kind==='character' || node.kind==='location' ? 'Author setup, not evidence of an event' : node.kind==='fact' ? 'Confirmed by a human from accepted prose' : labels[node.kind];
    $('evidence').hidden = !node.evidence;
    $('evidence').textContent = node.evidence || '';
    source = graph.nodes.find(n=>n.id===`episode-${node.source_revision_id}`) || (node.kind==='episode' ? node : null);
    $('source').disabled = !source;
    $('source-text').hidden = true;
    $('connections').replaceChildren();
    graph.edges.filter(e=>e.source===node.id || e.target===node.id).forEach(edge=>{
      const other = graph.nodes.find(n=>n.id===(edge.source===node.id ? edge.target : edge.source));
      if (!other) return;
      const button = document.createElement('button'); button.type='button';
      button.textContent = `${relation[edge.kind] || 'Linked to'}: ${other.label}`;
      button.addEventListener('click',()=>selectNode(other)); $('connections').appendChild(button);
    });
    const related = neighbors(node.id);
    document.querySelectorAll('.node').forEach(el=>{
      el.classList.toggle('selected',el.dataset.nodeId===selected);
      el.classList.toggle('dim',el.dataset.nodeId!==selected && !related.has(el.dataset.nodeId));
    });
  }
  function render() {
    const root = $('focus').value, query = $('search').value.trim().toLocaleLowerCase();
    const allowed = new Set();
    let seeds = graph.nodes.filter(n=>$('history').checked || n.status!=='historical');
    if (root) {
      const selectedRoot = graph.nodes.find(n=>n.id===root);
      const entity = Number(root.split('-')[1]);
      seeds = seeds.filter(n=>n.id===root || n.kind==='fact' && (selectedRoot.kind==='situation' ? n.situation_id===entity : n.subject_id===entity || n.object_id===entity) || n.kind==='direction' && (n.subject_id===null || selectedRoot.kind!=='situation' && n.subject_id===entity));
      seeds.forEach(n=>{ allowed.add(n.id); graph.edges.filter(e=>e.source===n.id).forEach(e=>allowed.add(e.target)); });
      seeds = graph.nodes.filter(n=>allowed.has(n.id) && ($('history').checked || n.status!=='historical'));
    }
    if (query) {
      const matches = seeds.filter(n=>(n.label+' '+(n.evidence||'')).toLocaleLowerCase().includes(query));
      const connected = new Set(matches.map(n=>n.id));
      matches.forEach(n=>graph.edges.filter(e=>e.source===n.id).forEach(e=>connected.add(e.target)));
      seeds = seeds.filter(n=>connected.has(n.id));
    }
    const nodes = seeds.slice(0,250);
    const byId = new Map(nodes.map(n=>[n.id,n]));
    const edges = graph.edges.filter(e=>byId.has(e.source)&&byId.has(e.target));
    $('canvas').replaceChildren();
    $('results').textContent = `${nodes.length} visible items · ${edges.length} connections`+(seeds.length>250 ? ' · narrow the filters to inspect the remaining items' : '');
    if (!nodes.length) {
      const empty = document.createElement('div'); empty.className='empty';
      const title=document.createElement('h2'); title.textContent=graph.nodes.length ? 'No matching developments' : 'Your story connections will grow here';
      const copy=document.createElement('p'); copy.textContent=graph.nodes.length ? 'Clear the filters or try another character, situation or passage.' : 'Accept an episode, confirm a fact with its supporting passage, then recreate this saved view.';
      empty.append(title,copy); $('canvas').appendChild(empty); $('source').disabled=true;
      $('selected-title').textContent='Select a fact when one is available'; $('evidence').hidden=true; $('connections').replaceChildren(); $('source-text').hidden=true;
      return;
    }
    const css=getComputedStyle(document.documentElement), number=name=>Number(css.getPropertyValue(name));
    const g={column:number('--graph-column'),row:number('--graph-row'),w:number('--graph-node-width'),h:number('--graph-node-height'),gutter:number('--graph-gutter'),header:number('--graph-header')};
    const lanes=[[],[],[],[]];
    nodes.forEach(n=>lanes[n.kind==='character'||n.kind==='location'?0:n.kind==='fact'||n.kind==='direction'?1:n.kind==='situation'?2:3].push(n));
    const height=Math.max(number('--graph-min-height'),Math.max(...lanes.map(l=>l.length))*g.row+g.header+g.gutter);
    const svg=document.createElementNS(svgNS,'svg'); svg.setAttribute('viewBox',`0 0 ${g.column*4} ${height}`); svg.setAttribute('aria-label','Characters linked to facts, situations and accepted prose'); $('canvas').appendChild(svg);
    const positions=new Map();
    lanes.forEach((lane,index)=>{
      put(svg,'text',['Cast & places','Facts & directions','Situations','Accepted prose'][index],{x:g.column*index+g.gutter,y:g.header/2,class:'lane'});
      lane.forEach((node,row)=>positions.set(node.id,{x:g.column*index+g.gutter,y:g.header+row*g.row}));
    });
    edges.forEach(edge=>{
      const a=positions.get(edge.source), b=positions.get(edge.target), forward=b.x>a.x;
      const sx=a.x+(forward?g.w:0),tx=b.x+(forward?0:g.w),sy=a.y+g.h/2,ty=b.y+g.h/2;
      const path=put(svg,'path',null,{d:`M ${sx} ${sy} C ${(sx+tx)/2} ${sy}, ${(sx+tx)/2} ${ty}, ${tx} ${ty}`,class:'edge'+(edge.kind==='guides_future'?' planned':'')});
      put(path,'title',relation[edge.kind]||edge.kind);
    });
    nodes.forEach(node=>{
      const p=positions.get(node.id), group=put(svg,'g',null,{class:'node',tabindex:0,role:'button','aria-label':`${labels[node.kind]}: ${node.label}`,'data-node-id':node.id,'data-kind':node.kind});
      put(group,'rect',null,{x:p.x,y:p.y,width:g.w,height:g.h,rx:4});
      put(group,'text',node.kind==='direction'?'Future, not a fact':node.status==='historical'?'Earlier fact':labels[node.kind],{x:p.x+g.gutter,y:p.y+g.gutter,class:'kind'});
      const lines=words(node.label); put(group,'text',lines[0],{x:p.x+g.gutter,y:p.y+g.gutter*2+4});
      if(lines[1])put(group,'text',lines[1],{x:p.x+g.gutter,y:p.y+g.gutter*3+4});
      group.addEventListener('click',()=>selectNode(node));
      group.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();selectNode(node);}});
    });
    selectNode(nodes.find(n=>n.id===selected)||nodes.find(n=>n.kind==='fact')||nodes[0]);
  }
  try {
    graph=JSON.parse($('story-data').textContent);
    $('saved').textContent=`Saved view ${graph.memory_revision} · next episode ${graph.next_episode}`;
    const facts=graph.nodes.filter(n=>n.kind==='fact'&&n.status==='current').length;
    const plans=graph.nodes.filter(n=>n.kind==='direction').length;
    $('counts').textContent=`${facts} current facts · ${plans} future directions`;
    graph.nodes.filter(n=>['character','location','situation'].includes(n.kind)).forEach(node=>{const option=document.createElement('option');option.value=node.id;option.textContent=`${labels[node.kind]}: ${node.label}`;$('focus').appendChild(option);});
    const hero=graph.nodes.find(n=>n.role==='protagonist'); if(hero)$('focus').value=hero.id;
    $('focus').addEventListener('change',render); $('history').addEventListener('change',render); $('search').addEventListener('input',render);
    $('clear').addEventListener('click',()=>{$('search').value='';$('focus').value='';render();});
    $('source').addEventListener('click',()=>{if(!source)return;$('source-heading').textContent=source.label+' · accepted version';$('source-prose').textContent=source.text;$('source-text').hidden=false;});
    render();
  } catch(error) {
    $('canvas').replaceChildren(); const message=document.createElement('p');message.className='empty';message.textContent='This saved view could not be read. Recreate the graph export, then open the new file.';$('canvas').appendChild(message);$('saved').textContent='Saved view unavailable';$('source').disabled=true;
  }
})();
