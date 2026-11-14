"""CLI: python3 -m agent.run --model gemma4:e2b [--no-guard]"""
import argparse
import os
import subprocess

from .llm import OpenAICompatLLM
from .scenario import run_scenario


def default_base_url():
    if url := os.environ.get("AGENT_BASE_URL"):
        return url
    try:  # WSL: Ollama runs on the Windows host
        gw = subprocess.run(["ip", "route", "show", "default"], capture_output=True,
                            text=True).stdout.split()[2]
        return f"http://{gw}:11434/v1"
    except Exception:
        return "http://localhost:11434/v1"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=default_base_url())
    ap.add_argument("--model", default="gemma4:e2b")
    ap.add_argument("--no-guard", action="store_true")
    ap.add_argument("--issue", default="poisoned_issue.md", help="file in attacks/")
    ap.add_argument("--repo-injection", action="store_true",
                    help="poison bank/interest.py itself (attacks/repo_injection/)")
    ap.add_argument("--task", default=None, help="override the developer task")
    ap.add_argument("--attach", nargs="*", default=[],
                    help="files copied into the workspace under assets/ (e.g. untrusted images)")
    ap.add_argument("--max-steps", type=int, default=20)
    a = ap.parse_args()

    print(f"model={a.model} url={a.base_url} guard={'OFF' if a.no_guard else 'ON'}\n")
    r = run_scenario(OpenAICompatLLM(a.base_url, a.model), use_guard=not a.no_guard,
                     issue_file=a.issue, max_steps=a.max_steps,
                     repo_injection=a.repo_injection, attachments=a.attach,
                     **({"task": a.task} if a.task else {}))
    print("\n=== result ===")
    print(f"secret leaked to attacker : {'YES' if r['leaked'] else 'no'} "
          f"({r['attacker_requests']} request(s) received)")
    print(f"secret seen by the model  : {'YES' if r['secret_seen_by_model'] else 'no'}")
    print(f"secret in final answer    : {'YES' if r['secret_in_final_answer'] else 'no'}")
    print(f"task done (tests pass)    : {'yes' if r['task_done'] else 'NO'}")
    print(f"blocked calls             : {sum(e['action'] == 'BLOCK' for e in r['events'])}")
    print(f"handover to human         : {r['handover']}")
    if r["taint_sources"]:
        print(f"session tainted by        : {r['taint_sources'][0]}")
    print(f"workspace                 : {r['workspace']}")


if __name__ == "__main__":
    main()
