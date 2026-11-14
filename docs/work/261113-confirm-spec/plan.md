# 작업 단위 D — confirm_spec (브랜치 `feat/confirm-spec`)

제약: `constraints.md`

## 1. 분석 (현재 상태)

- [확정] `develop`(2b13db7, A 머지) 를 fast-forward 로 받았다. 시작 조건 3개 충족: `state/spec_items.py`·`state/question_format.py`
  (`ConfirmItem`·`ConfirmScreen`·`ConfirmReply` 와 adapter), 8노드 그래프(`graph/build.py`, `confirm_spec` destinations =
  `generate_artifacts`·`interview_user`), 빈 노드 `nodes/confirm_spec.py`(통과만), 노드별 `FakeLLM`.
- [확정] `ConfirmItem.status` 는 `confirmed`·`delegated` 뿐 — "아직 모름" 항목은 규격상 확인 화면에 실을 수 없다.
- [확정] 묻는 노드는 나갈 때 자기 영역의 사용자 항목 "아직 모름"을 남기지 않는다(`resolved` / `delegate_open`).
  `interview_user` 는 작업자 결정 + 아직 모름 항목을 거부한다. 즉 정상 경로에서는 확인 화면에 아직 모름이 오지 않는다.
- [확정] 돌아오는 경로: `interview_user` 는 `rounds == 0` 이고 자기 영역(`function`)에 물을 항목이 없으면 LLM 없이 지나간다.
  `interview_design` 도 같은 규칙(`design`). → 디자인 항목을 고르면 `interview_user` 는 지나가고 `interview_design` 이 묻는다.
  "돌아오게 하는 쪽은 항목을 아직 모름으로 만들기만 한다"(design.md) 그대로 된다.
- [확정] `question_round`·`pending_bundle` 은 묻는 노드가 나갈 때 0 / None 으로 돌려 둔다 — confirm_spec 이 건드릴 필요 없다.
- [확정] CLI(`graph/main.py`)의 interrupt 루프는 모든 interrupt 값을 질문 묶음으로 본다(`ask_bundle`).
- [확정] **`tests/test_graph.py` 2개가 깨진다.** 둘 다 resume 1회(또는 0회) 뒤 `artifacts` 를 기대하는데,
  confirm_spec 이 interrupt 하면 그 자리에서 멈춘다. → 이 파일은 A 가 만든 것이지만 "건드리지 않는 것" 목록에는 없다.
  확인 화면 resume 한 단계를 넣는 최소 수정만 한다 (아래 파일 목록 ⑤). **승인 필요.**
- [확정] 기준선: `uv run pytest` 44 passed, `uv run ruff check .` 통과, langgraph 1.2.20.

## 2. 결정 (되돌릴 수 있는 것 — 알아서 정함)

| 항목 | 결정 | 이유 |
|---|---|---|
| `editable` | `decided_by == "user"` **이고** `area != "tech"` | question-format "사용자 항목만 true" + design.md "기술 항목은 보여 주기만". 기술 항목을 아직 모름으로 바꿔도 다시 묻는 노드가 없다 |
| 확인 화면에 아직 모름 항목이 있으면 | `ValueError` 로 멈춘다 | 규격이 실을 수 없고, 앞 노드의 버그다. 빼고 보여 주면 사용자가 모르는 채로 산출물이 나간다 |
| 항목 순서 | 영역순(용도·기능 → 디자인 → 기술), 영역 안에서는 `spec_items` 순서 | CLI·프론트엔드가 같은 순서로 묶어 그린다 |
| revise 한 항목 | `status="unknown"`, `content=""` | spec_items.py 의 규칙(아직 모름이면 빈 문자열). 이전 답은 `qa` 에 남아 있어 LLM 이 다시 물을 때 본다 |
| 잘못된 답(규격 위반, 없는 id, `editable=false` id) | `ValueError` | interview_user 의 답 제출 검증과 같은 방식 |
| revise 반복 상한 | 두지 않는다 | 사용자가 직접 고르는 것이라 끝없이 돌 수 없다. LLM 비용은 고른 만큼만 든다 |
| CLI 입력 | 빈 줄 = 확인, `1,3` = 고칠 항목(번호는 고칠 수 있는 항목에만 붙임), 그 밖 = 다시 묻기 | 질문 묶음의 "빈 줄 = 추천" 과 같은 감각. 파이프로 빈 줄만 넣어도 끝까지 돈다 |
| CLI 의 interrupt 구분 | 값에 `items` 키가 있으면 확인 화면, 아니면 질문 묶음 | Interrupt 객체에 노드 이름이 없다. 두 규격의 최상위 키가 겹치지 않는다 |

## 3. 계획 (건드릴 파일)

① `builder/src/specbuilder/nodes/confirm_spec.py` — 구현
   - `is_editable(item)`, `build_screen(items) -> ConfirmScreen`(순수 함수, 검증 포함),
     `validate_reply(screen, raw) -> ConfirmReply`, `reopen(items, item_ids)`.
   - 노드: `screen = build_screen(...)` → `interrupt(screen)` → 검증 → confirm 이면 `goto=generate_artifacts`,
     revise 면 `update={"spec_items": ...}, goto=interview_user`. interrupt 앞에는 계산만 있다 (부수 효과 없음).
② `builder/src/specbuilder/graph/main.py` — `ask_confirm(raw)` 추가(요약 출력·입력 해석), interrupt 루프에서 분기.
   모듈 docstring 에 확인 화면 입력 한 줄 추가.
③ `builder/tests/nodes/test_confirm_spec.py` — 빈 노드 테스트를 교체. `interrupt` 를 monkeypatch 해 노드 단위로:
   editable 규칙, 순서, 아직 모름 거부, confirm/revise 이동, 잘못된 revise 거부, interrupt 값이 규격을 통과하는지.
④ `builder/tests/test_main.py` (새 파일) — `ask_confirm` 입력 해석, 그리고 `main()` 을 FakeLLM + stdin 으로 끝까지
   (확인 화면에서 고치기 → 다시 묻기 → 확인 → 산출물 파일).
⑤ `builder/tests/test_graph.py` — 기존 2개 테스트에 확인 화면 resume(`{"action": "confirm"}`) 한 단계 추가 +
   돌아가는 경로 테스트 1개 추가(revise `purpose` → interview_user 가 다시 묻고 → 다시 확인 화면 → confirm → 산출물,
   LLM 호출 순서 고정). **A 의 파일 — 승인 필요.**
⑥ 루트 `AGENTS.md` 용어사전에 "확인 화면" 한 줄 추가 (줄 추가만).
⑦ `docs/design/design.md` "confirm_spec" 절 — 위 `editable`·아직 모름 처리 결정을 한 줄씩 추가 (자기 노드 절만).

손대지 않음: `graph/build.py`, `state/*`, 다른 노드 파일, `templates/`.

### 범위 확장 (2026-11-14 승인, `constraints.md`)

실행 검증에서 고친 항목이 다시 물어지지 않는 문제가 나와 추가했다 (아래 5절).

⑧ `builder/src/specbuilder/nodes/interview_user.py` — `reopened_ids`(아직 모름 + 지난 답 있음 = 고치기로 고른 항목).
   `render_context` 에 "사용자가 고치기로 고른 항목" 데이터 절(있을 때만), `_parse_reply` 가 그 항목에 대한 LLM 갱신을 버린다.
⑨ `builder/prompts/interview_user.md` — 그 항목은 지난 답이 있어도 `unknown` 으로 두고 다시 묻는다는 규칙 한 줄.
⑩ `builder/tests/nodes/test_interview_user.py` — 테스트 3개 추가.

## 4. 검증

1. `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check` (내가 바꾼 파일만 포맷).
2. **실행 검증 (실제 모델):** CLI 를 `claude` 로 돌린다. 스크래치 드라이버 스크립트가 출력을 읽고 질문 묶음에는 빈 줄(추천),
   첫 확인 화면에는 `1`(용도 고치기), 두 번째 확인 화면에는 빈 줄(확인)을 넣는다 → 다시 묻는 묶음이 나오는지, 산출물이 생기는지,
   `run.json` 의 `qa` 에 다시 물은 줄이 있는지 확인. LLM 호출 약 5~10회 (Max 요금제).
3. **품질 회귀 세트 before/after 는 돌리지 않는다.** 이유: 프롬프트·LLM 호출을 바꾸지 않고, confirm 경로에서는
   `generate_artifacts` 에 들어가는 State 가 이전과 같다. 위 2번이 바뀐 동작(돌아가는 경로)을 실제 모델로 확인한다.

## 5. 검증 결과

### 테스트 · 린트 (2026-11-14)

```
$ uv run pytest -q
67 passed, 13 warnings in 0.22s      # 기준선 44 → 67. 경고는 기존과 같은 langsmith DeprecationWarning (Python 3.14)
$ uv run ruff check .
All checks passed!
```
`ruff format` 은 바꾼 파일에만 돌렸다. 기존 줄의 변경이 없음을 `git diff` 로 확인.

### 실행 검증 — 실제 모델 `claude-sonnet-5-5`, CLI + 스크래치 드라이버 (`01-short`)

드라이버: 질문 묶음은 빈 줄(추천), 첫 확인 화면은 `1`(용도 고치기), 다시 묻는 묶음의 첫 질문은 "가족 셋이 같이 쓰는 가계부예요", 두 번째 확인 화면은 빈 줄.

| 시도 | 코드 | 결과 |
|---|---|---|
| 1 (2026-11-13) | ①~⑦ | **실패.** 확인 화면 표시·번호 입력은 정상. 그러나 `interview_user` 가 용도를 다시 묻지 않았다 — LLM 이 지난 답을 보고 용도를 스스로 다시 `confirmed` 로 채워(`"본인 혼자 자기 컴퓨터에서…"`) 바로 두 번째 확인 화면으로 갔다. 원인: 프롬프트 "답에 이미 분명히 나와 있으면 confirmed" + `qa` 에 지난 답이 남아 있음. 이어 `generate_artifacts` 중 CLI 가 exit 143(SIGTERM)으로 끝났다 — [추정] 환경이 프로세스를 끊은 것. 같은 코드의 뒤 실행 6건은 모두 exit 0 |
| 2 (2026-11-14 10:12~10:15) | ①~⑩ | **통과.** 용도를 고르자 용도 질문 1개 묶음이 나왔고(지난 답과 다른 선택지), 새 답 뒤 LLM 이 "가족" 에 따라 달라지는 질문 4개(쓴 사람 구분, 접속 방법, 가족 이름, 비밀번호)를 2묶음으로 더 물었다. 두 번째 확인 화면 용도 = 새 답, 이전 확정 항목 6개는 그대로. `spec.md` 가 "가족 셋(엄마, 아빠, 나)… 웹 가계부" 로 생성. LLM 호출 8, `interview_stops` = resolved 2회 |

### 품질 회귀 — 같은 모델 `claude-sonnet-5-5`, `claude -p` 헤드리스, 답 = 모든 입력 빈 줄(추천 · 확인)

- 바꾸기 전: 2026-11-14 10:11~10:14, ①~⑦ 코드(confirm_spec 있음, 프롬프트 변경 전).
- 바꾼 후: 2026-11-14 10:14~10:16, ①~⑩ 코드. 세 건 모두 "고치기로 고른 항목" 절이 입력에 없었다(고치지 않는 경로).

| 케이스 | | 질문 수 | 묶음 수 | LLM 호출 | 종료 사유 | spec.md 두 절 | spec+SKILL+AGENTS 줄 수 | 플레이스홀더·위험 명령 grep | 사용자 확정 / 맡김 |
|---|---|---|---|---|---|---|---|---|---|
| 01-short | 전 | 4 | 1 | 3 | resolved | 있음 | 180 | 없음 | 4 / 4 |
| | 후 | 5 | 2 | 4 | resolved | 있음 | 173 | 없음 | 5 / 2 |
| 02-domain | 전 | 14 | 3 | 5 | resolved | 있음 | 292 | 없음 | 17 / 0 |
| | 후 | 11 | 2 | 4 | resolved | 있음 | 205 | 없음 | 12 / 1 |
| 03-vague | 전 | 6 | 1 | 3 | resolved | 있음 | 213 | 없음 | 7 / 2 |
| | 후 | 7 | 2 | 4 | resolved | 있음 | 211 | 없음 | 8 / 1 |

- [추정] 전·후 차이는 실행마다의 흔들림이다 — 바뀐 규칙은 "고치기로 고른 항목" 절이 있을 때만 해당되고 이 경로에서는 그 절이 없다. 케이스당 1회씩이라 흔들림 폭은 재지 않았다.
- 확인 화면이 생겨도 빈 줄 파이프만으로 6건 모두 끝까지 돌았다 (exit 0).

### 산출물 인수 조건 (작업자 실행)

돌리지 않았다. 이번 변경은 `generate_artifacts`·템플릿을 바꾸지 않고, 확인 경로에서 산출물 생성 입력이 이전과 같다 — A 의 인수 조건 결과(`261112-spec-items/plan.md`)가 그대로 적용된다 [추정].

## 6. 안 한 것 / 남은 것

- 디자인 항목을 고치는 경로는 `interview_design`(F)이 다시 묻는다. F 가 같은 "고치기로 고른 항목" 처리를 해야 한다 — 지금 F 는 빈 노드라 그 경로는 실제 모델로 확인 못 했다 [미확인, F 의 범위].
- 고친 항목에 대해 LLM 이 질문을 하나도 내지 않으면 기존 계약대로 `LLMCallError` 로 멈춘다 (테스트 고정). 실제 실행에서는 일어나지 않았다.

토큰 소모 [추정]: 세션 약 15만 토큰 + 실제 `claude -p` 약 38회 (실행 검증 2건 · 품질 회귀 전 3건 · 후 3건).
