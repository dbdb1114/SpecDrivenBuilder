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


def test_spec_decision_sections_are_written_by_builder_not_llm():
    """결정 두 절은 스펙 항목을 옮겨 적는 부분이다 — 코드가 그려서 출력 토큰을 줄이고 사용자의 답이 바뀌지 않게 한다."""
    state = state_with(BUILD)
    state["spec_items"] = [
        item("purpose", content="혼자 씀"),
        item("share", "delegated", ""),
        item("login", "delegated", ""),
        item("storage", "delegated", "파일 하나에 저장", decided_by="worker"),
        item(
            "tech-1",
            "delegated",
            "선택: Flask\n버전: (pypi: flask@3.1.0)",
            "worker",
            "tech",
        ),
    ]
    spec = (
        "# 스펙\n\n## 목적\n가계부.\n\n"
        "## 사용자가 정한 것\n- purpose 항목: LLM 이 바꿔 적음\n\n"
        "## 작업자가 정하는 것\n이 절의 항목은 사용자에게 다시 묻지 않고 기본 방향대로 정한다.\n\n"
        "- share 항목: 나누는 기능은 넣지 않는다.\n- 비밀번호 보관: 환경 변수에 둔다."
    )
    llm = FakeLLM({"generate_artifacts": [files_reply(**{"docs/spec.md": spec})]})

    result = make_generate_artifacts(llm)(state)["artifacts"]["docs/spec.md"]

    assert result == (
        "# 스펙\n\n## 목적\n가계부.\n\n"
        "## 사용자가 정한 것\n"
        "- purpose 항목: 혼자 씀\n\n"
        "## 작업자가 정하는 것\n"
        "이 절의 항목은 사용자에게 다시 묻지 않고 기본 방향대로 정한다.\n\n"
        "- storage 항목: 파일 하나에 저장\n"
        "- tech-1 항목\n  - 선택: Flask\n  - 버전: (pypi: flask@3.1.0)\n"
        # LLM 이 정한 것: 기본 방향이 비어 있던 항목과 스스로 더 정한 기본값.
        "- share 항목: 나누는 기능은 넣지 않는다.\n- 비밀번호 보관: 환경 변수에 둔다.\n"
        # LLM 이 빠뜨린 빈 항목은 작업자가 되묻지 않도록 정하는 쪽을 적어 둔다.
        "- login 항목: 정해진 방향이 없다. 사용자가 정한 것에 맞는 기본값을 정하고 무엇으로 정했는지 한 줄로 알린다.\n"
    )


def test_spec_without_llm_decision_section_still_gets_both_sections():
    state = state_with(BUILD)
    state["spec_items"] = [item("purpose", content="혼자 씀")]

    spec = make_generate_artifacts(FakeLLM())(state)["artifacts"]["docs/spec.md"]

    assert spec.startswith(
        "# 스펙\n\n가계부 프로그램.\n\n## 사용자가 정한 것\n- purpose 항목: 혼자 씀\n"
    )
    assert "## 작업자가 정하는 것\n이 절의 항목은" in spec


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
