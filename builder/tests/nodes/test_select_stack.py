import json

import pytest

from specbuilder.llm import LLMCallError
from specbuilder.nodes.select_stack import make_select_stack
from specbuilder.registry.refs import parse_refs
from specbuilder.state import initial_state
from tests.fakes.fake_llm import FakeLLM, item, package, stack_reply, tech


def _state(**overrides):
    state = initial_state("가계부 만들어줘")
    state["spec_items"] = [item("purpose", content="혼자 쓰는 가계부")]
    return state | overrides


def test_writes_tech_items_with_versions_and_goes_to_verify():
    llm = FakeLLM()
    result = make_select_stack(llm)(_state())

    assert result.goto == "verify_stack"
    tech_items = [i for i in result.update["spec_items"] if i["area"] == "tech"]
    assert [i["id"] for i in tech_items] == ["tech-runtime", "tech-web-framework"]
    assert all(
        i["decided_by"] == "worker" and i["status"] == "delegated" for i in tech_items
    )
    framework = tech_items[1]["content"]
    assert framework.startswith("선택: Next.js\n")
    assert "이유: 혼자 쓰는 가계부라서" in framework
    assert [r.label for r in parse_refs(framework)] == ["next@16.4.6", "react@19.2.0"]
    assert result.update["stack_mismatches"] == []
    assert result.update["verify_returns"] == 0
    assert len(llm.calls_for("select_stack")) == 1


def test_context_carries_answers_environment_and_mismatches():
    llm = FakeLLM()
    profile = {
        "domain": "",
        "tech_exposure": "",
        "explanation": "",
        "environment": "macOS, Claude Code",
        "delegation": "",
    }
    mismatch = {
        "item_id": "tech-web-framework",
        "reason": "next@99.0.0: 저장소에 없는 버전. npm 최신 안정판 16.4.6",
    }
    result = make_select_stack(llm)(
        _state(profile=profile, stack_mismatches=[mismatch], verify_returns=1)
    )

    prompt = llm.calls_for("select_stack")[0]
    assert "혼자 쓰는 가계부" in prompt
    assert "macOS, Claude Code" in prompt
    assert "npm 최신 안정판 16.4.6" in prompt
    # 검증에서 돌아온 경우에는 왕복 횟수를 유지한다
    assert "verify_returns" not in result.update


def test_missing_info_becomes_unknown_user_items_and_goes_back():
    llm = FakeLLM(
        {
            "select_stack": [
                stack_reply(
                    [],
                    [
                        {
                            "id": "shared-editing",
                            "name": "여러 사람이 같은 기록을 동시에 고치는가",
                        }
                    ],
                )
            ]
        }
    )
    result = make_select_stack(llm)(_state())

    assert result.goto == "interview_user"
    assert result.update["stack_returns"] == 1
    added = [i for i in result.update["spec_items"] if i["id"] == "shared-editing"]
    assert added == [
        {
            "id": "shared-editing",
            "name": "여러 사람이 같은 기록을 동시에 고치는가",
            "area": "function",
            "decided_by": "user",
            "status": "unknown",
            "content": "",
        }
    ]
    assert (
        "## 부족한 정보를 사용자에게 다시 물을 수 있는가\n예"
        in llm.calls_for("select_stack")[0]
    )


def test_missing_info_already_answered_is_not_asked_again():
    llm = FakeLLM(
        {
            "select_stack": [
                stack_reply(
                    [tech("runtime", [package("eol", "nodejs", "24")])],
                    [{"id": "purpose", "name": "용도"}],
                )
            ]
        }
    )
    result = make_select_stack(llm)(_state())
    assert result.goto == "verify_stack"
    assert "stack_returns" not in result.update


def test_at_return_limit_missing_info_is_ignored_and_defaults_are_used():
    llm = FakeLLM(
        {
            "select_stack": [
                stack_reply(
                    [tech("runtime", [package("eol", "nodejs", "24")])],
                    [{"id": "shared-editing", "name": "동시 편집"}],
                )
            ]
        }
    )
    result = make_select_stack(llm)(_state(stack_returns=1))

    assert result.goto == "verify_stack"
    assert not any(i["id"] == "shared-editing" for i in result.update["spec_items"])
    assert (
        "## 부족한 정보를 사용자에게 다시 물을 수 있는가\n아니오"
        in llm.calls_for("select_stack")[0]
    )


def test_tech_items_are_replaced_not_merged():
    old = item(
        "tech-old-db",
        status="delegated",
        content="선택: 옛것",
        decided_by="worker",
        area="tech",
    )
    llm = FakeLLM()
    result = make_select_stack(llm)(_state(spec_items=[item("purpose"), old]))
    ids = [i["id"] for i in result.update["spec_items"]]
    assert "tech-old-db" not in ids
    assert ids[0] == "purpose"


@pytest.mark.parametrize(
    "packages",
    [
        [package("npm", "../etc", "1.0.0")],
        [package("maven", "spring-boot", "4.1.2")],
        [package("npm", "next", "16 (latest)")],
        [package("cargo", "serde", "1.0.0")],
    ],
)
def test_rejects_malformed_packages(packages):
    llm = FakeLLM({"select_stack": [stack_reply([tech("x", packages)])]})
    with pytest.raises(LLMCallError):
        make_select_stack(llm)(_state())


def test_rejects_too_many_packages():
    many = [
        tech(f"t{i}", [package("npm", f"p{i}{j}", "1.0.0") for j in range(4)])
        for i in range(3)
    ]
    llm = FakeLLM({"select_stack": [stack_reply(many)]})
    with pytest.raises(LLMCallError, match="상한"):
        make_select_stack(llm)(_state())


def test_rejects_empty_reply():
    llm = FakeLLM({"select_stack": [json.dumps({"items": [], "missing": []})]})
    with pytest.raises(LLMCallError):
        make_select_stack(llm)(_state())


def test_requests_json_schema():
    llm = FakeLLM()
    make_select_stack(llm)(_state())
    ((_, schema),) = [s for s in llm.schemas if s[0] == "select_stack"]
    assert schema["type"] == "object" and {"items", "missing"} <= set(
        schema["properties"]
    )
