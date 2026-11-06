import operator
from typing import Annotated, TypedDict


class QA(TypedDict):
    question: str
    answer: str


class State(TypedDict):
    request: str
    # 노드가 새 문답만 반환하면 reducer 가 이어 붙인다 — 전체 리스트를 반환하면 중복 누적됨.
    qa: Annotated[list[QA], operator.add]
    # interrupt 후 resume 하면 노드가 처음부터 다시 돈다. 질문을 여기 먼저 저장해 두어야 resume 때 LLM 을 다시 부르지 않는다.
    pending_question: str | None
    # 파일명 → 내용. 디스크 기록은 CLI 가 한다 (노드는 부수효과 없이 State 만 바꾼다).
    artifacts: dict[str, str]


def initial_state(request: str) -> State:
    """요청 원문으로 그래프 입력 State 를 만든다."""
    return {"request": request, "qa": [], "pending_question": None, "artifacts": {}}
