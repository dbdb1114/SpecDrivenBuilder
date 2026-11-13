import pytest

from specbuilder.llm import LLMCallError
from specbuilder.nodes.generate_artifacts import make_generate_artifacts
from specbuilder.state import initial_state
from tests.fakes.fake_llm import FakeLLM, files_reply, item


def test_returns_only_artifacts_key_with_fixed_claude_md():
    result = make_generate_artifacts(FakeLLM({"generate_artifacts": [files_reply()]}))(
        initial_state("가계부")
    )

    assert list(result) == ["artifacts"]
    assert set(result["artifacts"]) == {"spec.md", "SKILL.md", "AGENTS.md", "CLAUDE.md"}
    assert result["artifacts"]["CLAUDE.md"] == "@AGENTS.md\n"
    assert result["artifacts"]["SKILL.md"].startswith("---\nname: build-ledger")


def test_splits_user_decisions_from_worker_decisions():
    state = initial_state("가계부")
    state["spec_items"] = [
        item("purpose", content="혼자 씀"),
        item("share", "delegated", ""),
        item("storage", "delegated", "파일 하나에 저장", decided_by="worker"),
    ]
    llm = FakeLLM()
    make_generate_artifacts(llm)(state)
    prompt = llm.calls_for("generate_artifacts")[0]
    user_part, worker_part = prompt.split("## 작업자가 정하는 것")

    assert "혼자 씀" in user_part and "share" not in user_part
    assert "파일 하나에 저장" in worker_part
    assert "기본 방향 없음" in worker_part


def test_missing_file_raises():
    llm = FakeLLM({"generate_artifacts": ["=== FILE: spec.md ===\n스펙만 있음"]})
    with pytest.raises(LLMCallError, match="SKILL.md"):
        make_generate_artifacts(llm)(initial_state("가계부"))
