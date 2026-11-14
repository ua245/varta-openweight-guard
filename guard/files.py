import fnmatch
import os
from pathlib import Path
from .decision import allow, deny


class FileBoundary:
    def __init__(self, policy, project_root):
        self.root = Path(os.path.realpath(project_root))
        self.deny = policy["files"]["deny"]
        self.write_root = Path(os.path.realpath(self.root / policy["files"].get("write_only_in", "./")))

    def resolve(self, path: str) -> Path:
        p = Path(os.path.expanduser(path))
        if not p.is_absolute():
            p = self.root / p
        return Path(os.path.realpath(p))   # follows symlinks, collapses ../

    def _denied(self, real: Path):
        for pat in self.deny:
            if pat.startswith("~"):
                base = Path(os.path.realpath(os.path.expanduser(pat)))
                if real == base or base in real.parents:
                    return pat
            elif any(fnmatch.fnmatch(part, pat) for part in real.parts):
                return pat
        return None

    def check(self, tool, args):
        real = self.resolve(args.get("path", ""))
        if pat := self._denied(real):
            return deny(f"{args.get('path')} resolves to {real}, which matches protected pattern '{pat}'")
        if tool == "write_file" and not (real == self.write_root or self.write_root in real.parents):
            return deny(f"writes are only allowed inside {self.write_root}; {real} is outside")
        if tool == "read_file" and not (real == self.root or self.root in real.parents):
            return Decision_external(real)
        return allow(args)


def Decision_external(real):
    # Reading outside the project is allowed but counts as untrusted (read_external_file).
    d = allow()
    d.reason = f"external file {real}"
    d.external = True
    return d
