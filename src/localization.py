# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pixel Clothing Studio contributors
"""Shared, offline translations. File paths, credentials and image IDs stay untouched."""
import json,re
from pathlib import Path

CATALOG=json.loads((Path(__file__).with_name('locales.json')).read_text('utf-8'))
LANGUAGES={row['code'] for row in CATALOG['languages']}

def normalize(language):
    value=str(language or 'tr').replace('_','-')
    exact=next((c for c in LANGUAGES if c.lower()==value.lower()),None)
    if exact:return exact
    base=value.split('-')[0].lower()
    return next((c for c in LANGUAGES if c.split('-')[0]==base),'en')

def text(key,language='tr',**values):
    lang=normalize(language);translations=CATALOG['strings'].get(key,{})
    result=translations.get(lang,translations.get('en',key))
    return re.sub(r'\{(\w+)\}',lambda m:str(values.get(m[1],m[0])),result)

def guides(language='tr'):
    return CATALOG['guides'][normalize(language)].copy()

def message(value,language='tr'):
    lang=normalize(language);value=str(value)
    if lang=='tr':return value
    key=CATALOG['source'].get(value)
    if key:return text(key,lang)
    match=re.fullmatch(r'(\d+) model · (\d+) varyant · (\d+) tarama uyarısı',value)
    if match:return ' · '.join(n+' '+text(k,lang) for n,k in zip(match.groups(),['models','variants','warnings']))
    match=re.fullmatch(r'(\d+) görsel hazır · (\d+) eksik/hata',value)
    if match:return match[1]+' '+text('images',lang)+' · '+match[2]+' '+text('failedLabel',lang)
    match=re.fullmatch(r'Otomatik entegrasyon tamamlandı · (\d+) kıyafet · (\d+) varyant',value)
    if match:return text('linkedCount',lang,models=match[1],variants=match[2])
    match=re.fullmatch(r'(\d+) görsel daha önce doğrulandı; tekrar yüklenmeyecek\.',value)
    if match:return text('cachedCount',lang,count=match[1])
    for prefix,key in [('Yeni/değişen görsel yükleniyor ','uploading'),('Önceki ayarlar yedeklendi: ','backup')]:
        if value.startswith(prefix):return text(key,lang)+': '+value[len(prefix):]
    if value.startswith('Görsel yüklenemedi/doğrulanamadı.'):
        return text('uploadError',lang)+(value[value.rfind(' ('):] if ' (' in value else '')
    english=CATALOG['english']
    if value in english:
        group=CATALOG['groups'].get(value)
        return (text(group,lang)+'\n'+english[value]) if group and lang!='en' else english[value]
    for source in sorted(english,key=len,reverse=True):
        if source.endswith(': ') and value.startswith(source):return english[source]+value[len(source):]
        if source.startswith('İşlenebilir kıyafet bulunamadı.') and value.startswith(source):return english[source]
    return value  # External engine diagnostics and literal paths are not rewritten.

def localized_state(state,language):
    state['messageSource']=state['message'];state['message']=message(state['message'],language)
    for row in state.get('logs',[]):
        row['source']=row['text'];row['text']=message(row['text'],language)
    state['language']=normalize(language)
    return state
