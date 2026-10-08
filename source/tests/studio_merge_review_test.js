// Synthetic DOM consent boundary. No browser, key, network or real billing.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
class Element {
 constructor(id){this.id=id;this.value='';this.textContent='';this.hidden=false;this.disabled=false;this.listeners={};this.children=[];this.classList={toggle(){}};}
 addEventListener(n,f){(this.listeners[n]??=[]).push(f);}appendChild(e){this.children.push(e);return e;}
 input(v){this.value=v;for(const event of ['input','change'])for(const f of this.listeners[event]??[])f();}
 click(){assert.ok(this.listeners.click?.length,this.id+' missing author action');return this.listeners.click[0]();}
}
let ready, consent=false, pendingFlight;const els={};const get=n=>els[n]??=new Element(n);
const basis={history_revision:0,memory_revision:0,plan_id:1,settings_version:2,feedback_revision:0,next_episode:1};
const state={writable:true,generation_enabled:true,story:{premise:'Synthetic',next_episode:1},basis,plan:{id:1,status:'approved',future:[],established:[]},pending:null,settings:{version:2,provider:'merge',model:'synthetic/concrete-v1',vendor:'synthetic-vendor',prompt_template:'Only prose',output_limit_words:700,feedback_scope:'this-revision'},accepted:[],receipts:[],memory:{entities:[],facts:[]}};
state.merge_accounting={calls:[{operation_id:'overcharge',status:'uncertain',spent_micro_usd:0,reserved_micro_usd:2000050,reported_charge_micro_usd:2000050,receipt:{output_eligible:false},confirmation:null}]};
const flight={preflight_id:'synthetic-flight',operation_id:'synthetic-op',model:state.settings.model,vendor:state.settings.vendor,reservation_micro_usd:30000,max_input_tokens:1400,shared_budget:{remaining_micro_usd:900000},fee_assumption_bps:500,fee_assumption_note:"Synthetic qualification only, account terms not verified",max_output_tokens:2800,expires_at:Date.now()/1000+120,service_tier:'standard',frozen:{payload:{basis}}};let calls=[];
const fetch=async(url,opt={})=>{if(opt.method==='POST'){const payload=JSON.parse(opt.body);calls.push({url,payload});if(url==='/api/merge/preflight'){flight.operation_id=payload.operation_id;return new Promise(resolve=>pendingFlight=()=>resolve({ok:true,json:async()=>structuredClone(flight)}));}if(url==='/api/merge/confirm')return {ok:true,json:async()=>({revision_id:1,synthetic:false})};throw Error('Unexpected mutation '+url);}return {ok:true,json:async()=>structuredClone(state)};};
vm.runInNewContext(fs.readFileSync(process.argv[2],'utf8'),{document:{getElementById:get,querySelector:()=>({content:'synthetic'}),createElement:()=>new Element('new'),addEventListener:(n,f)=>ready=f},fetch,crypto:require('node:crypto').webcrypto,confirm:()=>consent,Date});ready();async function flush(){for(let i=0;i<30;i++)await Promise.resolve();}
(async()=>{await flush();
 assert.match(get('merge-recovery').children[0].textContent,/reported USD 2\.000050/,'Uncertain exposure must not appear as a zero charge');
 assert.match(get('merge-recovery').children[0].textContent,/held USD 2\.000050/);
 const preparing=get('generate').click();await flush();
 get('prompt-template').input('Intervening edit');consent=true;await get('use-saved').click();
 pendingFlight();await preparing;await flush();
 assert.equal(get('confirm-merge').hidden,true,'Late preflight must not resurrect invalidated consent after edits are discarded');
 const second=get('generate').click();await flush();pendingFlight();await second;
 assert.match(get('merge-preflight').textContent,/USD 0\.030000/,'Reservation must be readable before confirmation');
 assert.match(get('merge-preflight').textContent,/USD 0\.900000/,'Shared remaining allowance must be readable');
 assert.match(get('merge-preflight').textContent,/1,400|1400/);
 assert.match(get('merge-preflight').textContent,/2,800|2800/);
 assert.match(get('merge-preflight').textContent,/standard/);
 assert.match(get('merge-preflight').textContent,/5%/);
 assert.match(get('merge-preflight').textContent,/no retry/i);
 assert.ok(get('merge-preflight').textContent.length<900,'Full frozen JSON must not occupy the cost summary');
 assert.match(get('merge-preflight-details').textContent,/preflight_id/);
 assert.equal(get('merge-details').open,false,'Details are collapsed by default in the native document');
 consent=false;await get('confirm-merge').click();assert.equal(calls.length,2,'Cancel sends no confirmation');
 consent=true;await get('confirm-merge').click();await flush();
 assert.equal(calls.at(-1).url,'/api/merge/confirm');
 assert.equal(get('confirm-merge').hidden,true,'Acknowledged success must clear consent');
 await get('confirm-merge').click();assert.equal(calls.filter(c=>c.url==='/api/merge/confirm').length,1);
 const html=fs.readFileSync(process.argv[3],'utf8');
 assert.ok(html.indexOf('id="merge-preflight"')<html.indexOf('id="confirm-merge"'));
 assert.match(html,/<details id="merge-details" hidden>/);
 console.log('PASS: edit invalidation, readable USD summary, collapsed inert details, cancellation and success consent clearing.');
})().catch(e=>{console.error(e);process.exitCode=1;});
