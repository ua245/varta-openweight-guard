"""Evidence must come from actual agent CLI/fixture effects, not a model verdict."""
import json
import sys

from agent import run
from agent.scenario import FAKE_SECRET, run_scenario
from tests.test_agent_loop import HijackedLLM


def test_capture_records_prove_the_synthetic_transfer():
    result = run_scenario(HijackedLLM(), use_guard=False, shell='local', log=lambda *_: None)
    assert result['leaked']
    assert any(FAKE_SECRET in record['body'] for record in result['attacker_received'])


def test_cli_json_output_contains_same_measured_result(tmp_path, monkeypatch):
    expected = {'leaked': True, 'attacker_requests': 1, 'secret_seen_by_model': True,
                'secret_in_final_answer': False, 'task_done': True, 'events': [],
                'handover': False, 'taint_sources': [], 'workspace': '/tmp/synthetic',
                'audit_log': None, 'attacker_received': [{'body': 'SYNTHETIC_ONLY'}]}
    monkeypatch.setattr(run, 'run_scenario', lambda *args, **kwargs: expected)
    path = tmp_path / 'evidence/result.json'
    monkeypatch.setattr(sys, 'argv', ['agent.run', '--base-url', 'http://127.0.0.1:8080/v1',
                                     '--model', 'gpt-oss-20b', '--no-guard', '--json-output', str(path)])
    run.main()
    assert json.loads(path.read_text()) == expected
