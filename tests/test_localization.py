# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pixel Clothing Studio contributors
from pathlib import Path
import json,re,sys,tempfile,unittest,threading,urllib.request,urllib.error
root=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(root/'src'))
import localization as loc
import studio_core as core
from desktop import Controller,LocalServer

class Tests(unittest.TestCase):
 def test_all_messages_and_guides_exist_in_every_language(self):
  self.assertEqual(len(loc.LANGUAGES),18)
  for key,values in loc.CATALOG['strings'].items():
   self.assertEqual(set(values),loc.LANGUAGES)
   expected=set(re.findall(r'\{\w+\}',values['en']))
   for value in values.values():self.assertTrue(value);self.assertEqual(set(re.findall(r'\{\w+\}',value)),expected)
  for lang in loc.LANGUAGES:
   guides=loc.guides(lang);self.assertEqual(set(guides),{'package','key','game','skin'})
   self.assertIn('private_',guides['key']);self.assertIn('Read and write',guides['key']);self.assertIn('restart pixel-skin',guides['skin'])
 def test_locales_normalized_and_unsupported_fallback(self):
  self.assertEqual(loc.normalize('pt-PT'),'pt-BR');self.assertEqual(loc.normalize('ZH_tw'),'zh-CN');self.assertEqual(loc.normalize('__proto__'),'en')
 def test_state_localization_does_not_mutate_job_or_paths(self):
  c=Controller();c.update(message='Görseller ImageKit’e yükleniyor…',current=r'C:\custom\item.ytd');c.log(r'Önceki ayarlar yedeklendi: C:\backups')
  for lang in loc.LANGUAGES:
   s=c.snapshot(lang);self.assertEqual(s['current'],r'C:\custom\item.ytd');self.assertEqual(s['message'],loc.text('uploading',lang) if lang!='tr' else 'Görseller ImageKit’e yükleniyor…')
   self.assertIn(r'C:\backups',s['logs'][0]['text'])
  self.assertEqual(c.snapshot()['message'],'Görseller ImageKit’e yükleniyor…');self.assertNotIn('messageSource',c.snapshot())
 def test_dynamic_logs_translate_and_keep_identifiers(self):
  for lang in loc.LANGUAGES-{'tr'}:
   self.assertIn('1036',loc.message('1036 model · 12 varyant · 3 tarama uyarısı',lang))
   self.assertIn('clothing/abc.webp',loc.message('Yeni/değişen görsel yükleniyor 1/1: clothing/abc.webp',lang))
   self.assertNotIn('görsel',loc.message('12 görsel daha önce doğrulandı; tekrar yüklenmeyecek.',lang))
 def test_preview_uses_selected_language_and_keeps_image_mapping(self):
  with tempfile.TemporaryDirectory(dir=None) as temp:
   catalog={'schema':1,'packs':{'pack':{'items':{'male/tops/model/1':{'variants':{'0':'pack/'+'a'*64+'.webp'}}}}}}
   for lang in ['en','ar','ja']:
    core.write_preview(temp,catalog,lang);html=(Path(temp)/'preview.html').read_text('utf-8');self.assertIn('lang="'+lang+'"',html);self.assertIn('pack/'+'a'*64+'.webp',html);self.assertNotIn('Daha fazla göster',html);self.assertNotIn('__IMAGES__',html)
 def test_localized_api_bootstrap_state_and_errors(self):
  c=Controller();server=LocalServer(c);threading.Thread(target=server.serve_forever,daemon=True).start()
  try:
   for lang in loc.LANGUAGES:
    headers={'X-Pixel-Token':server.token,'X-Pixel-Language':lang}
    def get(path):
     with urllib.request.urlopen(urllib.request.Request(server.origin+path,headers=headers),timeout=5) as response:return json.load(response)
    self.assertEqual(get('/api/bootstrap')['language'],lang);self.assertEqual(get('/api/bootstrap')['guides'],loc.guides(lang));self.assertEqual(get('/api/state')['language'],lang)
    req=urllib.request.Request(server.origin+'/api/action',headers={**headers,'Content-Type':'application/json'},data=b'{"action":"upload","key":"public_wrong"}')
    try:urllib.request.urlopen(req,timeout=5);self.fail('invalid key should be rejected')
    except urllib.error.HTTPError as exc:self.assertEqual(json.load(exc)['error'],loc.text('wrongKey',lang) if lang!='tr' else 'ImageKit sayfasındaki private_ ile başlayan anahtarı girin.')
   with urllib.request.urlopen(server.origin+'/locales.json',timeout=5) as r:self.assertEqual(len(json.load(r)['languages']),18)
  finally:server.shutdown();server.server_close()

if __name__=='__main__':
 unittest.main()
