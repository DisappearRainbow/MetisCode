from metiscode.tui.prompt import PromptInput


def test_prompt_submit_emits_content() -> None:
    prompt = PromptInput()
    event = prompt.submit("hello")
    assert event.content == "hello"


def test_prompt_history_up_returns_previous_entry() -> None:
    prompt = PromptInput()
    prompt.submit("first")
    prompt.submit("second")
    assert prompt.history_up() == "second"
    assert prompt.history_up() == "first"

