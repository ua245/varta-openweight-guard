from dataclasses import dataclass, field


@dataclass
class Decision:
    action: str                  # allow | deny | ask
    reason: str = ""
    args: dict = field(default_factory=dict)   # possibly rewritten args (secrets injected)
    handover: bool = False
    sensitive: bool = False      # tainted-and-sensitive: goes to the researcher when one is attached
    research: dict | None = None # researcher verdict + trace, for the audit log

    @property
    def allowed(self) -> bool:
        return self.action == "allow" and not self.handover


def allow(args=None):
    return Decision("allow", args=args or {})


def deny(reason):
    return Decision("deny", reason)


def deny_sensitive(reason):
    return Decision("deny", reason, sensitive=True)
