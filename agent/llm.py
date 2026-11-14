"""Minimal client for any OpenAI-compatible chat endpoint (Ollama, vLLM, SGLang)."""
import json
import urllib.request


class OpenAICompatLLM:
    def __init__(self, base_url: str, model: str, api_key: str = "none", timeout: int = 300):
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.model = model
        self.api_key = api_key
        self.timeout = timeout

    def chat(self, messages: list, tools: list) -> dict:
        body = {"model": self.model, "messages": messages, "tools": tools, "temperature": 0}
        req = urllib.request.Request(
            self.url, data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            msg = json.load(resp)["choices"][0]["message"]
        return {"role": "assistant", "content": msg.get("content") or "",
                "tool_calls": msg.get("tool_calls") or []}
