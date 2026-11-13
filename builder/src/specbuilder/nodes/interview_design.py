from langgraph.types import Command

from specbuilder.llm import LLMClient
from specbuilder.state import State

NEXT = "select_stack"


def make_interview_design(llm: LLMClient):
    """[빈 노드 — F 가 구현] 읽음: `request`·`spec_items`. 채움: `area="design"` 스펙 항목, 질문 묶음의 `visual`·`preview`.
    `needs_asking(items, "design")` 이 거짓이면 지나간다. 묻는 키는 interview_user 와 같다. 갈 곳: 자기 자신 | select_stack.
    """

    def interview_design(state: State) -> Command:
        return Command(goto=NEXT)

    return interview_design
