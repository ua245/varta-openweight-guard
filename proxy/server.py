"""
THE PROXY HTTP surface.

Coding agents MUST point base_url here. Backends from llm_map.json are internal only.
Future features (Docker shell, MCP execute mode, live audit, Tavily) belong in this package.
Tavily: POST /v1/tavily/search and /v1/tavily/verify (stale-answer detector).
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from proxy.map_loader import load_llm_map, pick_backend
from proxy.tools import build_guard, execute_tool

HOST = "127.0.0.1"
PORT = 8787
ROOT = Path(__file__).resolve().parent.parent


class ProxyState:
    def __init__(self):
        self.guard = build_guard(ROOT)
        self.refresh_map()

    def refresh_map(self):
        self.llm_map = load_llm_map(ROOT / "llm_map.json")


STATE = ProxyState()


def _json_response(handler: BaseHTTPRequestHandler, code: int, payload: Any):
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("X-Proxy-Product", "open-weight-agent-guard")
    handler.send_header(
        "X-Agent-Contract",
        "Use this proxy as base_url; do not call llm_map backends directly",
    )
    handler.end_headers()
    handler.wfile.write(body)


def _read_json(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0") or 0)
    raw = handler.rfile.read(length) if length else b"{}"
    if not raw:
        return {}
    return json.loads(raw.decode("utf-8"))


class Handler(BaseHTTPRequestHandler):
    server_version = "OpenWeightAgentGuardProxy/0.1"

    def log_message(self, fmt, *args):  # quieter default
        print(f"[proxy] {self.address_string()} {fmt % args}")

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/health":
            return _json_response(
                self,
                200,
                {
                    "ok": True,
                    "product": "proxy",
                    "notice": "This is THE proxy. All future coding-agent features land here.",
                    "map_loaded": not STATE.llm_map.get("missing"),
                    "endpoints": len(STATE.llm_map.get("endpoints", [])),
                },
            )
        if path == "/v1/map":
            STATE.refresh_map()
            return _json_response(self, 200, STATE.llm_map)
        if path == "/v1/models":
            STATE.refresh_map()
            models = []
            for ep in STATE.llm_map.get("endpoints", []):
                for mid in ep.get("models") or []:
                    models.append({"id": mid, "object": "model", "owned_by": ep.get("name", "local")})
            if not models:
                models.append(
                    {
                        "id": "proxy-no-backend",
                        "object": "model",
                        "owned_by": "proxy",
                        "note": "Run llm-map (Step 1) against a running local LLM",
                    }
                )
            return _json_response(self, 200, {"object": "list", "data": models})
        return _json_response(self, 404, {"error": f"unknown path {path}"})

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/v1/tools/execute":
            return self._tools_execute()
        if path == "/v1/chat/completions":
            return self._chat_completions()
        if path == "/v1/tavily/search":
            body = _read_json(self)
            return _json_response(
                self,
                200,
                execute_tool(STATE.guard, "tavily_search", body),
            )
        if path == "/v1/tavily/verify":
            body = _read_json(self)
            return _json_response(
                self,
                200,
                execute_tool(STATE.guard, "verify_claim", body),
            )
        return _json_response(self, 404, {"error": f"unknown path {path}"})

    def _tools_execute(self):
        body = _read_json(self)
        tool = body.get("tool") or body.get("name")
        args = body.get("args") or body.get("arguments") or {}
        if isinstance(args, str):
            args = json.loads(args)
        no_guard = bool(body.get("no_guard", False))
        if not tool:
            return _json_response(self, 400, {"error": "missing tool"})
        result = execute_tool(STATE.guard, tool, args, no_guard=no_guard)
        return _json_response(self, 200, result)

    def _chat_completions(self):
        body = _read_json(self)
        STATE.refresh_map()
        model = body.get("model")
        backend = pick_backend(STATE.llm_map, model)
        if not backend:
            return _json_response(
                self,
                503,
                {
                    "error": {
                        "message": (
                            "No OpenAI-compatible backend in llm_map.json. "
                            "Run Step 1 (llm-map) while a local LLM server is up."
                        ),
                        "type": "proxy_no_backend",
                    }
                },
            )
        upstream = backend["base_url"].rstrip("/") + "/v1/chat/completions"
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            upstream,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                payload = resp.read()
                self.send_response(resp.status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("X-Proxy-Backend", backend.get("base_url", ""))
                self.send_header("X-Proxy-Product", "open-weight-agent-guard")
                self.end_headers()
                self.wfile.write(payload)
        except urllib.error.HTTPError as e:
            err_body = e.read()
            self.send_response(e.code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(err_body)))
            self.end_headers()
            self.wfile.write(err_body)
        except urllib.error.URLError as e:
            return _json_response(
                self,
                502,
                {"error": {"message": f"upstream {upstream} failed: {e}", "type": "proxy_upstream"}},
            )


def main():
    from varta.banner import print_banner

    STATE.refresh_map()
    n_ep = len(STATE.llm_map.get("endpoints") or [])
    print_banner(
        "proxy",
        extra=(
            f"listen=http://{HOST}:{PORT}  "
            f"map={ROOT / 'llm_map.json'}  "
            f"endpoints={n_ep}  missing={STATE.llm_map.get('missing')}"
        ),
    )
    print("  See proxy/AGENT_CONTRACT.md — all future features land in proxy/.")
    print()
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[proxy] shut down")


if __name__ == "__main__":
    main()
