import operator
from typing import Annotated, Literal, TypedDict

from specbuilder.state.question_format import QA, QuestionBundle
from specbuilder.state.spec_items import SpecItem, purpose_item


class Profile(TypedDict):
    """interview_profile(G) 이 채우는 사용자 프로필. 축은 docs/design/interview-profile.md "수집 축"."""

    domain: str
    tech_exposure: str
    explanation: str
    environment: str
    delegation: str


class InterviewStop(TypedDict):
    """묻는 노드가 질문을 멈춘 이유. 실행 기록(run.json)에 남는다."""

    node: str
    # resolved: 물어야 할 항목이 없음(코드 판정) / user_finished: "그만 묻고 만들어 주세요" / round_limit: 안전 상한
    reason: Literal["resolved", "user_finished", "round_limit"]
    rounds: int


class StackMismatch(TypedDict):
    """verify_stack(B) → select_stack 으로 넘기는 맞지 않는 항목. reason 에 저장소에서 가져온 실제 버전 정보를 적는다."""

    item_id: str
    reason: str


class SkillEntry(TypedDict):
    """select_skills(C) 의 출력 한 줄 (design.md "select_skills")."""

    name: str
    when: str
    source: Literal["common", "new"]
    basis: list[str]


class State(TypedDict):
    request: str
    profile: Profile | None
    # 노드가 항목을 고치므로 reducer 없이 통째로 교체한다. 바꾼 노드는 전체 목록을 반환한다.
    spec_items: list[SpecItem]
    # interrupt 후 resume 하면 노드가 처음부터 다시 돈다. 묶음을 여기 먼저 저장해 두어야 resume 때 LLM 을 다시 부르지 않는다.
    # 한 번에 한 노드만 물으므로 묻는 노드 셋이 같이 쓴다.
    pending_bundle: QuestionBundle | None
    # 이번 진입에서 낸 질문 묶음 수. 묻는 노드가 나갈 때 0 으로 돌린다 — 돌아오는 경로로 다시 들어오면 새로 센다.
    question_round: int
    # 노드가 새 줄만 반환하면 reducer 가 이어 붙인다 — 전체 리스트를 반환하면 중복 누적됨.
    qa: Annotated[list[QA], operator.add]
    interview_stops: Annotated[list[InterviewStop], operator.add]
    stack_returns: int
    verify_returns: int
    stack_mismatches: list[StackMismatch]
    skills: list[SkillEntry]
    # 파일명 → 내용. 디스크 기록은 CLI 가 한다 (노드는 부수효과 없이 State 만 바꾼다).
    artifacts: dict[str, str]


def initial_state(request: str) -> State:
    """요청 원문으로 그래프 입력 State 를 만든다. "용도" 항목을 아직 모름으로 심어 첫 질문 묶음이 용도를 묻게 한다."""
    return {
        "request": request,
        "profile": None,
        "spec_items": [purpose_item()],
        "pending_bundle": None,
        "question_round": 0,
        "qa": [],
        "interview_stops": [],
        "stack_returns": 0,
        "verify_returns": 0,
        "stack_mismatches": [],
        "skills": [],
        "artifacts": {},
    }
