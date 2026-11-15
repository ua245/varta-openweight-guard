"""Separate target transport: never reuses OPENAI_API_KEY from the curator."""
import json
import os
import time
import urllib.request
from urllib.parse import urlsplit

from .openai_client import NoRedirect


class TargetLLM:
    def __init__(self, base_url, model, *, temperature=0.2, max_tokens=512, seed=1729):
        parsed = urlsplit(base_url)
        if parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('Target base URL must be an HTTP(S) endpoint without credentials, query or fragment')
        self.timings = []
        self.url = base_url.rstrip('/') + '/chat/completions'
        self.model, self.temperature, self.max_tokens, self.seed = model, temperature, max_tokens, seed

    def chat(self, messages, tools):
        body = {'model': self.model, 'messages': messages, 'tools': tools,
                'temperature': self.temperature, 'max_tokens': self.max_tokens,
                'reasoning_effort': 'low', 'seed': self.seed}
        headers = {'Content-Type': 'application/json'}
        if os.environ.get('TARGET_API_KEY'):
            headers['Authorization'] = 'Bearer ' + os.environ['TARGET_API_KEY']
        request = urllib.request.Request(self.url, data=json.dumps(body).encode(), headers=headers)
        started = time.monotonic()
        with urllib.request.build_opener(NoRedirect).open(request, timeout=120) as response:
            result = json.load(response)
        self.timings.append({'seconds': time.monotonic() - started, 'usage': result.get('usage'),
                             'timings': result.get('timings'), 'returned_model': result.get('model'),
                             'system_fingerprint': result.get('system_fingerprint')})
        msg = result['choices'][0]['message']
        return {'role': 'assistant', 'content': msg.get('content') or '', 'tool_calls': msg.get('tool_calls') or []}
