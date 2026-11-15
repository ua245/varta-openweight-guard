"""Minimal client for any OpenAI-compatible chat endpoint (Ollama, vLLM, SGLang)."""
import json
import urllib.request


class OpenAICompatLLM:
    def __init__(self, base_url: str, model: str, api_key: str = "none", timeout: int = 300,
                 temperature: float = 0.0):
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        self.temperature = temperature

    def chat(self, messages: list, tools: list) -> dict:
        body = {"model": self.model, "messages": messages, "tools": tools, "temperature": self.temperature}
        req = urllib.request.Request(
            self.url, data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            msg = json.load(resp)["choices"][0]["message"]
        out = {"role": "assistant", "content": msg.get("content") or "",
               "tool_calls": msg.get("tool_calls") or []}
        if msg.get("reasoning"):
            out["reasoning"] = msg["reasoning"]   # kept for the log, not sent back
        return out

    def describe_image(self, data_url: str, prompt: str) -> str:
        """Vision-only call (no tools): used when this model is the agent's 'eyes'."""
        body = {"model": self.model, "temperature": self.temperature, "messages": [
            {"role": "user", "content": [{"type": "text", "text": prompt},
                                         {"type": "image_url", "image_url": {"url": data_url}}]}]}
        req = urllib.request.Request(
            self.url, data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.load(resp)["choices"][0]["message"].get("content") or ""
