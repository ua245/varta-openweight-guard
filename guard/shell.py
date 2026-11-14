"""Fast first-layer text filter. Not a security boundary on its own: the shell runs in Docker."""
import re
from .decision import allow, deny

SENSITIVE = {
    "git_push": re.compile(r"\bgit\b.*\bpush\b"),
    "install_package": re.compile(
        r"\b(pip3?|uv|poetry|npm|pnpm|yarn|apt(-get)?|brew|cargo|gem)\b.*\b(install|add|i)\b"),
    "network_unknown": re.compile(r"\b(curl|wget|nc|ncat|ssh|scp)\b|\bgit\b.*\b(clone|fetch|pull)\b"),
}
SECRET_FILES = re.compile(r"\.env\b|\.pem\b|\.ssh\b|id_rsa")


class ShellFilter:
    def check(self, args):
        """Stage 1 (policy)."""
        cmd = args.get("cmd", "")
        if SECRET_FILES.search(cmd):
            return deny(f"shell command references a protected file: {cmd!r}")
        return allow(args)

    def sensitive(self, args):
        """Stage 2: which sensitive action this is, if any."""
        cmd = args.get("cmd", "")
        return next((name for name, pat in SENSITIVE.items() if pat.search(cmd)), None)

    def fetches_external(self, args) -> bool:
        return SENSITIVE["network_unknown"].search(args.get("cmd", "")) is not None
