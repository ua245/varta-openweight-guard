"""VARTA ASCII loader scenarios expose LOADED context for coding LLMs."""
import os

from varta.banner import ASCII_LOGO, known_scenarios, render


def test_logo_matches_html_wordmark():
    assert "╭━━━╮" in ASCII_LOGO
    assert ASCII_LOGO.count("\n") >= 5


def test_each_scenario_lists_loaded_surface():
    for key in known_scenarios():
        block = render(key)
        assert "VARTA" in block
        assert "LOADED:" in block
        assert key.replace("-", "").lower() in block.lower() or key.upper().split("-")[0] in block


def test_quiet_env_skips_print(capsys):
    os.environ["VARTA_QUIET"] = "1"
    try:
        from varta.banner import print_banner

        print_banner("proxy")
        assert capsys.readouterr().out == ""
    finally:
        os.environ.pop("VARTA_QUIET", None)
