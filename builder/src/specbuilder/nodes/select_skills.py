import copy
import json
from typing import Annotated, Literal, TypedDict

from langgraph.types import Command
from pydantic import Field, StringConstraints, TypeAdapter, ValidationError

from specbuilder.common_skills import CommonSkill, load_common_skills
from specbuilder.llm import LLMCallError, LLMClient, parse_json_reply
from specbuilder.paths import load_prompt
from specbuilder.state import SkillEntry, State
from specbuilder.state.spec_items import ItemId

NODE = "select_skills"
NEXT = "confirm_spec"
# 생성 1회 호출이 스킬 본문을 전부 쓰므로 출력 길이를 막는다. 보통 2~3개.
MAX_SKILLS = 6

# 이름은 산출물의 폴더 이름이 된다 — 경로 구분자나 `..` 가 들어올 수 없게 slug 로 묶는다.
SkillName = Annotated[
    str, StringConstraints(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$", max_length=40)
]
When = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)
]


class SkillChoice(TypedDict):
    name: SkillName
    when: When
    source: Literal["common", "new"]
    basis: Annotated[list[ItemId], Field(min_length=1)]


class SkillsReply(TypedDict):
    skills: Annotated[list[SkillChoice], Field(min_length=1, max_length=MAX_SKILLS)]


skills_reply_adapter = TypeAdapter(SkillsReply)


def reply_schema(item_ids: list[str]) -> dict:
    """근거로 댈 수 있는 값을 지금 있는 스펙 항목 id 로 묶은 JSON Schema — 없는 항목을 근거로 대는 것을 형식 단계에서 막는다."""
    schema = copy.deepcopy(skills_reply_adapter.json_schema())
    schema["$defs"]["SkillChoice"]["properties"]["basis"]["items"] = {
        "type": "string",
        "enum": item_ids,
    }
    return schema


def render_context(state: State, common: dict[str, CommonSkill]) -> str:
    """스펙 항목과 공통 스킬 목록을 LLM 입력용 데이터 블록으로 만든다 (지시문 없음 — 지시는 prompts/ 에)."""
    catalog = [{"name": s["name"], "when": s["description"]} for s in common.values()]
    return "\n".join(
        [
            "## 스펙 항목",
            json.dumps(state["spec_items"], ensure_ascii=False, indent=2),
            "",
            "## 공통 스킬 목록",
            json.dumps(catalog, ensure_ascii=False, indent=2) if catalog else "(없음)",
        ]
    )


def check_skills(
    text: str, item_ids: set[str], common: dict[str, CommonSkill]
) -> list[SkillEntry]:
    """LLM 응답을 검증해 스킬 목록으로 바꾼다."""
    try:
        choices = skills_reply_adapter.validate_python(parse_json_reply(text))["skills"]
    except ValidationError as e:
        raise LLMCallError(f"{NODE} 응답이 규격에 맞지 않음: {e}") from e
    names = [c["name"] for c in choices]
    if len(names) != len(set(names)):
        raise LLMCallError(f"스킬 이름 중복: {names}")
    skills = []
    for choice in choices:
        name = choice["name"]
        if choice["source"] == "common" and name not in common:
            raise LLMCallError(f"공통 스킬 목록에 없는 스킬: {name}")
        if choice["source"] == "new" and name in common:
            raise LLMCallError(f"새로 쓰는 스킬이 공통 스킬과 이름이 같음: {name}")
        stray = [i for i in choice["basis"] if i not in item_ids]
        if stray:
            raise LLMCallError(f"없는 스펙 항목을 근거로 댐: {name} ← {stray}")
        # 공통 스킬은 그대로 들어가므로 "언제 쓰는지"도 LLM 이 옮긴 문장이 아니라 원문을 쓴다.
        # 새 스킬의 문장은 frontmatter 한 줄에 들어가므로 줄바꿈을 없앤다.
        when = (
            common[name]["description"]
            if choice["source"] == "common"
            else " ".join(choice["when"].split())
        )
        skills.append({**choice, "when": when})
    if not any(s["source"] == "new" for s in skills):
        raise LLMCallError("새로 쓰는 스킬이 없음 — 프로그램을 만드는 스킬이 필요하다")
    return skills


def make_select_skills(llm: LLMClient):
    """LLM 클라이언트를 주입한 select_skills 노드를 만든다. 읽음: `spec_items`, 공통 스킬 목록. 채움: `skills`."""
    system = load_prompt(NODE)

    def select_skills(state: State) -> Command:
        # 호출마다 읽는다 — 파일 몇 개라 싸고, 목록을 바꾼 뒤 서버를 다시 띄우지 않아도 된다.
        common = load_common_skills()
        item_ids = [item["id"] for item in state["spec_items"]]
        reply = llm.complete(
            system, render_context(state, common), reply_schema(item_ids)
        )
        return Command(
            update={"skills": check_skills(reply, set(item_ids), common)}, goto=NEXT
        )

    return select_skills
