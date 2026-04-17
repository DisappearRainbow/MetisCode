from metiscode.tui import MetiscodeApp


def test_app_instantiates() -> None:
    app = MetiscodeApp()
    assert app is not None


def test_app_compose_contains_message_list_prompt_and_footer() -> None:
    app = MetiscodeApp()
    layout = app.compose()
    assert "body" in layout
    assert "footer" in layout

