"""Run the actual legal workflow inside the resource-limited outer container."""
import argparse,json,threading,time
from pathlib import Path
from http.server import ThreadingHTTPServer
from eval.demo.container_entry import Bridge
from agent.llm import OpenAICompatLLM
from .scenario import run_law


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--guard',choices=['on','off'],required=True);ap.add_argument('--mode',choices=['text','image'],required=True);args=ap.parse_args()
    out=Path('/evidence');start=time.time()
    def emit(kind,**data):
        event={'type':kind,'timestamp':time.time(),'elapsed':round(time.time()-start,2),**data}
        with (out/'events.jsonl').open('a') as f:f.write(json.dumps(event)+'\n')
        print(json.dumps(event),flush=True)
    server=ThreadingHTTPServer(('127.0.0.1',8080),Bridge)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    llm=OpenAICompatLLM('http://127.0.0.1:8080/v1','gpt-oss-20b',timeout=190)
    vision=OpenAICompatLLM('http://127.0.0.1:8080/v1','qwen3-vl-2b-local',timeout=190) if args.mode=='image' else None
    try:run_law(llm,args.guard=='on',args.mode,out,vision=vision,emit=emit)
    except Exception as exc:
        emit('run.error',error=type(exc).__name__)
        raise
    finally:server.shutdown()


if __name__=='__main__':main()
