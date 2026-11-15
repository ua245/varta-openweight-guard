import argparse
import json
import os
import sys
from pathlib import Path

from agent.llm import OpenAICompatLLM
from .curate import generate
from .openai_client import available_models, load_env_file
from .study import CASES, load_cases, run_study


def main():
    parser = argparse.ArgumentParser(description='Source-backed VARTA lab comparison; read eval/redteam/README.md first')
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ['models', 'generate']:
        p = sub.add_parser(name)
        p.add_argument('--env-file', type=Path)
        if name == 'generate':
            p.add_argument('--model')
            p.add_argument('--case-ids', nargs='+', required=True)
            p.add_argument('--per-case', type=int, default=1, choices=range(1, 4))
            p.add_argument('--max-output-tokens', type=int, default=6000)
            p.add_argument('--output', type=Path, required=True)
    p = sub.add_parser('run')
    p.add_argument('--cases', type=Path, default=CASES)
    p.add_argument('--case-ids', nargs='+')
    p.add_argument('--base-url', required=True)
    p.add_argument('--model', required=True)
    p.add_argument('--repeats', type=int, default=1)
    p.add_argument('--seed', type=int, default=1729)
    p.add_argument('--temperature', type=float, default=0.2)
    p.add_argument('--max-steps', type=int, default=10)
    p.add_argument('--max-output-tokens', type=int, default=512)
    p.add_argument('--output', type=Path, required=True)
    p = sub.add_parser('validate')
    p.add_argument('--cases', type=Path, default=CASES)
    args = parser.parse_args()
    if getattr(args, 'env_file', None):
        load_env_file(args.env_file)
    if args.command == 'models':
        print('\n'.join(available_models()))
        return
    cases = load_cases(getattr(args, 'cases', CASES))
    if getattr(args, 'case_ids', None):
        ids = set(args.case_ids)
        unknown = ids - {c['id'] for c in cases}
        if unknown:
            parser.error('Unknown case IDs: ' + ', '.join(sorted(unknown)))
        cases = [c for c in cases if c['id'] in ids]
    if args.command == 'validate':
        from .study import ROOT
        refs = {s['id'] for s in json.loads((ROOT / 'research/sources.json').read_text())['sources']}
        missing = {s for c in cases for s in c['source_ids']} - refs
        if missing:
            parser.error('Missing sources: ' + ', '.join(sorted(missing)))
        print(f'{len(cases)} cases validated; all source references resolve; no API calls made.')
    elif args.command == 'generate':
        model = args.model or os.environ.get('OPENAI_MODEL')
        if not model:
            parser.error('Provide the exact --model ID or OPENAI_MODEL; use models to list available IDs')
        if any(c['kind'] != 'attack' for c in cases):
            parser.error('Generate from attack seeds; keep benign controls fixed')
        print(json.dumps(generate(cases, args.output, model, per_case=args.per_case,
                                 max_tokens=args.max_output_tokens, seed=pair_seed), indent=2))
    else:
        if not 1 <= args.repeats <= 100 or not 1 <= args.max_steps <= 30:
            parser.error('repeats must be 1–100; max-steps must be 1–30')
        from .target import TargetLLM
        factory = lambda pair_seed: TargetLLM(args.base_url, args.model, temperature=args.temperature,
                                   max_tokens=args.max_output_tokens, seed=pair_seed)
        result = run_study(factory, cases, args.output, repeats=args.repeats, seed=args.seed,
                           max_steps=args.max_steps, metadata={'target_model': args.model,
                           'base_url': args.base_url, 'temperature': args.temperature,
                           'max_output_tokens': args.max_output_tokens})
        print(json.dumps(result, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError) as exc:
        sys.exit(str(exc))
