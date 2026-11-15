class Taint:
    """Session taint. Set once untrusted content is read; never resets."""

    def __init__(self, untrusted_sources):
        self.untrusted = set(untrusted_sources)
        self.sources: list[str] = []

    @property
    def tainted(self) -> bool:
        return bool(self.sources)

    def observe(self, tool: str, args: dict):
        if tool in self.untrusted:
            self.sources.append(f"{tool}({_short(args)})")


def _short(args):
    keys = ("url", "path", "repo", "number", "issue", "query", "claim", "cmd")
    s = ", ".join(f"{k}={v}" for k, v in args.items() if k in keys)
    return s[:120]
