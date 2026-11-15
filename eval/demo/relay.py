"""Host Unix-socket relay: only the local model API, with a fixed request budget."""
import argparse
import json
import os
import socketserver
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler


class Server(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.forward()

    def do_POST(self):
        self.forward()

    def forward(self):
        allowed = {'GET': {'/health', '/v1/models'}, 'POST': {'/v1/chat/completions'}}
        if self.path not in allowed.get(self.command, set()):
            self.send_error(403, 'Only the local model API is exposed')
            return
        try:
            n = int(self.headers.get('Content-Length', '0'))
            if n < 0 or n > 1024 * 1024:
                self.send_error(413)
                return
            data = self.rfile.read(n) if n else None
            if self.command == 'POST':
                body = json.loads(data)
                if body.get('model') != 'gpt-oss-20b':
                    self.send_error(403, 'Only the declared target model is exposed')
                    return
                body.update(max_tokens=512, reasoning_effort='low', seed=1729, stream=False)
                data = json.dumps(body).encode()
            req = urllib.request.Request('http://127.0.0.1:8080' + self.path,
                data=data, method=self.command, headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=180) as response:
                content = response.read()
                self.send_response(response.status)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(content)))
                self.end_headers()
                self.wfile.write(content)
        except (ValueError, TypeError, OSError, urllib.error.URLError):
            self.send_error(502, 'Model relay failed')

    def log_message(self, *args):
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--socket', required=True)
    args = parser.parse_args()
    with Server(args.socket, Handler) as server:
        os.chmod(args.socket, 0o600)
        server.serve_forever()


if __name__ == '__main__':
    main()
