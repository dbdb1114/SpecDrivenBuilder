from langgraph.types import Command

from specbuilder.llm import LLMClient
from specbuilder.state import State

NEXT = "verify_stack"


def make_select_stack(llm: LLMClient):
    """[빈 노드 — B 가 구현] 읽음: `spec_items`·`profile`·`stack_mismatches`·`stack_returns`. 채움: `area="tech"`·`decided_by="worker"` 항목(버전 포함).
    부족한 정보가 있으면 `user`·`unknown`·`function` 항목을 추가하고 `stack_returns += 1` 후 interview_user 로. 갈 곳: verify_stack | interview_user.
    """

    def select_stack(state: State) -> Command:
        return Command(goto=NEXT)

    return select_stack
