import pytest


@pytest.fixture(autouse=True)
def no_real_detector(monkeypatch):
    # Tests never call the external detector API.
    monkeypatch.delenv("ADAPTION_API_KEY", raising=False)
