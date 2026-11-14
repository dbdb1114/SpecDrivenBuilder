# 작업 단위 H — 공통 항목 (`feat/common-items`)

제약: `constraints.md`. 설계: `docs/design/design.md` "공통 항목", "interview_user", "interview_design".

## 1. 분석

- [확정] 기준선: `develop` `2f2da92` (A~G 머지됨). `cd builder && uv run pytest -q` → 197 passed.
- [확정] 공통 항목 코드는 아직 없다. `design.md` 의 공통 항목 절과 두 노드 절에 "(2026-11-14 결정, 구현 전)" 표시.
- [확정] 두 노드 모두 한 번의 LLM 호출로 `items` + `questions` 를 받고, `_check_questions` 가 "아직 모름 항목이 있는데 질문이 없음" ·
  "물을 필요가 없는 항목을 물음" 이면 `LLMCallError` 를 낸다 → 공통 항목을 코드가 묻게 되면 이 검사에서 공통 항목 id 를 빼야 한다.
- [확정] `interview_user` 의 LLM 응답 형식 `InterviewReply` 는 `state/question_format.py`(규격 모델, 고치지 않음)에 있다.
  `interview_design` 은 노드 파일 안에 `DesignReply` 를 따로 둔 선례가 있다 → `interview_user` 도 노드 파일 안에 확장 형식을 둔다.
- [확정] `interview_design._render_context` 는 `interview_user.render_context` 를 그대로 부른다 → 공통 항목 목록 블록은
  `render_context` 안이 아니라 각 노드가 자기 영역 것만 덧붙인다 (안 그러면 디자인 노드에 기능 영역 목록이 섞인다).
- [확정] 답 반영 `apply_submission` 은 option 답의 내용에 **라벨**만, delegate 는 빈 내용을 남기고 기본 방향은 다음 LLM 호출이 채운다.
  공통 항목은 기본 방향이 고정이므로 코드가 바로 채운다 (LLM 이 덮어쓰지 못하게 LLM 의 공통 항목 갱신은 버린다 — `CODE_OWNED` 와 같은 방식).
- [확정] 고정 질문 파일의 선례: `prompts/interview_profile.json` (+ 노드가 pydantic 으로 검증해 읽음). `FakeLLM` 은 `prompts/*.md` 만 읽어 `.json` 은 영향 없음.
- [확정] `confirm_spec` · `generate_artifacts` 는 스펙 항목을 영역·결정 주체로만 다룬다 → 공통 항목도 그대로 지나간다. 고칠 것 없음.
  확인 화면에서 `basic-accessibility`(작업자)는 `editable: false`, 나머지 둘은 고칠 수 있다. 고치면 아직 모름이 되고 코드가 고정 질문을 다시 붙인다.
- [확정] CLI 는 stdin 빈 줄 = 추천 선택지(없으면 맡김). 품질 회귀는 F·G 와 같은 방식(`yes '' |` 파이프, 저장된 프로필)으로 돌릴 수 있다.

## 2. 정할 것 (선택지와 추천안)

### Q1. 공통 항목 목록의 저장 위치와 형식

1. **`builder/prompts/common_items.json` + 읽는 모듈 `src/specbuilder/common_items.py` (추천)** — `interview_profile.json` 과 같은 자리·형식.
   사용자에게 보이는 고정 문구가 코드 밖(`prompts/`)에 있고, 읽을 때 pydantic 으로 검증(id 중복·결정 주체별 필수 필드·추천 1개)한다.
2. 파이썬 상수 (`common_items.py` 안에 목록) — 타입 검사는 바로 되지만 "prompts/ 외부에 문구 금지" 규칙과 어긋난다.
3. 항목마다 파일 (`templates/common_items/<id>.md`, 공통 스킬처럼 폴더가 목록) — `templates/` 는 산출물 서식 자리라 층이 다르다.

형식 (안 1):

```json
{ "items": [
  { "id": "input-validation", "name": "잘못 입력했을 때 알려 주는 방식", "area": "function",
    "when": "사용자가 값을 직접 입력하는 곳이 있다 (글자·숫자·날짜를 적어 넣는 칸, 메시지로 받는 명령 등)",
    "decided_by": "user",
    "question": { "text": "…", "multiple": false,
                  "options": [ { "label": "사용자에게 보이는 말", "content": "작업자가 따를 내용", "recommended": true } ] },
    "default": "작업자가 따를 기본 방향" } ] }
```

- 선택지에 `content`(작업자용 내용)를 따로 둔다. 라벨("네, 넣어 주세요")만 남으면 작업자가 질문 없이 뜻을 알기 어렵다 →
  option 답이면 항목 내용은 `content`, 실행 기록(문답)에는 라벨. 직접 입력은 입력한 글 그대로, 맡김·답 없음·그만 묻기·상한은 `default`.
- 결정 주체가 작업자인 항목은 `question` 이 없다 (있으면 읽을 때 오류).

### Q2. 첫 공통 항목 3개의 문구·선택지·기본 방향 (추천안)

**`input-validation`** (용도·기능 · 사용자) — "잘못 입력했을 때 알려 주는 방식"
- 질문: "숫자 자리에 글자를 넣거나 꼭 필요한 칸을 비워 두는 것처럼 잘못 입력했을 때, 어떻게 알려 줄까요?"
- 선택지
  1. (추천) "입력한 그 자리에서 바로 알려 줘요" → 값을 넣는 즉시 그 칸 바로 옆에 무엇이 잘못됐고 어떻게 고치면 되는지 쉬운 말로 보여 준다. 잘못된 값은 저장하지 않는다.
  2. "다 입력하고 저장할 때 한꺼번에 알려 줘요" → 저장(보내기)을 누를 때 한 번에 검사해 잘못된 곳을 모두 목록으로 보여 주고, 첫 번째 잘못된 곳으로 옮겨 준다. 잘못된 값은 저장하지 않는다.
  3. "잘못된 값은 아예 입력되지 않게 막아 줘요" → 숫자 칸에는 숫자만, 날짜는 달력에서 고르는 식으로 처음부터 잘못 넣을 수 없게 만든다. 막을 수 없는 경우(빈 칸 등)는 그 자리에서 알려 준다.
- 기본 방향 = 선택지 1의 내용.

**`text-size`** (디자인 · 사용자) — "글자 크게/작게 보기"
- 질문: "화면 글자를 크게 또는 작게 바꿔 볼 수 있게 할까요?"
- 선택지
  1. (추천) "휴대폰·브라우저에서 글자를 키우면 따라 커지기만 하면 돼요" → 따로 버튼은 두지 않는다. 기기·브라우저의 글자 크기 설정과 확대(200%까지)를 따라 커져도 글자가 잘리거나 겹치지 않게 만든다.
  2. "화면 안에 글자 크기 버튼을 넣어 주세요" → 화면 위쪽에 글자 크기 버튼(작게·보통·크게)을 두고, 고른 크기를 기억해 다음에 열 때도 유지한다. 크게 해도 화면이 깨지지 않게 만든다.
  3. "처음부터 글자를 크게 해 주세요" → 기본 글자를 보통보다 크게(본문 18px 이상) 하고 버튼·누르는 곳도 크게 만든다. 기기 설정으로 더 키워도 깨지지 않게 한다.
- 기본 방향 = 선택지 1의 내용.

**`basic-accessibility`** (디자인 · 작업자, 묻지 않음) — "기본 접근성"
- 기본 방향: "고른 색 톤 안에서 글자와 바탕의 대비를 4.5:1 이상(큰 글자는 3:1 이상)으로 맞춘다. 마우스 없이 키보드(Tab·Enter·Esc)만으로 모든 기능을 쓸 수 있게 하고, 지금 고른 곳이 눈에 보이게 표시한다. 뜻이 있는 그림과 아이콘 버튼에는 화면 읽기 프로그램이 읽을 설명 글을 붙인다."

언제 넣는가: `input-validation` 은 "화면에 사용자가 글자나 숫자를 직접 쳐 넣는 칸이 있다 (파일을 올리기만 하는 프로그램은 해당하지 않는다)" (2026-11-14 회귀 뒤 좁힘 — 6절), `text-size`·`basic-accessibility` 는 "사람이 보고 누르는 화면이 있다".

## 3. 변경 요지

`common_items.py` (두 노드가 같이 쓰는 함수 — 노드가 아니라 `common_skills.py` 처럼 패키지 바로 아래):
- `load_common_items()` — json 을 읽어 검증. `render_catalog(area, items)` — LLM 입력용 데이터 블록 (id · 이름 · 언제 넣는가 · 이미 들어갔는가).
- `add_selected(items, ids, area)` — LLM 이 고른 id 중 이 영역 목록에 있고 아직 없는 것만 스펙 항목으로 추가
  (사용자 → 아직 모름 · 빈 내용, 작업자 → 맡김 · 기본 방향). 목록에 없거나 다른 영역 id 는 버린다 (한 번 잘못 고른 것으로 실행 전체를 멈추지 않는다).
- `fixed_questions(items, area)` — 아직 모름인 공통 항목의 고정 질문 초안.
- `record_answers(items, bundle, submission)` — `apply_submission` 뒤에 공통 항목의 내용을 선택지 `content`/기본 방향으로 바꾼다.
- `fill_defaults(items)` — 내용이 빈 맡김 공통 항목에 기본 방향 (그만 묻기·상한의 `delegate_open` 뒤).

`interview_user.py` · `interview_design.py`:
- LLM 응답에 `common_items: [id]`(선택, 기본 빈 목록)를 더한다 — `interview_user` 는 노드 파일 안에 `UserReply`, `interview_design` 은 `DesignReply` 에 필드 추가.
- LLM 이 낸 공통 항목 id 의 항목 갱신·질문은 버린다 (설계: "LLM 이 공통 항목의 질문을 직접 쓰면 그 응답은 버린다").
- 질문 묶음 = (용도 질문) + LLM 질문 + 고정 질문, 10개를 넘으면 고정 질문을 다음 묶음으로 미룬다 (아직 모름으로 남아 다음에 묻는다).
  `interview_design` 은 미리보기 질문이 맨 앞인 것 그대로.
- `_check_questions` 의 "질문이 없음"·"물을 필요 없음" 판정에서 공통 항목 id 를 뺀다 (LLM 질문 0개 + 고정 질문만인 묶음 허용).
- "사용자가 고치기로 고른 항목" 목록에서 공통 항목을 뺀다 — 코드가 다시 묻는다.
- LLM 호출 수는 그대로 (같은 호출이 id 만 더 고른다).

프롬프트 2개: "공통 항목" 절 추가 — 입력의 공통 항목 목록에서 조건이 요청·답으로 분명한 것의 id 만 `common_items` 에 담는다.
공통 항목의 질문·항목은 쓰지 않는다. 조건이 아직 불분명하면 고르지 않는다(다음 묶음에서 고를 수 있다).

## 4. 건드릴 파일

| 파일 | 변경 |
|---|---|
| `builder/prompts/common_items.json` | 새 파일 — 3개 항목 |
| `builder/src/specbuilder/common_items.py` | 새 파일 — 읽기·검증·위 함수들 |
| `builder/src/specbuilder/nodes/interview_user.py` | 공통 항목 고르기·고정 질문·답 반영 |
| `builder/src/specbuilder/nodes/interview_design.py` | 같음 |
| `builder/prompts/interview_user.md` · `interview_design.md` | "공통 항목" 절, 출력 예시에 `common_items` |
| `builder/tests/test_common_items.py` | 새 파일 — 실제 json 검증, 잘못된 목록 거부 |
| `builder/tests/nodes/test_interview_user.py` · `test_interview_design.py` | 테스트 추가 |
| `builder/tests/fakes/fake_llm.py` | `interview_reply` 에 `common_items` 인자 (기본 없음 — 기존 테스트 그대로) |
| `docs/design/design.md` | 공통 항목 절·두 노드 절의 "구현 전" → 구현 (자기 절만) |

## 5. 검증

1. `uv run pytest -q`, `uv run ruff check . && uv run ruff format --check .`
   - 고른 id → 항목 추가 + 고정 질문 (문구·선택지가 json 그대로) / LLM 이 쓴 공통 항목 질문·갱신은 버림 / 목록 밖·다른 영역 id 버림 /
     option → `content`, custom → 입력 글, delegate·답 없음·finish·상한 → 기본 방향 / 작업자 항목은 묻지 않고 맡김+기본 방향 /
     LLM 질문 0개 + 고정 질문만인 묶음 / 10개 초과면 다음 묶음 / 확인 화면에서 고친 공통 항목 → 고정 질문 다시 / LLM 호출 수 변화 없음.
2. 품질 회귀 — 같은 모델 `claude-sonnet-5-5` (`claude -p`), `evals/cases/` 4개 × 전(`2f2da92`)/후, CLI 끝까지(산출물까지), 답은 빈 줄(추천),
   저장된 프로필 1개(G 의 P1: 알아서) 고정. 약 50회 `claude -p` [추정: 케이스당 6~7회]. 나란히 비교:
   공통 항목이 골라졌는가(01·02·03 은 입력 있음, 03 은 화면 있음, 04 는 화면 없음 → 디자인 공통 항목 없어야 함),
   묻는 질문 수, LLM 호출 수, 산출물 `spec.md` 에 입력 오류 안내·글자 크기·접근성이 적혔는가.
3. 실행 검증은 하지 않는다 — 산출물 서식(`generate_artifacts`·템플릿)은 바뀌지 않고 스펙 항목이 하나둘 늘 뿐이다.

## 6. 검증 결과 (2026-11-14)

계획과 달라진 것: 없음. 계획 밖 파일은 건드리지 않았다.

```
$ cd builder && uv run pytest -q
223 passed, 13 warnings      # 시작 전 197 → 26개 추가 (공통 항목 모듈 9 · interview_user 12 · interview_design 5). 경고는 기존 langsmith DeprecationWarning
$ uv run ruff check . && uv run ruff format --check .
All checks passed!
73 files already formatted
```

### 품질 회귀 — 같은 모델 `claude-sonnet-5-5` (`claude -p`, 빌더 CLI 기본값), 2026-11-14

전 = `2f2da92` (`git archive` 로 뽑은 사본), 후 = 이 브랜치 작업 트리 사본. 4케이스 × 전/후 8회 전부 exit 0.
저장된 프로필 하나로 고정(사무·행정·회계 / 해 본 것 없음 / 결과만 / 알아서 / Windows · Claude Pro). 답은 전부 빈 줄(= 추천), 확인 화면도 빈 줄(= 확인).
"spec.md 언급" 은 `spec.md` 에서 정규식으로 센 횟수 — 입력 오류(잘못 입력·잘못된 값·빈 칸 …) / 글자 크기(글자 크기·확대 …) / 접근성(대비·키보드·화면 읽기 …).

| 케이스 | | LLM 호출 | 질문 수 (user / design) | 사용자 항목 | 공통 항목 | spec.md 언급 (입력 / 글자 / 접근성) |
|---|---|---|---|---|---|---|
| 01-short | 전 | 8 | 5 / 1 | 8 | — | 2 / 1 / 0 |
| | 후 | 8 | 4 / 4 | 8 | input-validation 확정 · text-size 확정 · basic-accessibility 맡김 | 3 / 11 / 6 |
| 02-domain | 전 | 9 | 4 / 3 | 10 | — | 0 / 0 / 4 |
| | 후 | 8 | 6 / 4 | 12 | 같음 | 3 / 8 / 11 |
| | 후 2 (`when` 좁힘) | 9 | 9 / 4 | 14 | text-size 확정 · basic-accessibility 맡김 (input-validation 안 고름) | 0 / 7 / 10 |
| 03-vague | 전 | 8 | 5 / 1 | 8 | — | 0 / 0 / 0 |
| | 후 | 10 | 12 / 4 | 16 | 같음 (input-validation 은 2번째 묶음에서 고름) | 4 / 7 / 7 |
| 04-no-screen | 전 | 10 | 6 / 0 | 7 | — | 0 / 0 / 0 |
| | 후 | 9 | 2 / 0 | 4 | 없음 | 0 / 0 / 0 |

- **고정 문구가 흔들리지 않는다:** 화면 있는 3케이스 모두 `input-validation`·`text-size` 질문 문장과 선택지가 json 그대로 나갔고,
  항목 내용에는 라벨이 아니라 작업자용 문장(`content`)이 들어갔다 [확정: run.json]. `basic-accessibility` 는 묻지 않고 기본 방향으로 맡겨졌다.
- **고르는 판단:** 화면 없는 04 는 디자인 공통 항목을 고르지 않았고(`screen` 판정 그대로), 입력 칸도 없어 `input-validation` 도 고르지 않았다.
  03 은 1번째 묶음에서 고르지 않고 기능을 들은 뒤 2번째 묶음에서 골랐다 — 프롬프트의 "조건이 분명할 때만" 대로.
  LLM 이 공통 항목과 같은 내용을 다른 id 로 만든 경우는 없었다 [확정: 8회 항목 id 목록].
- **전에는 빠졌던 것:** 전에는 입력 오류 안내가 01 에만 2곳, 글자 크기는 01 에 1곳, 접근성은 02 에만 나왔다 (프로그램마다 들쭉날쭉 — 설계가 공통 항목을 둔 이유).
  후에는 화면 있는 3케이스 모두 셋 다 `spec.md` 에 들어갔다.
- **질문 수 · LLM 호출:** 공통 항목 몫으로 화면 있는 케이스마다 질문이 2개(기능 1 · 디자인 1) 는다. 묶음이 늘지는 않았다 — 고정 질문이 그 묶음 뒤에 붙는다.
  LLM 호출 수는 케이스마다 ±1~2 로 방향이 없다(01 같음, 02·04 −1, 03 +2) [추정: 케이스당 1회라 실행마다의 변동 — 03 후는 기능 묶음이 3개로 늘어서
  질문 12개였고, 그중 공통 항목 질문은 1개뿐이다].
- **경계 사례 (판단 필요):** 02(엑셀 파일을 넣는 프로그램)도 `input-validation` 을 골랐다. 거래처별 열 위치를 사용자가 정해 두는 화면이 있어 조건에 맞기는 하지만,
  고정 문구("숫자 자리에 글자를 넣거나 칸을 비워 두는 것처럼")와 내용("그 칸 바로 옆에")은 직접 적는 칸을 전제해서
  "넣은 엑셀 파일의 값이 잘못됐을 때"는 다루지 못한다. `when` 을 "사용자가 화면이나 메시지에 값을 직접 적어 넣는 곳이 있다 (파일을 넣기만 하는 것은 아님)" 처럼 좁힐지,
  파일 입력용 공통 항목을 따로 둘지는 문구를 정한 사람의 판단이라 고치지 않았다.
  → **결정 (2026-11-14, 사용자):** `when` 을 "화면에 사용자가 글자나 숫자를 직접 쳐 넣는 칸이 있다 (파일을 올리기만 하는 프로그램은 해당하지 않는다)" 로 좁혔다.
  02 만 같은 모델·같은 프로필·같은 답 방식으로 다시 돌린 결과가 표의 "후 2" — `input-validation` 을 고르지 않았고 디자인 공통 항목은 그대로 들어갔다.
  질문 수 차이(6 → 9)는 기능 묶음이 2개로 늘어서다 [추정: 실행마다의 변동 — 늘어난 질문은 매입·매출 구분, 집계 나누기 같은 업무 규칙이고 공통 항목과 무관].
  01·03·04 는 다시 돌리지 않았다 (사용자 지시: 02 만). 01·03 은 화면에 직접 쳐 넣는 칸이 있어 같은 결과일 것으로 본다 [추정].

### 남은 것

- 파일 입력용 공통 항목(올린 파일의 값이 잘못됐을 때 알려 주는 방식)은 이번에 만들지 않는다 (2026-11-14 사용자 결정). 02 같은 "파일을 올리기만 하는" 프로그램은 지금 이 결정을 LLM 이 뽑는 항목에 맡긴다.

산출물 파일: `/private/tmp/claude-501/-Users-yujeonghyeon-orca-workspaces-SpecDrivenBuilder-feat-common-items/fda7e98a-debc-4038-91ac-0a9d4d5e6c7b/scratchpad/{before,after}/builder/output/` (임시 폴더 — 재부팅하면 지워진다).

### 실행 검증

하지 않음 (계획 5-3) — 산출물 서식(`generate_artifacts`·템플릿)은 바뀌지 않고 스펙 항목이 늘 뿐이다.

### 토큰 소모

- [추정] 세션 약 20만 토큰 (문서·코드 읽기 + 구현 + 회귀 분석). 품질 회귀 9회 = `claude -p` 79회 (run.json `llm_calls` 합, 요금제 내).
