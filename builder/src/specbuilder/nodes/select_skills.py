from langgraph.types import Command

from specbuilder.llm import LLMClient
from specbuilder.state import State

NEXT = "confirm_spec"


def make_select_skills(llm: LLMClient):
    """[빈 노드 — C 가 구현] 읽음: `spec_items`, 공통 스킬 목록. 채움: `skills`. 갈 곳: confirm_spec."""

    def select_skills(state: State) -> Command:
        return Command(goto=NEXT)

    return select_skills
