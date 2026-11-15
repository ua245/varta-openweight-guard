"""Pre-flight check for a model server: reachable, model listed, tool calling works.

python3 -m agent.check --base-url http://<server>:8000/v1 --model <name> [--api-key ...]
"""
import argparse
import json
import os
import time
import urllib.error
import urllib.request

from .llm import OpenAICompatLLM
from .run import default_base_url
from .tools import TOOL_SPECS


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=default_base_url())
    ap.add_argument("--model", default=os.environ.get("AGENT_MODEL", "gemma4:e2b"))
    ap.add_argument("--api-key", default=os.environ.get("AGENT_API_KEY", "none"))
    a = ap.parse_args()
    print(f"server: {a.base_url}\nmodel : {a.model}\n")

    req = urllib.request.Request(a.base_url.rstrip("/") + "/models",
                                 headers={"Authorization": f"Bearer {a.api_key}"})
    try:
        models = [m["id"] for m in json.load(urllib.request.urlopen(req, timeout=15))["data"]]
    except Exception as e:
        print(f"[FAIL] server not reachable: {e}")
        return
    print(f"[ok]   server reachable, models: {models}")
    print(f"[{'ok' if a.model in models else 'FAIL'}]   model '{a.model}' "
          f"{'is served' if a.model in models else 'not in the list (check --model)'}")

    t = time.time()
    try:
        msg = OpenAICompatLLM(a.base_url, a.model, api_key=a.api_key).chat(
            [{"role": "user", "content": "Read the file bank/interest.py"}], TOOL_SPECS)
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:300]
        print(f"[FAIL] tool-calling request rejected (HTTP {e.code}): {body}")
        return
    calls = [c["function"]["name"] + c["function"]["arguments"] for c in msg["tool_calls"]]
    if calls:
        print(f"[ok]   tool calling works ({time.time() - t:.1f}s): {calls}")
    else:
        print(f"[FAIL] no tool_calls returned ({time.time() - t:.1f}s). The server must enable "
              f"tool calling for this model. Answer was: {msg['content'][:200]!r}")


if __name__ == "__main__":
    main()
