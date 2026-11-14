"""Single enforcement point. Every tool call goes through Guard.check(). Deterministic, no LLM.

Pipeline (see README diagram), for each tool call:
  1. Allowed by policy?            no  -> block, reason sent back to agent
  2. Tainted and sensitive action? yes -> block (or ask the human in interactive mode)
  3. Execute (caller), with real secrets injected at egress only
  4. Source in trusted list?       no  -> mark session tainted (never resets)
  5. Audit log; 3 denials in a row -> hand over to the human
"""
from .audit import AuditLog
from .decision import Decision, allow, deny
from .files import FileBoundary
from .network import NetworkBoundary
from .secrets import SecretStore
from .shell import ShellFilter
from .taint import Taint


class Guard:
    def __init__(self, policy, project_root=".", audit_path="audit.jsonl", ask_human=None):
        self.policy = policy
        self.mode = policy.get("mode", "autonomous")
        self.ask_human = ask_human            # callable(reason) -> bool, used in interactive mode
        self.taint = Taint(policy["trusted_sources"])
        self.tainted_deny = set(policy["tainted_session"]["deny"])
        self.files = FileBoundary(policy, project_root)
        self.network = NetworkBoundary(policy)
        self.shell = ShellFilter()
        self.secrets = SecretStore()
        self.audit = AuditLog(audit_path)
        self.max_denials = policy.get("handover_after_denials", 3)
        self.consecutive_denials = 0
        self.paused = False

    def check(self, tool: str, args: dict) -> Decision:
        if self.paused:
            d = deny("guard paused after repeated denials; waiting for human")
            d.handover = True
        else:
            d = self._policy(tool, args)                      # stage 1
            if d.action != "deny":
                d = self._tainted_sensitive(tool, args, d)    # stage 2
            d = self._resolve_ask(d)
            if d.action == "allow":
                d = self._inject_secrets(tool, args, d)
            self._count(d)
        if d.action == "allow" and not self._trusted_source(tool, args, d):
            self.taint.mark(tool, args)                       # stage 4 (content will be read)
        self.audit.write(tool, args, d, self.taint)
        return d

    def resume(self):
        """Called by the human after a handover."""
        self.paused = False
        self.consecutive_denials = 0

    # --- stage 1: policy -------------------------------------------------
    def _policy(self, tool, args):
        if tool in ("read_file", "write_file"):
            return self.files.check(tool, args)
        if tool == "view_image":
            return self.files.check("read_file", args)
        if tool == "list_files":
            return self.files.check("read_file", {"path": args.get("path") or "."})
        if tool == "shell":
            return self.shell.check(args)
        if tool == "http_request":
            return self.network.check(args)
        if tool == "run_tests" or tool in ("read_github_issue",):
            return allow(args)
        return deny(f"unknown tool '{tool}'")

    # --- stage 2: tainted and sensitive? -----------------------------------
    def _tainted_sensitive(self, tool, args, d):
        if not self.taint.tainted:
            return d
        kind = {"shell": self.shell.sensitive, "http_request": self.network.sensitive}.get(
            tool, lambda a: None)(args)
        if kind in self.tainted_deny:
            detail = d.reason or args.get("cmd") or args.get("url") or ""
            return deny(f"'{kind}' is not allowed in a session tainted by "
                        f"{self.taint.sources[0]} ({detail})")
        return d

    def _resolve_ask(self, d):
        if d.action != "ask":
            return d
        if self.mode == "interactive" and self.ask_human and self.ask_human(d.reason):
            return allow(d.args)
        return deny(d.reason + " (autonomous mode: unknown hosts are denied)")

    # --- stage 3: secrets at egress, allowlisted hosts only ------------------
    def _inject_secrets(self, tool, args, d):
        if not self.secrets.has_placeholder(args):
            return d
        if tool == "http_request" and self.network.host_allowed(self.network.host(args)):
            d.args = self.secrets.inject(args)
            return d
        return deny("secrets are only injected into requests to allowlisted hosts")

    # --- stage 4: trusted source? -------------------------------------------
    def _trusted_source(self, tool, args, d):
        if getattr(d, "external", False):        # read_file outside the project
            return False
        if tool == "shell" and self.shell.fetches_external(args):
            return False
        return self.taint.is_trusted(tool)

    def _count(self, d):
        if d.action == "deny":
            self.consecutive_denials += 1
            if self.consecutive_denials >= self.max_denials:
                self.paused = True
                d.handover = True
                d.reason += f" | {self.max_denials} denials in a row: handing over to the human"
        else:
            self.consecutive_denials = 0
