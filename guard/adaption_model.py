"""Adapter: drive the fine-tuned Adaption model (Responses API) as the researcher's brain.

The researcher (guard/researcher.py) speaks OpenAI chat-completions with function tools. The
Adaption fine-tuned model speaks the Responses API (`/api/v1/responses`, `input`/`output`).
This converts between them so `Researcher(AdaptionModel(...).complete)` just works.

Safety: only the function tools the researcher passes are enabled — the Adaption endpoint's
default MCP servers (GitHub write tools) are not. If the API ever returns a server-side tool
execution (`mcp_call`), the review is aborted (fail closed), so a hijacked reviewer still
cannot act.
"""
import json
import os
import urllib.error
import urllib.request

from .researcher import ResearcherError

ADAPTION_URL = "https://api.prod.adaptionlabs.ai/api/v1/responses"


def split_instructions(messages: list[dict]) -> str:
    """Responses API takes the system prompt as top-level `instructions`, not an input message."""
    return "\n\n".join(m.get("content") or "" for m in messages if m.get("role") == "system")


def to_responses_input(messages: list[dict]) -> list[dict]:
    """chat-completions messages -> Responses API input items (system handled separately)."""
    items: list[dict] = []
    for m in messages:
        role = m.get("role")
        if role == "user":
            items.append({"role": role, "content": m.get("content") or ""})
        elif role == "assistant":
            if m.get("content"):
                items.append({"role": "assistant", "content": m["content"]})
            for tc in m.get("tool_calls") or []:
                fn = tc.get("function") or {}
                items.append({"type": "function_call", "call_id": tc.get("id") or fn.get("name"),
                              "name": fn.get("name"), "arguments": fn.get("arguments") or "{}"})
        elif role == "tool":
            items.append({"type": "function_call_output", "call_id": m.get("tool_call_id") or "",
                          "output": m.get("content") or ""})
    return items


def to_responses_tools(tools: list[dict]) -> list[dict]:
    """chat-completions tool specs -> Responses API function tools (flattened)."""
    out = []
    for t in tools:
        fn = t.get("function") or {}
        out.append({"type": "function", "name": fn.get("name"),
                    "description": fn.get("description", ""),
                    "parameters": fn.get("parameters", {"type": "object", "properties": {}})})
    return out


def from_responses_output(body: dict) -> dict:
    """Responses API output -> a chat-completions assistant message {content, tool_calls}."""
    tool_calls, content = [], body.get("output_text") or ""
    for o in body.get("output", []):
        otype = o.get("type")
        if otype in ("mcp_call", "mcp_list_tools", "code_interpreter_call", "file_search_call"):
            # Server-side tool execution must never happen for the reviewer. Abort, fail closed.
            raise ResearcherError(f"reviewer model attempted a server-side '{otype}'; aborted")
        if otype == "function_call":
            tool_calls.append({"id": o.get("call_id") or o.get("id") or o.get("name"),
                               "type": "function",
                               "function": {"name": o.get("name"),
                                            "arguments": o.get("arguments") or "{}"}})
        elif otype == "message" and not content:
            parts = o.get("content") or []
            content = "".join(p.get("text", "") for p in parts if isinstance(p, dict))
    return {"role": "assistant", "content": content, "tool_calls": tool_calls}


class AdaptionModel:
    """OpenAI-chat-completions-shaped `.complete(messages, tools)` backed by Adaption Responses API."""

    def __init__(self, api_key=None, model="stack:uvx", url=ADAPTION_URL, timeout=120):
        self.api_key = api_key or os.environ.get("ADAPTION_API_KEY", "")
        self.model, self.url, self.timeout = model, url, timeout

    # name mirrors OpenAICompatLLM.chat so it is interchangeable as the researcher's `complete`
    def complete(self, messages: list[dict], tools: list[dict]) -> dict:
        body = {"model": self.model, "input": to_responses_input(messages),
                "tools": to_responses_tools(tools), "tool_choice": "auto", "store": False}
        instructions = split_instructions(messages)
        if instructions:
            body["instructions"] = instructions
        req = urllib.request.Request(
            self.url, data=json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                parsed = json.load(resp)
        except (urllib.error.URLError, TimeoutError) as e:
            raise ResearcherError(f"Adaption model unreachable: {e}") from None
        except json.JSONDecodeError as e:
            raise ResearcherError(f"Adaption model returned invalid JSON: {e}") from None
        return from_responses_output(parsed)

    chat = complete        # so it can also stand in where a .chat(messages, tools) is expected
