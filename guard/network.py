from urllib.parse import urlparse
from .decision import Decision, allow, deny


class NetworkBoundary:
    def __init__(self, policy):
        self.allow_hosts = set(policy["network"]["allow"])
        self.unknown = policy["network"].get("unknown", "ask")

    @staticmethod
    def host(args) -> str:
        return (urlparse(args.get("url", "")).hostname or "").lower()

    def host_allowed(self, host: str) -> bool:
        return any(host == h or host.endswith("." + h) for h in self.allow_hosts)

    def check(self, args):
        """Stage 1 (policy)."""
        host = self.host(args)
        if self.host_allowed(host) or self.unknown == "allow":
            return allow(args)
        if self.unknown == "ask":
            return Decision("ask", f"host '{host}' is not on the allowlist")
        return deny(f"host '{host}' is not on the allowlist")

    def sensitive(self, args):
        """Stage 2: which sensitive action this is, if any."""
        return None if self.host_allowed(self.host(args)) else "network_unknown"
