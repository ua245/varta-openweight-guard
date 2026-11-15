"""Minimal OpenAI Responses client. Credentials are never written to result files."""
import json
import os
import shlex
import stat
import urllib.error
import urllib.request
from pathlib import Path


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def load_env_file(path):
    """Read only named API settings, without executing shell syntax or echoing values."""
    path = Path(path).expanduser()
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise ValueError('Environment file must be private: chmod 600 the file')
    allowed = {'OPENAI_API_KEY', 'OPENAI_MODEL', 'OPENAI_BASE_URL'}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('export '):
            line = line[7:].lstrip()
        key, sep, value = line.partition('=')
        if sep and key.strip() in allowed:
            tokens = shlex.split(value, comments=True)
            if len(tokens) != 1:
                raise ValueError('Expected a single quoted or unquoted API setting value')
            os.environ[key.strip()] = tokens[0]


def api_request(path, body=None):
    key = os.environ.get('OPENAI_API_KEY')
    if not key:
        raise ValueError('OPENAI_API_KEY is not available; use --env-file or an exported environment')
    base = os.environ.get('OPENAI_BASE_URL', 'https://api.openai.com/v1').rstrip('/')
    # Do not send this key to arbitrary proxy hosts or follow redirects.
    if base != 'https://api.openai.com/v1':
        raise ValueError('This generator only sends credentials to https://api.openai.com/v1')
    request = urllib.request.Request(base + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=180) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f'OpenAI API returned HTTP {exc.code}; response body omitted') from None
    except urllib.error.URLError:
        raise RuntimeError('OpenAI API transport failed; credentials omitted') from None


def available_models():
    return sorted(item['id'] for item in api_request('/models').get('data', []) if isinstance(item.get('id'), str))
