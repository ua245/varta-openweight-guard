import json
import time


class AuditLog:
    def __init__(self, path):
        self.path = path

    def write(self, tool, args, decision, taint):
        if not self.path:
            return
        rec = {"ts": time.time(), "tool": tool, "args": args, "decision": decision.action,
               "reason": decision.reason, "tainted": taint.tainted, "taint_sources": taint.sources,
               "handover": decision.handover}
        if decision.research is not None:
            rec["research"] = decision.research
        with open(self.path, "a") as f:
            f.write(json.dumps(rec, default=str) + "\n")
