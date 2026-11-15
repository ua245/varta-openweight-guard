"""GPT-OSS tool history must retain the backend reasoning protocol field."""
import io
import json

from agent.llm import OpenAICompatLLM
from agent.loop import run_agent


def test_tool_history_preserves_reasoning_content(monkeypatch):
    requests = []
    responses = [
        {"content": "", "reasoning_content": "private protocol state", "tool_calls": [
            {"id": "one", "type": "function", "function": {"name": "list_files", "arguments": "{}"}}]},
        {"content": "Done", "tool_calls": []},
    ]

    def open_request(request, **kwargs):
        requests.append(json.loads(request.data))
        return io.BytesIO(json.dumps({"choices": [{"message": responses.pop(0)}]}).encode())

    monkeypatch.setattr("urllib.request.urlopen", open_request)

    class Tools:
        def execute(self, name, args):
            return "public-summary.md"

    logs = []
    result = run_agent(OpenAICompatLLM("http://localhost/v1", "gpt-oss-20b"),
                       "List files", Tools(), log=logs.append)
    assert result["final"] == "Done"
    assistant = requests[1]["messages"][2]
    assert assistant["reasoning_content"] == "private protocol state"
    assert "private protocol state" not in "\n".join(logs)
