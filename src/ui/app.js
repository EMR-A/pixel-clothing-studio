// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Pixel Clothing Studio contributors
'use strict';
const token=location.hash.slice(1)||sessionStorage.getItem('pixelCapability')||'';
if(token)sessionStorage.setItem('pixelCapability',token);
history.replaceState(null,'',location.pathname);
const $=selector=>document.querySelector(selector),$$=selector=>[...document.querySelectorAll(selector)];
let localization=null,staticTranslations=[],currentGuide='',guides={},values={},lastState=null,previewVersion=0,previewURL='',toastTimer,connectionFailures=0,currentView='render',pickerPending=false;
const supportedLanguages=['tr','en','de','fr','es','pt-BR','it','nl','pl','ru','uk','ar','hi','id','vi','zh-CN','ja','ko'];
function normalizeLanguage(value){const tag=String(value||'en').replace('_','-');return supportedLanguages.find(c=>c.toLowerCase()===tag.toLowerCase())||supportedLanguages.find(c=>c.split('-')[0]===tag.split('-')[0].toLowerCase())||'en'}
let language=normalizeLanguage(navigator.language);try{language=normalizeLanguage(localStorage.getItem('pixelLanguage')||navigator.language)}catch(_){}
function t(key,params={}){const strings=localization?.strings[key]||{};return (strings[language]||strings.en||key).replace(/\{(\w+)\}/g,(match,name)=>String(params[name]??match))}
function bindStaticTranslations(){
 const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);let node;
 while((node=walker.nextNode())){if(node.parentElement?.closest('svg,script,style,code'))continue;const key=localization.source[node.textContent.trim()];if(key){const target=node;const leading=node.textContent.match(/^\s*/)[0],trailing=node.textContent.match(/\s*$/)[0];staticTranslations.push(()=>{if(target.isConnected)target.textContent=leading+t(key)+trailing})}}
 document.querySelectorAll('[aria-label],[title],[placeholder],[alt]').forEach(el=>{for(const name of ['aria-label','title','placeholder','alt']){const key=localization.source[el.getAttribute(name)];if(key)staticTranslations.push(()=>el.setAttribute(name,t(key)))}});
}
function populateLanguages(){const select=$('#language');select.replaceChildren(...localization.languages.map(row=>Object.assign(document.createElement('option'),{value:row.code,textContent:row.name})));select.value=language}
function applyLanguage(){
 document.documentElement.lang=language;document.documentElement.dir=language==='ar'?'rtl':'ltr';$('#language').value=language;
 staticTranslations.forEach(update=>update());guides=localization.guides[language];showView(currentView);
 $('#toggle-key').setAttribute('aria-label',t($('#private-key').type==='text'?'hideKey':'showKey'));
 if($('#guide-dialog').open&&currentGuide)guideContent(currentGuide);
 $('#event-log').dataset.last='';
}
$('#language').addEventListener('change',async()=>{values={...values,...payload()};language=normalizeLanguage($('#language').value);try{localStorage.setItem('pixelLanguage',language)}catch(_){}applyLanguage();refreshValues();await poll()});
function setTheme(theme){
 if(!['light','dark'].includes(theme))return;
 document.documentElement.dataset.theme=theme;
 try{localStorage.setItem('pixelTheme',theme)}catch(_){}
 $$('button[data-theme]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.theme===theme)));
}
let initialTheme='light';try{initialTheme=localStorage.getItem('pixelTheme')||(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light')}catch(_){}
setTheme(initialTheme);
const formatNumber=n=>Number(n||0).toLocaleString(language);
const formatDecimal=n=>Number(n||0).toLocaleString(language,{maximumFractionDigits:1});
function elapsed(seconds){seconds=Math.max(0,Math.floor(seconds||0));return (seconds>=3600?String(Math.floor(seconds/3600)).padStart(2,'0')+':':'')+String(Math.floor(seconds/60)%60).padStart(2,'0')+':'+String(seconds%60).padStart(2,'0')}
function duration(seconds){if(seconds==null)return t('calculating');if(seconds===0)return t('complete');seconds=Math.max(1,Math.round(seconds));if(seconds<60)return '~ '+formatNumber(seconds)+' '+t('seconds');const m=Math.ceil(seconds/60);return m<60?'~ '+formatNumber(m)+' '+t('minutes'):'~ '+formatNumber(Math.floor(m/60))+' '+t('hours')+' '+formatNumber(m%60)+' '+t('minutes')}
function bytes(n){if(!n)return '0 KB';return n>=1048576?formatDecimal(n/1048576)+' MB':formatNumber(Math.round(n/1024))+' KB'}
async function api(path,body){
 const response=await fetch('/api/'+path,{method:body?'POST':'GET',headers:{'X-Pixel-Token':token,'X-Pixel-Language':language,...(body?{'Content-Type':'application/json'}:{})},...(body?{body:JSON.stringify(body)}:{})});
 const data=await response.json();if(!response.ok)throw new Error(data.error||t('connectionLost'));return data;
}
function toast(message){$('#toast').textContent=message;$('#toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').hidden=true,6500)}
function showView(view){
 if(!['render','upload','help'].includes(view))return;
 currentView=view;$$('.view').forEach(el=>el.classList.toggle('active',el.id==='view-'+view));
 $$('.nav-item').forEach(el=>el.classList.toggle('active',el.dataset.view===view));
 $('#breadcrumb').replaceChildren(document.createTextNode(t('studio')+' '),Object.assign(document.createElement('i'),{textContent:'/'}),document.createTextNode(' '+t(view)));
}
function payload(){return {source:$('#source-input').value.trim(),output:$('#output').value,game:$('#game').value,collection:$('#collection').value,skin:$('#skin').value.trim()}}
function refreshValues(){
 const source=values.source||'';const name=source.split(/[\\/]/).filter(Boolean).at(-1);
 $('#source-name').textContent=name||t('sourceEmpty');$('#source-path').textContent=source||t('sourceScan');$('#source-path').title=source;
 $('#source-input').value=source;
 for(const key of ['output','game','collection','skin'])$('#'+key).value=values[key]||'';
 $('#upload-folder').textContent=values.output||t('output')+' / Pixel Clothing Studio';$('#upload-folder').title=values.output||'';
}
async function action(name,extra={}){return api('action',{action:name,...extra})}
async function choose(field){
 if(pickerPending)return;
 pickerPending=true;$('#picker-status').hidden=false;$$('[data-choose],#edit-output,#render-start,#upload-start').forEach(el=>el.disabled=true);
 // Preserve edits before a native picker changes one specific field.
 values={...values,...payload()};
 try{const result=await action('choose',{...payload(),field});values[result.field||field]=result.value;refreshValues()}catch(error){toast(error.message)}
 finally{pickerPending=false;$('#picker-status').hidden=true;if(lastState)renderState(lastState)}
}
function guideContent(name){
 const titles={package:t('sourceGuide'),key:t('keyGuide'),game:t('renderGuide'),skin:t('skinGuide')};
 if(!guides[name])return;
 $('#guide-title').textContent=titles[name];$('#guide-body').textContent=guides[name];$('#guide-keys-link').hidden=name!=='key';currentGuide=name;
}
function help(name){guideContent(name);if(guides[name]&&!$('#guide-dialog').open)$('#guide-dialog').showModal();
}
async function startRender(){
 if(!payload().source){help('package');return}
 try{await action('render',payload());await poll()}catch(error){toast(error.message)}
}
async function startUpload(){
 if(!payload().skin){toast(t('selectSkinFirst'));$('#skin').focus();return}
 const input=$('#private-key'),key=input.value.trim();
 if(!key){help('key');return}
 if(!key.startsWith('private_')){toast(t('wrongKey'));return}
 try{await action('upload',{...payload(),key});input.value='';input.type='password';$('#toggle-key').setAttribute('aria-pressed','false');await poll()}catch(error){toast(error.message)}
}
function renderState(state){
 lastState=state;const p=state.progress||{},busy=state.busy,upload=state.kind==='upload';
 const phaseText={idle:t('idle'),preparing:t('preparing'),setup:t('setup'),scanning:t('scanning'),rendering:t('rendering'),validating:t('validating'),'upload-start':t('preparing'),uploading:t('uploading'),verifying:t('verifying'),uploaded:t('uploading'),'upload-complete':t('finalizing'),finalizing:t('finalizing'),integrating:t('integrating'),complete:t('complete'),stopped:t('stopped'),error:t('error')}[state.phase]||t('ready');
 const pill=$('#status-pill');pill.classList.toggle('busy',busy);pill.classList.toggle('error',state.phase==='error');pill.querySelector('b').textContent=busy?phaseText:state.phase==='complete'?t('complete'):state.phase==='error'?t('error'):t('ready');
 $$('.progress-card').forEach(card=>{
  card.querySelector('.phase-label').textContent=phaseText;
  card.querySelector('.percent').replaceChildren(document.createTextNode(formatNumber(p.percent)),Object.assign(document.createElement('span'),{textContent:'%'}));
  card.querySelector('.counter').textContent=formatNumber(p.done)+' / '+formatNumber(p.total)+' '+t('images');
  card.querySelector('.ring-value').style.strokeDashoffset=String(427.26*(1-(p.percent||0)/100));
  card.querySelector('.mini-progress span').style.width=(p.percent||0)+'%';
  card.querySelector('.eta').textContent=state.phase==='idle'?'—':state.phase==='error'?t('interrupted'):!busy&&state.phase!=='complete'?t('paused'):duration(p.eta);
  card.querySelector('.eta-note').textContent=state.phase==='complete'?t('taskComplete'):state.phase==='error'?t('seeDetails'):p.eta==null?t('etaHint'):t('etaLive');
  card.querySelector('.elapsed').textContent=elapsed(p.elapsed);
  card.querySelector('.speed-label').textContent=upload?t('uploadSpeed'):t('renderSpeed');
  card.querySelector('.speed').textContent=upload?(p.bytesPerSecond?bytes(p.bytesPerSecond)+'/'+t('seconds'):'—'):(p.perMinute?formatDecimal(p.perMinute)+' / '+t('minutes'):'—');
  card.querySelector('.current-label').textContent=upload&&p.totalBytes?bytes(p.doneBytes)+' / '+bytes(p.totalBytes):p.total?t('imagesLeft',{count:formatNumber(Math.max(0,p.total-p.done))}):t('noTask');
  card.querySelector('.stop-button').hidden=!busy;
 });
 for(const selector of ['#render-start','#upload-start','[data-choose]','#edit-output','#private-key','#source-input','#output','#game','#collection','#skin','#integrate-existing'])$$(selector).forEach(el=>el.disabled=busy||pickerPending);
 $('#activity-message').textContent=localization.source[state.messageSource||state.message]?t(localization.source[state.messageSource||state.message]):state.message;
 $('#activity-current').textContent=state.current?(upload?t('currentFile',{file:state.current}):state.current):state.cached?t('cachedCount',{count:formatNumber(state.cached)}):t('activityHint');
 $('#stat-saved').textContent=formatNumber(state.saved);$('#stat-cached').textContent=formatNumber(state.cached);$('#stat-failed').textContent=formatNumber(state.failed);
 $('#cloud-result').hidden=!state.settingsReady;$('#cloud-url').value=state.cloud||'';
 $('#integration-title').textContent=state.integrated?t('linked'):t('linkPending');
 $('#integration-message').textContent=state.integrated?t('linkedCount',{models:formatNumber(state.integration?.models),variants:formatNumber(state.integration?.variants)}):t('linkRetry');
 $('#integration-restart').hidden=!state.integrated;
 const log=$('#event-log');const rows=state.logs||[];
 if(log.dataset.last!==JSON.stringify(rows.at(-1))){log.replaceChildren(...rows.map(row=>{const div=document.createElement('div'),time=document.createElement('time');time.textContent=row.time;div.append(time,document.createTextNode(row.text));return div}));log.dataset.last=JSON.stringify(rows.at(-1));log.scrollTop=log.scrollHeight}
 if(state.previewVersion&&state.previewVersion!==previewVersion){previewVersion=state.previewVersion;loadPreview()}
}
async function loadPreview(){
 try{const response=await fetch('/api/preview',{headers:{'X-Pixel-Token':token,'X-Pixel-Language':language}});if(!response.ok)return;const blob=await response.blob();if(previewURL)URL.revokeObjectURL(previewURL);previewURL=URL.createObjectURL(blob);$('#latest-preview').src=previewURL;$('#latest-preview').hidden=false;$('#preview-placeholder').setAttribute('hidden','')}catch(_){}
}
async function poll(){
 const requestedLanguage=language;
 try{const state=await api('state');if(requestedLanguage!==language)return;connectionFailures=0;$('#connection-label').textContent=t('connected');renderState(state)}
 catch(error){connectionFailures++;if(connectionFailures>2){$('#connection-label').textContent=t('connecting');if(connectionFailures===3)toast(t('connectionLost'))}}
}
$$('[data-view]').forEach(el=>el.addEventListener('click',()=>showView(el.dataset.view)));
$$('[data-choose]').forEach(el=>el.addEventListener('click',()=>choose(el.dataset.choose)));
$$('[data-guide]').forEach(el=>el.addEventListener('click',()=>help(el.dataset.guide)));
$$('[data-action]').forEach(el=>el.addEventListener('click',async()=>{try{await action(el.dataset.action,payload())}catch(error){toast(error.message)}}));
$$('button[data-theme]').forEach(el=>el.addEventListener('click',()=>setTheme(el.dataset.theme)));
$$('.stop-button').forEach(el=>el.addEventListener('click',async()=>{try{await action('stop');await poll()}catch(error){toast(error.message)}}));
$('#integrate-existing').addEventListener('click',async()=>{try{await action('integrate',payload());await poll()}catch(error){toast(error.message)}});
$('#render-start').addEventListener('click',startRender);$('#upload-start').addEventListener('click',startUpload);
$('#open-keys').addEventListener('click',()=>action('open-link',{name:'keys'}).catch(e=>toast(e.message)));
$('#guide-keys-link').addEventListener('click',()=>action('open-link',{name:'keys'}).catch(e=>toast(e.message)));
$('#close-guide').addEventListener('click',()=>$('#guide-dialog').close());
$('#guide-dialog').addEventListener('click',event=>{if(event.target===$('#guide-dialog')){const r=event.target.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)event.target.close()}});
$('#toggle-key').addEventListener('click',()=>{const input=$('#private-key'),show=input.type==='password';input.type=show?'text':'password';$('#toggle-key').setAttribute('aria-pressed',String(show));$('#toggle-key').setAttribute('aria-label',show?t('hideKey'):t('showKey'))});
$('#edit-output').addEventListener('click',async()=>{await choose('output')});
for(const key of ['output','game','collection','skin'])$('#'+key).addEventListener('change',()=>{values[key]=$('#'+key).value;if(key==='output')$('#upload-folder').textContent=values.output});
$('#source-input').addEventListener('input',()=>{values.source=$('#source-input').value.trim();const name=values.source.split(/[\\/]/).filter(Boolean).at(-1);$('#source-name').textContent=name||t('sourceEmpty');$('#source-path').textContent=values.source||t('sourceScan')});
$('#copy-cloud').addEventListener('click',async()=>{try{await navigator.clipboard.writeText($('#cloud-url').value);toast(t('copied'))}catch(_){$('#cloud-url').select();toast(t('copyManually'))}});
$('#exit').addEventListener('click',async()=>{try{await action('close');window.close();toast(t('appClosed'))}catch(error){toast(error.message)}});
async function boot(){
 try{localization=await (await fetch('/locales.json')).json();bindStaticTranslations();populateLanguages();applyLanguage();if(!token)throw new Error(t('launchApp'));const data=await api('bootstrap');values=data.values;guides=localization.guides[language]||data.guides;refreshValues();await poll()}
 catch(error){toast(error.message)}
 setInterval(poll,1000);
}
boot();
