// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Pixel Clothing Studio contributors
const fs=require('fs'),path=require('path'),assert=require('assert');
const {chromium}=require('playwright');
const repository=path.resolve(__dirname,'..'),root=path.join(repository,'.test-artifacts'),source=path.join(repository,'src'),data=JSON.parse(fs.readFileSync(path.join(source,'locales.json'),'utf8'));
fs.mkdirSync(root,{recursive:true});
let checks=0;function check(v,m){assert(v,m);checks++}
const tr=(k,l)=>data.strings[k][l];
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.BROWSER_EXECUTABLE_PATH?{executablePath:process.env.BROWSER_EXECUTABLE_PATH}:{})});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000},locale:'tr-TR'}),errors=[],headers=[];let busy=false;
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/*',async route=>{
   const request=route.request(),url=new URL(request.url()),lang=request.headers()['x-pixel-language']||'tr';
   if(url.pathname==='/api/bootstrap')return route.fulfill({json:{values:{source:'C:\\custom\\pack',output:'C:\\output',game:'C:\\GTA V',collection:'mp_m_freemode_01_test',skin:'C:\\server\\pixel-skin'},guides:data.guides[lang]}});
   if(url.pathname==='/api/state'){headers.push(lang);return route.fulfill({json:{busy,kind:'upload',phase:busy?'uploading':'idle',message:tr(busy?'uploading':'startHint',lang),saved:12,cached:2,failed:0,progress:{done:12,total:100,percent:12,eta:120,elapsed:60,bytesPerSecond:4096},logs:[{time:'12:00:00',text:tr('uploading',lang)}]}})}
   const files={'/':'ui/index.html','/style.css':'ui/style.css','/app.js':'ui/app.js','/locales.json':'locales.json'};
   if(files[url.pathname])return route.fulfill({body:fs.readFileSync(path.join(source,files[url.pathname])),contentType:url.pathname.endsWith('.json')?'application/json':url.pathname.endsWith('.js')?'text/javascript':url.pathname.endsWith('.css')?'text/css':'text/html'});
   return route.abort();
  });
  await page.goto('http://127.0.0.1:8765/#fixture');await page.waitForFunction(()=>document.querySelector('#language').options.length===18);
  check(await page.locator('#language option').count()===18,'18 languages listed');
  await page.locator('.nav-item[data-view="upload"]').click();await page.locator('#private-key').fill('private_unsaved_fixture');
  await page.locator('button[data-theme="dark"]').click();busy=true;
  for(const row of data.languages){
   const lang=row.code;
   await page.locator('#language').selectOption(lang);await page.waitForFunction(expected=>document.querySelector('#activity-message').textContent===expected,tr('uploading',lang));
   check(await page.locator('html').getAttribute('lang')===lang,lang+' document language');
   check(await page.locator('html').getAttribute('dir')===row.dir,lang+' document direction');
   check(await page.locator('#render-start').innerText()===tr('generate',lang),lang+' render action translated');
   check(await page.locator('#upload-start').innerText()===tr('uploadConnect',lang),lang+' upload action translated');
   check((await page.locator('#view-upload .counter').innerText()).includes(tr('images',lang)),lang+' progress translated');
   check(await page.locator('#skin').inputValue()==='C:\\server\\pixel-skin',lang+' target preserved');
   check(await page.locator('#source-input').inputValue()==='C:\\custom\\pack',lang+' source preserved');
   check(await page.locator('#private-key').inputValue()==='private_unsaved_fixture',lang+' unsent key preserved in memory');
   check(await page.locator('#upload-start').isDisabled(),lang+' running task remains protected');
   check((await page.evaluate(()=>JSON.stringify(localStorage))).includes('private_unsaved_fixture')===false,lang+' key never persisted');
   check(await page.locator('html').getAttribute('data-theme')==='dark',lang+' theme unchanged');
   await page.locator('[data-guide="key"]:visible').first().click();
   check(await page.locator('#guide-body').innerText()===data.guides[lang].key,lang+' key instructions translated');
   check((await page.locator('#guide-body').innerText()).includes('Read and write'),lang+' key permissions retained');
   await page.locator('#close-guide').click();
   for(const width of [1280,360]){
    await page.setViewportSize({width,height:1000});
    for(const view of ['render','upload','help']){
     await page.locator('.nav-item[data-view="'+view+'"]').click();
     check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),lang+' '+view+' no horizontal overflow '+width);
    }
   }
   await page.setViewportSize({width:1440,height:1000});
   if(['en','ar','ja'].includes(lang)){
    await page.locator('.nav-item[data-view="upload"]').click();await page.evaluate(()=>scrollTo(0,0));await page.waitForTimeout(250);
    await page.screenshot({path:path.join(root,'preview-language-'+lang+'.png'),fullPage:true});
   }
  }
  await page.locator('#language').selectOption('ar');await page.reload();await page.waitForFunction(()=>document.documentElement.lang==='ar'&&document.querySelector('#language').options.length===18);
  check(await page.locator('#language').inputValue()==='ar','language selection survives reload');
  check(await page.locator('html').getAttribute('dir')==='rtl','RTL survives reload');
  check(await page.locator('#private-key').inputValue()==='','key not restored from storage');
  await page.evaluate(()=>localStorage.setItem('pixelLanguage','__proto__'));await page.reload();await page.waitForFunction(()=>document.documentElement.lang==='en');
  check(await page.locator('#language').inputValue()==='en','unsupported locale safely falls back to English');
  check(new Set(headers).size===18,'all locales reach the local API');
  check(errors.length===0,'no page errors: '+errors.join(';'));
  const result={status:'passed',checks,languages:data.languages.map(x=>x.code),rtl:'ar',persistence:true,pathsPreserved:true,privateKeysNeverStored:true,busySwitching:true,pageErrors:errors};
  fs.writeFileSync(path.join(root,'language-browser-tests.json'),JSON.stringify(result,null,2));console.log(result);
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
