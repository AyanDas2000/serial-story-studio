/* Offline writing desk. All story/provider data stays text, never executable HTML. */
(function () {
 'use strict';
 var state = null, busy = false, catalog = [], forms = {}, el = {}, mergeFlight = null, mergeEpoch = 0;
 var meta = document.querySelector('meta[name="studio-token"]');
 var token = meta ? meta.content : '';
 function id(name) { return document.getElementById(name); }
 function copy(value) { return JSON.parse(JSON.stringify(value)); }
 function message(text) { el.banner.textContent = text ?? ''; el.banner.hidden = !text; }
 function request(route, payload) {
  var options = payload === undefined ? {} : {method:'POST',headers:{'Content-Type':'application/json','X-Studio-Token':token},body:JSON.stringify(payload)};
  return fetch(route, options).then(function(r){return r.json().then(function(body){if(!r.ok)throw new Error(body.message ?? 'Action failed. Compare saved copies before retrying.');return body;});});
 }
 function group(name, fields) {
  var f = {dirty:false,edits:0,fields:fields,basis:null,pending:null,plan:null,settings:null};forms[name]=f;
  fields.forEach(function(field){['input','change'].forEach(function(event){id(field).addEventListener(event,function(){f.dirty=true;f.edits++;if(['setup','prose','plan','settings','feedback'].includes(name)){mergeFlight=null;mergeEpoch++;}renderActions();});});});
  return f;
 }
 function load(name, values) {
  var f=forms[name];if(f.dirty)return;
  Object.keys(values).forEach(function(k){id(k).value=values[k] ?? '';});
  f.basis=copy(state.basis);f.pending=copy(state.pending);f.plan=copy(state.plan);f.settings=copy(state.settings);
 }
 function action(route,payload,clear) {
  if(busy)return Promise.resolve();var submitted={};(clear ?? []).forEach(function(name){submitted[name]=forms[name].edits;});busy=true;el.manuscriptStatus.textContent='Saving...';renderActions();
  return request(route,payload).then(function(result){
   if(route==='/api/merge/confirm'){mergeFlight=null;mergeEpoch++;id('merge-details').hidden=true;id('merge-preflight').textContent='Merge confirmation saved. Inspect the retained call receipt below.';}
   (clear ?? []).forEach(function(name){
    var f=forms[name];f.dirty=f.edits!==submitted[name];
    // Advance only versions acknowledged by this mutation, not unseen
    // versions from a later refresh while a newer edit remains dirty.
    if(name==='prose'){
     if(result.text_version&&f.pending)f.pending.text_version=result.text_version;
     if(result.revision_id)f.pending={id:result.revision_id,text_version:1};
     if(route==='/api/accept'||route==='/api/reject')f.pending=null;
    }
    if(name==='settings'&&result.settings){f.settings=copy(result.settings);f.basis.settings_version=result.settings.version;}
    if(name==='plan'&&result.plan_id){f.plan=copy(f.plan ?? {});f.plan.id=result.plan_id;f.plan.status=result.status;f.basis.plan_id=result.plan_id;}
    if(name==='feedback'&&result.feedback_revision!==undefined)f.basis.feedback_revision=result.feedback_revision;
   });
   message('');el.manuscriptStatus.textContent='Saved.';return refresh().then(function(){return result;});
  }).catch(function(error){message(error.message);el.manuscriptStatus.textContent='Not saved. Your inputs and original saved versions are kept.';})
  .finally(function(){busy=false;renderActions();});
 }
 function options(select,rows,value) {
  select.textContent='';rows.forEach(function(row){var o=document.createElement('option');o.value=row.value;o.textContent=row.label;select.appendChild(o);});if(value!==undefined&&value!==null&&String(value)!==''&&!rows.some(function(row){return String(row.value)===String(value);})){var unavailable=document.createElement('option');unavailable.value=value;unavailable.textContent=String(value)+' (unavailable in current list; retained for review)';select.appendChild(unavailable);}select.value=value ?? '';
 }
 function list(target,rows,write) {target.textContent='';rows.forEach(function(row){var item=document.createElement('li');write(item,row);target.appendChild(item);});}
 function acceptanceDirty(){return ['setup','prose','plan','settings','feedback'].some(function(name){return forms[name].dirty;});}
 function renderActions() {
  if(!state)return;var pending=Boolean(state.pending),approved=state.plan ? state.plan.status==='approved' : false;
  el.draftActions.hidden=!pending;el.newDraftActions.hidden=pending;el.feedbackSection.hidden=!pending;
  id('save-draft').classList.toggle('primary',forms.prose.dirty);id('accept').classList.toggle('primary',!forms.prose.dirty);
  id('accept').disabled=busy || !state.writable || acceptanceDirty();
  id('accept').title=acceptanceDirty() ? 'Save prose, plan, settings and feedback before acceptance.' : '';
  if(acceptanceDirty())el.nextStep.textContent='Save your unsaved prose, plan, settings and feedback before accepting final prose.';
  id('revise').disabled=busy || forms.prose.dirty || forms.feedback.dirty || !state.writable || (state.settings.provider==='merge' && !state.generation_enabled);
  id('generate').textContent=state.settings.provider==='merge' ? (state.generation_enabled ? 'Review Merge request' : 'Merge generation OFF') : 'Generate synthetic draft';
  id('confirm-merge').hidden=!mergeFlight;
  id('confirm-merge').disabled=busy || !mergeFlight || acceptanceDirty() || !state.writable;
  id('merge-note').textContent=state.generation_enabled ? 'Paid requests require review and a separate one-shot confirmation. The shared USD 1 allowance applies across stories. Prices and the 5% fee assumption are not a provider billing cap.' : 'Real Merge generation is OFF. No paid writing is permitted in this session.';
  id('generate').disabled=busy || !approved || !state.writable || (state.settings.provider==='merge' && !state.generation_enabled) || forms.prose.dirty;
  id('new-draft').disabled=busy || !approved || !state.writable;
  id('save-draft').disabled=busy || !state.writable;
 }
 function render() {
  var story=state.story,pending=state.pending,plan=state.plan;
  el.setupSection.hidden=Boolean(story);
  id('manuscript-panel').hidden=!story||(!pending&&plan?.status!=='approved');
  ['plan-section','settings-section','memory-section'].forEach(name=>{id(name).hidden=!story;});
  el.episodeTitle.textContent=story ? 'Episode '+(pending ? pending.number : story.next_episode)+(pending ? ': draft' : '') : 'New story';
  el.nextStep.textContent=!story ? 'Describe a premise to begin.' : pending ? 'Save edits, add feedback and revise, or accept final prose. Memory review is separate.' : 'Approve future intentions, then paste prose or generate synthetic material.';
  if(!state.writable)el.nextStep.textContent='Read-only studio. Start a new chosen database with --enable-writes to author.';
  load('setup',{'premise':story ? story.premise : ''});
  load('prose',{'manuscript':pending ? pending.text : ''});
  if(!forms.settings.dirty){if(!catalog.length){options(id('model'),[{value:state.settings.model ?? '',label:state.settings.model ?? 'No model selected'}],state.settings.model);options(id('vendor'),[{value:state.settings.vendor ?? '',label:state.settings.vendor ?? 'No vendor selected'}],state.settings.vendor);}else{options(id('model'),catalog.map(function(m){return {value:m.model,label:m.display_name ?? m.model};}),state.settings.model);vendors(state.settings.vendor);}}
  load('settings',{'provider':state.settings.provider,'model':state.settings.model,'vendor':state.settings.vendor,'prompt-template':state.settings.prompt_template,'output-limit':state.settings.output_limit_words,'feedback-scope':state.settings.feedback_scope});
  var future=plan ? plan.future : [];
  load('plan',{'plan-note':future.map(function(b){return b.unplanned ? '[unplanned] '+b.intention : b.intention;}).join('\n')});
  load('feedback',{'feedback-note':'','feedback-note-scope':state.settings.feedback_scope ?? 'this-revision'});
  load('entity',{'entity-name':'','entity-kind':'location','entity-role':''});
  if(!forms.fact.dirty){options(id('fact-entity'),(state.memory ? state.memory.entities : []).map(function(e){return {value:e.id,label:e.name};}),'');options(id('fact-source'),state.accepted.map(function(a){return {value:a.revision_id,label:'Episode '+a.number+' ? accepted revision '+a.revision_id};}),'');}
  load('fact',{'fact-property':'','fact-value':'','fact-evidence':''});
  id('future-label').textContent='Future intentions from episode '+(story ? story.next_episode : 1)+', one per line';
  el.planStatus.textContent=plan ? 'Saved plan '+plan.id+': '+plan.status+'. Future intentions are not established events.' : 'Write your first future intentions, then save and approve.';
  list(id('established-plan'),plan ? plan.established : [],function(item,b){item.textContent='Episode '+b.episode+': '+b.intention;});
  list(id('feedback-list'),pending ? pending.feedback : [],function(item,f){item.textContent='Saved prose version '+f.source_text_version+': '+f.scope+': '+f.note;});
  id('draft-receipt').textContent=pending ? JSON.stringify(pending.run,null,2) : 'No draft source yet.';
  id('remote-copy').textContent=JSON.stringify({pending:state.pending,settings:state.settings,plan:state.plan},null,2);
  el.receiptSection.hidden=!state.receipts.length;
  list(el.receiptList,state.receipts,function(item,r){item.textContent='Accepted revision '+r.revision_id+': '+r.provider+(r.synthetic ? ' (synthetic)' : '')+': final text version '+r.accepted_text_version+'. Memory has not been marked reviewed.';var details=document.createElement('details'),summary=document.createElement('summary'),pre=document.createElement('pre');summary.textContent='Inspect immutable receipt';pre.textContent=JSON.stringify(r,null,2);details.appendChild(summary);details.appendChild(pre);item.appendChild(details);});
  list(id('merge-recovery'),state.merge_accounting ? state.merge_accounting.calls : [],function(item,call){item.textContent=call.operation_id+' | '+call.status+' | settled USD '+usd(call.spent_micro_usd)+' | reported '+(call.reported_charge_micro_usd===null || call.reported_charge_micro_usd===undefined ? 'charge unknown' : 'USD '+usd(call.reported_charge_micro_usd))+' | held USD '+usd(call.reserved_micro_usd)+'. ';var details=document.createElement('details'),summary=document.createElement('summary'),pre=document.createElement('pre');summary.textContent='Inspect call receipt';pre.textContent=JSON.stringify(call.receipt,null,2);details.appendChild(summary);details.appendChild(pre);item.appendChild(details);if(call.status==='succeeded'&&call.confirmation){var button=document.createElement('button');button.type='button';button.textContent='Recover saved Merge prose, no new call';button.addEventListener('click',function(){if(acceptanceDirty()){message('Save your edits before recovering charged prose.');return;}if(confirm('Recover this charged receipt without a new provider call?'))action('/api/merge/confirm',call.confirmation,['prose','feedback']);});item.appendChild(button);}});
  renderMemory();showPrice();renderActions();el.wordCount.textContent=el.manuscript.value.trim().split(/\s+/).filter(Boolean).length+' words';
 }
 function renderMemory() {
  var memory=state.memory,facts=memory ? memory.facts : [];
  id('memory-status').textContent='Accepted prose is not automatically reviewed memory. Add source-linked proposals, inspect each passage, then confirm or reject separately.';
  list(id('memory-list'),facts,function(item,f){
   var text=document.createElement('p');text.textContent=f.subject_name+': '+f.predicate+' = '+f.value+': '+f.status;item.appendChild(text);
   var quote=document.createElement('blockquote');quote.textContent='Accepted revision '+f.source_revision_id+', characters '+f.evidence_start+' to '+f.evidence_end+': '+f.evidence;item.appendChild(quote);
   if(f.status==='proposed'){['confirm','reject'].forEach(function(decision){var button=document.createElement('button');button.type='button';button.textContent=decision==='confirm' ? 'Confirm memory fact' : 'Reject memory proposal';button.addEventListener('click',function(){action('/api/memory/'+decision,{fact_id:f.id},[]);});item.appendChild(button);});}
  });
  showSource();
 }
 function showSource(){var source=state.accepted.find(function(a){return String(a.revision_id)===String(id('fact-source').value);});id('source-text').textContent=source ? source.text : 'Choose an accepted episode to inspect its exact source.';}
 function usd(micro){return (micro/1000000).toFixed(6);}
 function showFlight(flight){
  id('merge-preflight').textContent=flight.model+' via '+flight.vendor+' | standard tier\n'+
   'Input limit: '+flight.max_input_tokens+' tokens. Output limit: '+flight.max_output_tokens+' tokens.\n'+
   'Estimated reservation: USD '+usd(flight.reservation_micro_usd)+'. Shared remaining: USD '+usd(flight.shared_budget.remaining_micro_usd)+'.\n'+
   'Fee allowance: '+(flight.fee_assumption_bps/100)+'%. '+flight.fee_assumption_note+'\n'+
   'One paid request, no fallback and no retry. Nothing has been generated yet.';
  id('merge-preflight-details').textContent=JSON.stringify(flight,null,2);
  id('merge-details').open=false;id('merge-details').hidden=false;
 }
 function showPrice(){var model=catalog.find(function(m){return m.model===id('model').value;});var vendor=model ? model.vendors.find(function(v){return (v.vendor ?? v.id ?? v.name)===id('vendor').value;}) : null;id('model-price').textContent=vendor ? JSON.stringify(vendor,null,2) : 'No current vendor prices selected. Real generation stays OFF.';id('merge-note').hidden=id('provider').value!=='merge';}
 function vendors(preferred){var selected=preferred===undefined ? id('vendor').value : preferred;var model=catalog.find(function(m){return m.model===id('model').value;});options(id('vendor'),model ? model.vendors.map(function(v){return {value:v.vendor ?? v.id ?? v.name ?? '',label:v.vendor ?? v.id ?? v.name ?? 'Unnamed vendor, not eligible'};}) : [],selected);showPrice();}
 function refresh(){return request('/api/state').then(function(next){state=next;render();}).catch(function(error){message('Could not refresh the saved story. '+error.message);});}
 function pendingPayload(form){var f=forms[form];if(!f.pending)throw new Error('Load a pending draft first.');return {revision_id:f.pending.id,expected_text_version:f.pending.text_version,basis:f.basis};}
 function click(name,fn){id(name).addEventListener('click',function(){try{return fn();}catch(error){message(error.message);return Promise.resolve();}});}
 document.addEventListener('DOMContentLoaded',function(){
  ['banner','manuscript','provider','model','vendor'].forEach(function(name){el[name]=id(name);});
  [['episodeTitle','episode-title'],['nextStep','next-step'],['setupSection','setup-section'],['manuscriptStatus','manuscript-status'],['draftActions','draft-actions'],['newDraftActions','new-draft-actions'],['feedbackSection','feedback-section'],['planStatus','plan-status'],['receiptSection','receipt-section'],['receiptList','receipt-list'],['wordCount','word-count']].forEach(function(pair){el[pair[0]]=id(pair[1]);});
  group('setup',['premise']);group('prose',['manuscript']);group('settings',['provider','model','vendor','prompt-template','output-limit','feedback-scope']);group('plan',['plan-note']);group('feedback',['feedback-note','feedback-note-scope']);group('entity',['entity-name','entity-kind','entity-role']);group('fact',['fact-entity','fact-property','fact-value','fact-source','fact-evidence']);
  click('refresh',refresh);
  click('use-saved',function(){if(!confirm('Discard ALL unsaved forms and their original saved versions? Copy anything you want to keep first.'))return;mergeFlight=null;mergeEpoch++;id('merge-details').hidden=true;Object.values(forms).forEach(function(f){f.dirty=false;});render();message('Saved copies loaded.');});
  click('save-premise',function(){return action('/api/setup',{premise:id('premise').value},['setup']);});
  click('save-plan',function(){var f=forms.plan,established=f.plan ? f.plan.established : [];var lines=id('plan-note').value.split('\n').filter(function(line){return line.trim();});return action('/api/plan/save',{expected_plan_id:f.plan ? f.plan.id : null,content:{beats:established.concat(lines.map(function(line,i){return {episode:established.length+i+1,intention:line.replace(/^\[unplanned\] /,''),unplanned:line.indexOf('[unplanned] ')===0};}))}},['plan']);});
  click('approve-plan',function(){var f=forms.plan;if(f.dirty)throw new Error('Save your future intentions before approving.');if(!f.plan)throw new Error('Save a plan first.');return action('/api/plan/approve',{plan_id:f.plan.id},['plan']);});
  click('new-draft',function(){return action('/api/draft/save',{text:el.manuscript.value,basis:forms.prose.basis},['prose']);});
  click('save-draft',function(){var payload=pendingPayload('prose');delete payload.basis;payload.text=el.manuscript.value;return action('/api/draft/edit',payload,['prose']);});
  click('accept',function(){if(acceptanceDirty())throw new Error('Save prose, plan, settings and feedback before acceptance.');return action('/api/accept',pendingPayload('prose'),['prose']);});
  click('reject',function(){return action('/api/reject',pendingPayload('prose'),['prose']);});
  click('save-feedback',function(){var payload=pendingPayload('feedback');payload.note=id('feedback-note').value;payload.scope=id('feedback-note-scope').value;return action('/api/draft/feedback',payload,['feedback']);});
  function generate(revise){if(forms.prose.dirty)throw new Error('Save pasted prose or edits first. Generation never replaces unsaved writing.');if(forms.settings.dirty || forms.plan.dirty || forms.feedback.dirty)throw new Error('Save plan, settings and feedback before generating.');var payload=revise ? pendingPayload('prose') : {basis:forms.prose.basis};payload.operation_id=crypto.randomUUID();if(state.settings.provider==='merge'){if(!state.generation_enabled)throw new Error('Merge generation is OFF.');if(busy)return Promise.resolve();mergeFlight=null;var epoch=++mergeEpoch;id('merge-details').hidden=true;busy=true;id('merge-preflight').textContent='Checking saved instructions, exact route and shared allowance...';renderActions();return request('/api/merge/preflight',payload).then(function(flight){if(epoch!==mergeEpoch || acceptanceDirty()){id('merge-preflight').textContent='Request review cancelled because your writing or directions changed. Save changes and review a new request.';return;}mergeFlight=flight;showFlight(flight);message('Review the exact instructions, model, vendor, token limit, fee assumption and shared allowance. Nothing has been generated.');}).catch(function(error){message(error.message);id('merge-preflight').textContent='Request not ready. No paid writing was sent. Save changes or inspect the call receipts before trying again.';}).finally(function(){busy=false;renderActions();});}return action(revise ? '/api/draft/revise' : '/api/draft/generate',payload,['prose','feedback']);}
  click('generate',function(){return generate(false);});click('revise',function(){return generate(true);});
  click('confirm-merge',function(){if(!mergeFlight || acceptanceDirty())throw new Error('Review a new request after saving all prose, plan, settings and feedback.');if(busy)return;if(!confirm('Send exactly one paid request to '+mergeFlight.model+' via '+mergeFlight.vendor+', standard tier, with no fallback or retry? Reserve '+usd(mergeFlight.reservation_micro_usd)+' USD from the shared USD 1 allowance.'))return;var flight=mergeFlight;return action('/api/merge/confirm',{preflight_id:flight.preflight_id,operation_id:flight.operation_id,confirm:true},['prose','feedback']);});
  click('lookup-model',function(){var selected=id('model').value,vendor=id('vendor').value;id('catalog-status').textContent='Inspecting the exact canonical model ID...';return request('/api/merge/model?model='+encodeURIComponent(id('exact-model').value)).then(function(body){selected=id('model').value;vendor=id('vendor').value;body.models.forEach(function(model){catalog=catalog.filter(function(m){return m.model!==model.model;});catalog.push(model);});options(id('model'),catalog.map(function(m){return {value:m.model,label:m.display_name ?? m.model};}),selected);vendors(vendor);id('catalog-status').textContent='Exact model inspected. Metadata does not prove inference access. Select it explicitly and save settings if wanted.';}).catch(function(error){message(error.message);id('catalog-status').textContent='Exact model could not be inspected. Existing selections are kept.';});});
  click('save-settings',function(){return action('/api/settings',{expected_version:forms.settings.settings.version,provider:id('provider').value,model:id('model').value,vendor:id('vendor').value,prompt_template:id('prompt-template').value,output_limit_words:Number(id('output-limit').value),feedback_scope:id('feedback-scope').value},['settings']);});
  click('reset-prompt',function(){id('prompt-template').value='';forms.settings.dirty=true;forms.settings.edits++;mergeFlight=null;mergeEpoch++;id('merge-details').hidden=true;id('settings-status').textContent='Instructions reset locally. Save settings to apply. Other unsaved settings are kept.';renderActions();});
  click('load-catalog',function(){id('catalog-status').textContent='Reading the authorized model listing...';return request('/api/merge/catalog').then(function(body){catalog=body.models;var selected=id('model').value;options(id('model'),catalog.map(function(m){return {value:m.model,label:m.display_name ?? m.model};}),selected);vendors();id('catalog-status').textContent=catalog.length+' models in this credential listing, not the global inventory. Select model and vendor, then save settings.';}).catch(function(error){message(error.message);id('catalog-status').textContent='Catalog not loaded. Real generation remains OFF.';});});
  id('model').addEventListener('change',function(){forms.settings.dirty=true;vendors();});id('vendor').addEventListener('change',function(){forms.settings.dirty=true;showPrice();});id('provider').addEventListener('change',showPrice);id('fact-source').addEventListener('change',showSource);
  click('add-entity',function(){return action('/api/memory/entity',{name:id('entity-name').value,kind:id('entity-kind').value,role:id('entity-role').value},['entity']);});
  click('propose-fact',function(){return action('/api/memory/fact',{subject_id:Number(id('fact-entity').value),predicate:id('fact-property').value,value:id('fact-value').value,source_revision_id:Number(id('fact-source').value),evidence:id('fact-evidence').value},['fact']);});
  refresh();
 });
})();
