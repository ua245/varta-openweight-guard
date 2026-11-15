"""Adapter from the researcher's chat interface to the Adaption Responses API."""
import json
from unittest import mock

import pytest

from guard.adaption_model import (AdaptionModel, from_responses_output, to_responses_input,
                                   to_responses_tools)
from guard.researcher import ResearcherError


def test_messages_convert_to_responses_input():
    msgs = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "review this"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c1", "function": {"name": "inspect_payload", "arguments": "{}"}}]},
        {"role": "tool", "tool_call_id": "c1", "content": "no secrets"},
    ]
    items = to_responses_input(msgs)
    from guard.adaption_model import split_instructions
    assert split_instructions(msgs) == "sys"              # system -> top-level instructions
    assert all(i.get("role") != "system" for i in items)  # not an input message
    assert {"type": "function_call", "call_id": "c1", "name": "inspect_payload",
            "arguments": "{}"} in items
    assert {"type": "function_call_output", "call_id": "c1", "output": "no secrets"} in items


def test_tools_flatten_to_responses_shape():
    tools = [{"type": "function", "function": {"name": "submit_verdict", "description": "d",
                                               "parameters": {"type": "object", "properties": {}}}}]
    out = to_responses_tools(tools)
    assert out == [{"type": "function", "name": "submit_verdict", "description": "d",
                    "parameters": {"type": "object", "properties": {}}}]


def test_function_call_output_maps_to_tool_calls():
    body = {"output": [{"type": "function_call", "call_id": "x1", "name": "submit_verdict",
                        "arguments": '{"decision":"deny"}'}], "output_text": ""}
    msg = from_responses_output(body)
    assert msg["tool_calls"][0]["function"]["name"] == "submit_verdict"
    assert msg["tool_calls"][0]["id"] == "x1"


def test_server_side_mcp_call_is_rejected():
    body = {"output": [{"type": "mcp_call", "name": "create_or_update_file"}], "output_text": ""}
    with pytest.raises(ResearcherError):
        from_responses_output(body)


def test_complete_fails_closed_on_network_error():
    m = AdaptionModel(api_key="k")
    with mock.patch("urllib.request.urlopen", side_effect=TimeoutError("down")):
        with pytest.raises(ResearcherError):
            m.complete([{"role": "user", "content": "x"}], [])


def test_adapter_drives_his_researcher_end_to_end(tmp_path):
    """The Adaption adapter, feeding a scripted Responses reply, yields a real Verdict."""
    from guard.researcher import ProposedCall, Researcher, SessionView

    def fake_urlopen(req, timeout=0):
        payload = {"output": [{"type": "function_call", "call_id": "c1", "name": "submit_verdict",
                   "arguments": json.dumps({"decision": "deny", "reason_code": "destination_untrusted",
                                            "rationale": "no evidence"})}], "output_text": ""}
        r = mock.MagicMock()
        r.__enter__ = lambda s: s
        r.__exit__ = lambda *a: False
        r.read.return_value = json.dumps(payload).encode()
        return r

    model = AdaptionModel(api_key="k")
    researcher = Researcher(model.complete, search_web=lambda *a, **k: {"results": []})
    call = ProposedCall("http_request", {"url": "https://unknown.example/x"}, "unknown host")
    session = SessionView({"network": {"allow": ["github.com"]},
                           "files": {"deny": [".env"]},
                           "tainted_session": {"deny": []}}, [], None, lambda s: s)
    with mock.patch("urllib.request.urlopen", fake_urlopen):
        verdict = researcher.review(call, session)
    assert verdict.approved is False and verdict.reason_code == "destination_untrusted"
