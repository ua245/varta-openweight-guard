"""Human-readable report from paired observations; no LLM judge."""
import json
from pathlib import Path

from .study import summarize


def render(directory):
    directory = Path(directory)
    rows = [json.loads(line) for line in (directory / 'runs.jsonl').read_text().splitlines()]
    manifest = json.loads((directory / 'manifest.json').read_text())
    result = summarize(rows)
    pairs = result['paired']
    n = pairs['eligible_attack_pairs']
    ratio = lambda k, d: f'{k}/{d} ({100*k/d:.1f}%)' if d else 'not available'
    lines = ['# VARTA curated lab comparison', '',
        '**Bounded in-memory tool simulation, not a Docker containment test.**', '',
        f'Target: `{manifest["metadata"].get("target_model", "scripted validation")}`. '
        f'Repeats: {manifest["repeats"]}. Optional external detector: disabled.', '',
        '| Primary paired metric | Guard off | Guard on |', '|---|---|---|',
        f'| Simulated attack success (eligible exposed pairs) | {ratio(pairs["attack_success_off"], n)} | {ratio(pairs["attack_success_on"], n)} |',
        '', f'Eligible pairs: {pairs["eligible_pairs"]}/{pairs["scheduled_pairs"]}. Excluded: {pairs["excluded_pairs"]}.', '',
        '| Per-arm diagnostics | Guard off | Guard on |', '|---|---|---|']
    for field in ['runs','errors','unscorable','unexposed_attack_runs','benign_scorable','benign_task_completion_rate','benign_intervention_rate','median_seconds']:
        lines.append(f'| {field} | {result["guard_off"][field]} | {result["guard_on"][field]} |')
    lines += ['', '| Case | Guard | Attack effect | Task complete | Read payload | Blocks | Scorable | Error |',
              '|---|---|---|---|---|---|---|---|']
    for row in sorted(rows, key=lambda r: (r['case_id'], r['guard'], r.get('repeat', 0))):
        attack = row['attack_success'] if row['kind'] == 'attack' else 'n/a'
        lines.append(f'| {row["case_id"]} | {"ON" if row["guard"] else "off"} | {attack} | {row["task_complete"]} | {row["exposed"]} | {row["blocked_calls"]} | {row["scorable"]} | {row["error"] or ""} |')
    lines += ['', '## Interpretation limits', '',
        '- Counts describe only these fixed synthetic cases, executor and target settings.',
        '- A virtual sink records a simulated transfer; no outbound exfiltration occurs.',
        '- Arbitrary shell, images, MCP metadata, real network and cross-session memory are not tested.',
        '- Benign intervention is a convenience metric, not an adjudicated false-positive rate.',
        '- A small pilot or one repeat per case does not establish statistical robustness or a general model ranking.',
        '- Source mappings, generator provenance and case snapshots are separate from runtime observations.', '']
    (directory / 'report.md').write_text('\n'.join(lines))
    return result
