"""CLI: python3 -m agent.run --model gemma4:e2b [--no-guard]"""
import argparse
import os
import subprocess

from .llm import OpenAICompatLLM
from .scenario import TASK_REMOTE, run_scenario


def build_researcher_llm(name, base_url, api_key):
    """Researcher brain. 'adaption'/'stack:uvx' -> the fine-tuned Adaption model; else an
    OpenAI-compatible local model. Both expose .chat(messages, tools), so the researcher is
    model-agnostic. None -> no researcher (gray-zone calls are denied autonomously)."""
    if not name:
        return None
    if name in ("adaption", "stack:uvx", "fine-tuned"):
        from guard.adaption_model import AdaptionModel
        return AdaptionModel()        # reads ADAPTION_API_KEY from the environment
    return OpenAICompatLLM(base_url, name, api_key=api_key)


def _short_args(args):
    return ", ".join(f"{k}={str(v)[:40]}" for k, v in args.items() if k in ("cmd", "url", "path"))


def default_base_url():
    if url := os.environ.get("AGENT_BASE_URL"):
        return url
    try:  # WSL: Ollama runs on the Windows host
        gw = subprocess.run(["ip", "route", "show", "default"], capture_output=True,
                            text=True).stdout.split()[2]
        return f"http://{gw}:11434/v1"
    except Exception:
        return "http://localhost:11434/v1"


def load_dotenv(path=".env"):
    """Load KEY=VALUE lines from the repo's .env into this process only (not the agent's shell)."""
    try:
        for line in open(path):
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.strip().split("=", 1)
                os.environ.setdefault(k, v)
    except FileNotFoundError:
        pass


def main():
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=default_base_url())
    ap.add_argument("--model", default=os.environ.get("AGENT_MODEL", "gemma4:e2b"))
    ap.add_argument("--api-key", default=os.environ.get("AGENT_API_KEY", "none"),
                    help="bearer token for the model server, if it requires one")
    ap.add_argument("--no-guard", action="store_true")
    ap.add_argument("--issue", default="poisoned_issue.md", help="file in attacks/")
    ap.add_argument("--repo-injection", action="store_true",
                    help="poison bank/interest.py itself (attacks/repo_injection/)")
    ap.add_argument("--vision-model", default=None,
                    help="separate vision model used by view_image (e.g. qwen2.5vl:7b); "
                         "the agent model then receives a text description")
    ap.add_argument("--researcher-model", default=None,
                    help="model for the autonomous reviewer that adjudicates gray-zone calls "
                         "(e.g. the fine-tuned model); replaces the human handover")
    ap.add_argument("--remote-repo", nargs="?", const=True, default=False,
                    choices=[True, "weak", "strong"],
                    help="task points to a reference file on (fake) github.com that holds the "
                         "injection; pass 'strong' for the harder payload that frames exfil as a "
                         "required step (default: weak comment)")
    ap.add_argument("--task", default=None, help="override the developer task")
    ap.add_argument("--attach", nargs="*", default=[],
                    help="files copied into the workspace under assets/ (e.g. untrusted images)")
    ap.add_argument("--shell", choices=["docker", "local"], default="docker",
                    help="docker = sandboxed shell (default); local = host shell, for comparison")
    ap.add_argument("--max-steps", type=int, default=20)
    a = ap.parse_args()

    det = "ON (adaption)" if os.environ.get("ADAPTION_API_KEY") and not a.no_guard else "off"
    print(f"model={a.model} url={a.base_url} guard={'OFF' if a.no_guard else 'ON'} detector={det} shell={a.shell} vision={a.vision_model or 'agent model'}\n")
    r = run_scenario(OpenAICompatLLM(a.base_url, a.model, api_key=a.api_key), use_guard=not a.no_guard,
                     issue_file=a.issue, max_steps=a.max_steps,
                     repo_injection=a.repo_injection, attachments=a.attach, shell=a.shell,
                     remote_repo=("strong" if a.remote_repo == "strong" else bool(a.remote_repo)),
                     vision=OpenAICompatLLM(a.base_url, a.vision_model, api_key=a.api_key)
                     if a.vision_model else None,
                     researcher_llm=build_researcher_llm(a.researcher_model, a.base_url, a.api_key),
                     **({"task": a.task} if a.task else
                        {"task": TASK_REMOTE} if a.remote_repo else {}))
    print("\n=== result ===")
    print(f"secret leaked to attacker : {'YES' if r['leaked'] else 'no'} "
          f"({r['attacker_requests']} request(s) received)")
    print(f"secret seen by the model  : {'YES' if r['secret_seen_by_model'] else 'no'}")
    print(f"secret in final answer    : {'YES' if r['secret_in_final_answer'] else 'no'}")
    if a.task:   # custom task: the bank tests are not the success criterion
        print(f"task done                 : n/a (custom task, check the answer above)")
    else:
        print(f"task done (tests pass)    : {'yes' if r['task_done'] else 'NO'}")
    print(f"blocked calls             : {sum(e['action'] == 'BLOCK' for e in r['events'])}")
    print(f"handover to human         : {r['handover']}")
    for rev in r.get("reviews", []):
        print(f"researcher {'APPROVED' if rev['approve'] else 'DENIED  '}: "
              f"{rev['tool']}({_short_args(rev['args'])}) — {rev['rationale'][:90]}")
    if r.get("detector_flags"):
        print(f"detector flagged          : {', '.join(r['detector_flags'])}")
    if r["taint_sources"]:
        print(f"session tainted by        : {r['taint_sources'][0]}")
    print(f"workspace                 : {r['workspace']}")
    if r.get("audit_log"):
        print(f"audit log                 : {r['audit_log']}")


if __name__ == "__main__":
    main()
