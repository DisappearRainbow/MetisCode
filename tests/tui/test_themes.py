from metiscode.tui.themes import load_theme


def test_load_theme_dark_returns_dark_background() -> None:
    theme = load_theme("dark")
    assert theme.name == "dark"
    assert theme.bg.startswith("#")

