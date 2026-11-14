"""Single enforcement point. Every tool call goes through Guard.check(). Deterministic, no LLM."""
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
        self.taint = Taint(policy["untrusted_sources"])
        self.files = FileBoundary(policy, project_root)
        self.network = NetworkBoundary(policy)
        self.shell = ShellFilter(policy)
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
            d = self._decide(tool, args)
            d = self._resolve_ask(d)
            self._count(d)
        if d.action == "allow":
            self.taint.observe(tool, args)    # taint after the call is permitted (content will be read)
            if getattr(d, "external", False):
                self.taint.sources.append(f"read_external_file(path={args.get('path')})")
        self.audit.write(tool, args, d, self.taint)
        return d

    def resume(self):
        """Called by the human after a handover."""
        self.paused = False
        self.consecutive_denials = 0

    def _decide(self, tool, args):
        if tool in ("read_file", "write_file"):
            return self.files.check(tool, args)
        if tool == "shell":
            return self.shell.check(args, self.taint)
        if tool == "http_request":
            d = self.network.check(args, self.taint)
            if d.action == "allow" and self.secrets.has_placeholder(args):
                d.args = self.secrets.inject(args)     # only reached for allowlisted hosts
            elif d.action != "allow" and self.secrets.has_placeholder(args):
                d = deny(d.reason + "; secrets are only injected for allowlisted hosts")
            return d
        if tool in self.taint.untrusted:
            return allow(args)                         # e.g. read_github_issue: allowed, taints
        return deny(f"unknown tool '{tool}'")

    def _resolve_ask(self, d):
        if d.action != "ask":
            return d
        if self.mode == "interactive" and self.ask_human and self.ask_human(d.reason):
            return allow(d.args)
        return deny(d.reason + " (autonomous mode: unknown hosts are denied)")

    def _count(self, d):
        if d.action == "deny":
            self.consecutive_denials += 1
            if self.consecutive_denials >= self.max_denials:
                self.paused = True
                d.handover = True
                d.reason += f" | {self.max_denials} denials in a row: handing over to the human"
        else:
            self.consecutive_denials = 0
