class Taint:
    """Session taint. Set once content from outside the trusted list is read; never resets."""

    def __init__(self, trusted_sources):
        self.trusted = set(trusted_sources)
        self.sources: list[str] = []

    @property
    def tainted(self) -> bool:
        return bool(self.sources)

    def is_trusted(self, tool: str) -> bool:
        return tool in self.trusted

    def mark(self, tool: str, args: dict):
        self.sources.append(f"{tool}({_short(args)})")


def _short(args):
    s = ", ".join(f"{k}={v}" for k, v in args.items() if k in ("url", "path", "repo", "number", "cmd"))
    return s[:120]
