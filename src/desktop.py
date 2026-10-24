# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Pixel Clothing Studio contributors
"""Local desktop UI host. Bound to loopback with a per-run capability token."""
from __future__ import annotations
import copy,json,mimetypes,os,queue,secrets,subprocess,sys,threading,time,webbrowser
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
import studio_core as core
import runtime_setup as runtime
import skin_integration as integration
import localization as locale
from progress import Progress
from guidance import KEY_GUIDE,PACKAGE_GUIDE,GAME_GUIDE,SKIN_GUIDE,KEYS_URL

SOURCE=Path(__file__).resolve().parent
ROOT=SOURCE.parent

class Controller:
    def __init__(self,engine_root=None):
        self.root=Path(engine_root or ROOT);self.lock=threading.RLock();self.dialogs=queue.Queue()
        self.cancelled=False;self.worker=None;self.child=None;self.meter=None;self.preview=None;self.closed=False
        self.last_seen=time.monotonic();self.dialog_pending=False
        self.language='tr'
        self.values={'source':'','output':str(Path.home()/'Documents/Pixel Clothing Studio'),'collection':'','game':runtime.game_root(),'skin':''}
        self.state={'busy':False,'kind':'idle','phase':'idle','message':'Kıyafet paketini seçerek başlayın.',
                    'progress':{'done':0,'total':0,'percent':0,'elapsed':0,'eta':None,'perMinute':None,'bytesPerSecond':None,'doneBytes':0,'totalBytes':0},
                    'saved':0,'empty':0,'failed':0,'cached':0,'current':'','logs':[], 'cloud':'','previewVersion':0,'settingsReady':False,'integrated':False,'integration':{}}
    def update(self,**data):
        with self.lock:self.state.update(data)
    def log(self,message):
        with self.lock:
            self.state['logs'].append({'time':time.strftime('%H:%M:%S'),'text':message})
            self.state['logs']=self.state['logs'][-120:]
    def snapshot(self,language=None):
        with self.lock:
            if self.meter and self.state['busy']:self.state['progress']=self.meter.snapshot()
            state=copy.deepcopy(self.state)
            return locale.localized_state(state,language) if language else state
    def dialog(self,kind,**data):
        with self.lock:
            if self.dialog_pending:raise ValueError('Açık olan klasör/kurulum penceresini tamamlayın veya iptal edin.')
            self.dialog_pending=True
        result=queue.Queue();self.dialogs.put((kind,data,result))
        try:
            while not self.closed:
                try:
                    value=result.get(timeout=.25)
                    if isinstance(value,Exception):raise ValueError('Windows klasör penceresi açılamadı. Klasör yolunu ilgili alana yapıştırabilirsiniz.') from None
                    return value
                except queue.Empty:continue
            return None
        finally:
            with self.lock:self.dialog_pending=False
    def launch(self,kind,task):
        with self.lock:
            if self.state['busy']:raise ValueError('Bir işlem zaten devam ediyor.')
            self.cancelled=False;self.meter=Progress()
            self.state.update(busy=True,kind=kind,phase='preparing',message='Hazırlanıyor…',current='',failed=0,empty=0,cached=0,integrated=False,integration={},settingsReady=False)
        def work():
            try:task()
            except InterruptedError:
                self.update(phase='stopped',message='Durduruldu. Tamamlanan görseller korunuyor.');self.log('İşlem durduruldu; tekrar başlatınca kaldığı yerden devam eder.')
            except Exception as exc:
                self.update(phase='error',message=str(exc));self.log(str(exc))
            finally:
                with self.lock:
                    self.state['progress']=self.meter.snapshot() if self.meter else self.state['progress']
                    self.state['busy']=False
        self.worker=threading.Thread(target=work,daemon=True);self.worker.start()
    def set_values(self,data):
        for key in self.values:
            if key in data:
                if not isinstance(data[key],str) or len(data[key])>4096:raise ValueError('Geçersiz klasör bilgisi.')
                self.values[key]=data[key].strip()
    def choose(self,field):
        if field not in ('source','source-file','output','game','skin'):raise ValueError('Bu alan için dosya/klasör seçilemez.')
        if self.snapshot()['busy']:raise ValueError('Klasörleri işlem bittikten sonra değiştirin.')
        file_mode=field=='source-file';field='source' if file_mode else field
        path=self.dialog('file' if file_mode else 'directory',title='Güncellenecek tek YDD/YTD dosyası' if file_mode else {'source':'Custom kıyafet paketi veya stream klasörü','output':'Üretim çıktısının kaydedileceği klasör','game':'GTA V Legacy kurulum klasörü','skin':'Sunucudaki pixel-skin resource klasörü'}[field],initial=self.values[field])
        if path and field=='skin':integration.validate_target(path)
        if path:self.values[field]=path
        return {'field':field,'value':self.values[field]}
    def action(self,data):
        action=data.get('action')
        if action=='choose':
            if not self.snapshot()['busy']:self.set_values(data)
            return self.choose(data.get('field'))
        if action=='stop':
            self.cancelled=True
            self.update(message='Durduruluyor; o anki dosyanın tamamlanması bekleniyor…')
            return {'ok':True}
        if action=='open-link':
            urls={'keys':KEYS_URL,'key-docs':'https://imagekit.io/docs/api-keys'}
            if data.get('name') not in urls:raise ValueError('Geçersiz bağlantı.')
            webbrowser.open(urls[data['name']]);return {'ok':True}
        if action=='close':
            if self.snapshot()['busy']:raise ValueError('Önce işlemi durdurun ve tamamlanmasını bekleyin.')
            self.closed=True;return {'ok':True}
        if action in ('preview','open-output','open-settings'):
            if not self.snapshot()['busy']:self.set_values(data)
            output=Path(self.values['output'])
            if action=='open-settings':path=output/'skin-ayarlari'
            elif action=='preview':path=output/'preview.html'
            else:path=output
            if not path.exists():raise ValueError('Bu çıktı henüz hazır değil.')
            if action=='preview':
                core.write_preview(output,json.loads((output/'catalog.json').read_text('utf-8')),self.language)
                webbrowser.open(path.resolve().as_uri())
            else:os.startfile(path)
            return {'ok':True}
        if self.snapshot()['busy']:raise ValueError('Bir işlem zaten devam ediyor.')
        self.set_values(data)
        if action=='render':
            if not self.values['source'] or not Path(self.values['source']).exists():raise ValueError('Kıyafet paketini veya tek YDD/YTD dosyasını seçin.')
            self.launch('render',lambda:self.render(dict(self.values)));return {'ok':True}
        if action=='upload':
            key=data.get('key','')
            if not isinstance(key,str) or not key.startswith('private_') or len(key)>4096:raise ValueError('ImageKit sayfasındaki private_ ile başlayan anahtarı girin.')
            if not (Path(self.values['output'])/'catalog.json').is_file():raise ValueError('Önce görselleri oluşturun veya mevcut çıktı klasörünüzü Diğer ayarlar’dan seçin.')
            integration.validate_target(self.values['skin'])
            output,skin=self.values['output'],self.values['skin']
            self.launch('upload',lambda:self.upload(output,key,skin));return {'ok':True}
        if action=='integrate':
            integration.validate_target(self.values['skin'])
            output,skin=self.values['output'],self.values['skin']
            self.launch('integrate',lambda:self.integrate(output,skin));return {'ok':True}
        raise ValueError('Geçersiz işlem.')
    def render(self,values):
        output=Path(values['output'])
        if not runtime.has_pymateria(self.root):
            self.update(phase='setup',message='İlk kullanım için resmi okuyucu bileşeni gerekiyor.')
            accepted=self.dialog('agreement')
            if not accepted:raise InterruptedError()
            self.log(runtime.install_pymateria(self.root))
        self.update(phase='scanning',message='Kıyafet modelleri ve dokular taranıyor…')
        path,plan=core.scan(values['source'],output,fallback_collection=values['collection'],game_root=values['game'])
        if self.cancelled:raise InterruptedError()
        total=sum(max(1,len(job['textures'])) for job in plan['jobs'])
        self.log(f"{len(plan['jobs'])} model · {total} varyant · {len(plan['scanErrors'])} tarama uyarısı")
        workdir=path.parent;renders=workdir/'renders';renders.mkdir(exist_ok=True)
        expected={f"{j['key']}/{t.get('textureId',i) if t else 0}" for j in plan['jobs'] for i,t in enumerate(j['textures'] or [None])}
        baseline={};manifest=renders/'manifest.jsonl'
        if manifest.exists():
            for line in manifest.read_text('utf-8').splitlines():
                try:
                    row=json.loads(line)
                    if row['key'] in expected:baseline[row['key']]=row
                except (ValueError,KeyError):continue
        valid=[r for r in baseline.values() if r['status']=='empty' or r['status']=='saved' and r.get('size')==512 and (renders/r['path']).is_file()]
        self.meter=Progress(total,len(valid));self.update(cached=len(valid),saved=sum(r['status']=='saved' for r in valid),empty=sum(r['status']=='empty' for r in valid),phase='rendering',message='Görseller oluşturuluyor…')
        (renders/'STOP').unlink(missing_ok=True)
        blender=self.root/'engine/blender/blender.exe'
        if not blender.is_file():raise ValueError('Motor klasörü bulunamadı. ZIP dosyasının tamamını çıkarın.')
        command=[str(blender),'--background','--factory-startup','--python-exit-code','1','--python',str(SOURCE/'render_clothing.py'),
                 '--','--plan',str(path),'--out',str(renders),'--scratch',str(workdir/'scratch'),'--engine','BLENDER_EEVEE']
        with (workdir/'render.log').open('a',encoding='utf-8') as log:
            self.render_started=time.time()
            self.child=subprocess.Popen(command,env=runtime.engine_environment(self.root),stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            try:
                while self.child.poll() is None:
                    if self.cancelled:(renders/'STOP').touch()
                    self.read_render_status(renders);time.sleep(.5)
                code=self.child.returncode
            finally:self.child=None
        self.read_render_status(renders)
        self.update(phase='finalizing',message='Görsel kataloğu ve önizleme hazırlanıyor…')
        report=core.finalize(path,output,self.language)
        self.log(f"{report['images']} görsel hazır · {len(report['failed'])} eksik/hata")
        if self.cancelled:raise InterruptedError()
        if code or report['failed']:
            raise ValueError('Üretim tamamlandı; bazı dosyalar işlenemedi. Çıktı klasöründeki report.json ve render.log dosyasına bakın.')
        self.update(phase='complete',message='Görseller hazır. Önizleyebilir veya buluta yükleyebilirsiniz.',failed=0)
    def read_render_status(self,renders):
        if (renders/'status.json').exists() and (renders/'status.json').stat().st_mtime<getattr(self,'render_started',0):return
        try:data=json.loads((renders/'status.json').read_text('utf-8'))
        except (ValueError,OSError):return
        # A previous run may still have a status file before the new process starts.
        if data.get('totalVariants')!=self.meter.total:return
        saved=data.get('saved',0);empty=data.get('empty',0);done=min(self.meter.total,saved+empty)
        with self.lock:
            self.meter.update(done);self.state.update(saved=saved,empty=empty,failed=data.get('failed',0))
            current=data.get('current') or {};key=current.get('key','').split('@')[0]
            self.state['current']=key+(' · texture '+str(current['texture']) if 'texture' in current else '')
        if saved:
            try:
                # Most recent successfully saved row; no recursive directory scans during rendering.
                with (renders/'manifest.jsonl').open('rb') as stream:
                    stream.seek(0,2);size=stream.tell();stream.seek(max(0,size-16384));tail=stream.read().decode('utf-8',errors='ignore')
                for line in reversed(tail.splitlines()):
                    try:
                        row=json.loads(line)
                        if row['status']=='saved' and row.get('path'):
                            candidate=(renders/row['path']).resolve()
                            if candidate.is_relative_to(renders.resolve()) and candidate.is_file():self.set_preview(candidate);break
                    except (ValueError,KeyError):continue
            except OSError:pass
    def set_preview(self,path):
        if self.preview!=path:
            self.preview=path
            with self.lock:self.state['previewVersion']+=1
    def upload(self,output,key,skin):
        self.update(settingsReady=False,integrated=False,integration={},cloud='',phase='validating',message='Görseller kontrol ediliyor…')
        def event(data):
            phase=data['phase']
            if phase=='upload-start':
                self.meter=Progress(data['total'],data['done'],data['totalBytes'],data['doneBytes'])
            elif 'done' in data:self.meter.update(data['done'],data.get('doneBytes',0))
            messages={'validating':'Görseller kontrol ediliyor…','upload-start':'Yükleme hazırlanıyor…','uploading':'Görseller ImageKit’e yükleniyor…','verifying':'Yüklenen görsel doğrulanıyor…','uploaded':'Görseller yükleniyor ve doğrulanıyor…','upload-complete':'Skin ayarları hazırlanıyor…'}
            values={'phase':phase,'message':messages.get(phase,phase),'current':data.get('current','')}
            if 'cached' in data:values.update(cached=data['cached'],saved=data['done'])
            self.update(**values)
            if data.get('current'):
                candidate=(Path(output)/'images'/data['current']).resolve()
                if candidate.is_relative_to((Path(output)/'images').resolve()) and candidate.is_file():self.set_preview(candidate)
        base=core.upload_imagekit(output,key,progress=self.log,cancelled=lambda:self.cancelled,event=event)
        core.export_skin_settings(output,base,self.language)
        self.update(cloud=base,settingsReady=True)
        if self.cancelled:raise InterruptedError()
        self.integrate(output,skin)
    def integrate(self,output,skin):
        self.update(integrated=False,integration={},phase='integrating',message='Görsel listesi ve ImageKit adresi pixel-skin’e bağlanıyor…')
        if self.cancelled:raise InterruptedError()
        result=integration.integrate(output,skin)
        if self.state['kind']=='integrate':self.meter=Progress(result['variants'],result['variants'])
        self.update(phase='complete',message='ImageKit görselleri pixel-skin’e bağlandı. Sonraki resource başlangıcında kullanılacak.',cloud=result['base'],settingsReady=True,integrated=True,integration=result)
        self.log(f"Otomatik entegrasyon tamamlandı · {result['models']} kıyafet · {result['variants']} varyant")
        if result['backup']:self.log('Önceki ayarlar yedeklendi: '+result['backup'])

class LocalServer(ThreadingHTTPServer):
    daemon_threads=True
    def __init__(self,controller):
        self.controller=controller;self.token=secrets.token_urlsafe(32)
        super().__init__(('127.0.0.1',0),Handler)
        self.origin='http://127.0.0.1:'+str(self.server_port)

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*_):pass  # Never log request bodies or credentials.
    def reply(self,code,data,content_type='application/json'):
        body=json.dumps(data,ensure_ascii=False).encode('utf-8') if content_type=='application/json' else data
        self.send_response(code);self.send_header('Content-Type',content_type);self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'self'; img-src 'self' blob:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers();self.wfile.write(body)
    def authorized(self):
        host=self.headers.get('Host','')
        if host!='127.0.0.1:'+str(self.server.server_port):return False
        token=self.headers.get('X-Pixel-Token','')
        accepted=secrets.compare_digest(token.encode('utf-8'),self.server.token.encode('utf-8')) and self.headers.get('Origin',self.server.origin)==self.server.origin
        if accepted:
            self.server.controller.last_seen=time.monotonic()
            self.server.controller.language=locale.normalize(self.headers.get('X-Pixel-Language',self.server.controller.language))
        return accepted
    def do_GET(self):
        path=urlparse(self.path).path
        if self.headers.get('Host')!='127.0.0.1:'+str(self.server.server_port):self.reply(403,{'error':'Erişim reddedildi.'});return
        if path in ('/api/state','/api/bootstrap','/api/preview'):
            if not self.authorized():self.reply(403,{'error':'Erişim reddedildi.'});return
            if path=='/api/state':self.reply(200,self.server.controller.snapshot(self.server.controller.language))
            elif path=='/api/bootstrap':self.reply(200,{'values':self.server.controller.values,'guides':locale.guides(self.server.controller.language),'language':self.server.controller.language})
            else:
                preview=self.server.controller.preview
                if not preview or not preview.is_file():self.reply(404,{'error':'Önizleme yok.'})
                else:self.reply(200,preview.read_bytes(),'image/webp')
            return
        static={'/':'index.html','/style.css':'style.css','/app.js':'app.js','/icon.svg':'icon.svg','/locales.json':'locales.json'}
        if path not in static:self.reply(404,{'error':'Bulunamadı.'});return
        file=SOURCE/static[path] if path=='/locales.json' else SOURCE/'ui'/static[path];mime='application/json; charset=utf-8' if path=='/locales.json' else 'text/html; charset=utf-8' if path=='/' else 'text/css; charset=utf-8' if path.endswith('.css') else 'image/svg+xml' if path.endswith('.svg') else 'text/javascript; charset=utf-8'
        self.reply(200,file.read_bytes(),mime)
    def do_POST(self):
        if urlparse(self.path).path!='/api/action' or not self.authorized():self.reply(403,{'error':'Erişim reddedildi.'});return
        try:
            size=int(self.headers.get('Content-Length','0'))
            if not 0<size<=20000:raise ValueError('Geçersiz istek boyutu.')
            data=json.loads(self.rfile.read(size));result=self.server.controller.action(data)
            self.reply(200,result)
        except (ValueError,KeyError,TypeError) as exc:self.reply(400,{'error':locale.message(str(exc),self.server.controller.language)})
        except Exception:self.reply(500,{'error':locale.message('İşlem başlatılamadı. Klasörü ve dosya izinlerini kontrol edin.',self.server.controller.language)})

def process_dialog_queue(controller,choose_directory,ask_agreement,choose_file=None):
    """Called on the GUI thread; a failed dialog must not stop the event pump."""
    while True:
        try:kind,data,result=controller.dialogs.get_nowait()
        except queue.Empty:return
        try:
            if kind=='directory':value=choose_directory(data)
            elif kind=='file' and choose_file:value=choose_file(data)
            elif kind=='agreement':value=ask_agreement()
            else:raise ValueError('Bilinmeyen pencere türü.')
        except Exception as exc:value=exc
        result.put(value)

def should_close_idle(controller,now=None):
    # Edge may hand its startup process off to an existing browser process.
    # The local UI's authenticated heartbeat is the reliable lifetime signal.
    return not controller.snapshot()['busy'] and not controller.dialog_pending and (now if now is not None else time.monotonic())-controller.last_seen>180

def main():
    import tkinter as tk
    from tkinter import filedialog,messagebox
    tkroot=tk.Tk();tkroot.withdraw();controller=Controller();server=LocalServer(controller)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    url=server.origin+'/#'+server.token
    browsers=[Path(os.environ.get('ProgramFiles(x86)','C:/Program Files (x86)'))/'Microsoft/Edge/Application/msedge.exe',
              Path(os.environ.get('ProgramFiles','C:/Program Files'))/'Google/Chrome/Application/chrome.exe']
    browser=next((p for p in browsers if p.is_file()),None)
    if browser:
        # A dedicated profile gives this local app its own window and lifetime.
        profile=ROOT/'state/browser';profile.mkdir(parents=True,exist_ok=True)
        proc=subprocess.Popen([str(browser),'--app='+url,'--user-data-dir='+str(profile),'--no-first-run','--disable-background-mode','--window-size=1280,860'],creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    else:proc=None;webbrowser.open(url)
    def with_owner(title,callback):
        # A withdrawn root produces unowned dialogs which can hide behind Edge.
        # Use a visible, raised, topmost owner for the modal Windows dialog.
        title=locale.message(title,controller.language)
        owner=tk.Toplevel(tkroot);owner.title(title);owner.configure(bg='#f3f5f7')
        width,height=540,150
        owner.geometry(f'{width}x{height}+{max(0,(owner.winfo_screenwidth()-width)//2)}+{max(0,(owner.winfo_screenheight()-height)//2)}')
        tk.Label(owner,text=title,bg='#f3f5f7',fg='#17242d',font=('Segoe UI',14,'bold'),wraplength=490).pack(padx=22,pady=(20,10))
        tk.Label(owner,text=locale.text('pickerHint',controller.language),bg='#f3f5f7',fg='#435362',font=('Segoe UI',11),wraplength=490).pack(padx=22)
        owner.attributes('-topmost',True);owner.deiconify();owner.lift();owner.focus_force();owner.update()
        try:return callback(owner)
        finally:owner.destroy()
    def choose_directory(data):
        initial=Path(data.get('initial') or Path.home())
        if not initial.is_dir():initial=Path.home()
        return with_owner(data['title'],lambda owner:filedialog.askdirectory(parent=owner,title=locale.message(data['title'],controller.language),initialdir=str(initial),mustexist=True))
    def ask_agreement():
        webbrowser.open(runtime.AGREEMENT)
        return with_owner('İlk kullanım · PyMateria',lambda owner:messagebox.askyesno(locale.text('setup',controller.language)+' · PyMateria',locale.text('agreement',controller.language),parent=owner))
    def choose_file(data):
        initial=Path(data.get('initial') or Path.home())
        if initial.is_file():initial=initial.parent
        if not initial.is_dir():initial=Path.home()
        return with_owner(data['title'],lambda owner:filedialog.askopenfilename(parent=owner,title=locale.message(data['title'],controller.language),initialdir=str(initial),filetypes=[(locale.text('singleFile',controller.language),'*.ydd *.ytd'),('YDD','*.ydd'),('YTD','*.ytd')]))
    def tick():
        process_dialog_queue(controller,choose_directory,ask_agreement,choose_file)
        if should_close_idle(controller):controller.closed=True
        if controller.closed:
            server.shutdown();server.server_close();tkroot.destroy();return
        tkroot.after(100,tick)
    tkroot.after(100,tick);tkroot.mainloop()

if __name__=='__main__':
    if '--self-check' in sys.argv:
        print(json.dumps({'modernUI':True,'cloudOnly':True,'loopbackOnly':True,'engine':(ROOT/'engine/blender/blender.exe').is_file()}))
    else:main()
