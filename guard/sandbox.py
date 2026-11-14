"""Docker sandbox for the agent's shell (CLAUDE.md principle 4).

Security comes from what a command can REACH, not from what it looks like:
  - only the project is mounted (/work); the host filesystem, ~/.ssh, other repos don't exist
  - protected files (.env, *.pem, ...) are masked with an empty /dev/null bind mount
  - no network at all (--network none); the only way out is http_request, through the guard
  - read-only root fs, non-root user, no capabilities, resource limits, per-command timeout
  - no host environment variables
"""
import fnmatch
import os
import subprocess
import uuid
from pathlib import Path

IMAGE = "agent-guard-sandbox:1"
DOCKERFILE_DIR = Path(__file__).resolve().parent.parent / "sandbox"
PROTECTED = [".env", ".env.*", "*.pem", "*.key", "id_rsa*"]
SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", "node_modules"}


class SandboxError(RuntimeError):
    pass


def docker_available() -> bool:
    try:
        return subprocess.run(["docker", "info"], capture_output=True, timeout=15).returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def ensure_image(image=IMAGE):
    if subprocess.run(["docker", "image", "inspect", image], capture_output=True).returncode == 0:
        return
    r = subprocess.run(["docker", "build", "-q", "-t", image, str(DOCKERFILE_DIR)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise SandboxError(f"could not build sandbox image: {r.stderr[-500:]}")


def protected_files(root: Path, patterns=PROTECTED):
    for d, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
        for f in files:
            if any(fnmatch.fnmatch(f, p) for p in patterns):
                yield Path(d, f).relative_to(root)


class DockerSandbox:
    def __init__(self, workspace, image=IMAGE, memory="1g", cpus="1", pids=256):
        self.ws = Path(workspace).resolve()
        self.image, self.memory, self.cpus, self.pids = image, memory, cpus, pids
        self.name = f"agent-sandbox-{uuid.uuid4().hex[:8]}"
        self.masked: list[str] = []

    def start(self):
        if not docker_available():
            raise SandboxError("docker is not available: refusing to run the shell unsandboxed")
        masks = []
        for rel in protected_files(self.ws):
            masks += ["-v", f"/dev/null:/work/{rel}:ro"]
            self.masked.append(str(rel))
        cmd = ["docker", "run", "-d", "--rm", "--name", self.name,
               "--network", "none",
               "--read-only", "--tmpfs", "/tmp:rw,size=64m",
               "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
               "--pids-limit", str(self.pids), "--memory", self.memory, "--cpus", self.cpus,
               "--user", f"{os.getuid()}:{os.getgid()}",
               "--env-file", "/dev/null",
               "-v", f"{self.ws}:/work:rw", *masks, "-w", "/work",
               self.image, "sleep", "infinity"]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            raise SandboxError(f"could not start sandbox: {r.stderr[-500:]}")
        return self

    def exec(self, cmd: str, timeout: int = 60):
        """Run `cmd` inside the sandbox. Returns (exit_code, combined output)."""
        r = subprocess.run(["docker", "exec", self.name, "timeout", "-s", "KILL", str(timeout),
                            "bash", "-c", cmd], capture_output=True, text=True, timeout=timeout + 15)
        out = r.stdout + r.stderr
        if r.returncode in (124, 137):
            out += f"\n[sandbox] command timed out after {timeout}s"
        return r.returncode, out

    def stop(self):
        subprocess.run(["docker", "rm", "-f", self.name], capture_output=True)

    def __enter__(self):
        return self.start()

    def __exit__(self, *a):
        self.stop()
