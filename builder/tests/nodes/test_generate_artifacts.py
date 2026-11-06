import pytest

from specbuilder.llm import LLMCallError
from specbuilder.nodes.generate_artifacts import make_generate_artifacts
from specbuilder.state import initial_state
from tests.fakes.fake_llm import FakeLLM, files_reply


def test_returns_only_artifacts_key_with_fixed_claude_md():
    result = make_generate_artifacts(FakeLLM([files_reply()]))(initial_state("가계부"))

    assert list(result) == ["artifacts"]
    assert set(result["artifacts"]) == {"spec.md", "SKILL.md", "AGENTS.md", "CLAUDE.md"}
    assert result["artifacts"]["CLAUDE.md"] == "@AGENTS.md\n"
    assert result["artifacts"]["SKILL.md"].startswith("---\nname: build-ledger")


def test_missing_file_raises():
    reply = "=== FILE: spec.md ===\n스펙만 있음"
    with pytest.raises(LLMCallError, match="SKILL.md"):
        make_generate_artifacts(FakeLLM([reply]))(initial_state("가계부"))
