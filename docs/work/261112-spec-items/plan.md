# 작업 단위 A — 스펙 항목 · JSON 규격 · interview_user 확장 · 그래프 뼈대 (#A, 브랜치 `feat/spec-items`)

승인 (2026-11-12): 계획 전체 — pydantic 직접 의존성 승격, interview_user LLM 호출 N+1 포함.


## Context

B~G 작업 단위가 전부 A 의 계약(스펙 항목, 질문 묶음·답 제출·확인 화면 규격, State 키, 그래프 엣지)에 기대어 동시에 진행된다.
지금 구현은 질문을 문자열 하나씩 묻고 문답만 넘기며 3개 상한에서 끝난다 — 스펙 항목도, JSON 규격도 없다.
이번 작업은 계약을 한 곳에 정의하고, `interview_user` 를 스펙 항목 기반 질문 묶음으로 바꾸고, 8노드 그래프 뼈대를 세운다.

## 1. 분석 (현재 상태)

- [확정] 노드는 `interview_user`, `generate_artifacts` 둘. State 키 `request`·`qa`·`pending_question`·`artifacts` (`state/schema.py`).
- [확정] `interview_user` 는 `pending_question` 에 질문을 먼저 저장하고 자기 자신으로 돌아온 뒤 interrupt — resume 시 LLM 재호출 방지. `tests/test_graph.py` 가 호출 3회로 고정.
- [확정] `FakeLLM` 은 응답을 **호출 순서대로** pop 한다 → 빈 노드가 실제 노드로 바뀌면 순서가 밀려 남의 테스트가 깨진다.
- [확정] `generate_artifacts` 는 `interview_user.render_context` 를 import 해 씀.
- [확정] pydantic 2.13.4 가 langgraph 의 전이 의존성으로 이미 설치돼 있음 (`uv tree` 에는 직접 의존성 아님).
- [확정] State 에 pydantic `BaseModel` 을 넣으면 SqliteSaver 복원 시 `Deserializing unregistered type ... will be blocked in a future version` 경고 (스크래치 실험으로 확인). → State 값은 dict/list 여야 한다.
- [확정] `pytest` 7 passed (현재 develop).
- [확정] 기준선 eval(바꾸기 전 코드, `claude-sonnet-5-5`) 3건을 백그라운드로 돌리는 중 → `builder/output/evals-before/` (커밋 안 됨).

## 2. 계획 단계에서 정할 것 — 결정안

| 항목 | 결정안 | 이유 |
|---|---|---|
| 규격 정의 방법 | **`TypedDict` + pydantic `TypeAdapter`** (`Annotated[..., Field(...)]`, `AfterValidator`) | TypedDict 값은 plain dict 라 State·checkpoint 에 그대로 넣어도 경고가 없고(BaseModel 은 위 경고), pydantic 이 같은 정의로 검증하고 E 의 FastAPI 가 OpenAPI 스키마를 만든다 — 원본 한 곳 |
| 의존성 | `uv add pydantic` (이미 설치된 2.13.x 를 **직접 의존성으로 승격**만. 새 패키지 없음) | 전이 의존성에 기대 import 하면 langgraph 가 바꿀 때 깨진다. **승인 필요 (의존성 변경)** |
| 질문 묶음 안전 상한 | 노드 진입 1회당 **5묶음** (`MAX_ROUNDS = 5`). 노드를 나갈 때 카운터 0 으로 리셋 | 보통 2~3묶음이면 끝남. 진입마다 리셋해야 D 의 "고칠 항목" 으로 돌아왔을 때 다시 물을 수 있다. 돌아오는 횟수 자체는 B·D 의 상한이 막는다 |
| LLM 호출 수 | `interview_user` = 질문 묶음 N 개 → **N+1 회** (마지막 답을 반영하는 호출에서 "아직 모름" 이 0 이 되면 종료). `finish`·상한 종료는 추가 호출 없음. 빈 노드 6개 0회. 전체 = N+1+1(generate) | 기존: 질문 수 Q 에 대해 최대 Q+1(판정)+1, Q≤3. 묶음이 질문을 여러 개 담으므로 보통 같거나 줄어든다(예상 3~4회 vs 기존 4~5회). **+1 회 이유:** 마지막 답 때문에 새로 생기는 "앞 답에 따라 달라지는 질문" 을 발견하고, 맡긴 항목의 기본 방향을 채우려면 답을 본 뒤 한 번 더 봐야 한다. **승인 필요** |

### State 키 (B~G 몫 포함, 전부 이번에 선언)

| 키 | 타입 | reducer | 쓰는 노드 |
|---|---|---|---|
| `request` | `str` | — | 입력 |
| `profile` | `Profile \| None` (도메인·기술 노출·설명 선호·환경·위임 범위, 각 `str`) | — | interview_profile (G) |
| `spec_items` | `list[SpecItem]` | — (통째 교체) | interview_*, select_stack, verify_stack, confirm_spec |
| `pending_bundle` | `QuestionBundle \| None` | — | 묻는 노드 공용 (`pending_question` 대체, 같은 이유) |
| `question_round` | `int` | — | 묻는 노드 공용 (나갈 때 0) |
| `qa` | `list[QA]` (`node`·`round`·`item_id`·`question`·`answer`) | `operator.add` | 묻는 노드 |
| `interview_stops` | `list[InterviewStop]` (`node`·`reason`·`rounds`) | `operator.add` | 묻는 노드 — 종료 사유 기록 |
| `stack_returns` | `int` | — | select_stack (B) — interview_user 로 돌아간 횟수 |
| `verify_returns` | `int` | — | verify_stack (B) — select_stack 으로 돌아간 횟수 |
| `stack_mismatches` | `list[StackMismatch]` (`item_id`·`reason`) | — | verify_stack → select_stack (B) |
| `skills` | `list[SkillEntry]` (`name`·`when`·`source`·`basis`) | — | select_skills (C) |
| `artifacts` | `dict[str, str]` | — | generate_artifacts |

D(확인 화면은 interrupt 값으로만 오감)·F(미리보기는 `pending_bundle.preview`)는 새 키가 필요 없다.

## 3. 규격 (`state/` 아래, 원본 한 곳)

**`state/spec_items.py`** — `SpecItem` = `id`(kebab-case slug) · `name` · `area: "function"|"design"|"tech"` ·
`decided_by: "user"|"worker"` · `status: "confirmed"|"delegated"|"unknown"` · `content: str`.
- 항목 id 는 LLM 이 slug 로 제안하고 코드가 형식·중복을 검증한다 (여러 호출에 걸쳐 같은 항목을 가리켜야 하므로). 질문·선택지 id 는 코드가 붙인다 (`q1`, `o1`).
- `PURPOSE_ITEM_ID = "purpose"` — `initial_state` 가 `purpose`(용도, function, user, unknown) 를 심어 둔다.
  → 실행 규칙상 첫 진입에 반드시 묻게 되고, "용도를 가장 먼저" 를 코드로 보장한다.
- 함수: `needs_asking(items, area)` (결정 주체 user + 아직 모름 존재?), `delegate_unknown(items, area)`, `merge_updates(items, updates)`.
  merge 규칙: 확정 항목은 바뀌지 않음 / 맡김 항목은 `content`(기본 방향)만 갱신 / 아직 모름·새 항목은 그대로 반영 / 삭제 없음(upsert).

**`state/question_format.py`** — `question-format.md` 전부:
`Option`·`Question`·`QuestionBundle`(questions 1~10, options 2~4, recommended ≤1), `Visual` = `PaletteVisual`(hex 색 목록) | `LayoutVisual`(`key ∈ LAYOUT_KEYS`),
`Preview`(`layout`·`colors`·`texts{title, menu}`), `Answer` = option|custom|delegate (`kind` 판별 유니온), `AnswerSubmission`(`submit`|`finish`),
`ConfirmItem`·`ConfirmScreen`, `ConfirmReply` = confirm | revise(`item_ids` ≥1).
- `LAYOUT_KEYS = ("sidebar-left",)` — 문서 예시 하나만. 목록 확정은 F 의 몫(상수 한 줄만 바꾸면 되게 분리).
- LLM 쪽 초안 모델 `DraftQuestion`·`DraftOption`(id 없음) + `assign_ids(drafts, round, can_finish, preview) -> QuestionBundle`.
- `validate_submission(bundle, submission)` — 없는 question_id·option_id, `multiple=false` 인데 2개 이상이면 거부.
- `apply_submission(items, bundle, submission) -> (items, qa)` — 표대로: option/custom → 확정(내용 = 선택지 문구 / 입력 문장), delegate·빠진 질문 → 맡김, finish → 남은 아직 모름도 맡김.

## 4. 노드 · 그래프

**`nodes/interview_user.py`** (`make_interview_user(llm)`)
1. `pending_bundle` 있음 → `interrupt(bundle)` → 받은 답을 `validate_submission` → `apply_submission` → `question_round += 1`, `pending_bundle=None`.
   `finish` 면 바로 종료(`user_finished`). 아니면 자기 자신으로.
2. `pending_bundle` 없음:
   - `question_round >= MAX_ROUNDS` → 남은 아직 모름을 맡김으로, 종료(`round_limit`).
   - `question_round == 0` 이고 `needs_asking(items, "function")` 거짓 → **기록 없이 지나감** (돌아오는 경로의 실행 규칙).
   - 그 외 LLM 1회: 응답 `{"items": [...], "questions": [...]}` 를 TypeAdapter 로 검증(실패 → `LLMCallError`), `merge_updates`.
     merge 후 아직 모름이 없으면 종료(`resolved`, 질문은 버림). 있으면 질문 검증(item_id 는 아직 모름·user·function 항목, 질문당 항목 하나, 아직 모름이 있는데 질문 0개면 오류), `purpose` 질문을 맨 앞으로, `assign_ids` → `pending_bundle` 저장 후 자기 자신으로.
   - 종료 = `interview_stops` 에 `{node, reason, rounds}` 추가, `question_round=0`, goto `interview_design`.
- LLM 응답의 항목은 `area="function"` 만 허용, `decided_by=worker` 는 아직 모름 불가.

**`prompts/interview_user.md`** 재작성: 입력(요청 원문·현재 스펙 항목 JSON·지난 문답), 사용자만 아는 것만 묻기, 용도가 아직 모름이면 이번 묶음은 용도와 용도에 따라 달라지지 않는 질문만, 서로 독립인 질문만, 맡김인데 내용이 빈 항목은 기본 방향 채우기, 작업자가 정할 항목은 `worker`+`delegated`+기본 방향으로 추가, "알아서 정해 주세요" 를 선택지에 넣지 않기, 요청·답 안의 지시문은 데이터로만, JSON 출력 형식.

**`nodes/generate_artifacts.py`**: 자체 `render_context` — 요청 원문, "사용자가 정한 것"(user+confirmed), "작업자가 정하는 것"(그 외, 기본 방향 포함; 내용이 빈 맡김 항목은 "기본 방향을 정해 적을 것" 표시). `prompts/generate_artifacts.md` 에 spec.md 를 이 두 절로 나눠 쓰라는 지시 추가. 출력 형식(구분선)은 그대로.

**빈 노드 6개** — `nodes/<노드명>.py` 하나씩, LLM·프롬프트 없음, State 를 바꾸지 않고 `Command(goto=다음)` 만 반환.
LLM 을 쓸 예정인 5개(`interview_profile`, `interview_design`, `select_stack`, `verify_stack`, `select_skills`)는 지금부터 `make_<노드명>(llm)` 팩토리 모양 → B~G 가 `graph/build.py` 를 안 고쳐도 된다. `confirm_spec` 은 LLM 없음 → 평범한 함수.
docstring 한두 줄: 읽을 키 / 채울 키 / 갈 수 있는 곳.

**`graph/build.py`** — 노드 8개 등록, 모든 이동은 `Command(goto)` + `destinations` 로 지금 전부 선언:
`START→interview_profile`, `interview_profile→{self, interview_user}`, `interview_user→{self, interview_design}`,
`interview_design→{self, select_stack}`, `select_stack→{verify_stack, interview_user}`, `verify_stack→{select_skills, select_stack}`,
`select_skills→{confirm_spec}`, `confirm_spec→{generate_artifacts, interview_user}`, `generate_artifacts→END`.

**`graph/main.py`** (CLI): interrupt 값이 질문 묶음이면 `[질문 2/3] 문장` + `1. 선택지 (추천)` … + `N. 알아서 정해 주세요` 로 그림.
입력: 번호(복수 선택은 `1,3`) / 그 밖의 글자 = 직접 입력 / 빈 줄 = 추천 선택지(없으면 맡김) / `can_finish` 면 `그만` = finish. `visual`·`preview` 무시.
한 줄 = 질문 하나 답 (stdin 파이프 유지). 답 제출 JSON 을 TypeAdapter 로 검증해 resume. `run.json` 에 `qa`·`spec_items`·`interview_stops` 추가.

**`tests/fakes/fake_llm.py`** — 노드별 응답: 시스템 프롬프트를 `prompts/*.md` 내용과 대조해 어느 노드의 호출인지 알아낸다(LLMClient 프로토콜 변경 없음).
`FakeLLM({"interview_user": [...], ...})`, 노드별 큐가 비면 `DEFAULT_REPLIES[노드]`(interview_user: purpose 를 확정하고 질문 0개 / generate_artifacts: `files_reply()`) 사용, `calls_for(node)`.
→ B 가 `select_stack` 프롬프트를 추가하면 `DEFAULT_REPLIES` 에 한 줄 추가 — 다른 테스트는 그대로 돈다. 프롬프트 없는 노드 이름의 응답을 받으면 오류.

## 5. 건드릴 파일

| 파일 | 변경 |
|---|---|
| `builder/pyproject.toml`, `uv.lock` | `uv add pydantic` |
| `builder/src/specbuilder/state/{schema,spec_items,question_format,__init__}.py` | State 키 전부, 규격 모델·함수 |
| `builder/src/specbuilder/nodes/interview_user.py`, `generate_artifacts.py` | 위 4절 |
| `builder/src/specbuilder/nodes/{interview_profile,interview_design,select_stack,verify_stack,select_skills,confirm_spec}.py` | 새 빈 노드 |
| `builder/src/specbuilder/graph/build.py`, `main.py` | 그래프 뼈대, CLI 질문 묶음 |
| `builder/prompts/interview_user.md`, `generate_artifacts.md` | 4절 |
| `builder/tests/fakes/fake_llm.py`, `tests/test_graph.py`, `tests/nodes/test_interview_user.py`, `test_generate_artifacts.py` | 노드별 fake, 새 동작 |
| `builder/tests/state/test_spec_items.py`, `test_question_format.py` (+ `__init__.py`) | 규격 검증 |
| `builder/tests/nodes/test_<빈 노드 6개>.py` | 지나가는지 1개씩 (tests/nodes 1:1 규칙) |
| `docs/design/state.md` | State 스키마 표 갱신 |
| `docs/design/design.md` | "미결정" 중 질문 묶음 안전 상한 줄만 결정으로 (interview_user 몫). 다른 절 손대지 않음 |
| `docs/work/261112-spec-items/plan.md`, `constraints.md` | 작업 기록 |

건드리지 않음: 빈 노드 실제 구현, `api/`, `frontend/`, `templates/`. 용어사전·lessons.md 는 필요할 때 줄 추가만 (현재 계획상 새 용어 없음).

## 6. 검증

1. `cd builder && uv run pytest -q` — 규격 검증(상한·recommended ≤1·판별 유니온·layout key), apply_submission 표 4줄, interview_user 종료 사유 3가지 + 지나감, resume 시 LLM 재호출 없음(`calls_for("interview_user")` 개수), 그래프 8노드 끝까지(START→END) + 노드별 fake.
2. `uv run ruff check . && uv run ruff format --check .`
3. 실제 실행 eval: 3 케이스를 **같은 모델**(`claude-sonnet-5-5`)로 바꾸기 전(진행 중) / 후 실행. 후는 빈 줄 파이프(= 추천 선택지). 질문 수·묶음 수·LLM 호출 수·spec.md 의 두 절 유무·플레이스홀더 grep 을 `plan.md` 에 나란히.
4. 마지막에 토큰 소모 기록, `PROMPT.md` 삭제(커밋 안 함), 완료 보고.

## 남는 것 (이번에 안 함)

- `finish`·상한으로 맡김이 된 항목은 기본 방향(content)이 비어 있다 → generate_artifacts 가 채운다. 확인 화면(D)에서 빈 내용을 보여 줄지는 D 의 몫.

## 7. 계획과 달라진 점

- **계획 밖 파일: `builder/src/specbuilder/llm/client.py`** (2026-11-13 사용자 승인, 선택지 1 `--json-schema`).
  eval 중 첫 `interview_user` 응답이 약 1/3 확률로 깨진 JSON 이었다 (따옴표 누락 — 예: `"「미분류」로 두고 집계에 그대로 포함해요}`).
  `LLMClient.complete(system, prompt, schema=None)` 에 선택 인자를 더하고, schema 가 있으면 `claude -p --json-schema` 로 형식을 강제해
  `structured_output` 을 JSON 문자열로 돌려준다. LLM 호출 수 변화 없음. pydantic 이 넣는 OpenAPI 전용 `discriminator` 키워드는
  claude -p strict 검증이 거부해서 보내기 전에 뺀다 (`oneOf` 는 남음). "recommended ≤1" 같은 규칙은 JSON Schema 로 표현되지 않아 코드가 계속 검증한다.
- `prompts/interview_user.md`: "여러 개를 고르는 질문이어도 recommended 는 하나만" 을 명시 — eval 에서 복수 선택 질문에 추천 3개를 붙여 거부된 일이 있었다.
- `graph/main.py`: `run.json` 에 `llm_calls` 를 남기는 `CountingClient` 추가 — LLM 호출 수 변화를 실제 실행으로 비교하려고.
- 묻는 노드 공용 LLM 응답 규격 `InterviewReply` 를 `question_format.py` 에 둠 (F 의 interview_design 이 같은 규격을 쓰도록).
- `uv add pydantic` 은 `uv.lock` 의 버전을 바꾸지 않았다 (직접 의존성 표시 2줄만).

## 8. 검증 결과

```
$ cd builder && uv run pytest -q
44 passed, 13 warnings in 0.29s      # 경고는 기존과 같은 langsmith DeprecationWarning (Python 3.14)
$ uv run ruff check . && uv run ruff format --check .
All checks passed!
```

### 품질 회귀 — 같은 모델 `claude-sonnet-5-5`, `claude -p` 헤드리스

- 바꾸기 전: 2026-11-12 21:29~21:34, develop 코드. 답 = 모든 질문에 "추천하는 걸로 해 주세요".
- 바꾼 후: 2026-11-13 16:59~17:06, 최종 코드. 답 = 모든 질문에 빈 줄(= 추천 선택지).

| 케이스 | | 질문 수 | 묶음 수 | LLM 호출 | 종료 사유 | spec.md 두 절 | spec+SKILL+AGENTS 줄 수 | 플레이스홀더·위험 명령 grep |
|---|---|---|---|---|---|---|---|---|
| 01-short | 전 | 2 | — | 4 [추정: 질문 2 + 판정 1 + 생성 1] | LLM "충분함" | 없음 | 234 | 없음 |
| | 후 | 8 | 2 | 4 | resolved | 있음 | 195 | 없음 |
| 02-domain | 전 | 3 | — | 4 (질문 3 + 생성 1, 상한) | 상한 3 | 없음 | 284 | 없음 |
| | 후 | 11 | 3 | 5 | resolved | 있음 | 388 | 없음 |
| 03-vague | 전 | 3 | — | 4 (질문 3 + 생성 1, 상한) | 상한 3 | 없음 | 217 | 없음 |
| | 후 | 9 | 2 | 4 | resolved | 있음 | 221 | 없음 |

- 스펙 항목 (후): 01 사용자 확정 9 / 작업자 맡김 1, 02 14 / 3, 03 10 / 3. 세 케이스 모두 판정(resolved)으로 끝났고 상한에 닿지 않았다.
- 첫 묶음: 01·02 는 용도 질문이 맨 앞. 03 은 요청 원문("동아리 사람들이 같이, 휴대폰으로도")에서 용도를 확정해 용도 질문 없이 시작 — 프롬프트가 허용한 동작.
- 02 의 spec.md "작업자가 정하는 것" 은 맨 앞에 "사용자에게 다시 묻지 않고 기본 방향대로 정한다" 를 두고 기본 방향을 구체적으로 적었다 (새 엑셀 양식 등록, 불공제 목록 관리 등).
- 이전 시도 (최종 전 코드, 결과 폐기): `--json-schema` 없이 9회 중 3회 첫 응답의 형식 오류(JSON 2, recommended 2개 1)로 중단, `claude -p` 자체가 종료 코드 1 을 낸 일시 오류 2회. 최종 코드로는 3/3 통과.

### 실행 검증 (인수 조건) — 2026-11-13, `claude-sonnet-5-5`

바꾼 후 산출물 3건을 각각 빈 임시 폴더(git init)에 풀고 `echo 시작해 | claude -p --setting-sources project --tools Read,Glob,Grep --max-turns 8`.
도구를 읽기 전용으로 제한했다 — 프로그램을 끝까지 만들게 하지 않고 첫 행동만 본다.

| 확인할 것 | 01 | 02 | 03 |
|---|---|---|---|
| AGENTS.md 가 읽히는가 (CLAUDE.md `@AGENTS.md`) | 통과 | 통과 | 통과 |
| 첫 작업이 되묻지 않고 시작되는가 | 통과 | 통과 | 통과 |
| 스킬이 발견·로드되는가 | **실패** | **실패** | **실패** |

- 세 건 모두 AGENTS.md 의 작업 절차대로 spec.md → SKILL.md 를 먼저 읽고 0~1단계(`python3 --version`)를 묻지 않고 시도했다.
  멈춘 이유는 테스트가 막은 실행 권한뿐이었고, 보고도 AGENTS.md 규칙(사용자 말, 번호 선택지 + 추천)을 따랐다.
- 스킬: `SKILL.md` 가 폴더 루트에 있어 init 의 skills 목록에 없다 (본문은 Read 로 읽었다). 스킬을 두는 경로는 작업 단위 C 의 결정 사항
  (`work-units.md` "C — 산출물에서 스킬을 두는 경로") 이라 이번에 고치지 않았다. 바꾸기 전 산출물도 같은 구조다.
- [미확인] 쓰기·실행 권한을 준 끝까지의 실행 (프로그램 완성 여부) — 비용·시간이 커서 돌리지 않았다.
- [추정] 질문 수가 2~3 → 8~11 로 늘어 사용자의 답하는 부담이 커졌다. 묶음 수(왕복)는 2~3 으로 기존 질문 수와 비슷하다.

## 9. 안 한 것 / 남은 것

- `finish`·상한으로 맡김이 된 항목은 기본 방향(`content`)이 비어 있다 → generate_artifacts 가 정해 쓴다. 확인 화면(D)에서 빈 내용을 어떻게 보일지는 D 의 몫.
- `LAYOUT_KEYS` 는 문서 예시 `sidebar-left` 하나 — F 가 확정.
- `Profile` 필드는 수집 축 5개를 `str` 로만 선언 — G 가 확정.
- 스킬 발견 실패 — C 의 범위 (위 "실행 검증").
- 질문 수가 2~3 → 8~11 로 늘어난 것이 사용자에게 괜찮은 부담인지는 사람이 봐야 판단할 수 있다.

토큰 소모 [추정]: 세션 약 30만 토큰 + 실제 `claude -p` 약 48회 (eval 전 3건·후 여러 차례·재현 호출·실행 검증 3건).
