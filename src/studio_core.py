# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pixel Clothing Studio contributors
"""Local clothing catalogue builder. No GTA files or credentials are distributed."""
from __future__ import annotations
import base64, hashlib, json, os, re, shutil, subprocess, time, urllib.request, uuid
from pathlib import Path

PARTS = {'berd':'masks','uppr':'gloves','lowr':'pants','hand':'bags','feet':'shoes',
         'teef':'accessories','accs':'undershirts','task':'vests','decl':'decals','jbib':'tops',
         'p_head':'hats','p_eyes':'glasses','p_ears':'earrings','p_lwrist':'watches','p_rwrist':'bracelets'}
MODEL = re.compile(r'^(?P<part>p_head|p_eyes|p_ears|p_lwrist|p_rwrist|berd|uppr|lowr|hand|feet|teef|accs|task|decl|jbib)_(?P<id>\d+)(?:_[ur])?(?P<alternate>_\d+)?\.ydd$', re.I)
TEXTURE = re.compile(r'^(?P<part>p_head|p_eyes|p_ears|p_lwrist|p_rwrist|berd|uppr|lowr|hand|feet|teef|accs|task|decl|jbib)_diff_(?P<id>\d+)_(?P<variant>[a-z]+|\d+)(?:_[a-z0-9_]+)?\.ytd$', re.I)
SAFE = re.compile(r'^[a-z0-9_-]+$')

def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''): h.update(chunk)
    return h.hexdigest()

def save_json(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, separators=(',',':')), encoding='utf-8')
    os.replace(temp, path)

def texture_index(token):
    if token.isdigit(): return int(token)
    result = 0
    for char in token.lower(): result = result*26 + ord(char)-96
    return result-1

def collection_identity(prefix):
    prefix = prefix.lower()
    m = re.fullmatch(r'(mp_[mf]_freemode_01)(?:_p)?(?:_[a-z0-9_]+)?', prefix)
    if not m: raise ValueError('Koleksiyon/cinsiyet belirlenemedi: '+prefix)
    return ('male' if m[1].startswith('mp_m_') else 'female'), prefix

def asset_identity(path, source, fallback_collection=''):
    full=path.name.lower();prefix,sep,name=full.partition('^')
    if not sep:
        name=full
        candidates=[p.name.lower() for p in path.parents if p.is_relative_to(source)]
        prefix=next((p for p in candidates if re.fullmatch(r'mp_[mf]_freemode_01(?:_p)?(?:_[a-z0-9_]+)?',p)),fallback_collection.lower().strip())
    model,texture=MODEL.fullmatch(name),TEXTURE.fullmatch(name)
    match=model or texture
    if not match:return None
    gender,collection=collection_identity(prefix);part=match['part'].lower()
    if part.startswith('p_'):
        base='mp_m_freemode_01' if gender=='male' else 'mp_f_freemode_01'
        if collection!=base+'_p' and not collection.startswith(base+'_p_'):collection=base+'_p'+collection[len(base):]
    return (gender,collection,part,int(match['id'])),model,texture,name

def scan(source, output, pack_id='', fallback_collection='', game_root=''):
    source, output = Path(source).resolve(), Path(output).resolve()
    selected=source if source.is_file() else None;target=None;selected_texture=None
    if selected:
        if selected.suffix.lower() not in ('.ydd','.ytd'):raise ValueError('Tek dosya için .ydd modelini veya .ytd dokusunu seçin.')
        source=next((p for p in selected.parents if (p/'fxmanifest.lua').is_file()),selected.parent)
        identity=asset_identity(selected,source,fallback_collection)
        if not identity:raise ValueError('Dosyanın kıyafet kimliği okunamadı.')
        target,model,texture,_=identity
        if model and model['alternate']:raise ValueError('Alternatif model yerine kıyafetin ana YDD modelini seçin.')
        if texture:selected_texture=texture_index(texture['variant'])
    if not source.is_dir(): raise ValueError('Kıyafet paketinin klasörünü seçin.')
    if source == output or source.is_relative_to(output) or output.is_relative_to(source):
        raise ValueError('Çıktı klasörü kıyafet paketinin dışında olmalıdır.')
    resource_name = source.parent.name if source.name.lower()=='stream' else source.name
    pack_id = pack_id.lower().strip() or re.sub('[^a-z0-9_-]+','_',resource_name.lower()).strip('_')
    if selected and (output/'catalog.json').exists():
        gender,collection,part,number=target;key=f'{gender}/{PARTS[part]}/{collection}/{number}'
        previous=json.loads((output/'catalog.json').read_text('utf-8'))
        owners=[pid for pid,p in previous['packs'].items() if key in p['items']]
        if len(owners)>1:raise ValueError('Bu kıyafet birden fazla çıktı paketinde var; ayrı çıktı klasörü kullanın.')
        if owners:pack_id=owners[0]
    if not SAFE.fullmatch(pack_id): raise ValueError('Paket adı yalnızca a-z, 0-9, _ ve - içerebilir.')
    groups, errors, ignored = {}, [], []
    for path in sorted(source.rglob('*')):
        if not path.is_file() or path.suffix.lower() not in ('.ydd','.ytd'): continue
        if not path.resolve().is_relative_to(source):
            errors.append({'file':str(path),'error':'Paket dışına çıkan bağlantı işlenmedi.'}); continue
        group_key=None
        try:
            identity=asset_identity(path,source,fallback_collection)
            if not identity:
                if not selected:ignored.append(str(path.relative_to(source)))
                continue
            group_key,model,texture,name=identity
            if selected and group_key!=target:continue
            gender,collection,part,number=group_key
            if texture and selected_texture is not None and texture_index(texture['variant'])!=selected_texture:continue
            group = groups.setdefault(group_key, {'models':[],'textures':{}})
            if model:
                if model['alternate']: ignored.append(str(path.relative_to(source))); continue
                group['models'].append({'name':name,'path':str(path),'sha256':digest(path)})
            else:
                index = texture_index(texture['variant'])
                if index in group['textures']: raise ValueError('Aynı texture numarası için iki dosya var.')
                group['textures'][index] = {'name':name,'path':str(path),'sha256':digest(path),'textureId':index}
        except ValueError as exc:
            if not selected or path==selected or group_key==target:
                errors.append({'file':str(path.relative_to(source)),'error':str(exc)})
    jobs = []
    for (gender,collection,part,number), group in sorted(groups.items()):
        if not group['models']:
            errors.append({'file':collection+'/'+part+'_'+str(number),'error':'Doku bulundu; eşleşen ana YDD modeli yok.'}); continue
        if len(group['models']) != 1:
            errors.append({'file':collection+'/'+part+'_'+str(number),'error':'Aynı kimliğe bağlı birden fazla ana model var; sessizce seçim yapılmadı.'}); continue
        model = group['models'][0]; textures = [t for _,t in sorted(group['textures'].items())]
        fingerprint = hashlib.sha256(json.dumps([model, textures],sort_keys=True).encode()).hexdigest()[:16]
        jobs.append({'key':f'{gender}/{collection}/{part}_{number:03d}@{fingerprint}',
                     'gender':gender,'collection':collection,'part':part,'category':PARTS[part],
                     'drawable':number,'model':model,'textures':textures,'alternates':[]})
    if not jobs: raise ValueError('İşlenebilir kıyafet bulunamadı. Dosya adları mp_m_freemode_01_paket^jbib_000_u.ydd gibi olmalı; düz adlarda gelişmiş koleksiyon alanını doldurun. '+str(errors[:3]))
    skeletons = {}
    if game_root:
        base = Path(game_root)/'x64v.rpf'/'models'/'cdimages'/'streamedpeds_mp.rpf'
        for gender, model in [('male','mp_m_freemode_01'),('female','mp_f_freemode_01')]:
            skeletons[gender+':'+model] = (base/(model+'.yft')).as_posix()
    plan = {'schema':1,'build':'custom','packId':pack_id,'source':str(source),'jobs':jobs,
            'skeletons':skeletons,'scanErrors':errors,'ignored':ignored,'partial':bool(selected),'selection':str(selected) if selected else ''}
    plan_path = output/'.pixel-work'/pack_id/'render-plan.json'; save_json(plan_path, plan)
    return plan_path, plan

def finalize(plan_path, output,language='tr'):
    from PIL import Image
    plan = json.loads(Path(plan_path).read_text('utf-8')); output = Path(output)
    renders = Path(plan_path).parent/'renders'; rows = {}
    manifest = renders/'manifest.jsonl'
    if manifest.exists():
        for line in manifest.read_text('utf-8').splitlines():
            try:
                row = json.loads(line); rows[row['key']] = row
            except (ValueError,KeyError): continue
    items, failed, empty, files = {}, list(plan['scanErrors']), [], {}
    for job in plan['jobs']:
        key = f"{job['gender']}/{job['category']}/{job['collection']}/{job['drawable']}"
        variants = {}
        for texture_id in [t['textureId'] for t in job['textures']] or [0]:
            row = rows.get(job['key']+'/'+str(texture_id))
            if not row or row['status'] not in ('saved','empty'):
                failed.append({'key':key,'texture':texture_id,'error':'Görsel üretilemedi; render.log / errors.jsonl dosyasına bakın.'}); continue
            if row['status']=='empty': empty.append({'key':key,'texture':texture_id}); continue
            source = (renders/row['path']).resolve()
            if not source.is_relative_to(renders.resolve()): raise ValueError('Geçersiz render dosyası yolu.')
            with Image.open(source) as image:
                if image.size != (512,512) or image.mode != 'RGBA' or image.getchannel('A').getextrema()[0] != 0:
                    raise ValueError('Görsel 512×512 RGBA / şeffaf değil: '+str(source))
            sha = digest(source); rel = plan['packId']+'/'+sha+'.webp'
            dest = output/'images'/rel; dest.parent.mkdir(parents=True,exist_ok=True)
            if not dest.exists(): shutil.copy2(source,dest)
            variants[str(texture_id)] = rel
            files[rel] = {'sha256':sha,'bytes':dest.stat().st_size}
        if variants: items[key] = {'variants':variants}
    catalog_path = output/'catalog.json'
    catalog = json.loads(catalog_path.read_text('utf-8')) if catalog_path.exists() else {'schema':1,'packs':{}}
    if plan.get('partial'):
        previous=catalog['packs'].get(plan['packId'],{'items':{},'files':{}})
        merged=json.loads(json.dumps(previous['items']))
        for key,item in items.items():merged.setdefault(key,{'variants':{}})['variants'].update(item['variants'])
        items=merged;files={**previous['files'],**files}
        used={rel for item in items.values() for rel in item['variants'].values()}
        files={rel:meta for rel,meta in files.items() if rel in used}
    pack = {'name':plan['packId'],'items':items,'files':files}
    pack['revision'] = hashlib.sha256(json.dumps(pack,sort_keys=True).encode()).hexdigest()[:16]
    catalog['packs'][plan['packId']] = pack; save_json(catalog_path,catalog)
    report = {'pack':plan['packId'],'models':len(items),'images':len(files),'bytes':sum(f['bytes'] for f in files.values()),
              'failed':failed,'empty':empty,'status':'complete' if not failed else 'complete-with-errors'}
    save_json(output/'report.json',report)
    write_preview(output,catalog,language)
    return report

def write_preview(output,catalog,language='tr'):
    import localization as locale
    from html import escape
    language=locale.normalize(language)
    rows=[{'name':key+' / texture '+texture,'path':'images/'+path}
          for pack in catalog['packs'].values() for key,item in pack['items'].items()
          for texture,path in item['variants'].items()]
    template='''<!doctype html><meta charset="utf-8"><title>Pixel Clothing Studio · Önizleme</title>
<style>body{background:#161a22;color:#e5ebf7;font:15px system-ui;margin:28px}input,button{padding:12px;background:#252d3b;color:inherit;border:1px solid #42516b;border-radius:8px}#grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:12px;margin:20px 0}article{background:#232b38;border-radius:12px;padding:12px;overflow-wrap:anywhere}img{width:100%;aspect-ratio:1;object-fit:contain;background:repeating-conic-gradient(#333b49 0% 25%,#28303e 0% 50%) 50%/20px 20px}small{display:block;margin-top:10px}</style>
<h1>Pixel Clothing Studio</h1><input id="search" placeholder="Koleksiyon / kategori / numara ara"><span id="count"></span><div id="grid"></div><button id="more">Daha fazla göster</button>
<script>const rows=__ROWS__;let limit=100;const grid=document.getElementById('grid'),search=document.getElementById('search');function draw(){const matches=rows.filter(r=>r.name.includes(search.value.toLowerCase()));grid.replaceChildren(...matches.slice(0,limit).map(r=>{const a=document.createElement('article'),im=document.createElement('img'),label=document.createElement('small');im.src=r.path;im.loading='lazy';label.textContent=r.name;a.append(im,label);return a}));document.getElementById('count').textContent=' '+matches.length+' görsel';document.getElementById('more').hidden=matches.length<=limit}search.oninput=()=>{limit=100;draw()};document.getElementById('more').onclick=()=>{limit+=100;draw()};draw();</script>'''
    template=template.replace('Önizleme',escape(locale.text('preview',language))).replace('Koleksiyon / kategori / numara ara',escape(locale.text('collection',language))).replace('Daha fazla göster',escape(locale.text('more',language))).replace("+' görsel'","+' '+__IMAGES__")
    template=template.replace('<meta',f'<html lang="{language}" dir="'+('rtl' if language=='ar' else 'ltr')+'"><meta',1)
    template=template.replace('__IMAGES__',json.dumps(locale.text('images',language),ensure_ascii=False))
    (Path(output)/'preview.html').write_text(template.replace('__ROWS__',json.dumps(rows,ensure_ascii=False).replace('</','<\\/'))+'</html>',encoding='utf-8')

def check_catalog(catalog, output):
    if catalog.get('schema') != 1 or not isinstance(catalog.get('packs'),dict): raise ValueError('Geçersiz katalog.')
    output = Path(output).resolve()
    for pack in catalog['packs'].values():
        for item in pack.get('items',{}).values():
            if any(rel not in pack['files'] for rel in item['variants'].values()):raise ValueError('Varyantın doğrulanmış görsel dosyası eksik.')
        for rel, meta in pack['files'].items():
            if not re.fullmatch(r'[a-z0-9_-]+/[a-f0-9]{64}\.webp',rel): raise ValueError('Geçersiz görsel yolu.')
            path = (output/'images'/rel).resolve()
            if not path.is_relative_to(output/'images') or digest(path) != meta['sha256']: raise ValueError('Görsel eksik/değişmiş: '+rel)

def merge_catalog(existing, new):
    result = json.loads(json.dumps(existing)); result.setdefault('schema',1); result.setdefault('packs',{})
    result['packs'].update(new['packs']); return result

def verified_public_catalog(output,cloud_base):
    from urllib.parse import urlparse
    output=Path(output).resolve()
    u=urlparse(cloud_base)
    if u.scheme!='https' or not u.hostname or u.username or u.password or u.query or u.fragment or re.search(r'[\s\x00-\x1f\"\'\\]',cloud_base):
        raise ValueError('Geçerli bir HTTPS kök adresi gerekiyor.')
    cloud_base=cloud_base.rstrip('/')+'/'
    catalog=json.loads((output/'catalog.json').read_text('utf-8'));check_catalog(catalog,output)
    if not any(pack.get('files') for pack in catalog['packs'].values()):
        raise ValueError('Önce kıyafet görsellerini oluşturun.')
    receipt_path=output/'upload-receipt.json'
    receipt=json.loads(receipt_path.read_text('utf-8')) if receipt_path.exists() else {}
    for pack in catalog['packs'].values():
        for rel,meta in pack['files'].items():
            if receipt.get('base')!=cloud_base or receipt.get('files',{}).get(rel,{}).get('sha256')!=meta['sha256']:
                raise ValueError('Ayarları almadan önce bütün görselleri yükleyip doğrulayın.')
    public_catalog=json.loads(json.dumps(catalog))
    for pack in public_catalog['packs'].values():pack.pop('files',None)
    return public_catalog

def export_skin_settings(output, cloud_base,language='tr'):
    """Export public metadata next to the renders; never read or edit a resource."""
    from guidance import SKIN_GUIDE
    import localization as locale
    output=Path(output).resolve();cloud_base=cloud_base.rstrip('/')+'/'
    public_catalog=verified_public_catalog(output,cloud_base)
    settings=output/'skin-ayarlari'
    if not settings.resolve().is_relative_to(output):raise ValueError('Ayar klasörü çıktı klasörünün dışında olamaz.')
    settings.mkdir(exist_ok=True)
    save_json(settings/'clothing-images.json',public_catalog)
    snippet='Config.Images.CustomCloudBaseUrl = '+json.dumps(cloud_base,ensure_ascii=False)+'\n'
    (settings/'cdn-ayari.txt').write_text(snippet,encoding='utf-8')
    (settings/'NASIL-KULLANILIR.txt').write_text(locale.guides(language)['skin']+'\n\n'+locale.text('integrationHelp',language)+':\n'+snippet,encoding='utf-8')
    return {'directory':str(settings),'base':cloud_base,'files':3}


def upload_imagekit(output, private_key, folder='pixel-clothing', progress=lambda _:None, cancelled=lambda:False, event=lambda _:None):
    """Keys exist only in process memory; never enter the generated resource or logs."""
    event({'phase':'validating','message':'Görseller kontrol ediliyor.'})
    output=Path(output); catalog=json.loads((output/'catalog.json').read_text('utf-8'));check_catalog(catalog,output)
    folder=folder.strip('/')
    if not re.fullmatch(r'[a-zA-Z0-9_/-]+',folder): raise ValueError('Geçersiz uzak klasör.')
    receipt_path=output/'upload-receipt.json';receipt=json.loads(receipt_path.read_text('utf-8')) if receipt_path.exists() else {'files':{}}
    fingerprint=hashlib.sha256(private_key.encode()).hexdigest()[:16]
    if receipt.get('credentialFingerprint')!=fingerprint:receipt={'files':{},'credentialFingerprint':fingerprint}
    auth=base64.b64encode((private_key+':').encode()).decode(); files={r:m for p in catalog['packs'].values() for r,m in p['files'].items()}
    cached={rel for rel,meta in files.items() if receipt.get('folder')==folder and receipt.get('files',{}).get(rel,{}).get('sha256')==meta['sha256']}
    completed=len(cached);completed_bytes=sum(files[rel]['bytes'] for rel in cached)
    total_bytes=sum(meta['bytes'] for meta in files.values())
    def emit(phase,current=''):
        event({'phase':phase,'current':current,'done':completed,'total':len(files),'doneBytes':completed_bytes,'totalBytes':total_bytes,'cached':len(cached)})
    emit('upload-start')
    if cached:progress(f'{len(cached)} görsel daha önce doğrulandı; tekrar yüklenmeyecek.')
    for index,(rel,meta) in enumerate(files.items()):
        if cancelled(): raise InterruptedError('Yükleme durduruldu; tamamlananlar korunuyor.')
        if rel in cached:continue
        progress(f'Yeni/değişen görsel yükleniyor {index+1}/{len(files)}: {rel}')
        emit('uploading',rel)
        boundary='pixel'+uuid.uuid4().hex;parts=[]
        for key,value in {'fileName':Path(rel).name,'folder':'/'+folder+'/'+str(Path(rel).parent).replace('\\','/'),'useUniqueFileName':'false','overwriteFile':'true'}.items():
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode())
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{Path(rel).name}"\r\nContent-Type: image/webp\r\n\r\n'.encode()+(output/'images'/rel).read_bytes()+b'\r\n')
        body=b''.join(parts)+f'--{boundary}--\r\n'.encode()
        request=urllib.request.Request('https://upload.imagekit.io/api/v1/files/upload',data=body,
               headers={'Authorization':'Basic '+auth,'Content-Type':'multipart/form-data; boundary='+boundary},method='POST')
        try:
            with urllib.request.urlopen(request,timeout=90) as response: result=json.load(response)
            url=result['url']; suffix='/'+rel
            if not url.startswith('https://') or not url.endswith(suffix): raise ValueError('Sunucu beklenmeyen dosya adresi döndürdü.')
            base=url[:-len(rel)]
            emit('verifying',rel)
            # Request the original bytes, bypassing automatic image format optimization.
            with urllib.request.urlopen(urllib.request.Request(url+'?tr=orig-true',headers={'Origin':'https://cfx-nui-pixel-skin'}),timeout=60) as response:
                raw=response.read(26*1024*1024)
            if hashlib.sha256(raw).hexdigest()!=meta['sha256']: raise ValueError('Yüklenen dosya SHA256 doğrulamasını geçemedi.')
        except Exception as exc:
            raise RuntimeError('Görsel yüklenemedi/doğrulanamadı. Bağlantıyı, ImageKit anahtarını ve kotayı kontrol edin. ('+type(exc).__name__+')') from None
        if receipt.get('base') and receipt['base']!=base:
            receipt={'files':{},'credentialFingerprint':fingerprint}
        receipt.update(base=base,folder=folder);receipt['files'][rel]={'sha256':meta['sha256'],'url':url}
        save_json(receipt_path,receipt)
        completed+=1;completed_bytes+=meta['bytes'];emit('uploaded',rel)
    emit('upload-complete')
    return receipt.get('base','')
