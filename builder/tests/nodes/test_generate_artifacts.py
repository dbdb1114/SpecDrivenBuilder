import pytest

from specbuilder.common_skills import load_common_skills
from specbuilder.llm import LLMCallError
from specbuilder.nodes.generate_artifacts import make_generate_artifacts
from specbuilder.state import initial_state
from tests.conftest import SAVED_PROFILE
from tests.fakes.fake_llm import FakeLLM, files_reply, item, skill

COMMON = "verify-before-report"
BUILD = {**skill(), "when": '가계부를 만들 때 쓴다: "처음부터" 만들 때'}


def state_with(*skills: dict):
    state = initial_state("가계부")
    state["skills"] = list(skills)
    return state


def test_returns_only_artifacts_key_with_fixed_claude_md():
    result = make_generate_artifacts(FakeLLM())(state_with(BUILD))

    assert list(result) == ["artifacts"]
    assert set(result["artifacts"]) == {
        "spec.md",
        "AGENTS.md",
        "CLAUDE.md",
        ".claude/skills/build-ledger/SKILL.md",
        ".agents/skills/build-ledger/SKILL.md",
    }
    assert result["artifacts"]["CLAUDE.md"] == "@AGENTS.md\n"


def test_new_skill_frontmatter_comes_from_skill_list_not_llm():
    llm = FakeLLM(
        {
            "generate_artifacts": [
                files_reply(
                    **{
                        "skills/build-ledger.md": "---\nname: wrong\ndescription: LLM 이 붙임\n---\n\n# 가계부 만들기\n\n1. 화면."
                    }
                )
            ]
        }
    )
    artifacts = make_generate_artifacts(llm)(state_with(BUILD))["artifacts"]
    content = artifacts[".claude/skills/build-ledger/SKILL.md"]

    assert content == (
        "---\n"
        "name: build-ledger\n"
        'description: "가계부를 만들 때 쓴다: \\"처음부터\\" 만들 때"\n'
        "---\n\n"
        "# 가계부 만들기\n\n1. 화면.\n"
    )
    assert artifacts[".agents/skills/build-ledger/SKILL.md"] == content


def test_common_skill_is_copied_verbatim_and_not_requested_from_llm():
    llm = FakeLLM()
    artifacts = make_generate_artifacts(llm)(
        state_with(BUILD, skill(COMMON, "common"))
    )["artifacts"]
    original = load_common_skills()[COMMON]["content"]

    assert artifacts[f".claude/skills/{COMMON}/SKILL.md"] == original
    assert artifacts[f".agents/skills/{COMMON}/SKILL.md"] == original
    prompt = llm.calls_for("generate_artifacts")[0]
    skill_part = prompt.split("## 스킬 목록")[1]
    assert f"`{COMMON}` (공통 스킬" in skill_part
    assert "`skills/build-ledger.md` 로 본문을 쓴다" in skill_part
    assert f".agents/skills/{COMMON}/SKILL.md" in skill_part


def test_splits_user_decisions_from_worker_decisions():
    state = state_with(BUILD)
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
    with pytest.raises(LLMCallError, match="AGENTS.md"):
        make_generate_artifacts(llm)(state_with(BUILD))


def test_missing_new_skill_body_raises():
    with pytest.raises(LLMCallError, match="skills/fix-rules.md"):
        make_generate_artifacts(FakeLLM())(state_with(BUILD, skill("fix-rules")))


def test_empty_skill_body_raises():
    llm = FakeLLM(
        {"generate_artifacts": [files_reply(**{"skills/build-ledger.md": " \n"})]}
    )
    with pytest.raises(LLMCallError, match="본문이 비어"):
        make_generate_artifacts(llm)(state_with(BUILD))


def test_context_has_profile_axes_for_worker_context():
    state = state_with(BUILD)
    state["profile"] = {**SAVED_PROFILE, "explanation": " "}
    llm = FakeLLM()
    make_generate_artifacts(llm)(state)

    prompt = llm.calls_for("generate_artifacts")[0]
    profile_block = prompt.split("## 사용자 프로필\n", 1)[1]
    assert profile_block.splitlines() == [
        "- 도메인 전문성: 사무·행정·회계",
        "- 기술 노출 정도: 셋 다 해 본 적 없어요",
        "- 설명 선호: (모름)",
        "- 환경: 운영체제: Mac / AI 도구·요금제: Claude Pro",
        "- 결정 위임 범위: 알아서 정하고 결과만 알려 주세요",
    ]


def test_context_without_profile_says_none():
    llm = FakeLLM()
    make_generate_artifacts(llm)(state_with(BUILD))
    assert llm.calls_for("generate_artifacts")[0].endswith("## 사용자 프로필\n(없음)")
