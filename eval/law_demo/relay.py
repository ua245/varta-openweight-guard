"""Local-only model relay. Hidden-image extraction and text reasoning both remain on the VM."""
import argparse,json,os,urllib.request,urllib.error
from http.server import BaseHTTPRequestHandler
from eval.demo.relay import Server


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path!='/v1/chat/completions':self.send_error(403);return
        try:
            n=int(self.headers.get('Content-Length','0'))
            if not 0<n<4000000:self.send_error(413);return
            data=json.loads(self.rfile.read(n));model=data.get('model')
            if model not in ['gpt-oss-20b','qwen3-vl-2b-local']:self.send_error(403);return
            port=8080 if model=='gpt-oss-20b' else 8081
            data.update(max_tokens=700 if port==8080 else 240,stream=False,seed=1729)
            if port==8080:data['reasoning_effort']='low'
            req=urllib.request.Request(f'http://127.0.0.1:{port}/v1/chat/completions',data=json.dumps(data).encode(),headers={'Content-Type':'application/json'})
            with urllib.request.urlopen(req,timeout=180) as r:body=r.read();code=r.status
            self.send_response(code);self.send_header('Content-Length',str(len(body)));self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(body)
        except urllib.error.HTTPError as exc:
            detail=exc.read(3000).decode(errors='replace')
            print(json.dumps({'type':'model.upstream_error','status':exc.code,'model':data.get('model'),'detail':detail}),flush=True)
            self.send_error(502,'Local model rejected request')
        except (OSError,ValueError,urllib.error.URLError) as exc:
            print(json.dumps({'type':'model.transport_error','error':type(exc).__name__}),flush=True)
            self.send_error(502,'Local model unavailable')
    def log_message(self,*args):pass


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--socket',required=True);a=ap.parse_args()
    with Server(a.socket,Handler) as server:os.chmod(a.socket,0o600);server.serve_forever()


if __name__=='__main__':main()
