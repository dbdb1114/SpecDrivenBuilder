"""API 요청 · 응답 모양. 규격(질문 묶음 · 확인 화면)은 state/ 의 원본을 감싸기만 하고 다시 적지 않는다.

state/ 와 같이 TypedDict 로 둔다 — 그래프에서 나온 plain dict 를 변환 없이 그대로 돌려줄 수 있다.
"""

from typing import Literal, TypedDict

from specbuilder.state.question_format import ConfirmScreen, QuestionBundle
from specbuilder.state.spec_items import NonEmpty


class StartRun(TypedDict):
    request: NonEmpty


class RunView(TypedDict):
    """실행 하나의 현재 화면. `status` 에 맞는 필드 하나만 채워진다."""

    run_id: str
    # question: 질문 묶음 대기 / confirm: 확인 화면 대기 / stalled: 중간에 멈춤(retry 로 이어감) / done: 산출물 완성
    status: Literal["question", "confirm", "stalled", "done"]
    bundle: QuestionBundle | None
    confirm: ConfirmScreen | None
    # 파일명 → 내용. done 일 때만 채운다.
    artifacts: dict[str, str]
    # 이번 요청에서 LLM 호출이 실패했을 때의 메시지. 저장하지 않으므로 다시 조회하면 null.
    error: str | None
