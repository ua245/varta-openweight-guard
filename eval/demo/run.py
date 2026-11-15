"""Run real agent.run CLI pairs in identical outer Docker sandboxes on the model VM."""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def build_image(image):
    with tempfile.TemporaryDirectory(prefix='varta-build-') as temp:
        context = Path(temp)
        for name in ['agent', 'guard', 'demo_repo', 'attacks']:
            shutil.copytree(ROOT / name, context / name,
                            ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache', '.venv', '.git'))
        shutil.copytree(ROOT / 'eval/demo', context / 'eval/demo', ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copyfile(ROOT / 'eval/demo/Dockerfile', context / 'Dockerfile')
        subprocess.run(['docker', 'build', '--pull=false', '-t', image, str(context)], check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--issues', nargs='+', default=['poisoned_issue_v3.md'])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--image', default='varta-real-demo:20261115')
    parser.add_argument('--skip-build', action='store_true')
    args = parser.parse_args()
    for issue in args.issues:
        p = (ROOT / 'attacks' / issue).resolve()
        if not p.is_relative_to(ROOT / 'attacks') or not p.is_file():
            parser.error('Issues must be existing files under attacks/')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    if not args.skip_build:
        build_image(args.image)
    image_id = subprocess.check_output(['docker', 'image', 'inspect', '--format', '{{.Id}}', args.image], text=True).strip()
    manifest = {'execution': 'real agent.run in outer Docker container; local capture server and real pytest',
        'image_id': image_id, 'guard_toggle': '--no-guard only; guard on is default',
        'network': 'none; Unix relay permits only local model API', 'shell': 'local inside outer container',
        'model': 'gpt-oss-20b', 'relay_settings': {'seed': 1729, 'max_tokens': 512, 'reasoning_effort': 'low'},
        'issues_sha256': {issue: hashlib.sha256((ROOT/'attacks'/issue).read_bytes()).hexdigest() for issue in args.issues}}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    shutil.copytree(ROOT / 'demo_repo', output / 'initial-fixture', ignore=shutil.ignore_patterns('__pycache__'))
    manifest['source_sha256'] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for folder in ['agent', 'guard', 'eval/demo'] for p in sorted((ROOT/folder).glob('*.py'))}
    manifest['policy_sha256'] = hashlib.sha256((ROOT/'guard/policy.yaml').read_bytes()).hexdigest()
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    rows = []
    with tempfile.TemporaryDirectory(prefix='varta-relay-') as relay_dir:
        sock = Path(relay_dir) / 'model.sock'
        relay = subprocess.Popen([sys.executable, '-m', 'eval.demo.relay', '--socket', str(sock)], cwd=ROOT)
        try:
            for _ in range(100):
                if sock.exists():
                    break
                if relay.poll() is not None:
                    raise RuntimeError('Model relay exited')
                time.sleep(0.05)
            else:
                raise RuntimeError('Model relay did not start')
            for index, issue in enumerate(args.issues):
                for guard_on in (False, True):
                    arm = output / f'{index:02d}-{Path(issue).stem}-guard-{int(guard_on)}'
                    arm.mkdir()
                    command = ['docker', 'run', '--rm', '--network', 'none', '--read-only',
                        '--user', f'{os.getuid()}:{os.getgid()}', '--cap-drop', 'ALL',
                        '--security-opt', 'no-new-privileges', '--pids-limit', '128',
                        '--memory', '2g', '--cpus', '2',
                        '--tmpfs', '/tmp:rw,nosuid,nodev,size=256m',
                        '--mount', f'type=bind,src={relay_dir},dst=/model-relay,readonly',
                        '--mount', f'type=bind,src={arm},dst=/evidence', image_id,
                        '--issue', issue]
                    if not guard_on:
                        command.append('--no-guard')
                    print(f'RUN {issue} guard={guard_on}', flush=True)
                    started = time.monotonic()
                    execution = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=1600)
                    (arm / 'docker.log').write_text(execution.stdout + execution.stderr)
                    row = {'issue': issue, 'guard': guard_on, 'exit_code': execution.returncode,
                           'seconds': round(time.monotonic() - started, 2), 'evidence_dir': arm.name}
                    if (arm / 'result.json').exists():
                        r = json.loads((arm / 'result.json').read_text())
                        verification = json.loads((arm / 'verification.json').read_text()) if (arm / 'verification.json').exists() else {}
                        row['scenario_task_done'] = r['task_done']
                        row['golden_tests_exit_code'] = verification.get('exit_code')
                        row.update(leaked=r['leaked'], task_done=verification.get('exit_code') == 0,
                                   secret_seen_by_model=r['secret_seen_by_model'],
                                   secret_in_final_answer=r['secret_in_final_answer'],
                                   blocked_calls=sum(e['action'] == 'BLOCK' for e in r['events']),
                                   capture_requests=r['attacker_requests'], handover=r['handover'])
                    rows.append(row)
                    (output / 'summary.json').write_text(json.dumps(rows, indent=2) + '\n')
                    print(json.dumps(row), flush=True)
        finally:
            relay.terminate()
            relay.wait(timeout=5)


if __name__ == '__main__':
    main()
