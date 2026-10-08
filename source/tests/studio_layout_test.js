const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
class Element {
 constructor(id){this.id=id;this.hidden=false;this.value='';this.textContent='';this.attrs={};this.listeners={};this.dataset={};this.open=false;this.disabled=false;}
 addEventListener(name,fn){(this.listeners[name] ??= []).push(fn);}
 setAttribute(k,v){this.attrs[k]=String(v);} removeAttribute(k){delete this.attrs[k];}
 focus(){document.activeElement=this;} fire(name,event={}){(this.listeners[name]??[]).forEach(fn=>fn(event));}
}
const elements = {}; const get=id=>elements[id] ??=new Element(id);
const names=['plan','write','continuity','models'];
const nav=names.map(name=>{const e=get('nav-'+name);e.dataset.view=name;return e;});
const panels=names.map(name=>get('view-'+name));
const jump=get('jump-write');jump.dataset.view='write';
let ready; const observers=[];
const document={getElementById:get,querySelectorAll:s=>s==='[data-view]'?nav.concat(jump):s==='[data-workspace]'?panels:[],addEventListener:(n,fn)=>ready=fn,activeElement:null};
let scrollResets=0;
const window={location:{hash:''},scrollTo(x,y){assert.equal(x,0);assert.equal(y,0);scrollResets++;},addEventListener(){},history:{replaceState(){} }};
const context={document,window,MutationObserver:class{constructor(fn){observers.push(fn);}observe(){}},console};
get('manuscript-panel').hidden=true;get('setup-section').hidden=false;
vm.runInNewContext(fs.readFileSync(process.argv[2],'utf8'),context);ready();
get('manuscript').value='Unsaved fictional text';
nav[2].fire('click');assert.equal(panels[2].hidden,false);assert.equal(panels[0].hidden,true);
assert.equal(scrollResets,1,'Navigation must reveal the new workspace heading, not inherit deep scroll from another panel.');
assert.equal(nav[2].attrs['aria-current'],'page');assert.equal(get('manuscript').value,'Unsaved fictional text');
let prevented=false;nav[2].fire('keydown',{key:'ArrowRight',preventDefault(){prevented=true;}});
assert.ok(prevented);assert.equal(document.activeElement,nav[3]);assert.equal(panels[3].hidden,false);
nav[3].fire('keydown',{key:'Home',preventDefault(){}});assert.equal(panels[0].hidden,false);
nav[0].fire('keydown',{key:'End',preventDefault(){}});assert.equal(panels[3].hidden,false);
assert.equal(get('write-prerequisite').hidden,false);
assert.equal(get('approved-intention').hidden,true);
get('setup-section').hidden=true;get('manuscript-panel').hidden=false;
get('remote-copy').textContent=JSON.stringify({pending:{number:2,text:'Saved fictional text',text_version:3},plan:{status:'approved',future:[{episode:2,intention:'The keeper finds the missing page.'}]},settings:{provider:'fake'}});
observers.forEach(fn=>fn());
assert.equal(get('write-prerequisite').hidden,true);
assert.equal(get('intention-text').textContent,'The keeper finds the missing page.');
assert.match(get('editor-save-state').textContent,/Unsaved/);
get('manuscript').value='Saved fictional text';get('manuscript').fire('input');
assert.match(get('editor-save-state').textContent,/Saved.*3/);
assert.equal(get('continuity-prerequisite').hidden,true);
assert.equal(get('models-prerequisite').hidden,true);
assert.equal(get('manuscript').value,'Saved fictional text');
jump.fire('click');assert.equal(document.activeElement,get('workspace'),'A contextual link must not leave focus inside a hidden panel.');
vm.runInNewContext(fs.readFileSync(process.argv[2],'utf8'),context);ready();
assert.equal(panels[1].hidden,false,'A saved manuscript opens at the writing desk.');
console.log('PASS: all work areas, keyboard navigation and unsaved input preservation.');
