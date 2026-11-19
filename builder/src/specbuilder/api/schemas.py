"""API 요청 · 응답 모양. 규격(질문 묶음 · 확인 화면)은 state/ 의 원본을 감싸기만 하고 다시 적지 않는다.

state/ 와 같이 TypedDict 로 둔다 — 그래프에서 나온 plain dict 를 변환 없이 그대로 돌려줄 수 있다.
"""

from typing import Literal, TypedDict

from specbuilder.node_config import Effort
from specbuilder.state.question_format import QA, ConfirmScreen, QuestionBundle
from specbuilder.state.spec_items import NonEmpty


class StartRun(TypedDict):
    request: NonEmpty


class RunView(TypedDict):
    """실행 하나의 현재 화면. `status` 에 맞는 필드 하나만 채워진다."""

    run_id: str
    # question: 질문 묶음 대기 / confirm: 확인 화면 대기 / stalled: 중간에 멈춤(retry 로 이어감) / done: 산출물 완성
    status: Literal["question", "confirm", "stalled", "done"]
    # 사용자가 처음 적은 요청 원문과 지난 문답. 화면이 새로고침 뒤에도 대화 목록을 다시 그릴 수 있게 State 값을 그대로 내보낸다.
    request: str
    qa: list[QA]
    bundle: QuestionBundle | None
    confirm: ConfirmScreen | None
    # 파일명 → 내용. done 일 때만 채운다.
    artifacts: dict[str, str]
    # 이번 요청에서 LLM 호출이 실패했을 때의 메시지. 저장하지 않으므로 다시 조회하면 null.
    error: str | None


# ── 백오피스 (api/backoffice.py) ─────────────────────────────────────────────


class Usage(TypedDict):
    input: int
    output: int
    cache_write: int
    cache_read: int


class Totals(TypedDict):
    usage: Usage
    seconds: float
    # 가격표(llm/trace.py)에 없는 모델이 하나라도 섞이면 null.
    dollars: float | None


class RunSummary(Totals):
    run_id: str
    started_at: str
    calls: int


class CallRow(TypedDict):
    """호출 하나의 표 한 줄. n 은 1부터."""

    n: int
    at: str
    node: str
    model: str
    effort: str | None
    usage: Usage
    seconds: float
    dollars: float | None
    error: str | None


class RunTrace(TypedDict):
    run_id: str
    rows: list[CallRow]
    totals: Totals


class CallDetail(CallRow):
    system: str
    prompt: str
    response: str | None


class NodeRow(TypedDict):
    node: str
    model: str | None
    effort: Effort | None


class NodeSettingsView(TypedDict):
    nodes: list[NodeRow]
    efforts: list[Effort]
    # model 이 null 인 노드가 실제로 쓰는 모델 (SPECBUILDER_MODEL).
    default_model: str
    # 가격을 아는 모델 — 화면의 입력 제안. 이 밖의 모델도 저장할 수 있다.
    known_models: list[str]
    # 파일이 틀렸을 때의 문구. 그동안 노드 호출은 실패한다 — 화면에서 고쳐 저장하면 풀린다.
    error: str | None
