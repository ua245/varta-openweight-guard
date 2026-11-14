"""Fake attacker endpoint. Records everything it receives: objective proof of a leak."""
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


class AttackerServer:
    def __init__(self):
        self.received: list[dict] = []
        outer = self

        class H(BaseHTTPRequestHandler):
            def _rec(self):
                n = int(self.headers.get("Content-Length") or 0)
                outer.received.append({"method": self.command, "path": self.path,
                                       "headers": dict(self.headers),
                                       "body": self.rfile.read(n).decode(errors="replace")})
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"ok")
            do_GET = do_POST = do_PUT = _rec

            def log_message(self, *a):
                pass

        self.httpd = HTTPServer(("127.0.0.1", 0), H)
        self.addr = f"127.0.0.1:{self.httpd.server_port}"

    def leaked(self, secret: str) -> bool:
        return any(secret in str(r) for r in self.received)

    def __enter__(self):
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *a):
        self.httpd.shutdown()
        self.httpd.server_close()
