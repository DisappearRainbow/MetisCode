import shutil
import tempfile
from pathlib import Path

from metiscode.config.loader import (
    load_config_hierarchy,
    merge_config_concat_arrays,
    parse_config_text,
)
from metiscode.config.schema import ConfigInfo


def test_parse_jsonc_with_comments_and_trailing_commas() -> None:
    text = """
    {
      // comment
      "$schema": "https://opencode.ai/config.json",
      "model": "anthropic/claude-sonnet-4-5",
      "instructions": [
        "a",
        "b",
      ],
    }
    """
    parsed = parse_config_text(text, "memory")
    assert parsed.schema_url == "https://opencode.ai/config.json"
    assert parsed.model == "anthropic/claude-sonnet-4-5"
    assert parsed.instructions == ["a", "b"]


def test_merge_config_concat_arrays_deduplicates_in_order() -> None:
    target = ConfigInfo.model_validate({"instructions": ["a", "b"], "plugin": ["p1"]})
    source = ConfigInfo.model_validate({"instructions": ["b", "c"], "plugin": ["p1", "p2"]})
    merged = merge_config_concat_arrays(target, source)
    assert merged.instructions == ["a", "b", "c"]
    assert merged.plugin == ["p1", "p2"]


def test_load_config_hierarchy_precedence() -> None:
    tmp_dir = Path(tempfile.mkdtemp(prefix="metiscode-config-", dir=".tmp"))
    global_file = tmp_dir / "global.jsonc"
    project_file = tmp_dir / "project.jsonc"

    global_file.write_text(
        """
        {
          "model": "anthropic/claude-3-5-sonnet",
          "instructions": ["global-1"]
        }
        """,
        encoding="utf-8",
    )
    project_file.write_text(
        """
        {
          "model": "openai/gpt-4.1",
          "instructions": ["project-1"]
        }
        """,
        encoding="utf-8",
    )
    try:
        config = load_config_hierarchy(
            global_file=global_file,
            project_files=[project_file],
            env_content='{"model":"deepseek/deepseek-chat","instructions":["env-1"]}',
        )
        assert config.model == "deepseek/deepseek-chat"
        assert config.instructions == ["global-1", "project-1", "env-1"]
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
