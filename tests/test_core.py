# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pixel Clothing Studio contributors
from pathlib import Path
import importlib.util,json,shutil,sys,tempfile,unittest,io
from unittest.mock import patch
root=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(root/'src'))
import studio_core as core

class StudioTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=None);self.base=Path(self.tmp.name)
        self.source=self.base/'customer-pack';self.source.mkdir();self.output=self.base/'output'
    def tearDown(self):self.tmp.cleanup()
    def file(self,name,data=b'example'):
        path=self.source/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data);return path
    def image_catalog(self):
        from PIL import Image
        self.output.mkdir(exist_ok=True);image=Image.new('RGBA',(512,512));image.putpixel((250,250),(200,50,30,255))
        provisional=self.output/'sample.webp';image.save(provisional,format='WEBP',lossless=True)
        sha=core.digest(provisional);rel='custom/'+sha+'.webp';dest=self.output/'images'/rel;dest.parent.mkdir(parents=True);shutil.move(provisional,dest)
        catalog={'schema':1,'packs':{'custom':{'revision':'example','files':{rel:{'sha256':sha,'bytes':dest.stat().st_size}},'items':{'male/tops/mp_m_freemode_01_custom/0':{'variants':{'0':rel}}}}}}
        core.save_json(self.output/'catalog.json',catalog);return catalog,rel,sha
    def skin(self):
        skin=self.base/'pixel-skin';(skin/'shared').mkdir(parents=True)
        (skin/'fxmanifest.lua').write_text("fx_version 'cerulean'",encoding='utf-8')
        (skin/'shared/image-sources.lua').write_text("Config.Images = {}\nConfig.Images.CloudBaseUrl = 'https://stock.example/'\nConfig.Images.CustomCloudBaseUrl = ''\n",encoding='utf-8')
        return skin
    def receipt(self,rel,sha,base='https://customer.example/pixel-clothing/'):
        core.save_json(self.output/'upload-receipt.json',{'base':base,'files':{rel:{'sha256':sha}}})
    def test_prefixed_models_gender_and_collection(self):
        self.file('stream/mp_f_freemode_01_custom^jbib_004_u.ydd')
        self.file('stream/mp_f_freemode_01_custom^jbib_diff_004_c_uni.ytd')
        path,plan=core.scan(self.source,self.output)
        self.assertEqual(len(plan['jobs']),1);job=plan['jobs'][0]
        self.assertEqual((job['gender'],job['category'],job['collection'],job['drawable']),('female','tops','mp_f_freemode_01_custom',4))
        self.assertEqual(job['textures'][0]['textureId'],2)
    def test_texture_gaps_and_alphabetic_indices(self):
        self.file('mp_m_freemode_01_custom^jbib_000_u.ydd')
        for token in ['aa','z','a','c']:self.file('mp_m_freemode_01_custom^jbib_diff_000_'+token+'_uni.ytd',token.encode())
        _,plan=core.scan(self.source,self.output)
        self.assertEqual([t['textureId'] for t in plan['jobs'][0]['textures']],[0,2,25,26])
    def test_alternates_do_not_duplicate_drawables(self):
        self.file('mp_m_freemode_01_custom^jbib_000_u.ydd')
        self.file('mp_m_freemode_01_custom^jbib_000_u_1.ydd')
        _,plan=core.scan(self.source,self.output);self.assertEqual(len(plan['jobs']),1);self.assertEqual(len(plan['ignored']),1)
    def test_props_match_fivem_prop_collection(self):
        self.file('mp_m_freemode_01_custom^p_head_002.ydd')
        _,plan=core.scan(self.source,self.output);self.assertEqual(plan['jobs'][0]['collection'],'mp_m_freemode_01_p_custom')
    def test_collection_starting_with_p_is_not_mistaken_for_prop_marker(self):
        self.file('mp_m_freemode_01_police^p_head_002.ydd')
        _,plan=core.scan(self.source,self.output);self.assertEqual(plan['jobs'][0]['collection'],'mp_m_freemode_01_p_police')
    def test_plain_names_require_collection(self):
        self.file('jbib_000_u.ydd')
        with self.assertRaises(ValueError):core.scan(self.source,self.output)
        _,plan=core.scan(self.source,self.output,fallback_collection='mp_m_freemode_01_custom');self.assertEqual(len(plan['jobs']),1)
    def test_unknown_models_are_reported(self):
        self.file('mp_m_freemode_01_custom^jbib_000_u.ydd')
        self.file('broken^feet_001_u.ydd')
        _,plan=core.scan(self.source,self.output);self.assertEqual(len(plan['scanErrors']),1)
    def test_duplicate_models_reported_not_guessed(self):
        self.file('a/mp_m_freemode_01_custom^jbib_000_u.ydd')
        self.file('b/mp_m_freemode_01_custom^jbib_000_u.ydd')
        with self.assertRaises(ValueError):core.scan(self.source,self.output)
    def test_output_cannot_be_source_or_nested(self):
        for output in [self.source,self.source/'output',self.base]:
            with self.assertRaises(ValueError):core.scan(self.source,output)
    def test_scan_fingerprint_changes_for_modified_texture(self):
        self.file('mp_m_freemode_01_custom^jbib_000_u.ydd')
        p=self.file('mp_m_freemode_01_custom^jbib_diff_000_a_uni.ytd')
        _,first=core.scan(self.source,self.output);p.write_bytes(b'changed')
        _,second=core.scan(self.source,self.output);self.assertNotEqual(first['jobs'][0]['key'],second['jobs'][0]['key'])
    def test_export_produces_only_public_metadata_and_instructions(self):
        cat,rel,sha=self.image_catalog();skin=self.skin();self.receipt(rel,sha)
        before={p.relative_to(skin):p.read_bytes() for p in skin.rglob('*') if p.is_file()}
        result=core.export_skin_settings(self.output,'https://customer.example/pixel-clothing/')
        settings=Path(result['directory'])
        self.assertEqual(set(p.name for p in settings.iterdir()),{'clothing-images.json','cdn-ayari.txt','NASIL-KULLANILIR.txt'})
        self.assertEqual(len(list(settings.rglob('*.webp'))),0)
        exported=json.loads((settings/'clothing-images.json').read_text())
        self.assertNotIn('files',exported['packs']['custom'])
        self.assertEqual((settings/'cdn-ayari.txt').read_text(),'Config.Images.CustomCloudBaseUrl = "https://customer.example/pixel-clothing/"\n')
        self.assertEqual(before,{p.relative_to(skin):p.read_bytes() for p in skin.rglob('*') if p.is_file()})
    def test_unverified_upload_cannot_export_settings(self):
        self.image_catalog()
        with self.assertRaises(ValueError):core.export_skin_settings(self.output,'https://customer.example/')
        self.assertFalse((self.output/'skin-ayarlari').exists())
    def test_local_and_insecure_sources_rejected(self):
        self.image_catalog()
        for base in ['file:///C:/images','http://example.com','https://user:pass@example.com','https://example.com?secret=a']:
            with self.assertRaises(ValueError):core.export_skin_settings(self.output,base)
    def test_modified_image_rejected_before_export(self):
        cat,rel,sha=self.image_catalog();self.receipt(rel,sha)
        (self.output/'images'/rel).write_bytes(b'corrupt')
        with self.assertRaises(ValueError):core.export_skin_settings(self.output,'https://customer.example/pixel-clothing/')
    def test_all_project_packs_included_in_export(self):
        cat,rel,sha=self.image_catalog();self.receipt(rel,sha)
        cat['packs']['second']=json.loads(json.dumps(cat['packs']['custom']))
        core.save_json(self.output/'catalog.json',cat)
        result=core.export_skin_settings(self.output,'https://customer.example/pixel-clothing/')
        exported=json.loads((Path(result['directory'])/'clothing-images.json').read_text())
        self.assertEqual(set(exported['packs']),{'custom','second'})
    def test_old_upload_receipt_rejected(self):
        cat,rel,sha=self.image_catalog();self.receipt(rel,'0'*64)
        with self.assertRaises(ValueError):core.export_skin_settings(self.output,'https://customer.example/pixel-clothing/')
    def test_legacy_core_installer_entry_point_is_absent(self):
        self.assertFalse(hasattr(core,'install'))
    def test_export_guidance_does_not_contain_credentials(self):
        cat,rel,sha=self.image_catalog();self.receipt(rel,sha)
        result=core.export_skin_settings(self.output,'https://customer.example/pixel-clothing/')
        text=(Path(result['directory'])/'NASIL-KULLANILIR.txt').read_text('utf-8')
        self.assertIn('pixel-skin/data/',text);self.assertIn('shared/image-sources.lua',text)
        self.assertNotIn('credentialFingerprint',text)
    def test_multipart_upload_verification_resume_and_no_secret_files(self):
        cat,rel,sha=self.image_catalog();calls=[];key='test-private-key-should-not-leak'
        def network(request,timeout):
            calls.append(request)
            if request.full_url.endswith('/upload'):
                self.assertIn(b'name="file"',request.data)
                self.assertIn(b'name="useUniqueFileName"\r\n\r\nfalse',request.data)
                return io.BytesIO(json.dumps({'url':'https://ik.imagekit.io/customer/pixel-clothing/'+rel}).encode())
            self.assertIn('orig-true',request.full_url)
            return io.BytesIO((self.output/'images'/rel).read_bytes())
        with patch('urllib.request.urlopen',side_effect=network):
            base=core.upload_imagekit(self.output,key);self.assertEqual(len(calls),2)
            self.assertEqual(core.upload_imagekit(self.output,key),base);self.assertEqual(len(calls),2)
            core.upload_imagekit(self.output,'changed-key');self.assertEqual(len(calls),4)
        for file in self.output.rglob('*.json'):self.assertNotIn(key,file.read_text())
    def test_wrong_remote_bytes_do_not_produce_receipt(self):
        cat,rel,sha=self.image_catalog()
        def network(request,timeout):
            return io.BytesIO(json.dumps({'url':'https://ik.imagekit.io/customer/pixel-clothing/'+rel}).encode() if request.full_url.endswith('/upload') else b'wrong')
        with patch('urllib.request.urlopen',side_effect=network):
            with self.assertRaises(RuntimeError):core.upload_imagekit(self.output,'example')
        self.assertFalse((self.output/'upload-receipt.json').exists())
    def test_cancelled_upload_does_not_activate(self):
        self.image_catalog()
        with self.assertRaises(InterruptedError):core.upload_imagekit(self.output,'example',cancelled=lambda:True)
    def test_preview_is_generated_from_catalog(self):
        cat,rel,sha=self.image_catalog();core.write_preview(self.output,cat)
        html=(self.output/'preview.html').read_text('utf-8');self.assertIn('loading=',html);self.assertIn(rel,html);self.assertNotIn('test-private-key',html)

if __name__=='__main__':
 unittest.main()
