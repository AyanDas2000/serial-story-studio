// DOM contract only, not browser or layout certification.
const fs = require('node:fs');const vm = require('node:vm');const assert = require('node:assert/strict');
class Element {
 constructor(id){this.id=id;this.value='';this.textContent='';this.hidden=false;this.children=[];this.listeners={};this.classList={toggle(){},add(){},remove(){}};this.content='synthetic-session';}
 addEventListener(name,fn){this.listeners[name]=fn;} appendChild(e){this.children.push(e);return e;} replaceChildren(...children){this.children=children;} focus(){}
 click(){assert.ok(this.listeners.click,this.id+' has no working action');return this.listeners.click({preventDefault(){}});}
 input(value){this.value=value;if(this.listeners.input)this.listeners.input();if(this.listeners.change)this.listeners.change();}
}
const elements={};const get=id=>{if(!elements[id])elements[id]=new Element(id);return elements[id];};let ready;
const document={getElementById:get,querySelector:()=>get('token'),querySelectorAll:()=>[],createElement:()=>new Element('new'),addEventListener:(name,fn)=>{ready=fn;},activeElement:null};
const basis={history_revision:0,memory_revision:0,plan_id:1,settings_version:1,feedback_revision:0,next_episode:1};
const state={writable:true,story:{next_episode:1,history_revision:0,premise:'Synthetic story'},basis,
 plan:{id:1,status:'approved',content:{beats:[{episode:1,intention:'Original intention',unplanned:false}]},future:[{episode:1,intention:'Original intention',unplanned:false}],established:[],feedback:[]},
 pending:{id:1,number:1,text:'Saved prose',text_version:1,feedback:[],run:{source:'manual',synthetic:false}},
 settings:{version:1,provider:'fake',model:'',vendor:'',prompt_template:'Original instructions',prompt_version:1,output_limit_words:700,feedback_scope:'this-revision'},accepted:[],receipts:[],memory:{entities:[],facts:[]}};
let remote=structuredClone(state),calls=[];
const fetch=async(url,options={})=>{if(options.method==='POST'){calls.push({url,payload:JSON.parse(options.body)});return {ok:false,status:409,json:async()=>({message:'Changed elsewhere. Compare copies.'})};}return {ok:true,status:200,json:async()=>structuredClone(remote)};};
const context={document,window:{},fetch,console,crypto:require('node:crypto').webcrypto,structuredClone,setTimeout,clearTimeout,confirm:()=>false};
vm.runInNewContext(fs.readFileSync(process.argv[2],'utf8'),context);ready();const settle=()=>new Promise(resolve=>setTimeout(resolve,15));
(async()=>{
 await settle();
 assert.equal(get('episode-title').textContent,'Episode 1: draft');
 assert.equal(get('plan-status').textContent,'Saved plan 1: approved. Future intentions are not established events.');
 get('manuscript').input('My unsaved prose');get('prompt-template').input('My unsaved instructions');get('plan-note').input('My future intention');get('feedback-note').input('My feedback');
 remote.pending.text='Unseen remote prose';remote.pending.text_version=2;remote.settings.version=2;remote.settings.prompt_template='Remote instructions';remote.basis.settings_version=2;remote.plan.id=2;remote.basis.plan_id=2;
 await get('refresh').click();await settle();
 assert.equal(get('manuscript').value,'My unsaved prose');assert.equal(get('prompt-template').value,'My unsaved instructions');assert.equal(get('plan-note').value,'My future intention');assert.equal(get('feedback-note').value,'My feedback');
 await get('save-draft').click();await settle();assert.equal(calls.at(-1).payload.expected_text_version,1);
 await get('save-settings').click();await settle();assert.equal(calls.at(-1).payload.expected_version,1);
 await get('save-plan').click();await settle();assert.equal(calls.at(-1).payload.expected_plan_id,1);
 await get('save-feedback').click();await settle();assert.equal(calls.at(-1).payload.expected_text_version,1);assert.equal(calls.at(-1).payload.basis.plan_id,1);
 assert.equal(get('manuscript').value,'My unsaved prose');
 remote.story=null;remote.pending=null;remote.plan=null;await get('refresh').click();await settle();
 assert.equal(get('setup-section').hidden,false);
 assert.equal(get('manuscript-panel').hidden,true,'An empty editor must not hide the first story setup action.');
 assert.equal(get('plan-section').hidden,true);
 remote.story=structuredClone(state.story);remote.plan=structuredClone(state.plan);remote.plan.status='proposed';await get('refresh').click();await settle();
 assert.equal(get('manuscript-panel').hidden,true,'Plan approval must precede the empty manuscript.');
 remote.plan.status='approved';await get('refresh').click();await settle();assert.equal(get('manuscript-panel').hidden,false);
 console.log('PASS: dirty forms preserve original versions; setup and plan approval precede the manuscript.');
})().catch(error=>{console.error(error);process.exitCode=1;});
