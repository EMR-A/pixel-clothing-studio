# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pixel Clothing Studio contributors
from pathlib import Path
import copy,io,json,sys,threading,unittest,urllib.error,urllib.request,tempfile,hashlib
from unittest.mock import patch
root=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(root/'src'))
from progress import Progress
from desktop import Controller,LocalServer,process_dialog_queue,should_close_idle
import studio_core as core

class Tests(unittest.TestCase):
 def test_no_eta_without_enough_samples(self):
  now=[0];p=Progress(10,clock=lambda:now[0]);now[0]=10;p.update(1)
  self.assertIsNone(p.snapshot()['eta'])
 def test_render_rate_and_remaining(self):
  now=[0];p=Progress(20,clock=lambda:now[0])
  for n in range(1,5):now[0]=n*10;p.update(n)
  s=p.snapshot();self.assertEqual(s['eta'],160);self.assertEqual(s['perMinute'],6);self.assertEqual(s['percent'],20)
 def test_resumed_files_do_not_inflate_speed(self):
  now=[0];p=Progress(100,80,clock=lambda:now[0])
  for n in range(1,4):now[0]=n*10;p.update(80+n)
  self.assertEqual(p.snapshot()['eta'],170);self.assertEqual(p.snapshot()['perMinute'],6)
 def test_bytes_eta(self):
  now=[0];p=Progress(10,0,10000,0,clock=lambda:now[0])
  for n in range(1,4):now[0]=n*10;p.update(n,n*1000)
  self.assertEqual(p.snapshot()['eta'],70);self.assertEqual(p.snapshot()['bytesPerSecond'],100)
 def test_stalled_estimate_withheld(self):
  now=[0];p=Progress(10,clock=lambda:now[0])
  for n in range(1,4):now[0]=n*5;p.update(n)
  now[0]=100;self.assertIsNone(p.snapshot()['eta'])
 def test_progress_never_wraps_at_100(self):
  now=[0];p=Progress(10,clock=lambda:now[0]);now[0]=20;p.update(10)
  self.assertEqual(p.snapshot()['percent'],100);self.assertEqual(p.snapshot()['eta'],0)
 def test_decreasing_status_ignored(self):
  p=Progress(100,80);p.update(10);self.assertEqual(p.snapshot()['done'],80)
 def test_controller_never_exposes_private_key(self):
  c=Controller();self.assertNotIn('key',json.dumps(c.snapshot()))
  with self.assertRaises(ValueError):c.action({'action':'upload','key':'public_example'})
 def test_busy_action_rejected(self):
  c=Controller();c.update(busy=True)
  with self.assertRaises(ValueError):c.action({'action':'render'})
 def test_stop_preserves_output(self):
  c=Controller();c.action({'action':'stop'});self.assertTrue(c.cancelled)
 def test_skin_path_and_single_file_selectors(self):
  c=Controller();self.assertIn('skin',c.values)
  with patch.object(c,'dialog',return_value='C:/fixture/one.ydd') as dialog:
   result=c.choose('source-file')
  self.assertEqual(result,{'field':'source','value':'C:/fixture/one.ydd'});self.assertEqual(dialog.call_args.args[0],'file')
  with self.assertRaises(ValueError):c.choose('unsupported')
 def test_url_allowlist(self):
  with self.assertRaises(ValueError):Controller().action({'action':'open-link','name':'https://evil.example'})
 def test_dialog_success_cancel_and_exception_do_not_stop_pump(self):
  import queue
  c=Controller();results=[queue.Queue() for _ in range(3)]
  for n in range(3):c.dialogs.put(('directory',{'n':n},results[n]))
  def chooser(data):
   if data['n']==1:raise OSError('chooser failed')
   return 'C:/chosen' if data['n']==0 else ''
  process_dialog_queue(c,chooser,lambda:False)
  self.assertEqual(results[0].get_nowait(),'C:/chosen');self.assertIsInstance(results[1].get_nowait(),OSError);self.assertEqual(results[2].get_nowait(),'')
 def test_picker_preserves_typed_values_on_cancel(self):
  c=Controller()
  with patch.object(c,'dialog',return_value='') as dialog:
   result=c.action({'action':'choose','field':'source','source':'C:/manual','output':'C:/output'})
  self.assertEqual(result['value'],'C:/manual');self.assertEqual(c.values['output'],'C:/output');self.assertEqual(dialog.call_args.kwargs['initial'],'C:/manual')
 def test_lifetime_follows_heartbeat_and_waits_for_modal_or_work(self):
  c=Controller();c.last_seen=100
  self.assertFalse(should_close_idle(c,279));self.assertTrue(should_close_idle(c,281))
  c.dialog_pending=True;self.assertFalse(should_close_idle(c,1000))
  c.dialog_pending=False;c.update(busy=True);self.assertFalse(should_close_idle(c,1000))
  c.update(busy=False);c.last_seen=999;self.assertFalse(should_close_idle(c,1000))
 def test_upload_events_only_complete_after_sha_verified(self):
  from PIL import Image
  with tempfile.TemporaryDirectory(dir=None) as folder:
   output=Path(folder);image=Image.new('RGBA',(512,512));image.putpixel((100,100),(255,0,0,255))
   image.save(output/'test.webp',format='WEBP',lossless=True);raw=(output/'test.webp').read_bytes();sha=hashlib.sha256(raw).hexdigest();rel='custom/'+sha+'.webp'
   (output/'images/custom').mkdir(parents=True);(output/'images'/rel).write_bytes(raw)
   core.save_json(output/'catalog.json',{'schema':1,'packs':{'custom':{'files':{rel:{'sha256':sha,'bytes':len(raw)}},'items':{}}}})
   events=[]
   def network(request,timeout):return io.BytesIO(json.dumps({'url':'https://ik.imagekit.io/customer/pixel-clothing/'+rel}).encode() if request.full_url.endswith('/upload') else raw)
   with patch('urllib.request.urlopen',side_effect=network):core.upload_imagekit(output,'private_example',event=events.append)
   self.assertEqual(events[-1]['done'],1);self.assertEqual(events[-1]['doneBytes'],len(raw))
   self.assertEqual(next(e for e in events if e['phase']=='verifying')['done'],0)
   events=[]
   with patch('urllib.request.urlopen',side_effect=AssertionError('cached upload attempted')):core.upload_imagekit(output,'private_example',event=events.append)
   self.assertEqual(next(e for e in events if e['phase']=='upload-start')['cached'],1)
   self.assertNotIn('private_example',json.dumps(events))
 def test_loopback_server_auth_and_static(self):
  c=Controller();server=LocalServer(c);threading.Thread(target=server.serve_forever,daemon=True).start()
  def request(path,headers=None,data=None):
   return urllib.request.urlopen(urllib.request.Request(server.origin+path,headers=headers or {},data=data),timeout=5)
  try:
   self.assertEqual(server.server_address[0],'127.0.0.1')
   with request('/') as r:self.assertIn(b'Pixel Clothing Studio',r.read());self.assertIn("frame-ancestors 'none'",r.headers['Content-Security-Policy'])
   with self.assertRaises(urllib.error.HTTPError):request('/api/state')
   headers={'X-Pixel-Token':server.token}
   with request('/api/bootstrap',headers) as r:self.assertIn('guides',json.load(r))
   with self.assertRaises(urllib.error.HTTPError):request('/api/state',{**headers,'Origin':'https://evil.example'})
   with self.assertRaises(urllib.error.HTTPError):request('/api/state',{**headers,'Host':'evil.example'})
   with self.assertRaises(urllib.error.HTTPError):request('/../../source/studio_core.py',headers)
   with request('/api/action',headers,b'{"action":"stop"}') as r:self.assertTrue(json.load(r)['ok'])
  finally:server.shutdown();server.server_close()

if __name__=='__main__':
 unittest.main()
