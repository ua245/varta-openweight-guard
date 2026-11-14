from pathlib import Path
import yaml

DEFAULT_POLICY = Path(__file__).with_name("policy.yaml")


def load_policy(path=None) -> dict:
    with open(path or DEFAULT_POLICY) as f:
        return yaml.safe_load(f)
