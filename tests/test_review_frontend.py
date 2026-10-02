"""Dependency-free behavioral checks of the shipped browser modules via Node.

The tiny DOM exercises text, events and focus, not browser layout. Parent browser
QA owns responsive rendering, real selection, font and accessibility-tree checks.
"""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

ASSETS = Path(__file__).resolve().parents[1] / 'serial_story' / 'assets'

DOM = r'''
import assert from 'node:assert/strict';
class Element {
  constructor(tag='div') { this.tagName=tag.toUpperCase(); this.children=[]; this.attrs={}; this.dataset={}; this.listeners={}; this.value=''; this.hidden=false; this._text=''; this.className=''; this.selectionStart=0; this.selectionEnd=0; }
  set textContent(value) { this._text=String(value); this.children=[]; }
  get textContent() { return this._text + this.children.map(c=>c.textContent).join(''); }
  append(...items) { for (const item of items) { const c=typeof item==='string'?new Text(item):item; c.parentElement=this; this.children.push(c); } }
  replaceChildren(...items) { this.children=[]; this._text=''; this.append(...items); this.replacements=(this.replacements||0)+1; }
  setAttribute(k,v) { this.attrs[k]=String(v); if(k==='id')this.id=v; }
  getAttribute(k) { return this.attrs[k]??null; }
  removeAttribute(k) { delete this.attrs[k]; }
  addEventListener(k,fn) { (this.listeners[k]??=[]).push(fn); }
  dispatch(k) { const event={target:this,preventDefault(){}}; let current=this; do { for(const fn of current.listeners[k]||[]) fn(event); current=k==='click'?current.parentElement:null; } while(current); }
  get classList() { return {add:()=>{},remove:()=>{}}; }
  closest(selector) { let element=this; while(element){if(matches(element,selector))return element;element=element.parentElement;}return null; }
  focus() { document.activeElement=this; }
  contains(target) { return this===target||this.children.some(c=>c.contains?.(target)); }
  querySelectorAll(selector) { return descendants(this).filter(e=>matches(e,selector)); }
  querySelector(selector) { return this.querySelectorAll(selector)[0]||null; }
  setSelectionRange(a,b) { this.selectionStart=a; this.selectionEnd=b; }
  scrollIntoView() {}
}
class Text extends Element { constructor(text){super('#text');this.textContent=text;} }
function descendants(root){return root.children.flatMap(c=>[c,...descendants(c)]);}
function matches(e,s){if(s.startsWith('#'))return e.id===s.slice(1);if(s==='[data-focus-key]')return Boolean(e.dataset.focusKey);return e.tagName===s.toUpperCase();}
globalThis.Node=Element;
const root=new Element('body');
globalThis.document={body:root,activeElement:root,hidden:false,createElement:t=>new Element(t),createTextNode:t=>new Text(t),getElementById:id=>descendants(root).find(e=>e.id===id),querySelectorAll:s=>root.querySelectorAll(s),addEventListener(){}};
function find(root,tag,text){return root.querySelectorAll(tag).find(e=>e.textContent.includes(text));}
'''


BOOT = r'''
const workspace=new Element('main');workspace.id='workspace';
const nav=new Element('nav');nav.id='nav';
const mobile=new Element('select');mobile.id='mobile-view';
const refreshButton=new Element('button');refreshButton.id='refresh';
const connection=new Element('p');connection.id='connection';
const error=new Element('div');error.id='error';error.hidden=true;
const scope=new Element('div');scope.id='scope';
root.append(workspace,nav,mobile,refreshButton,connection,error,scope);
for(const view of ['read','storyboard','memory','quality','receipts','model']){const b=new Element('button');b.dataset.view=view;nav.append(b);}
globalThis.window=new Element('window');
globalThis.location={hash:''};
globalThis.history={pushState(_a,_b,hash){location.hash=hash;},replaceState(_a,_b,hash){location.hash=hash;}};
let tick;globalThis.setInterval=fn=>{tick=fn;};
let snapshot={revision:'one',fixture_only:true,episodes:[{id:2,number:1,revision:2,status:'accepted',words:3,prose:'Final accepted prose.'}],facts:[{id:4,subject_id:1,status:'confirmed',predicate:'knows',value:'Final',source_revision_id:2,evidence_start:0,evidence_end:5,evidence:'Final'},{id:5,status:'proposed',predicate:'wonders',value:'Draft'}],entities:[{id:1,name:'Keeper'}],plan:{content:{arcs:[{start:1,end:2}],beats:[{episode:1,intention:'Final keeper'},{episode:2,intention:'Cross bay'}]}},directions:[],calls:[],reviews:[]};
let storyCalls=0;
let fetchStory=async()=>({ok:true,json:async()=>snapshot});
let fetchProvider=async()=>({ok:true,json:async()=>({})});
globalThis.fetch=url=>{if(url==='/api/story'){storyCalls++;return fetchStory();}return fetchProvider();};
const settle=async()=>{for(let i=0;i<12;i++)await new Promise(resolve=>setImmediate(resolve));};
await import('./review.js');
'''


@unittest.skipUnless(shutil.which('node'), 'Installed Node is required for JS behavior tests')
class ReviewFrontendTests(unittest.TestCase):
    def run_js(self, code):
        result = subprocess.run(
            ['node', '--input-type=module', '-e', DOM + code],
            cwd=ASSETS, text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_memory_graph_scope_is_distinct_from_all_state_list(self):
        self.run_js(r'''
import {memoryView} from './ui/evidence.js';
const stage=new Element('main');
memoryView(stage,{revision:'scope-check',episodes:[],facts:[],entities:[]},
  {memoryFilter:'all',graphOpen:false},{inspect(){}});
const details=stage.querySelector('details');
assert.match(details.textContent,/confirmed/i);
assert.doesNotMatch(details.textContent,/all recorded states/i);
''')

    def test_responsive_style_contract_uses_defined_tokens(self):
        import re
        css = (ASSETS / 'review.css').read_text(encoding='utf-8')
        defined = set(re.findall(r'(--[\w-]+)\s*:', css))
        used = set(re.findall(r'var\((--[\w-]+)\)', css))
        self.assertFalse(used - defined)
        self.assertIn('.mobile-navigation', css)
        self.assertIn('.revision-list', css)
        self.assertIn('prefers-reduced-motion', css)
        self.assertIn(':focus-visible', css)
        self.assertIn('url("/font.ttf")', css)

    def test_html_boots_modules_and_exposes_all_mobile_sections(self):
        from html.parser import HTMLParser
        class Elements(HTMLParser):
            def __init__(self):
                super().__init__()
                self.elements = []
            def handle_starttag(self, tag, attrs):
                self.elements.append((tag, dict(attrs)))
        parsed = Elements()
        parsed.feed((ASSETS / 'review.html').read_text(encoding='utf-8'))
        self.assertIn(('script', {'type': 'module', 'src': '/review.js'}), parsed.elements)
        self.assertTrue(any(tag == 'select' and attrs.get('id') == 'mobile-view'
                            for tag, attrs in parsed.elements))
        sections = {'read', 'storyboard', 'memory', 'quality', 'receipts', 'model'}
        self.assertEqual({attrs['value'] for tag, attrs in parsed.elements if tag == 'option'}, sections)
        self.assertEqual({attrs['data-view'] for tag, attrs in parsed.elements if tag == 'button' and 'data-view' in attrs}, sections)
        self.assertTrue(any(tag == 'a' and attrs.get('href') == '#workspace' for tag, attrs in parsed.elements))

    def test_polling_defers_changed_prose_while_selected(self):
        self.run_js(BOOT + r'''
await settle();
const rendered=workspace.replacements;
window.getSelection=()=>({isCollapsed:false,anchorNode:workspace.querySelector('article')});
snapshot={...snapshot,revision:'two',episodes:[{...snapshot.episodes[0],prose:'Changed final prose.'}]};
tick();await settle();
assert.equal(workspace.replacements,rendered);
assert.ok(workspace.textContent.includes('Final accepted prose.'));
assert.ok(connection.textContent.includes('waiting'));
window.getSelection=()=>({isCollapsed:true});tick();await settle();
assert.ok(workspace.textContent.includes('Changed final prose.'));
''')

    def test_skip_link_does_not_change_the_current_section(self):
        self.run_js(BOOT + r'''
await settle();mobile.value='memory';mobile.dispatch('change');
location.hash='#workspace';window.dispatch('hashchange');
assert.ok(workspace.textContent.includes('Trace an interpretation'));
''')

    def test_assembled_navigation_source_return_and_hash(self):
        self.run_js(BOOT + r'''
await settle();
assert.ok(workspace.textContent.includes('Revision 2'));
nav.querySelectorAll('button').find(b=>b.dataset.view==='memory').dispatch('click');
assert.equal(location.hash,'#memory');
assert.ok(workspace.textContent.includes('1 of 2 interpretations'));
find(workspace,'button','Inspect episode').dispatch('click');
assert.equal(location.hash,'#read');
assert.equal(workspace.querySelector('mark').textContent,'Final');
find(workspace,'button','Return to memory').dispatch('click');
assert.equal(location.hash,'#memory');
assert.equal(document.activeElement.dataset.focusKey,'source-4');
location.hash='#quality';window.dispatch('hashchange');
assert.ok(workspace.textContent.includes('Quality needs'));
location.hash='#not-a-section';window.dispatch('hashchange');
assert.equal(location.hash,'#read');
mobile.value='storyboard';mobile.dispatch('change');
assert.equal(location.hash,'#storyboard');
assert.ok(workspace.querySelector('input'));
''')

    def test_refresh_preserves_focus_selection_and_unchanged_content(self):
        self.run_js(BOOT + r'''
await settle();
mobile.value='storyboard';mobile.dispatch('change');
const input=workspace.querySelector('input');input.focus();input.value='Final';input.dispatch('input');input.setSelectionRange(1,3);
const rendered=workspace.replacements;
refreshButton.dispatch('click');await settle();
assert.equal(workspace.replacements,rendered);
assert.equal(document.activeElement,input);
snapshot={...snapshot,revision:'second'};
refreshButton.dispatch('click');await settle();
const renewed=workspace.querySelector('input');
assert.notEqual(renewed,input);
assert.equal(renewed.value,'Final');
assert.equal(document.activeElement,renewed);
assert.equal(renewed.selectionStart,1);assert.equal(renewed.selectionEnd,3);
assert.ok(connection.textContent.includes('Last read'));
''')

    def test_refresh_overlap_errors_retry_and_provider_independence(self):
        self.run_js(BOOT + r'''
await settle();
let release;fetchStory=()=>new Promise(resolve=>release=resolve);
const before=storyCalls;
refreshButton.dispatch('click');refreshButton.dispatch('click');
assert.equal(storyCalls,before+1);
assert.equal(refreshButton.disabled,true);
release({ok:false});await settle();
assert.equal(error.hidden,false);
assert.ok(error.textContent.includes('last successful'));
assert.equal(refreshButton.disabled,false);
fetchStory=async()=>({ok:true,json:async()=>snapshot});
fetchProvider=async()=>({ok:false});
refreshButton.dispatch('click');await settle();
mobile.value='model';mobile.dispatch('change');
assert.ok(workspace.textContent.includes('could not be read'));
fetchProvider=async()=>({ok:true,json:async()=>({model:'offline/catalog',advertised_streaming:false})});
refreshButton.dispatch('click');await settle();
assert.ok(workspace.textContent.includes('Streaming is not advertised'));
assert.equal(error.hidden,true);
const calls=storyCalls;document.hidden=true;tick();await settle();assert.equal(storyCalls,calls);
''')

    def test_initial_error_replaces_loading_and_retry_opens_empty_story(self):
        self.run_js(BOOT.replace("let fetchStory=async()=>({ok:true,json:async()=>snapshot});", "let fetchStory=async()=>({ok:false});") + r'''
await settle();
assert.ok(workspace.textContent.includes('could not be opened'));
assert.equal(workspace.getAttribute('aria-busy'),'false');
snapshot={...snapshot,episodes:[]};fetchStory=async()=>({ok:true,json:async()=>snapshot});
refreshButton.dispatch('click');await settle();
assert.ok(workspace.textContent.includes('Your first episode'));
''')

    def test_memory_filter_is_behavioral_and_safe(self):
        self.run_js(r'''
const {memoryView}=await import('./ui/evidence.js');
const stage=new Element();root.append(stage);
const story={revision:'one',episodes:[],entities:[],facts:[{id:1,status:'confirmed',predicate:'knows',value:'<script>unsafe</script>'},{id:2,status:'confirmed',superseded_by:1,predicate:'was',value:'earlier'}]};
const state={memoryFilter:'current'};
memoryView(stage,story,state,{inspect(){}});
assert.ok(stage.textContent.includes('1 of 2 interpretations'));
assert.ok(stage.textContent.includes('<script>unsafe</script>'));
assert.equal(stage.querySelector('script'),null);
const select=stage.querySelector('select');select.value='rejected';select.dispatch('change');
assert.ok(stage.textContent.includes('No interpretations match'));
find(stage,'button','Clear filter').dispatch('click');assert.equal(state.memoryFilter,'all');
assert.ok(stage.textContent.includes('2 of 2 interpretations'));
assert.equal(document.activeElement,select);
assert.equal(stage.querySelector('iframe'),null);
''')

    def test_exact_unicode_evidence_and_invalid_offsets_are_honest(self):
        self.assertTrue((ASSETS / 'ui/evidence.js').exists(), 'Evidence module is missing')
        self.run_js(r'''
const {evidenceProse}=await import('./ui/evidence.js');
const episode={id:7,status:'accepted',prose:'A 🦉 keeps watch.'};
const fact={source_revision_id:7,evidence_start:2,evidence_end:3,evidence:'🦉'};
const prose=evidenceProse(episode,fact);
assert.equal(prose.textContent,episode.prose);
assert.equal(prose.querySelector('mark').textContent,'🦉');
assert.equal(evidenceProse(episode,{...fact,evidence:'wrong'}).querySelector('mark'),null);
assert.equal(evidenceProse(episode,{...fact,evidence_start:-1}).querySelector('mark'),null);
assert.equal(evidenceProse({...episode,status:'pending'},fact).querySelector('mark'),null);
''')

    def test_reader_names_revisions_and_returns_from_source(self):
        self.assertTrue((ASSETS / 'ui/reader.js').exists(), 'Reader module is missing')
        self.run_js(r'''
const {readerView}=await import('./ui/reader.js');
const stage=new Element();root.append(stage);
const story={episodes:[{id:1,number:1,revision:1,status:'rejected',words:3,prose:'Earlier draft.'},{id:2,number:1,revision:2,status:'accepted',words:3,prose:'Final accepted prose.'}],facts:[],entities:[]};
readerView(stage,story,{selected:2,evidence:null}, {select(){},inspect(){},returnSource(){}});
assert.ok(stage.textContent.includes('Revision 1'));
assert.ok(stage.textContent.includes('Revision 2'));
assert.ok(stage.textContent.includes('accepted'));
assert.equal(stage.querySelector('select').value,'2');
const fact={id:4,source_revision_id:2,evidence_start:0,evidence_end:5,evidence:'Final'};
stage.replaceChildren();
let returned=false;
readerView(stage,story,{selected:2,evidence:fact,returnLabel:'memory'}, {select(){},inspect(){},returnSource(){returned=true;}});
find(stage,'button','Return to memory').dispatch('click');
assert.equal(returned,true);
assert.equal(stage.querySelector('mark').textContent,'Final');
''')

    def test_planning_search_updates_results_without_replacing_input(self):
        self.assertTrue((ASSETS / 'ui/planning.js').exists(), 'Planning module is missing')
        self.run_js(r'''
const {planningView}=await import('./ui/planning.js');
const stage=new Element();root.append(stage);
const story={plan:{content:{arcs:[{start:1,end:2}],beats:[{episode:1,intention:'Find the keeper'},{episode:2,intention:'Cross the bay'}]}},episodes:[],directions:[]};
const state={beatRange:'1:2',beatSearch:''};
planningView(stage,story,state,{select(){}});
const input=stage.querySelector('input');input.focus();input.value='bay';input.dispatch('input');
assert.equal(state.beatSearch,'bay');
assert.equal(stage.querySelector('input'),input);
assert.equal(document.activeElement,input);
assert.ok(stage.textContent.includes('Cross the bay'));
assert.ok(!stage.textContent.includes('Find the keeper'));
input.value='missing';input.dispatch('input');
find(stage,'button','Clear filters').dispatch('click');
assert.equal(state.beatSearch,'');assert.equal(input.value,'');assert.equal(document.activeElement,input);
''')

    def test_provider_false_streaming_missing_prices_and_absent_model(self):
        self.assertTrue((ASSETS / 'ui/review-details.js').exists(), 'Review details module is missing')
        self.run_js(r'''
const {modelView}=await import('./ui/review-details.js');
const stage=new Element();
modelView(stage,{model:'local/model',advertised_streaming:false,pricing:{input_per_million:0}},'loaded');
assert.ok(stage.textContent.includes('Streaming is not advertised'));
assert.ok(stage.textContent.includes('Unknown'));
assert.ok(stage.textContent.includes('0'));
assert.ok(!stage.textContent.includes('undefined'));
stage.replaceChildren();modelView(stage,{},'loaded');
assert.ok(stage.textContent.includes('has not been selected'));
assert.ok(!stage.textContent.includes('discovery is complete'));
stage.replaceChildren();modelView(stage,null,'error');
assert.ok(stage.textContent.includes('could not be read'));
''')


if __name__ == '__main__':
    unittest.main()
