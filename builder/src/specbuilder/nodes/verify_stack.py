from langgraph.types import Command

from specbuilder.llm import LLMClient
from specbuilder.state import State

NEXT = "select_skills"


def make_verify_stack(llm: LLMClient):
    """[빈 노드 — B 가 구현] 읽음: `spec_items` 의 tech 항목·`verify_returns`. 채움: 확인한 버전·날짜를 tech 항목 `content` 에.
    맞지 않으면 `stack_mismatches` 를 채우고 `verify_returns += 1` 후 select_stack 으로. 갈 곳: select_skills | select_stack.
    """

    def verify_stack(state: State) -> Command:
        return Command(goto=NEXT)

    return verify_stack
