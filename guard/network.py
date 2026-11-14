from urllib.parse import urlparse
from .decision import Decision, allow, deny


class NetworkBoundary:
    def __init__(self, policy):
        self.allow_hosts = set(policy["network"]["allow"])
        self.unknown = policy["network"].get("unknown", "ask")
        self.tainted_deny = set(policy["tainted_session"]["deny"])

    def host_allowed(self, host: str) -> bool:
        return any(host == h or host.endswith("." + h) for h in self.allow_hosts)

    def check(self, args, taint):
        host = (urlparse(args.get("url", "")).hostname or "").lower()
        if self.host_allowed(host):
            return allow(args)
        if taint.tainted and "network_unknown" in self.tainted_deny:
            return deny(f"host '{host}' is not on the allowlist and the session is tainted by "
                        f"{taint.sources[0]}")
        if self.unknown == "allow":
            return allow(args)
        if self.unknown == "ask":
            return Decision("ask", f"host '{host}' is not on the allowlist")
        return deny(f"host '{host}' is not on the allowlist")
