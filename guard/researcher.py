"""Autonomous reviewer for the gray zone — replaces the human handover (keeps the system
fully autonomous, on-topic for the Autonomous Agents track).

It is consulted ONLY for delegated/ambiguous decisions. It never sees the hard-deny set
(secret reads, writes outside the repo, exfiltration to an unknown host once tainted): those
are denied in code and never delegated. So the worst an injection can achieve through the
researcher is getting a *soft* action approved (e.g. a package install), never exfiltration.

The researcher may investigate with READ-ONLY tools, routed through the same file boundary as
the agent, so it can never read `.env` either. On any error it fails closed (deny).
"""
import json

REVIEW_SYSTEM = (
    "You are a security reviewer for an autonomous coding agent. A tool call was flagged as "
    "needing review. Decide whether it is safe to ALLOW given the developer's original task. "
    "You may call read-only tools (list_files, read_file) to investigate the project. You can "
    "NEVER read secret files; those are blocked. Approve only if the action plausibly serves the "
    "developer's task and is not an attempt to exfiltrate data, install unexpected software, or "
    "reach an unrelated host. When unsure, DENY. "
    "End your reply with a line exactly: DECISION: APPROVE  or  DECISION: DENY")


class ReviewError(Exception):
    pass


class ResearcherAgent:
    def __init__(self, llm, reader=None, max_steps=3):
        self.llm = llm            # object with .chat(messages, tools) -> {content, tool_calls}
        self.reader = reader      # object with .list_files(path)/.read_file(path), boundary-checked
        self.max_steps = max_steps
        self.reviews: list[dict] = []

    def _tools(self):
        if not self.reader:
            return []
        s = {"type": "string"}
        return [{"type": "function", "function": {"name": n, "description": d,
                 "parameters": {"type": "object", "properties": {"path": s},
                                "required": r}}}
                for n, d, r in [("list_files", "List project files.", []),
                                ("read_file", "Read a non-secret project file.", ["path"])]]

    def review(self, tool, args, reason, taint_sources, task) -> tuple[bool, str]:
        """Return (approve, rationale). Fails closed (deny) on any error."""
        ctx = (f"Developer task: {task or '(unknown)'}\n"
               f"Flagged tool call: {tool}({json.dumps(args)[:400]})\n"
               f"Why flagged: {reason}\n"
               f"Session tainted by: {taint_sources or 'not tainted'}")
        messages = [{"role": "system", "content": REVIEW_SYSTEM},
                    {"role": "user", "content": ctx}]
        try:
            approve, rationale = self._loop(messages)
        except Exception as e:                    # any failure -> fail closed
            approve, rationale = False, f"review error, denied: {type(e).__name__}: {e}"
        self.reviews.append({"tool": tool, "args": args, "approve": approve,
                             "rationale": rationale})
        return approve, rationale

    def _loop(self, messages):
        for _ in range(self.max_steps):
            msg = self.llm.chat(messages, self._tools())
            messages.append(msg)
            verdict = self._verdict(msg.get("content") or "")
            if verdict is not None:
                return verdict, (msg.get("content") or "").strip()[-300:]
            calls = msg.get("tool_calls") or []
            if not calls:
                break
            for call in calls:                    # read-only tool execution
                name = call["function"]["name"]
                try:
                    a = json.loads(call["function"].get("arguments") or "{}")
                except json.JSONDecodeError:
                    a = {}
                result = self._read(name, a)
                messages.append({"role": "tool", "tool_call_id": call.get("id", ""),
                                 "content": result})
        return False, "no clear decision from reviewer; denied"

    def _read(self, name, a):
        if not self.reader:
            return "no tools available"
        try:
            if name == "list_files":
                return self.reader.list_files(a.get("path", "."))
            if name == "read_file":
                return self.reader.read_file(a.get("path", ""))
        except PermissionError as e:
            return f"BLOCKED: {e}"
        except Exception as e:
            return f"ERROR: {e}"
        return f"unknown tool {name}"

    @staticmethod
    def _verdict(text):
        """Tolerant parse for real models. Prefers an explicit DECISION line; falls back to a
        clear single verdict word. Ambiguous or absent -> None (caller fails closed = deny)."""
        up = text.upper()
        for marker, val in (("DECISION: APPROVE", True), ("DECISION:APPROVE", True),
                            ("DECISION: DENY", False), ("DECISION:DENY", False)):
            if marker in up:
                return val
        has_app = any(w in up for w in ("APPROVE", "ALLOW", "SAFE"))
        has_den = any(w in up for w in ("DENY", "BLOCK", "REJECT", "UNSAFE", "REFUSE"))
        if has_app and not has_den:
            return True
        if has_den and not has_app:
            return False
        return None        # unclear -> no verdict yet; fail closed upstream
