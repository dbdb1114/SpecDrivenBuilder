# LangGraph 상태 · checkpointer

## 결정 (2026-11-06)

- interview 노드는 `interrupt()`로 사용자 응답을 기다린다 → checkpointer는 첫 그래프부터 필수.
- 개발: `SqliteSaver` (파일 하나, `--reload`해도 상태 유지)
- 테스트: `InMemorySaver` (`MemorySaver`는 구 별칭 — 쓰지 않는다)
- 운영 저장소: 미결정 (`PostgresSaver` 후보). 외부 사용자가 생길 때 결정.

## State 스키마 (2026-11-06, #1 스파이크 뼈대)

`builder/src/specbuilder/state/schema.py` — TypedDict.

| 키 | 타입 | reducer | 쓰는 노드 |
|---|---|---|---|
| `request` | `str` | — | 입력 (CLI) |
| `qa` | `list[QA]` (`question`, `answer`) | `operator.add` | interview_user |
| `pending_question` | `str \| None` | — | interview_user |
| `artifacts` | `dict[str, str]` (파일명 → 내용) | — | generate_artifacts |

- **`pending_question` 이 있는 이유:** `interrupt()` 후 resume 하면 노드가 처음부터 다시 실행된다. LLM 호출과 interrupt 를
  한 실행에 두면 resume 때마다 질문 생성이 재호출된다(비용 + 질문이 바뀜). 그래서 질문을 먼저 State 에 저장하고
  자기 자신으로 돌아온 다음 실행에서 interrupt 한다. 테스트 `tests/test_graph.py` 가 호출 횟수로 이를 고정한다.
- 산출물 파일 기록은 노드가 아니라 CLI(`graph/main.py`)가 한다 — 노드는 State 만 바꾼다.
- 개발용 SqliteSaver 파일: `builder/.checkpoints.sqlite` (git 무시). thread_id = 실행 ID(`<YYMMDD-HHMMSS>-<케이스명>`).

## 미결정

- 프로필 수집용 키 (interview-profile.md) — 프로필 노드를 만들 때
- "가이드 vs 템플릿" 결정(#2)에 따른 키 추가 여부
- 저장된 checkpoint의 스키마 변경 시 호환 정책
