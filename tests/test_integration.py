# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pixel Clothing Studio contributors
from pathlib import Path
import copy,hashlib,io,json,shutil,sys,tempfile,unittest
from unittest.mock import patch
root=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(root/'src'))
import studio_core as core
import skin_integration as integration
from desktop import Controller
from PIL import Image

BASE='https://ik.imagekit.io/customer/pixel-clothing/'
KEY='private_test_fixture'
ITEM='male/tops/mp_m_freemode_01_custom/0'

class Tests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(dir=None);self.home=Path(self.temp.name)
  self.output=self.home/'output';self.output.mkdir();self.skin=self.home/'pixel-skin'
  for folder in ['shared','html','data']:(self.skin/folder).mkdir(parents=True,exist_ok=True)
  self.original_config=("-- CustomCloudBaseUrl documentation\r\nConfig.Images = {}\r\nConfig.Images.CloudBaseUrl = 'https://stock.example/v1/' -- stock\r\n--[[\r\nConfig.Images.CustomCloudBaseUrl = 'ignored'\r\n]]\r\nConfig.Images.CustomCloudBaseUrl = '' -- custom\r\n").encode()
  (self.skin/'shared/image-sources.lua').write_bytes(self.original_config)
  (self.skin/'fxmanifest.lua').write_text("shared_script 'shared/image-sources.lua'\nfiles {'data/clothing-images.json','html/custom-clothing-images.js','html/clothing-thumbnails.js'}")
  for name in ['custom-clothing-images.js','clothing-thumbnails.js']:(self.skin/'html'/name).write_text('// supported')
  core.save_json(self.skin/'data/clothing-images.json',{'schema':1,'packs':{}})
  self.catalog={'schema':1,'packs':{'custom':{'name':'custom','items':{},'files':{}}}}
  self.add_image(ITEM,'0',(220,30,30,255));self.add_image(ITEM,'1',(30,220,30,255));self.add_image(ITEM[:-1]+'1','0',(30,30,220,255))
  self.save_project();self.record_uploads()
 def tearDown(self):self.temp.cleanup()
 def add_image(self,item,texture,color):
  image=Image.new('RGBA',(512,512));image.paste(color,(120,120,390,390));buff=io.BytesIO();image.save(buff,format='WEBP',lossless=True)
  data=buff.getvalue();sha=hashlib.sha256(data).hexdigest();rel='custom/'+sha+'.webp';path=self.output/'images'/rel;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
  pack=self.catalog['packs']['custom'];pack['files'][rel]={'sha256':sha,'bytes':len(data)};pack['items'].setdefault(item,{'variants':{}})['variants'][texture]=rel
  return rel
 def save_project(self):core.save_json(self.output/'catalog.json',self.catalog)
 def record_uploads(self):
  self.receipt={'base':BASE,'folder':'pixel-clothing','credentialFingerprint':hashlib.sha256(KEY.encode()).hexdigest()[:16],'files':{rel:{'sha256':m['sha256'],'url':BASE+rel} for rel,m in self.catalog['packs']['custom']['files'].items()}}
  core.save_json(self.output/'upload-receipt.json',self.receipt)
 def originals(self):return {p.relative_to(self.skin).as_posix():p.read_bytes() for p in self.skin.rglob('*') if p.is_file()}
 def existing(self,catalog=None,base=BASE):
  core.save_json(self.skin/'data/clothing-images.json',catalog or integration.public_catalog(self.catalog))
  (self.skin/'shared/image-sources.lua').write_bytes(integration.config_setting(self.original_config,base))
 def source(self):
  source=self.home/'custom';(source/'stream').mkdir(parents=True);(source/'fxmanifest.lua').write_text("fx_version 'cerulean'")
  for name in ['jbib_000_u.ydd','jbib_diff_000_a_uni.ytd','jbib_diff_000_b_uni.ytd','jbib_001_u.ydd','jbib_diff_001_a_uni.ytd']:
   (source/'stream'/('mp_m_freemode_01_custom^'+name)).write_bytes(name.encode())
  return source
 def test_auto_installs_only_two_public_files_and_backups(self):
  before=self.originals();result=integration.integrate(self.output,self.skin);after=self.originals()
  self.assertEqual(result['changedFiles'],2);self.assertEqual(result['models'],2);self.assertEqual(result['variants'],3)
  self.assertEqual(set(before),set(after));self.assertEqual({p for p in before if before[p]!=after[p]},{'shared/image-sources.lua','data/clothing-images.json'})
  self.assertIn(b"Config.Images.CloudBaseUrl = 'https://stock.example/v1/' -- stock",after[integration.CONFIG]);self.assertIn(b'\r\n',after[integration.CONFIG])
  self.assertEqual((Path(result['backup'])/integration.CONFIG).read_bytes(),self.original_config)
  self.assertFalse(any(self.skin.rglob('*.webp')));self.assertNotIn(KEY,json.dumps(result));self.assertNotIn('credentialFingerprint',after[integration.CATALOG].decode())
 def test_repeated_integration_changes_nothing(self):
  integration.integrate(self.output,self.skin);before=self.originals();result=integration.integrate(self.output,self.skin)
  self.assertEqual(result['changedFiles'],0);self.assertEqual(result['backup'],'');self.assertEqual(before,self.originals())
 def test_other_packs_and_variants_are_preserved(self):
  old=integration.public_catalog(self.catalog);old['packs']['other']=copy.deepcopy(old['packs']['custom']);old['packs']['custom']['items'][ITEM]['variants']['5']=next(iter(self.catalog['packs']['custom']['files']))
  self.existing(old);integration.integrate(self.output,self.skin)
  final=json.loads((self.skin/integration.CATALOG).read_text());self.assertIn('other',final['packs']);self.assertIn('5',final['packs']['custom']['items'][ITEM]['variants'])
 def test_other_cdn_is_not_silently_broken(self):
  old=integration.public_catalog(self.catalog);old['packs']['other']=copy.deepcopy(old['packs']['custom']);self.existing(old,'https://old.example/')
  before=self.originals()
  with self.assertRaisesRegex(ValueError,'farklı CDN'):integration.integrate(self.output,self.skin)
  self.assertEqual(before,self.originals())
 def test_moving_all_existing_records_to_new_cdn_is_allowed(self):
  self.existing(base='https://old.example/');integration.integrate(self.output,self.skin)
  self.assertEqual(integration.config_setting((self.skin/integration.CONFIG).read_bytes()),BASE)
 def test_bad_or_missing_receipt_cannot_activate(self):
  self.receipt['files']={};core.save_json(self.output/'upload-receipt.json',self.receipt);before=self.originals()
  with self.assertRaises(ValueError):integration.integrate(self.output,self.skin)
  self.assertEqual(before,self.originals())
 def test_corrupt_image_cannot_activate(self):
  next((self.output/'images').rglob('*.webp')).write_bytes(b'corrupt');before=self.originals()
  with self.assertRaises(ValueError):integration.integrate(self.output,self.skin)
  self.assertEqual(before,self.originals())
 def test_unverified_variant_reference_cannot_activate(self):
  self.catalog['packs']['custom']['items'][ITEM]['variants']['7']='custom/'+'a'*64+'.webp';self.save_project();before=self.originals()
  with self.assertRaises(ValueError):integration.integrate(self.output,self.skin)
  self.assertEqual(before,self.originals())
 def test_unsupported_resource_rejected(self):
  (self.skin/'fxmanifest.lua').write_text("fx_version 'cerulean'");before=self.originals()
  with self.assertRaises(ValueError):integration.integrate(self.output,self.skin)
  self.assertEqual(before,self.originals())
 def test_no_directory_selection_means_no_network(self):
  c=Controller();c.values['output']=str(self.output)
  with patch.object(core,'upload_imagekit',side_effect=AssertionError('network should not run')):
   with self.assertRaises(ValueError):c.action({'action':'upload','key':KEY,'skin':''})
 def test_second_write_failure_rolls_back_first(self):
  before=self.originals();real=integration.replace_bytes;calls=[]
  def fail_second(path,raw):
   calls.append(path)
   if len(calls)==2:raise PermissionError('locked')
   real(path,raw)
  with patch.object(integration,'replace_bytes',side_effect=fail_second):
   with self.assertRaises(PermissionError):integration.integrate(self.output,self.skin)
  self.assertEqual(before,self.originals());self.assertFalse((self.skin/'.pixel-studio.lock').exists())
 def test_lock_is_not_stolen(self):
  lock=self.skin/'.pixel-studio.lock';lock.write_text('another process')
  with self.assertRaises(ValueError):integration.integrate(self.output,self.skin)
  self.assertEqual(lock.read_text(),'another process')
 def test_invalid_existing_catalog_is_preserved(self):
  (self.skin/integration.CATALOG).write_text('{bad');before=self.originals()
  with self.assertRaises(ValueError):integration.integrate(self.output,self.skin)
  self.assertEqual(before,self.originals())
 def test_missing_catalog_is_created(self):
  (self.skin/integration.CATALOG).unlink();result=integration.integrate(self.output,self.skin)
  self.assertTrue((self.skin/integration.CATALOG).is_file());self.assertEqual(result['variants'],3)
 def test_bom_comments_and_crlf_are_preserved(self):
  raw=b'\xef\xbb\xbf'+self.original_config;updated=integration.config_setting(raw,BASE)
  self.assertTrue(updated.startswith(b'\xef\xbb\xbf'));self.assertEqual(integration.config_setting(updated),BASE)
  self.assertEqual(updated.count(b'\r\n'),raw.count(b'\r\n'));self.assertIn(b"CustomCloudBaseUrl = 'ignored'",updated)
 def test_ambiguous_configuration_rejected(self):
  for extra in [b"\nConfig.Images.CustomCloudBaseUrl = ''",b"\nConfig.Images.CustomCloudBaseUrl = get_url()"]:
   with self.assertRaises(ValueError):integration.config_setting(self.original_config+extra,BASE)
 def test_single_model_only_plans_that_drawable(self):
  source=self.source();_,plan=core.scan(source/'stream/mp_m_freemode_01_custom^jbib_000_u.ydd',self.output)
  self.assertTrue(plan['partial']);self.assertEqual(plan['packId'],'custom');self.assertEqual(len(plan['jobs']),1);self.assertEqual(len(plan['jobs'][0]['textures']),2)
 def test_single_texture_only_plans_that_variant(self):
  source=self.source();_,plan=core.scan(source/'stream/mp_m_freemode_01_custom^jbib_diff_000_b_uni.ytd',self.output)
  self.assertEqual(len(plan['jobs']),1);self.assertEqual([t['textureId'] for t in plan['jobs'][0]['textures']],[1])
 def test_missing_matching_model_fails_before_render(self):
  source=self.source();(source/'stream/mp_m_freemode_01_custom^jbib_000_u.ydd').unlink()
  with self.assertRaises(ValueError):core.scan(source/'stream/mp_m_freemode_01_custom^jbib_diff_000_b_uni.ytd',self.output)
 def partial_render(self):
  source=self.source();plan_path,plan=core.scan(source/'stream/mp_m_freemode_01_custom^jbib_diff_000_b_uni.ytd',self.output)
  renders=plan_path.parent/'renders';renders.mkdir();data_path=renders/'changed.webp'
  image=Image.new('RGBA',(512,512));image.paste((210,50,180,255),(110,110,410,410));image.save(data_path,format='WEBP',lossless=True)
  row={'key':plan['jobs'][0]['key']+'/1','status':'saved','path':'changed.webp'};(renders/'manifest.jsonl').write_text(json.dumps(row)+'\n')
  return core.finalize(plan_path,self.output)
 def test_partial_finalize_keeps_other_items_and_variants(self):
  old=copy.deepcopy(self.catalog);self.partial_render();new=json.loads((self.output/'catalog.json').read_text())
  self.assertEqual(new['packs']['custom']['items'][ITEM]['variants']['0'],old['packs']['custom']['items'][ITEM]['variants']['0'])
  self.assertEqual(new['packs']['custom']['items'][ITEM[:-1]+'1'],old['packs']['custom']['items'][ITEM[:-1]+'1'])
  self.assertNotEqual(new['packs']['custom']['items'][ITEM]['variants']['1'],old['packs']['custom']['items'][ITEM]['variants']['1'])
  self.assertEqual(len(new['packs']['custom']['files']),3);core.check_catalog(new,self.output)
 def test_single_change_uploads_only_one_file_and_auto_connects(self):
  self.existing();self.partial_render();calls=[]
  def network(request,timeout):
   calls.append(request.full_url)
   if request.full_url.endswith('/upload'):
    cat=json.loads((self.output/'catalog.json').read_text());rel=cat['packs']['custom']['items'][ITEM]['variants']['1']
    return io.BytesIO(json.dumps({'url':BASE+rel}).encode())
   rel=request.full_url.split('?',1)[0][len(BASE):];return io.BytesIO((self.output/'images'/rel).read_bytes())
  c=Controller();c.state['kind']='upload'
  with patch('urllib.request.urlopen',side_effect=network):c.upload(str(self.output),KEY,str(self.skin))
  self.assertEqual(len(calls),2);self.assertEqual(sum(u.endswith('/upload') for u in calls),1)
  self.assertTrue(c.snapshot()['integrated']);self.assertEqual(c.snapshot()['integration']['variants'],3)
  new=json.loads((self.output/'catalog.json').read_text());installed=json.loads((self.skin/integration.CATALOG).read_text())
  self.assertEqual(installed['packs']['custom']['items'],new['packs']['custom']['items'])
 def test_existing_upload_can_integrate_without_key_or_network(self):
  c=Controller();c.state['kind']='integrate'
  with patch('urllib.request.urlopen',side_effect=AssertionError('network should not run')):c.integrate(self.output,self.skin)
  self.assertTrue(c.snapshot()['integrated']);self.assertEqual(c.meter.snapshot()['percent'],100)

if __name__=='__main__':
 unittest.main()
