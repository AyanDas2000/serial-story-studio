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
const flight={preflight_id:'synthetic-flight',operation_id:'synthetic-op',model:state.settings.model,vendor:state.settings.vendor,reservation_micro_usd:30000,max_input_tokens:1400,shared_budget:{remaining_micro_usd:1000000},fee_assumption_bps:500,fee_assumption_note:"Synthetic qualification only",max_output_tokens:2800,expires_at:Date.now()/1000+120,service_tier:'standard',frozen:{payload:{basis}}};let calls=[];
const fetch=async(url,opt={})=>{if(opt.method==='POST'){const payload=JSON.parse(opt.body);calls.push({url,payload});if(url==='/api/merge/preflight'){flight.operation_id=payload.operation_id;return new Promise(resolve=>pendingFlight=()=>resolve({ok:true,json:async()=>structuredClone(flight)}));}if(url==='/api/merge/confirm')return {ok:true,json:async()=>({revision_id:1,synthetic:false})};throw Error('Unexpected mutation '+url);}return {ok:true,json:async()=>structuredClone(state)};};
vm.runInNewContext(fs.readFileSync(process.argv[2],'utf8'),{document:{getElementById:get,querySelector:()=>({content:'synthetic'}),createElement:()=>new Element('new'),addEventListener:(n,f)=>ready=f},fetch,crypto:require('node:crypto').webcrypto,confirm:()=>consent,Date});ready();async function flush(){for(let i=0;i<30;i++)await Promise.resolve();}
(async()=>{await flush();assert.equal(get('generate').disabled,false,'Enabled startup must permit preflight, not silently generate');
 const preparing=get('generate').click();await flush();assert.equal(calls.length,1);assert.equal(calls[0].url,'/api/merge/preflight');pendingFlight();await preparing;await flush();assert.match(get('merge-preflight').textContent,/synthetic\/concrete-v1/);
 await get('confirm-merge').click();assert.equal(calls.length,1,'No confirmation means no paid dispatch');
 get('manuscript').input('Typing after preflight');consent=true;await get('confirm-merge').click();assert.equal(calls.length,1,'Dirty writing must block confirmation');
 await get('use-saved').click();await flush();const second=get('generate').click();await flush();pendingFlight();await second;await get('confirm-merge').click();await flush();assert.equal(calls.at(-1).url,'/api/merge/confirm');assert.equal(calls.at(-1).payload.confirm,true);assert.equal(calls.at(-1).payload.operation_id,flight.operation_id);
 console.log('PASS: enabled startup only permits preflight; explicit consent and clean controls gate paid confirmation.');
})().catch(e=>{console.error(e);process.exitCode=1;});
