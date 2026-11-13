# LangGraph 상태 · checkpointer

## 결정 (2026-11-06)

- interview 노드는 `interrupt()`로 사용자 응답을 기다린다 → checkpointer는 첫 그래프부터 필수.
- 개발: `SqliteSaver` (파일 하나, `--reload`해도 상태 유지)
- 테스트: `InMemorySaver` (`MemorySaver`는 구 별칭 — 쓰지 않는다)
- 운영 저장소: 미결정 (`PostgresSaver` 후보). 외부 사용자가 생길 때 결정.

## State 스키마 (2026-11-12, 작업 단위 A — 8노드 뼈대. B~G 의 키 포함)

`builder/src/specbuilder/state/schema.py` — TypedDict. 스펙 항목·질문 묶음 규격은 같은 디렉토리의
`spec_items.py`·`question_format.py` (TypedDict + pydantic `TypeAdapter` 로 검증).

| 키 | 타입 | reducer | 쓰는 노드 |
|---|---|---|---|
| `request` | `str` | — | 입력 (CLI) |
| `profile` | `Profile \| None` | — | interview_profile (G) |
| `spec_items` | `list[SpecItem]` | — (통째 교체) | interview_*, select_stack, verify_stack, confirm_spec |
| `pending_bundle` | `QuestionBundle \| None` | — | 묻는 노드 공용 |
| `question_round` | `int` | — | 묻는 노드 공용 — 이번 진입의 묶음 수, 나갈 때 0 |
| `qa` | `list[QA]` (`node`·`round`·`item_id`·`question`·`answer`) | `operator.add` | 묻는 노드 |
| `interview_stops` | `list[InterviewStop]` (`node`·`reason`·`rounds`) | `operator.add` | 묻는 노드 — 종료 사유 `resolved` / `user_finished` / `round_limit` |
| `stack_returns` | `int` | — | select_stack (B) — interview_user 로 돌아간 횟수 |
| `verify_returns` | `int` | — | verify_stack (B) — select_stack 으로 돌아간 횟수 |
| `stack_mismatches` | `list[StackMismatch]` (`item_id`·`reason`) | — | verify_stack → select_stack (B) |
| `skills` | `list[SkillEntry]` (`name`·`when`·`source`·`basis`) | — | select_skills (C) |
| `artifacts` | `dict[str, str]` (파일명 → 내용) | — | generate_artifacts |

- **State 값은 plain dict/list 로 둔다.** pydantic `BaseModel` 을 넣으면 SqliteSaver 복원 때 LangGraph 가
  `Deserializing unregistered type ... will be blocked in a future version` 경고를 낸다 (2026-11-12 확인). 그래서 규격을 TypedDict 로 정의한다.
- **`pending_bundle` 이 있는 이유** (이전 `pending_question` 과 같음): `interrupt()` 후 resume 하면 노드가 처음부터 다시 실행된다.
  LLM 호출과 interrupt 를 한 실행에 두면 resume 때마다 질문 생성이 재호출된다(비용 + 질문이 바뀜). 그래서 묶음을 먼저 State 에 저장하고
  자기 자신으로 돌아온 다음 실행에서 interrupt 한다. 한 번에 한 노드만 물으므로 묻는 노드 셋이 같이 쓴다. `tests/test_graph.py` 가 호출 횟수로 고정.
- `initial_state` 는 `spec_items` 에 `purpose`(용도, 사용자, 아직 모름) 항목을 심는다 — 묻는 노드의 실행 규칙상 첫 묶음이 용도를 묻는다.
- 산출물 파일 기록은 노드가 아니라 CLI(`graph/main.py`)가 한다 — 노드는 State 만 바꾼다.
- 개발용 SqliteSaver 파일: `builder/.checkpoints.sqlite` (git 무시). thread_id = 실행 ID(`<YYMMDD-HHMMSS>-<케이스명>`).

## 미결정

- `Profile` 의 필드 (지금은 수집 축 5개를 `str` 로만 선언) — G 가 프로필 노드를 만들 때
- "가이드 vs 템플릿" 결정(#2)에 따른 키 추가 여부
- 저장된 checkpoint의 스키마 변경 시 호환 정책
