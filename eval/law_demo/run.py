"""Real model runs, real synthetic files/capture, source mail obtained through IMAP."""
import argparse,hashlib,json,os,shutil,subprocess,sys,tempfile,time,uuid
from pathlib import Path
from .mail import snapshot
ROOT=Path(__file__).resolve().parents[2]
IMAGE='varta-law-demo:20261115'


def build():
    with tempfile.TemporaryDirectory(prefix='kvl-build-') as d:
        c=Path(d)
        for name in ['agent','guard','eval/demo','eval/law_demo']:
            shutil.copytree(ROOT/name,c/name,ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copyfile(ROOT/'eval/law_demo/Dockerfile',c/'Dockerfile')
        subprocess.run(['docker','build','--pull=false','-t',IMAGE,str(c)],check=True)


def inputs_unchanged(mail,source):
    # MIME text uses CRLF; compare bytes instead of universal-newline read_text.
    mail=Path(mail)
    return (mail/'message.txt').read_bytes()==source['body'].encode('utf-8') and (not source['signature'] or (mail/'signature.png').read_bytes()==source['signature'])


def run_one(runtime,mode,guard_on,*,candidate=0,source=None,run_id=None):
    runtime=Path(runtime);source=source or snapshot(runtime,mode,candidate)
    run_id=run_id or str(uuid.uuid4())[:12];out=runtime/'runs'/run_id;out.mkdir(parents=True,exist_ok=False)
    mail=runtime/'inputs'/run_id;mail.mkdir(parents=True); (mail/'message.txt').write_text(source['body']);(mail/'message.eml').write_bytes(source['raw'])
    if source['signature']:(mail/'signature.png').write_bytes(source['signature'])
    metadata={k:v for k,v in source.items() if k not in ['raw','signature']}
    metadata['image_id']=subprocess.check_output(['docker','image','inspect','--format','{{.Id}}',IMAGE],text=True).strip()
    metadata.update(run_id=run_id,guard=guard_on,mode=mode,status='running',started=time.time())
    (out/'manifest.json').write_text(json.dumps(metadata,indent=2)+'\n')
    with tempfile.TemporaryDirectory(prefix='kvl-relay-') as d:
        socket=Path(d)/'model.sock'
        relay=subprocess.Popen([sys.executable,'-m','eval.law_demo.relay','--socket',str(socket)],cwd=ROOT)
        try:
            for _ in range(100):
                if socket.exists():break
                if relay.poll() is not None:raise RuntimeError('Relay exited')
                time.sleep(.05)
            command=['docker','run','--rm','--name','kvl-run-'+run_id,'--network','none','--read-only',
              '--user',f'{os.getuid()}:{os.getgid()}','--cap-drop','ALL','--security-opt','no-new-privileges',
              '--pids-limit','128','--memory','2g','--cpus','2','--tmpfs','/tmp:rw,nosuid,nodev,size=128m',
              '--mount',f'type=bind,src={d},dst=/model-relay,readonly',
              '--mount',f'type=bind,src={mail},dst=/mail-input,readonly',
              '--mount',f'type=bind,src={out},dst=/evidence',IMAGE,'--guard','on' if guard_on else 'off','--mode',mode]
            with (out/'docker.log').open('w') as log:
                process=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=1800)
            metadata['input_unchanged'] = inputs_unchanged(mail,source)
            metadata.update(status='completed' if process.returncode==0 and metadata['input_unchanged'] else 'failed',exit_code=process.returncode,finished=time.time())
            if (out/'result.json').exists():
                result=json.loads((out/'result.json').read_text())
                metadata.update(fixture_sha256=result['fixture_sha256'],workflow_version=result['workflow_version'],policy_sha256=result['policy_sha256'],leaked=result['leaked'],protected_read=result['protected_read'],task_done=result['task_done'],
                  canary_in_final=result['canary_in_final'],blocked_calls=sum(e['action']=='BLOCK' for e in result['events']))
        finally:relay.terminate();relay.wait(timeout=5)
    (out/'manifest.json').write_text(json.dumps(metadata,indent=2)+'\n')
    return metadata


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--runtime',required=True);ap.add_argument('--mode',choices=['text','image'],default='text');ap.add_argument('--guard',choices=['on','off','both'],default='both');ap.add_argument('--candidate',type=int,default=0);ap.add_argument('--build',action='store_true');a=ap.parse_args()
    if a.build:build()
    source=snapshot(a.runtime,a.mode,a.candidate)
    for flag in ([False,True] if a.guard=='both' else [a.guard=='on']):
        r=run_one(a.runtime,a.mode,flag,candidate=a.candidate,source=source)
        print(json.dumps({k:v for k,v in r.items() if k!='body'}),flush=True)


if __name__=='__main__':main()
