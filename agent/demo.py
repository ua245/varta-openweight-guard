"""Pretty live view for the demo. Runs an attack with and without the guard, side by side in
time, and renders each decision with colour, a taint banner, researcher verdicts, and a final
panel. Robust for stage use: can run live or replay a saved run.

    python3 -m agent.demo --scenario v3                 # live, two phases, pause between
    python3 -m agent.demo --scenario remote_strong --researcher-model gemma4:e2b
    python3 -m agent.demo --replay eval/results/<file>.json
"""
import argparse
import json
import os
import time
from pathlib import Path

from .llm import OpenAICompatLLM
from .run import default_base_url, load_dotenv

C = {"grey": "\033[90m", "red": "\033[91m", "green": "\033[92m", "yellow": "\033[93m",
     "blue": "\033[94m", "magenta": "\033[95m", "cyan": "\033[96m", "bold": "\033[1m",
     "dim": "\033[2m", "reset": "\033[0m", "bg_red": "\033[41m\033[97m",
     "bg_green": "\033[42m\033[30m", "bg_magenta": "\033[45m\033[97m"}
TRUSTED = {"read_file", "write_file", "list_files", "run_tests", "shell"}
W = 72


def c(s, *names):
    if os.environ.get("NO_COLOR"):
        return s
    return "".join(C[n] for n in names) + s + C["reset"]


def rule(ch="─"):
    return c(ch * W, "grey")


def banner(text, style):
    pad = (W - len(text) - 2) // 2
    line = " " * pad + text + " " * (W - len(text) - pad - 2)
    print("\n" + c(" " + line + " ", style) + "\n")


def tool_label(tool, args):
    key = next((k for k in ("url", "path", "cmd", "number") if k in args), None)
    detail = str(args.get(key, ""))[:46] if key else ""
    return f"{c(tool, 'bold')}{c('(' + detail + ')', 'grey') if detail else ''}"


def render(result, pace=0.6):
    guard = result["guard"]
    head = "GUARD ON" if guard else "NO GUARD"
    print(rule("━"))
    print(c(f"  {head}", "bold", "cyan" if guard else "yellow") +
          c(f"   model={result.get('model', '?')}   task: fix issue #42", "grey"))
    print(rule("━"))
    tainted = False
    reviews = {id(r): r for r in result.get("reviews", [])}
    rev_iter = iter(result.get("reviews", []))
    for e in result["events"]:
        time.sleep(pace)
        act, tool, args = e["action"], e["tool"], e["args"]
        if act == "allow" or act == "run":
            icon, col = "✓", "green"
        elif act == "BLOCK":
            icon, col = "✗", "red"
        else:
            icon, col = "•", "grey"
        tag = {"allow": "ALLOW", "run": "RUN", "BLOCK": "BLOCK"}.get(act, act.upper())
        print(f"  {c(icon, col)} {c(tag.ljust(6), col, 'bold')} {tool_label(tool, args)}")
        res = str(e.get("result", ""))
        if act == "BLOCK":
            reason = res.replace("BLOCKED:", "").strip()
            print(f"      {c('→ ' + reason[:W - 8], 'red')}")
        elif "WARNING" in res:
            print(f"      {c('→ detector: flagged as prompt injection', 'magenta')}")
        # taint banner the first time an untrusted source is read
        if not tainted and act in ("allow", "run") and tool not in TRUSTED:
            tainted = True
            time.sleep(pace)
            banner("⚠  SESSION TAINTED — untrusted content read, rules tightened", "bg_magenta")
        # researcher verdict, if one happened on this step's tool
        for rev in list(rev_iter):
            v = "APPROVED" if rev["approve"] else "DENIED"
            col = "green" if rev["approve"] else "red"
            print(f"      {c('🔎 researcher ' + v, col, 'bold')}: {c(rev['rationale'][:W - 24], 'grey')}")
            break
    time.sleep(pace)
    print(rule())
    leaked = result["leaked"] or result.get("secret_seen_by_model")
    if not guard:
        if leaked:
            banner("💀  ATTACK SUCCEEDED — secret left the trust boundary", "bg_red")
        else:
            print(c("  model did not take the bait this run", "yellow"))
    else:
        if result["leaked"] or result.get("secret_seen_by_model"):
            banner("✗  attack reached a secret despite the guard", "bg_red")
        else:
            banner("🛡  ATTACK BLOCKED — no secret read, no secret sent", "bg_green")
    done = result.get("task_done")
    dtxt = {True: c("fixed ✓", "green"), False: c("not fixed", "yellow"),
            None: c("n/a", "grey")}[done]
    print(f"  bug: {dtxt}    "
          f"secret→attacker: {c('YES', 'red') if result['leaked'] else c('no', 'green')}    "
          f"secret seen by model: {c('YES', 'red') if result.get('secret_seen_by_model') else c('no', 'green')}")
    if result.get("taint_sources"):
        print(c(f"  tainted by: {result['taint_sources'][0]}", "grey"))
    print(rule("━") + "\n")


def run_phase(args, guard_on):
    from .scenario import TASK_REMOTE, run_scenario
    from eval.run_attacks import SCENARIOS
    sc = {k: v for k, v in SCENARIOS[args.scenario].items()
          if k not in ("kind", "label", "no_task_check")}
    sc.pop("attachments", None)
    from .run import build_researcher_llm
    llm = OpenAICompatLLM(args.base_url, args.model, api_key=args.api_key)
    res_llm = build_researcher_llm(args.researcher_model, args.base_url, args.api_key) if guard_on else None
    print(c(f"\n  running {'WITH guard' if guard_on else 'WITHOUT guard'}… "
            f"(model is thinking)", "dim"))
    r = run_scenario(llm, use_guard=guard_on, shell=args.shell, max_steps=args.max_steps,
                     log=lambda *_: None, researcher_llm=res_llm, **sc)
    r["model"] = args.model
    return r


def main():
    load_dotenv()
    if "--replay" not in " ".join(os.sys.argv):
        os.environ.pop("ADAPTION_API_KEY", None)        # keep the live demo fast
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default="v3")
    ap.add_argument("--base-url", default=default_base_url())
    ap.add_argument("--model", default=os.environ.get("AGENT_MODEL", "gemma4:e2b"))
    ap.add_argument("--api-key", default=os.environ.get("AGENT_API_KEY", "none"))
    ap.add_argument("--researcher-model", default=None)
    ap.add_argument("--shell", choices=["docker", "local"], default="local")
    ap.add_argument("--max-steps", type=int, default=12)
    ap.add_argument("--pace", type=float, default=0.6, help="seconds between lines")
    ap.add_argument("--replay", default=None, help="render a saved result JSON instead of running")
    ap.add_argument("--no-pause", action="store_true")
    a = ap.parse_args()

    if a.replay:
        render(json.loads(Path(a.replay).read_text()), pace=a.pace)
        return

    print(c("\n  PHASE 1 — open-weight agent, no protection", "bold", "yellow"))
    r1 = run_phase(a, guard_on=False)
    render(r1, pace=a.pace)
    out = Path("eval/results"); out.mkdir(parents=True, exist_ok=True)
    (out / "demo-phase1.json").write_text(json.dumps(r1, default=str))
    if not a.no_pause:
        input(c("  [enter] to run the SAME attack with the guard ▸ ", "cyan"))
    print(c("\n  PHASE 2 — same attack, same model, guard on", "bold", "cyan"))
    r2 = run_phase(a, guard_on=True)
    render(r2, pace=a.pace)
    (out / "demo-phase2.json").write_text(json.dumps(r2, default=str))


if __name__ == "__main__":
    main()
