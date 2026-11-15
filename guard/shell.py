"""Fast first-layer text filter. Not a security boundary on its own: the shell runs in Docker."""
import re
from .decision import allow, deny, deny_sensitive

PATTERNS = {
    "git_push": re.compile(r"\bgit\b.*\bpush\b"),
    "install_package": re.compile(
        r"\b(pip3?|uv|poetry|npm|pnpm|yarn|apt(-get)?|brew|cargo|gem)\b.*\b(install|add|i)\b"),
    "network_unknown": re.compile(r"\b(curl|wget|nc|ncat|ssh|scp)\b"),
}
SECRET_FILES = re.compile(r"\.env\b|\.pem\b|\.ssh\b|id_rsa")


class ShellFilter:
    def __init__(self, policy):
        self.tainted_deny = set(policy["tainted_session"]["deny"])

    def check(self, args, taint):
        cmd = args.get("cmd", "")
        if SECRET_FILES.search(cmd):
            return deny(f"shell command references a protected file: {cmd!r}")
        if taint.tainted:
            for name, pat in PATTERNS.items():
                if name in self.tainted_deny and pat.search(cmd):
                    return deny_sensitive(
                        f"'{name}' is not allowed in a session tainted by {taint.sources[0]}")
        return allow(args)
