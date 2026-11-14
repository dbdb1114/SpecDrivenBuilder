import json

import pytest
from langgraph.types import Command

from specbuilder.llm import LLMCallError
from specbuilder.nodes.select_skills import make_select_skills
from specbuilder.state import initial_state
from tests.fakes.fake_llm import FakeLLM, item, skill, skills_reply

COMMON = "verify-before-report"


def run(reply: str, items: list[dict] | None = None):
    state = initial_state("가계부")
    state["spec_items"] = items or [item("purpose"), item("storage")]
    llm = FakeLLM({"select_skills": [reply]})
    return make_select_skills(llm)(state), llm


def test_fills_skills_and_goes_to_confirm_spec():
    result, llm = run(
        skills_reply(skill(basis=("purpose", "storage")), skill(COMMON, "common"))
    )

    assert isinstance(result, Command) and result.goto == "confirm_spec"
    assert list(result.update) == ["skills"]
    build, common = result.update["skills"]
    assert build == {
        "name": "build-ledger",
        "when": "가계부를 만들 때 쓴다",
        "source": "new",
        "basis": ["purpose", "storage"],
    }
    assert common["source"] == "common"
    assert len(llm.calls_for("select_skills")) == 1


def test_prompt_carries_spec_items_and_common_skill_list():
    _, llm = run(skills_reply())
    prompt = llm.calls_for("select_skills")[0]

    assert '"id": "storage"' in prompt
    assert COMMON in prompt.split("## 공통 스킬 목록")[1]


def test_schema_limits_basis_to_existing_item_ids():
    _, llm = run(skills_reply())
    schema = llm.schemas[0][1]

    assert schema["$defs"]["SkillChoice"]["properties"]["basis"]["items"]["enum"] == [
        "purpose",
        "storage",
    ]


def test_common_skill_when_is_replaced_with_the_original_description():
    result, _ = run(
        skills_reply(skill(), skill(COMMON, "common", when="LLM 이 바꿔 쓴 설명"))
    )
    when = result.update["skills"][1]["when"]

    assert when != "LLM 이 바꿔 쓴 설명"
    assert when.startswith("작업을 마쳤다고")


def test_new_skill_when_is_flattened_to_one_line():
    result, _ = run(skills_reply(skill(when="가계부를 만들 때 쓴다.\n순서를  따른다.")))

    assert result.update["skills"][0]["when"] == "가계부를 만들 때 쓴다. 순서를 따른다."


@pytest.mark.parametrize(
    ("reply", "message"),
    [
        (skills_reply(skill("no-such-skill", "common")), "공통 스킬 목록에 없는"),
        (skills_reply(skill(COMMON, "new")), "이름이 같음"),
        (skills_reply(skill(), skill()), "이름 중복"),
        (skills_reply(skill(COMMON, "common")), "새로 쓰는 스킬이 없음"),
        (skills_reply(skill(basis=("ghost",))), "없는 스펙 항목"),
        (skills_reply(skill("../escape")), "규격에 맞지 않음"),
        (skills_reply(skill(basis=())), "규격에 맞지 않음"),
        (json.dumps({"skills": []}), "규격에 맞지 않음"),
        (
            skills_reply(*(skill(f"skill-{n}") for n in range(7))),
            "규격에 맞지 않음",
        ),
    ],
)
def test_invalid_reply_raises(reply, message):
    with pytest.raises(LLMCallError, match=message):
        run(reply)
