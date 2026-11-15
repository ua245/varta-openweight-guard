import base64
import json

from agent.loop import run_agent
from agent.tools import Tools
from guard import Guard, load_policy


class Vision:
    def __init__(self, error=False):
        self.calls = []
        self.error = error

    def chat(self, messages, tools):
        self.calls.append((messages, tools))
        if self.error:
            raise RuntimeError("sidecar unavailable")
        return {"content": "Invoice total: GBP 123.45", "tool_calls": []}


def test_sidecar_returns_derived_text_without_queuing_image(tmp_path):
    (tmp_path / "invoice.png").write_bytes(b"test image")
    vision = Vision()
    tools = Tools(tmp_path, {}, vision=vision)
    tools.pending_images.append("stale image")
    result = tools.execute("view_image", {"path": "invoice.png"})
    assert "Invoice total: GBP 123.45" in result
    assert "untrusted" in result.lower()
    assert tools.pending_images == []
    messages, specs = vision.calls[0]
    assert specs == []
    image = messages[-1]["content"][-1]
    assert image["type"] == "image_url"
    assert image["image_url"]["url"] == "data:image/png;base64," + base64.b64encode(b"test image").decode()


def test_sidecar_error_never_falls_back_to_text_model(tmp_path):
    (tmp_path / "invoice.jpg").write_bytes(b"test image")
    tools = Tools(tmp_path, {}, vision=Vision(error=True))
    result = tools.execute("view_image", {"path": "invoice.jpg"})
    assert "sidecar unavailable" in result
    assert tools.pending_images == []


def test_native_vision_still_queues_image(tmp_path):
    (tmp_path / "invoice.png").write_bytes(b"test image")
    tools = Tools(tmp_path, {})
    assert "next message" in tools.execute("view_image", {"path": "invoice.png"})
    assert len(tools.pending_images) == 1


def test_text_agent_receives_only_transcription_and_image_taints_session(tmp_path):
    (tmp_path / "invoice.png").write_bytes(b"test image")

    class TextAgent:
        def chat(self, messages, tools):
            assert all(isinstance(message["content"], str) for message in messages)
            if len(messages) == 2:
                return {"role": "assistant", "content": "", "tool_calls": [{
                    "id": "read-image", "type": "function", "function": {
                        "name": "view_image", "arguments": json.dumps({"path": "invoice.png"})}}]}
            assert "Invoice total: GBP 123.45" in messages[-1]["content"]
            return {"role": "assistant", "content": "Invoice read.", "tool_calls": []}

    guard = Guard(load_policy(), project_root=tmp_path, audit_path=tmp_path / "audit.jsonl")
    result = run_agent(TextAgent(), "Read invoice.png", Tools(tmp_path, {}, vision=Vision()),
                       guard=guard, max_steps=2, log=lambda *_: None)
    assert result["final"] == "Invoice read."
    assert any("view_image" in source for source in guard.taint.sources)
