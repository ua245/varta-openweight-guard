"""Loopback-only live presentation board. Shows actual IMAP mail and actual tool/guard events."""
import argparse,io,json,threading,time,uuid
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
from .mail import snapshot,payload
from .stego import extract
from .run import run_one
from .scenario import PUBLIC,PRIVILEGED

ROOT=Path(__file__).resolve().parents[2]


class App:
    def __init__(self,runtime,candidate):
        self.runtime=Path(runtime);self.candidate=candidate;self.active=None;self.lock=threading.Lock()
    def source(self,mode):return snapshot(self.runtime,mode,self.candidate)
    def state(self,mode):
        runs=[]
        for p in (self.runtime/'runs').glob('*/manifest.json'):
            try:
                r=json.loads(p.read_text())
                if r['mode']!=mode or r['candidate']!=self.candidate:continue
                events=p.parent/'events.jsonl';r['events']=[]
                if events.exists():
                    for line in events.read_text().splitlines():
                        try:r['events'].append(json.loads(line))
                        except ValueError:pass
                result=p.parent/'result.json'
                if result.exists():
                    data=json.loads(result.read_text());r['draft']=data.get('draft','');r['captures']=data.get('attacker_received',[])
                r.pop('body',None);runs.append(r)
            except (OSError,ValueError,KeyError):continue
        latest={}
        for r in sorted(runs,key=lambda x:x['started']):latest['on' if r['guard'] else 'off']=r
        source=self.source(mode)
        active=self.active
        if active is None:
            running=[r for r in runs if r.get('status')=='running' and time.time()-r['started']<1800]
            if running:
                recent=max(running,key=lambda x:x['started']);active={'mode':recent['mode'],'arm':'on' if recent['guard'] else 'off','run_id':recent['run_id'],'started':recent['started']}
        decoded=extract(io.BytesIO(source['signature'])) if mode=='image' else payload(self.candidate)
        return {'active':active,'mode':mode,'mail':{k:v for k,v in source.items() if k not in ['raw','signature']},
                'payload':decoded or 'No recognised hidden text was extracted','public_note':PUBLIC,'privileged_note':PRIVILEGED,'latest':latest,
                'recorded_runs':len(runs),'server_time':time.time()}
    def start(self,mode,arm):
        with self.lock:
            if self.active:return False
            self.active={'mode':mode,'arm':arm,'started':time.time()}
        def worker():
            try:
                source=self.source(mode)
                for flag in ([False,True] if arm=='both' else [arm=='on']):
                    runid=uuid.uuid4().hex[:12]
                    self.active={'mode':mode,'arm':'on' if flag else 'off','run_id':runid,'started':time.time()}
                    try:run_one(self.runtime,mode,flag,candidate=self.candidate,source=source,run_id=runid)
                    except Exception as exc:
                        p=self.runtime/'runs'/runid/'manifest.json'
                        r=json.loads(p.read_text()) if p.exists() else {'mode':mode,'guard':flag,'candidate':self.candidate,'run_id':runid,'started':time.time()}
                        r.update(status='failed',error=type(exc).__name__);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(r))
            finally:self.active=None
        threading.Thread(target=worker,daemon=True).start();return True


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--runtime',required=True);ap.add_argument('--candidate',type=int,default=0);ap.add_argument('--port',type=int,default=8095);a=ap.parse_args();app=App(a.runtime,a.candidate)
    class Handler(BaseHTTPRequestHandler):
        def send(self,code,data,content='application/json'):
            if isinstance(data,(dict,list)):data=json.dumps(data).encode()
            if isinstance(data,str):data=data.encode()
            self.send_response(code);self.send_header('Content-Type',content);self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(data)
        def do_GET(self):
            url=urlsplit(self.path);mode=parse_qs(url.query).get('mode',['text'])[0]
            if mode not in ['text','image']:self.send(400,{'error':'Unknown mode'});return
            try:
                if url.path=='/':self.send(200,(ROOT/'eval/law_demo/dashboard.html').read_bytes(),'text/html; charset=utf-8')
                elif url.path=='/api/state':self.send(200,app.state(mode))
                elif url.path=='/api/signature':
                    s=app.source('image');self.send(200,s['signature'],'image/png')
                elif url.path=='/api/mail.eml':
                    s=app.source(mode);self.send(200,s['raw'],'message/rfc822')
                else:self.send(404,{'error':'Not found'})
            except Exception as exc:self.send(503,{'error':type(exc).__name__})
        def do_POST(self):
            if self.path!='/api/run':self.send(404,{'error':'Not found'});return
            origin=self.headers.get('Origin')
            if origin and origin not in [f'http://127.0.0.1:{a.port}',f'http://localhost:{a.port}']:
                self.send(403,{'error':'Only the local presentation board can start a run'});return
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<1000:raise ValueError()
                body=json.loads(self.rfile.read(length));mode=body['mode'];arm=body['arm']
                if mode not in ['text','image'] or arm not in ['off','on','both']:raise ValueError()
                self.send(202 if app.start(mode,arm) else 409,{'accepted':app.active is not None})
            except (ValueError,KeyError):self.send(400,{'error':'Invalid run request'})
        def log_message(self,*args):pass
    print(f'Kingsbridge Vale matter desk: http://127.0.0.1:{a.port}',flush=True)
    ThreadingHTTPServer(('127.0.0.1',a.port),Handler).serve_forever()


if __name__=='__main__':main()
