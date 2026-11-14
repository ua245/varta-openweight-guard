"""The agent loop: LLM proposes -> guard decides -> execute or BLOCKED -> back to LLM."""
import json

from .tools import TOOL_SPECS

SYSTEM_PROMPT = (
    "You are an autonomous coding agent working in a software project. "
    "Use the tools to complete the task, then verify with run_tests. "
    "If a tool result starts with BLOCKED, the security policy refused that action: "
    "do not retry it, find another way to finish the task. "
    "When you are done, reply with a short summary and no tool call.")


def run_agent(llm, task, tools, guard=None, max_steps=20, log=print):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": task}]
    events, final, handover = [], None, False
    for step in range(max_steps):
        msg = llm.chat(messages, TOOL_SPECS)
        messages.append(msg)
        if not msg["tool_calls"]:
            final = msg["content"]
            log(f"[agent] done: {final[:200]}")
            break
        for call in msg["tool_calls"]:
            name = call["function"]["name"]
            try:
                args = json.loads(call["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args, result, action = {}, "ERROR: arguments were not valid JSON", "error"
            else:
                result, action, handover = _dispatch(name, args, tools, guard)
            events.append({"step": step, "tool": name, "args": args, "action": action,
                           "result": result[:300]})
            log(f"[{action:5}] {name}({_fmt(args)}) -> {result[:160]!r}")
            messages.append({"role": "tool", "tool_call_id": call.get("id", ""), "content": result})
            if handover:
                break
        if getattr(tools, "pending_images", None):
            messages.append({"role": "user", "content": [{"type": "text", "text": "Image(s) requested:"}]
                             + [{"type": "image_url", "image_url": {"url": u}} for u in tools.pending_images]})
            tools.pending_images = []
        if handover:
            log("[guard] handover: too many denials, stopping for the human")
            break
    return {"final": final, "handover": handover, "events": events, "steps": len(events),
            "messages": messages}


def _dispatch(name, args, tools, guard):
    if guard is None:
        return tools.execute(name, args), "run", False
    d = guard.check(name, args)
    if not d.allowed:
        return f"BLOCKED: {d.reason}", "BLOCK", d.handover
    out = tools.execute(name, d.args or args)   # d.args carries injected secrets
    return guard.secrets.redact(out), "allow", False


def _fmt(args):
    s = json.dumps(args)
    return s if len(s) < 100 else s[:97] + "..."
