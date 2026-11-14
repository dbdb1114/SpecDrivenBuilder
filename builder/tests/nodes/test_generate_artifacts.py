import pytest

from specbuilder.common_skills import load_common_skills
from specbuilder.llm import LLMCallError
from specbuilder.nodes.generate_artifacts import make_generate_artifacts
from specbuilder.registry.refs import render_content
from specbuilder.state import initial_state
from tests.conftest import SAVED_PROFILE
from tests.fakes.fake_llm import FOLDER_AGENTS, FakeLLM, files_reply, item, skill

COMMON = "verify-before-report"
BUILD = {**skill(), "when": '가계부를 만들 때 쓴다: "처음부터" 만들 때'}


def state_with(*skills: dict):
    state = initial_state("가계부")
    state["skills"] = list(skills)
    return state


def tech_item(id: str, parts: list[str]) -> dict:
    content = render_content("고른 것", [], "이유", parts)
    return item(id, "delegated", content, decided_by="worker", area="tech")


def state_with_parts(*parts: list[str]):
    state = state_with(BUILD)
    state["spec_items"] = [
        item("purpose", content="혼자 씀"),
        *(tech_item(f"tech-{i}", p) for i, p in enumerate(parts)),
    ]
    return state


def test_returns_only_artifacts_key_with_fixed_claude_md():
    result = make_generate_artifacts(FakeLLM())(state_with(BUILD))

    assert list(result) == ["artifacts"]
    assert set(result["artifacts"]) == {
        "docs/spec.md",
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
    llm = FakeLLM({"generate_artifacts": ["=== FILE: docs/spec.md ===\n스펙만 있음"]})
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


def test_folders_follow_tech_item_parts():
    state = state_with_parts([], ["frontend"], ["database", "frontend"])
    artifacts = make_generate_artifacts(FakeLLM())(state)["artifacts"]

    assert {name for name in artifacts if "/" in name and "skills" not in name} == {
        "docs/spec.md",
        "frontend/AGENTS.md",
        "frontend/CLAUDE.md",
        "database/AGENTS.md",
        "database/CLAUDE.md",
    }
    assert artifacts["frontend/CLAUDE.md"] == "@AGENTS.md\n"
    assert artifacts["database/AGENTS.md"] == FOLDER_AGENTS


def test_context_lists_folders_with_their_tech_and_folders_left_out():
    state = state_with_parts([], ["frontend"])
    llm = FakeLLM()
    make_generate_artifacts(llm)(state)
    block = llm.calls_for("generate_artifacts")[0].split("## 산출물 폴더\n")[1]

    assert block.splitlines()[:2] == [
        "- `frontend/` (화면) — 이 폴더의 기술: tech-1 항목, tech-0 항목(여러 부분 공통)",
        "- 만들지 않는 폴더: `backend/`, `database/`",
    ]


def test_script_only_program_gets_root_docs_only():
    state = state_with_parts([], [])
    llm = FakeLLM()
    artifacts = make_generate_artifacts(llm)(state)["artifacts"]

    assert not [
        n for n in artifacts if n.split("/")[0] in ("frontend", "backend", "database")
    ]
    assert "## 산출물 폴더\n(없음" in llm.calls_for("generate_artifacts")[0]


def test_missing_folder_agents_raises():
    llm = FakeLLM(
        {
            "generate_artifacts": [
                files_reply().replace(
                    "=== FILE: backend/AGENTS.md", "=== FILE: x/AGENTS.md"
                )
            ]
        }
    )
    with pytest.raises(LLMCallError, match="backend/AGENTS.md"):
        make_generate_artifacts(llm)(state_with_parts(["backend"]))


def test_folder_agents_without_fixed_section_raises():
    llm = FakeLLM(
        {
            "generate_artifacts": [
                files_reply(
                    **{
                        "frontend/AGENTS.md": "## 구조\n\n## 명령어 (설치)\n\n## 코드 규칙\n"
                    }
                )
            ]
        }
    )
    with pytest.raises(LLMCallError, match="하지 말 것"):
        make_generate_artifacts(llm)(state_with_parts(["frontend"]))


@pytest.mark.parametrize(
    ("agents", "error"),
    [
        ("# AGENTS\n\n## 용어사전\n\ndocs/ frontend/\n", "구조' 섹션이 없음"),
        ("# AGENTS\n\n## 구조\n\ndocs/\n\n## 질문 규칙\n\nfrontend/\n", "frontend/"),
    ],
)
def test_root_structure_must_show_every_folder(agents, error):
    llm = FakeLLM({"generate_artifacts": [files_reply(**{"AGENTS.md": agents})]})
    with pytest.raises(LLMCallError, match=error):
        make_generate_artifacts(llm)(state_with_parts(["frontend"]))
