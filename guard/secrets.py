import re

PLACEHOLDER = re.compile(r"\{\{([A-Z0-9_]+)\}\}")


class SecretStore:
    """Agent only ever sees {{NAME}} placeholders; real values are swapped in at egress."""

    def __init__(self):
        self._secrets: dict[str, str] = {}

    def register(self, name, value):
        self._secrets[name] = value

    def has_placeholder(self, obj) -> bool:
        return bool(PLACEHOLDER.search(repr(obj)))

    def inject(self, obj):
        if isinstance(obj, str):
            return PLACEHOLDER.sub(lambda m: self._secrets.get(m.group(1), m.group(0)), obj)
        if isinstance(obj, dict):
            return {k: self.inject(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self.inject(v) for v in obj]
        return obj

    def redact(self, text: str) -> str:
        for name, value in self._secrets.items():
            text = text.replace(value, "{{" + name + "}}")
        return text
