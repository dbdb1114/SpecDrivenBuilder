from langgraph.types import Command

from specbuilder.state import State

NEXT = "generate_artifacts"


def confirm_spec(state: State) -> Command:
    """[빈 노드 — D 가 구현] 읽음: `spec_items`. `ConfirmScreen` 으로 interrupt 하고 `ConfirmReply` 를 받는다 (LLM 없음).
    revise 면 고른 항목을 `unknown` 으로 바꿔 `spec_items` 를 채우고 interview_user 로. 갈 곳: generate_artifacts | interview_user.
    """
    return Command(goto=NEXT)
