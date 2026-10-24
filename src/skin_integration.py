# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pixel Clothing Studio contributors
"""Install verified public image mappings into the resource selected by its owner."""
from pathlib import Path
import copy,hashlib,json,os,re,time,uuid
import studio_core as core

CONFIG='shared/image-sources.lua'
CATALOG='data/clothing-images.json'

def code_mask(text):
    """Keep Lua code positions while hiding comments and string contents."""
    chars=list(text);i=0
    while i<len(text):
        start=i;comment=text.startswith('--',i)
        if comment:i+=2
        bracket=re.match(r'\[(=*)\[',text[i:])
        if bracket:
            end=text.find(']'+bracket[1]+']',i+len(bracket[0]))
            i=len(text) if end<0 else end+len(bracket[1])+2
        elif comment:
            end=text.find('\n',i);i=len(text) if end<0 else end
        elif text[i] in "\"'":
            quote=text[i];i+=1
            while i<len(text):
                if text[i]=='\\':i+=2
                elif text[i]==quote:i+=1;break
                else:i+=1
        else:i+=1;continue
        for n in range(start,min(i,len(text))):
            if chars[n] not in '\r\n':chars[n]=' '
    return ''.join(chars)

def config_setting(raw,base=None):
    text=raw.decode('utf-8-sig');mask=code_mask(text)
    matches=list(re.finditer(r'(?m)^[ \t]*Config\.Images\.CustomCloudBaseUrl[ \t]*=[ \t]*',mask))
    if len(matches)!=1:raise ValueError('image-sources.lua içinde tek bir CustomCloudBaseUrl ayarı bulunmalı.')
    start=matches[0].start()
    literal=re.match(r'([ \t]*Config\.Images\.CustomCloudBaseUrl[ \t]*=[ \t]*)([\"\'])([^\"\'\r\n\\]*)\2([ \t]*(?:--[^\r\n]*)?)(\r?$)',text[start:],re.M)
    if not literal:raise ValueError('CustomCloudBaseUrl tek satırda, tırnak içinde bir HTTPS adresi olmalı.')
    if base is None:return literal[3]
    updated=text[:start]+literal[1]+json.dumps(base,ensure_ascii=False)+literal[4]+literal[5]+text[start+literal.end():]
    return (b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b'')+updated.encode('utf-8')

def checked_path(root,relative):
    candidate=root/relative
    if not candidate.resolve().is_relative_to(root.resolve()):raise ValueError('Skin dosyası seçilen klasörün dışına çıkıyor.')
    for part in [candidate,*candidate.parents]:
        if part.exists() and (part.is_symlink() or getattr(os.lstat(part),'st_file_attributes',0)&0x400):
            raise ValueError('Skin dosyaları bağlantı/junction üzerinden değiştirilemez.')
        if part==root:break
    return candidate

def validate_target(skin):
    if not str(skin).strip():raise ValueError('Önce sunucunuzdaki pixel-skin klasörünü seçin.')
    root=Path(skin).absolute()
    if not root.is_dir():raise ValueError('pixel-skin klasörü bulunamadı.')
    checked_path(root,'fxmanifest.lua');root=root.resolve()
    required=['fxmanifest.lua',CONFIG,'html/custom-clothing-images.js','html/clothing-thumbnails.js']
    for relative in required:
        if not checked_path(root,relative).is_file():raise ValueError('Uyumlu pixel-skin klasörünü seçin; eksik dosya: '+relative)
    manifest=(root/'fxmanifest.lua').read_text('utf-8-sig')
    for relative in [CONFIG,CATALOG,'html/custom-clothing-images.js']:
        if relative not in manifest:raise ValueError('Bu pixel-skin sürümü bulut görsellerini desteklemiyor. Güncel resource’u kullanın.')
    config_setting((root/CONFIG).read_bytes());checked_path(root,CATALOG)
    return root

def public_catalog(value):
    if value.get('schema')!=1 or not isinstance(value.get('packs'),dict):raise ValueError('Skin eşleştirme listesi geçersiz.')
    result=copy.deepcopy(value)
    for pack_id,pack in result['packs'].items():
        if not re.fullmatch(r'[a-z0-9_-]+',pack_id) or not isinstance(pack,dict) or not isinstance(pack.get('items'),dict):raise ValueError('Kıyafet paketinin eşleştirme kaydı geçersiz.')
        pack.pop('files',None)
        for key,item in pack['items'].items():
            if not re.fullmatch(r'(male|female)/[a-z]+/[a-z0-9_]+/\d+',key) or not isinstance(item,dict) or not isinstance(item.get('variants'),dict):raise ValueError('Kıyafet kimliği geçersiz.')
            for texture,rel in item['variants'].items():
                if not re.fullmatch(r'\d+',texture) or int(texture)>65535 or not isinstance(rel,str) or not re.fullmatch(r'[a-z0-9_-]+/[a-f0-9]{64}\.webp',rel):raise ValueError('Kıyafet görsel yolu geçersiz.')
    return result

def merge_public(existing,incoming):
    result=public_catalog(existing);incoming=public_catalog(incoming)
    for pack_id,pack in incoming['packs'].items():
        merged=result['packs'].setdefault(pack_id,{'name':pack_id,'items':{}})
        for key,item in pack['items'].items():
            merged['items'].setdefault(key,{'variants':{}})['variants'].update(item['variants'])
        merged['revision']=hashlib.sha256(json.dumps(merged['items'],sort_keys=True).encode()).hexdigest()[:16]
    return result

def replace_bytes(path,raw):
    temp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        temp.write_bytes(raw)
        for attempt in range(8):
            try:os.replace(temp,path);return
            except PermissionError:
                if attempt==7:raise
                time.sleep(.05*(attempt+1))
    finally:temp.unlink(missing_ok=True)

def integrate(output,skin):
    """No image binaries, credentials, server commands, or unrelated files are installed."""
    output=Path(output).resolve();root=validate_target(skin)
    if output==root or output.is_relative_to(root) or root.is_relative_to(output):raise ValueError('Çıktı klasörü pixel-skin klasörünün dışında olmalı.')
    if not (output/'upload-receipt.json').is_file():raise ValueError('Bu çıktı klasöründe doğrulanmış yükleme kaydı yok. Önce görselleri ImageKit’e yükleyin.')
    receipt=json.loads((output/'upload-receipt.json').read_text('utf-8'))
    base=receipt.get('base','');incoming=core.verified_public_catalog(output,base)
    lock=checked_path(root,'.pixel-studio.lock')
    try:fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    except FileExistsError:raise ValueError('Bu pixel-skin için başka bir entegrasyon devam ediyor.') from None
    backup=None
    try:
        os.close(fd)
        config=checked_path(root,CONFIG);catalog=checked_path(root,CATALOG)
        originals={CONFIG:config.read_bytes(),CATALOG:catalog.read_bytes() if catalog.exists() else None}
        existing=public_catalog(json.loads(originals[CATALOG].decode('utf-8-sig'))) if originals[CATALOG] is not None else {'schema':1,'packs':{}}
        previous=config_setting(originals[CONFIG]).rstrip('/')
        # A single custom base serves every installed pack. Never strand older mappings.
        retained=[]
        for pack_id,pack in existing['packs'].items():
            replacements=incoming['packs'].get(pack_id,{}).get('items',{})
            if any(texture not in replacements.get(key,{}).get('variants',{}) for key,item in pack['items'].items() for texture in item['variants']):retained.append(pack_id)
        if retained and previous!=base.rstrip('/'):raise ValueError('Skin’de farklı CDN’e ait eski görseller var. Bu projenin tüm paketlerini aynı ImageKit hesabına yükleyin; mevcut eşleştirmeler korundu.')
        merged=merge_public(existing,incoming)
        updates={CONFIG:config_setting(originals[CONFIG],base),CATALOG:json.dumps(merged,ensure_ascii=False,separators=(',',':')).encode('utf-8')}
        changed=[rel for rel,raw in updates.items() if raw!=originals[rel]]
        if changed:
            backup=output/'.pixel-backups'/(time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8])
            backup.mkdir(parents=True)
            for rel,raw in originals.items():
                if raw is not None:
                    dest=backup/rel;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
            written=[]
            try:
                for rel in changed:
                    path=checked_path(root,rel)
                    if (path.read_bytes() if path.exists() else None)!=originals[rel]:raise ValueError('Skin ayarı başka bir işlemde değişti; yeniden deneyin.')
                    path.parent.mkdir(parents=True,exist_ok=True);replace_bytes(path,updates[rel]);written.append(rel)
            except Exception:
                for rel in reversed(written):
                    path=checked_path(root,rel)
                    if path.read_bytes()==updates[rel]:
                        if originals[rel] is None:path.unlink()
                        else:replace_bytes(path,originals[rel])
                raise
        result={'skin':str(root),'base':base,'backup':str(backup) if backup else '', 'changedFiles':len(changed),'models':sum(len(p['items']) for p in incoming['packs'].values()),'variants':sum(len(i['variants']) for p in incoming['packs'].values() for i in p['items'].values()),'restartRequired':bool(changed)}
        core.save_json(output/'skin-integration.json',result)
        return result
    finally:lock.unlink(missing_ok=True)
