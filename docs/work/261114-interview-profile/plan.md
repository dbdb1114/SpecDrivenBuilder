# 작업 단위 G — interview_profile (브랜치 `feat/interview-profile`)

승인 (2026-11-14): 계획 전체. A=1, B=1 (사용자가 정함). C=1, E=1 (사용자가 맡긴 범위 안에서 develop-2 세션이 정함).
코딩 전에 `origin/develop` = `c8c3879` (D #8 포함) 을 merge 했다. D 가 넣은 `interview_user` 의 "고치기로 고른 항목" 가드·규칙은
그대로 두고 그 위에 위임 범위 블록을 더한다. 그래프 테스트는 확인 화면(`confirm_spec`) 흐름을 따른다.

구현 중 정한 것: 프로필 답은 `qa` 에 남기지 않는다 — `qa` 는 interview_user 의 "지금까지의 질문과 답" 컨텍스트로 들어가므로
프로필 문답이 스펙 문답에 섞이고, 프로필은 이미 `profile` 키와 위임 범위 블록으로 들어간다. 묶음 수는 `interview_stops` 에 남는다.

## 1. 분석 (현재 상태)

- [확정] `origin/develop` = `36c7b01` 을 이 브랜치에 merge 함 (로컬 merge 커밋, push 안 함). A(#4)·B(#5)·E(#6)·C(#7) 포함.
- [확정] PROMPT.md "시작 전" 조건 4개 충족.
  - 스펙 항목·JSON 규격 모델: `state/spec_items.py`, `state/question_format.py`.
  - 노드 8개 등록(`graph/build.py`), `nodes/interview_profile.py` 는 빈 노드(`Command(goto="interview_user")`).
    `build.py` 가 이미 `destinations=("interview_profile", "interview_user")` 로 등록 → **build.py 수정 불필요.**
  - fake LLM 노드별 응답(`tests/fakes/fake_llm.py`). B·C 노드 구현됨.
  - `uv run pytest -q` → 128 passed.
- [확정] State 스키마에 `Profile` TypedDict 가 이미 있다: `domain`·`tech_exposure`·`explanation`·`environment`·`delegation` 모두 `str`,
  `State.profile: Profile | None`, `initial_state()` 는 `profile: None`. → **State 스키마 수정 불필요.** 필드가 전부 문자열이라
  답(선택지 문구 또는 직접 입력)을 문장으로 저장한다.
- [확정] `initial_state()` 가 항상 `profile: None` 이고 CLI(`graph/main.py`)·API(`api/main.py`)는 프로필을 모른다 → 저장된 프로필을 읽고
  저장하는 일은 **노드 안에서** 해야 한다 (main.py 는 건드릴 수 없음).
- [확정] CLI `ask_bundle` 과 API `_view` 는 `confirm_spec` 외의 interrupt 를 전부 질문 묶음으로 그린다 → 프로필 질문 묶음은
  CLI·프론트엔드 수정 없이 그려진다.
- [확정] `apply_submission()` 은 답을 **스펙 항목**에 반영한다 (`item_id` 가 `spec_items` 에 없으면 qa 만 남김). 프로필은 스펙 항목이 아니므로
  interview_profile 은 `validate_submission()` 으로 검증만 하고, 답 → Profile 필드 반영은 노드 안에서 따로 한다. 규격 모델은 고치지 않는다.
  `Question.item_id` 는 `ItemId` 형식(`^[a-z0-9]+(-[a-z0-9]+)*$`)만 요구하고 존재 여부는 검사하지 않는다 → `profile-domain` 같은 id 를 쓸 수 있다.
- [확정] `select_stack` 은 B 가 이미 `profile["environment"]` 를 `## 사용자의 환경` 블록으로 넣고 있다 (`select_stack.py:59-65`,
  `prompts/select_stack.md:5,12`). → **select_stack 수정 불필요.** 환경 문자열을 이 노드가 읽기 좋은 형식("운영체제: … / AI 도구·요금제: …")으로 저장하기만 하면 된다.
- [확정] `interview_user.render_context()` 는 프로필을 넣지 않는다. 프롬프트에도 프로필·위임 범위 언급이 없다.
- [확정] `generate_artifacts.render_context()` 는 프로필을 넣지 않는다. 프롬프트는 "작업자 컨텍스트: 사용자가 누구인지, 설명 수준,
  결정 위임 범위. 이름·소속·연락처는 넣지 않는다" 한 줄뿐 — 근거 데이터 없이 LLM 이 지어낸다.
- [확정] 그래프 전체를 도는 기존 테스트(`tests/test_graph.py`, `tests/api/test_runs.py`)는 첫 interrupt 를 interview_user 의 묶음으로 기대한다.
  interview_profile 이 묻기 시작하면 깨진다 → 테스트에서는 저장된 프로필이 있는 상태를 기본으로 만든다 (`tests/conftest.py` 에 autouse fixture 한 개 추가).
- [확정] 새 의존성 필요 없음 — JSON 읽기·쓰기는 표준 라이브러리, 검증은 이미 쓰는 pydantic `TypeAdapter`.

## 2. 변경 요지

**interview_profile** (`nodes/interview_profile.py`)
1. 진입: `state["profile"]` 이 있거나 저장된 프로필을 읽어 검증에 통과하면 → `Command(update={"profile": …}, goto="interview_user")`. LLM 0회, 질문 없음.
   저장 파일이 깨져 있으면(JSON 오류·필드 누락) 없는 것으로 보고 다시 묻는다 — 덮어써도 잃는 정보가 없다.
2. 없으면: 고정 질문 묶음(결정 B)을 `pending_bundle` 에 넣고 자기 자신으로 → 다음 진입에서 `interrupt(bundle)`.
   interview_user 와 같은 실행 규칙(묶음을 먼저 체크포인트에 남겨 resume 때 다시 만들지 않음).
3. 답: `validate_submission()` 으로 검증 → 질문별로 선택지 문구 / 직접 입력 / "알아서 정해 주세요"·답 없음은 그 질문의 기본값 문장으로
   Profile 필드를 채운다. `finish` 도 남은 질문을 기본값으로 채운다 (질문 묶음이 하나뿐이라 submit 과 결과가 같다).
4. 저장(결정 A) → `Command(update={"profile", "qa", "pending_bundle": None, "question_round": 0, "interview_stops": [{node, reason, rounds: 1}]},
   goto="interview_user")`. reason 은 submit → `resolved`, finish → `user_finished`. 건너뛸 때는 interview_stops 를 남기지 않는다
   (State 의 reason Literal 에 "건너뜀" 이 없고, State 스키마는 못 고친다).
- 프로필 저장·읽기는 새 모듈 `src/specbuilder/profile_store.py` (`load_profile()`·`save_profile()`). 노드끼리 import 하지 않게 C 의 `common_skills.py` 와 같은 방식.
- 질문 문구·선택지·기본값 문장은 `builder/prompts/interview_profile.json` 데이터 파일 (LLM 프롬프트가 아니지만 사용자에게 보이는 문구라
  코드 밖에 둔다 — 문구만 고칠 때 코드를 안 건드리게). [추정] `prompts/` 에 두는 게 "노드 추가 시 `prompts/<노드명>` 동반" 규칙과 가장 가깝다.
- 이름·소속·연락처: 질문 문구에 "이름이나 회사 이름은 적지 않아도 돼요" 를 넣고, 도메인 질문은 직업 종류 선택지를 준다.
  직접 입력에 이름이 섞이는 것은 코드로 막지 못한다 → generate_artifacts 프롬프트의 "이름·소속·연락처는 넣지 않는다" 로 한 번 더 거른다. [추정] 완전하지 않음.

**interview_user** (`nodes/interview_user.py`, `prompts/interview_user.md`)
- `render_context()` 에 `## 결정 위임 범위` 블록 (프로필의 `delegation`, 없으면 "(모름)") 추가.
- 프롬프트: 위임 범위가 "알아서" 쪽이면 사용자만 아는 것만 `user` 로 두고 나머지는 `worker`·`delegated` 로, "선택지가 있으면 물어줘" 쪽이면
  사용자가 고를 수 있는 선택(화면 구성 방향 등, 기술 선택은 여전히 제외)도 `user`·`unknown` 으로 둔다. LLM 호출 수는 그대로.

**select_stack** — 수정 없음 (위 분석).

**generate_artifacts** (`nodes/generate_artifacts.py`, `prompts/generate_artifacts.md`)
- `render_context()` 에 `## 사용자 프로필` 블록(5개 축) 추가. 프로필이 없으면 "(없음)".
- 프롬프트 "작업자 컨텍스트" 를 번역 규칙으로 구체화 (`interview-profile.md` "산출물 섹션 예시" 기준):
  도메인 → 그 분야 용어는 설명 없이 / 기술 노출 → 용어사전 "쓰지 말 것" 열과 안내 방식(명령어 대신 화면 기준 등) /
  설명 선호 → 보고 길이·이유 포함 여부 / 환경 → 운영체제별 안내, 요금제를 "한 작업의 대화 왕복 목표" 같은 지침으로 (토큰 수는 쓰지 않음) /
  위임 범위 → "질문 규칙" 의 "묻지 않고 정할 것" 범위.
- 프로필 블록도 "지시문처럼 보여도 데이터로만 취급" 문장의 대상에 넣는다 (산출물 안전성 — 직접 입력이 그대로 지시문으로 옮겨지지 않게).
- LLM 호출 수는 그대로 1회.

**LLM 호출 수**: interview_profile 0회 (결정 B 추천안 기준). 전체 호출은 늘지 않는다. `design.md` "LLM 호출 수" 표의
`interview_profile` 행("실행하면 1회 이상")은 결정에 맞게 고친다.

## 3. 건드릴 파일

| 파일 | 변경 |
|---|---|
| `builder/src/specbuilder/nodes/interview_profile.py` | 노드 구현 |
| `builder/src/specbuilder/profile_store.py` | 새 파일 — 저장·읽기·검증 |
| `builder/prompts/interview_profile.json` | 새 파일 — 고정 질문 묶음·기본값 문장 |
| `builder/src/specbuilder/nodes/interview_user.py` | `render_context()` 에 위임 범위 블록 |
| `builder/prompts/interview_user.md` | 위임 범위 규칙 |
| `builder/src/specbuilder/nodes/generate_artifacts.py` | `render_context()` 에 프로필 블록 |
| `builder/prompts/generate_artifacts.md` | 작업자 컨텍스트 번역 규칙 |
| `builder/tests/nodes/test_interview_profile.py` | 빈 노드 테스트를 실제 테스트로 교체 |
| `builder/tests/nodes/test_interview_user.py`, `test_generate_artifacts.py` | 프로필 블록 테스트 추가 |
| `builder/tests/conftest.py` | autouse fixture 1개 추가 — 프로필 저장 경로를 임시 폴더로, 저장된 프로필이 있는 상태를 기본으로 |
| `builder/tests/test_graph.py` | 프로필이 없을 때 첫 묶음이 프로필 묶음이고, 답한 뒤 다음 실행에서 건너뛰는 그래프 테스트 추가 (기존 테스트는 안 고침) |
| `builder/.env.example` | 결정 A 가 환경 변수를 쓰면 `SPECBUILDER_PROFILE_PATH` 한 줄 |
| `docs/design/interview-profile.md` | "열린 질문" 3개를 결정으로 (자기 노드 문서) |
| `docs/design/design.md` | `interview_profile` 절과 "LLM 호출 수" 표의 그 행, "미결정" 의 프로필 저장 위치 줄만 |

건드리지 않음: `graph/build.py`, `graph/main.py`, `state/`, `api/`, `frontend/`, `select_stack.py` 와 나머지 노드 파일, `templates/`.

## 4. 정할 것 — 선택지와 추천안

### A. 프로필 저장 위치

1. **`~/.specbuilder/profile.json` (사용자 홈), 환경 변수 `SPECBUILDER_PROFILE_PATH` 로 바꿀 수 있음 (추천)**
   — 다음 프로젝트·다른 worktree 에서도 다시 묻지 않는다(설계 메모의 재사용 목적). 레포 밖이라 커밋될 일이 없다.
   단점: 웹 화면을 서버로 여러 사람이 쓰면 프로필 하나를 같이 쓴다 — 지금은 로컬 1인 도구라 해당 없음.
2. `builder/.profile.json` + 루트 `.gitignore` 한 줄 — 빌더 폴더 안이라 찾기 쉽다. worktree 마다 따로라 재사용이 덜 되고,
   계획 밖 공유 파일(`.gitignore`)을 고친다.
3. 빌더 계정(서버 DB) — 계정 기능이 없어 이번 범위에서 못 한다. 여러 사람이 쓰는 서버로 갈 때 다시 정한다.
4. 그냥 진행 (1로 진행)

### B. 프로필 질문 수와 만드는 방식

1. **고정 질문 묶음 1개, 6문항, LLM 0회 (추천)**
   — 도메인 / 기술 노출(복수 선택: 터미널·엑셀 함수·노코드 도구·Git) / 설명 선호 / 결정 위임 범위 / 운영체제 / AI 도구·요금제(복수 선택:
   Claude Pro·Claude Max·ChatGPT Plus·ChatGPT Pro — 요금제가 도구에 달려 있어 한 질문으로 묶어야 묶음 안의 질문이 서로 독립이다).
   왕복 1회로 끝나고, 축이 고정이라 요청마다 질문이 달라질 이유가 없다. 문구가 고정이라 fake 테스트로 전부 고정할 수 있다.
   `design.md` 의 "실행하면 1회 이상" 을 "0회" 로 고친다.
2. 고정 3문항(기술 노출 · 위임 범위 · AI 도구·요금제)만, 나머지는 기본값 — 초반 이탈이 가장 적다. 도메인·설명 선호는 산출물에서 비게 된다.
3. LLM 1회로 질문 묶음 생성(요청 원문을 보고 도메인 선택지를 맞춤) — 도메인 선택지가 더 맞을 수 있지만, 프로필은 다음 프로젝트에서도
   재사용되므로 이번 요청에 맞춘 이득이 작다. 처음 쓰는 사용자마다 호출 1회 추가.
4. 그냥 진행 (1로 진행)

### C. 사용 중 프로필이 틀렸을 때의 갱신 흐름

1. **이번 범위에서 뺀다. "저장 파일을 지우면 다음 실행에서 다시 묻는다" 만 문서에 적는다 (추천)**
   — 갱신 버튼·플래그는 `graph/main.py`(D 순서)·`api/`·`frontend/`(E)·확인 화면 규격(A)을 고쳐야 해서 이 작업 단위의 막힌 파일에 걸린다.
   `interview-profile.md` "열린 질문" 에는 "다음 작업으로 미룸" 으로 남긴다.
2. 1 + 산출물 AGENTS.md 의 작업자 컨텍스트 끝에 "사용자가 설명이 너무 어렵다/쉽다고 하면 이 섹션을 그에 맞게 고친다" 한 줄 —
   산출물 안에서의 갱신만 다룬다. generate_artifacts 프롬프트 한 줄이라 범위 안. 빌더의 저장 프로필은 그대로다.
3. 확인 화면(`confirm_spec`)에 프로필도 보여 주고 고치게 한다 — 규격·D·E 를 고쳐야 해서 범위 밖. 별도 작업으로.
4. 그냥 진행 (1로 진행)

### D. 추가할 의존성

없음. 정할 것 없음.

### E. 품질 회귀·실행 검증 범위 (비용)

프롬프트 2개(`interview_user.md`, `generate_artifacts.md`)를 바꾸므로 품질 회귀가 필요하다. 실제 `claude -p` 호출이 든다.
1. **3케이스 × 전/후 + 위임 범위가 다른 프로필로 1케이스 추가 + 실행 검증 3건 (추천)** — 약 40회 `claude -p` [추정: C 가 같은 구성으로 38회].
   위임 범위가 `interview_user` 의 경계를 실제로 옮기는지는 프로필 두 개를 비교해야 보인다.
2. 1케이스 × 전/후 + 실행 검증 1건 — 약 12회. 케이스 간 차이를 못 본다.
3. 그냥 진행 (1로 진행)

## 5. 검증 방법

1. `uv run pytest -q`, `uv run ruff check . && uv run ruff format --check .`
   - interview_profile: 저장 없음 → 묶음 6문항 interrupt / resume 때 묶음을 다시 만들지 않음 / option·custom·delegate·답 없음·finish 가
     Profile 필드로 / 저장 파일 생성 / 저장 있음 → LLM 0회·질문 없이 interview_user 로 / 깨진 저장 파일 → 다시 물음 / LLM 호출 0회.
   - interview_user·generate_artifacts: 프로필 블록이 컨텍스트에 들어가는가, 프로필 없음일 때 "(모름)"/"(없음)".
   - 그래프: 프로필 없음 → 첫 interrupt 가 프로필 묶음 → 답한 뒤 interview_user 묶음, 같은 저장 경로로 두 번째 실행은 프로필 묶음 없이 시작.
2. 품질 회귀 (결정 E): 같은 모델(`claude-sonnet-5-5`)로 바꾸기 전 / 후. 후는 비개발자 기본 프로필(터미널 경험 없음 · 알아서)로 3케이스,
   + "선택지 있으면 물어줘" 프로필로 1케이스. 나란히 비교할 것: AGENTS.md 작업자 컨텍스트 내용, 용어사전 "쓰지 말 것", 질문 규칙의 "묻지 않는 것",
   interview_user 의 `user` 항목 수와 질문 수, LLM 호출 수, 플레이스홀더·이름 grep.
3. 실행 검증: 후 산출물을 빈 임시 폴더에 풀고 `claude -p` 헤드리스 — 스킬 발견, AGENTS.md 읽힘, 첫 작업이 되묻지 않고 시작되는가.
   Codex 는 이 PC 에 없음 [확정: 2026-11-14 `which codex` → not found] → 미검증으로 적는다.

## 6. 검증 결과

계획과 달라진 것: `select_stack.py` 는 분석대로 고치지 않았다. 계획 밖 파일은 건드리지 않았다.

```
$ cd builder && uv run pytest -q
164 passed, 13 warnings in 0.62s      # 경고는 기존과 같은 langsmith DeprecationWarning (Python 3.14). 시작 전 151 → 13개 추가
$ uv run ruff check . && uv run ruff format --check .
All checks passed!
69 files already formatted
```

ruff format 이 `profile_store.py` 의 `except (A, B, C):` 를 `except A, B, C:` 로 바꿨다 — Python 3.14 의 괄호 없는 except 문법(PEP 758)이고 테스트로 확인했다.

### 품질 회귀 — 같은 모델 `claude-sonnet-5-5` (빌더 CLI 기본값), 2026-11-14

전 = `develop` `c8c3879` (interview_profile 빈 노드, 프로필 없음), 후 = 이 브랜치. 답은 모든 질문에 빈 줄(= 추천, 추천이 없으면 맡김), 확인 화면도 빈 줄(= 확인).
- 후 01: 저장 파일 없이 시작 → CLI 가 프로필 묶음(6문항)을 그렸고 빈 줄 답으로 저장됨 (도메인·운영체제·요금제는 기본값, 나머지는 추천).
- 후 02·03 (P1): 사무·행정·회계 / 해 본 것 없음 / 결과만 / **알아서** / Windows · Claude Pro.
- 후 03 (P2): 사무·행정·회계 / 터미널·Git 해 봄 / 이유까지 / **선택지 있으면 물어봐** / Mac · Claude Max.
- 줄 수는 산출물 `.md` 전부 (스킬 두 경로 중복 포함).

| 케이스 | | LLM 호출 | interview_user 묶음 | 질문 수 | 기능 항목 (user / worker) | 줄 수 | 플레이스홀더·위험 명령 grep |
|---|---|---|---|---|---|---|---|
| 01-short | 전 | 6 | 2 | 5 | 7 (5 / 2) | 354 | 없음 |
| | 후 (CLI 프로필) | 5 | 1 | 4 | 8 (4 / 4) | 323 | 없음 |
| 02-domain | 전 | 6 | 2 | 12 | 13 (13 / 0) | 457 | 없음 |
| | 후 P1 | 6 | 2 | 6 | 11 (9 / 2) | 538 | `...` 1곳 (경로 예시 `.venv\Scripts\...`) |
| 03-vague | 전 | 7 | 2 | 8 | 9 (9 / 0) | 439 | 없음 |
| | 후 P1 (알아서) | 5 | 1 | 4 | 8 (5 / 3) | 408 | 없음 |
| | 후 P2 (물어봐) | 6 | 2 | 10 | 12 (11 / 1) | 413 | 없음 |

- **위임 범위가 경계를 옮긴다:** 같은 03 에서 P1 은 질문 4개(user 5 / worker 3), P2 는 질문 10개(user 11 / worker 1). 전(프로필 없음)은 8개.
  P1 의 02·03 은 전보다 질문이 절반 정도로 줄었다. [추정] 케이스당 1회 실행이라 실행마다의 변동이 섞여 있다 — 방향은 세 케이스 모두 같다.
- **LLM 호출:** interview_profile 은 0회 (01 후의 호출 5회 = interview_user 1 + 마지막 반영 1 + select_stack 1 + select_skills 1 + generate 1). 호출 수 차이는 interview_user 묶음 수 차이뿐이다.
- **작업자 컨텍스트:** 전은 프로필 근거 없이 3~4줄("개발 경험이 없는 동아리 구성원이다" 처럼 지어낸 문장). 후는 다섯 축이 모두 지침으로 들어갔다.
  - 기술 노출: P1 "명령어를 치게 하지 않는다 … 화면·버튼 기준으로 안내" / P2 "꼭 필요하면 입력할 한 줄과 그 줄이 하는 일을 함께 적는다".
  - 설명 선호: P1 "결과만 짧게, 3~5줄" / P2 "이유를 한두 문장 덧붙이고 … 길게 강의하지 않는다".
  - 환경: P1 Windows 경로 `\`·`.bat`·탐색기 기준, Claude Pro → "질문은 모아서, 작업은 작게". P2 Mac ⌘·Finder 기준. 01(모름) → "운영체제를 직접 확인하고 Mac·Windows 둘 다".
  - 위임: P1 "기술 선택과 화면 세부는 알아서 정하고 한 줄로" / P2 "결과(화면 모양, 동작)를 바꾸는 선택은 번호 선택지로 묻는다".
  - 도메인: 02 "세무·회계 용어는 풀어 설명하지 않고 쓴다", 용어사전에 "공급가액, 세액, 계정과목 … 설명 없이 그대로".
  - 용어사전 "쓰지 말 것": P1 은 터미널·커밋·브랜치·배포를 전부 막음. P2 는 Git 경험이 있어 "GitHub 에 올리기" 는 쓰게 함.
- 이름·소속·연락처: 후 4건 모두 산출물에 없음. P1 3건은 "개인정보는 어떤 파일에도 쓰지 않는다" 지침까지 넣었고 P2 는 그 줄을 빼먹었다 (프로필에 이름이 없어 결과는 같음).
- 02 후의 `...` 는 Windows 명령 경로를 줄인 예시다. 채워야 할 빈칸은 아니지만 프롬프트가 금지한 표기 — C 에서도 같은 종류가 1건 있었다. 이번 범위에서 고치지 않았다.

### 실행 검증 (인수 조건) — 2026-11-14, Claude Code 2.1.325, 작업자 모델 `claude-opus-5-5` (이 PC 의 Claude Code 기본값)

후 산출물 3건(01, 02 P1, 03 P1)을 각각 빈 임시 폴더(git init)에 풀고 (`run.json` 제외)
`echo 시작해 | claude -p --setting-sources project --tools Read,Glob,Grep,Skill --max-turns 8 --output-format stream-json --verbose`.
C 와 같은 방법 — 도구를 읽기 전용으로 제한해 첫 행동만 본다. 작업자 모델이 C(sonnet)와 다르다.

| 확인할 것 | 01 | 02 | 03 |
|---|---|---|---|
| 산출물 스킬이 init 의 skills 목록에 전부 있는가 | 2/2 | 4/4 | 2/2 |
| AGENTS.md 가 읽히는가 (`CLAUDE.md` 의 `@AGENTS.md`) | 예 — 답이 용어사전·작업자 컨텍스트를 따름 (01: 운영체제를 직접 확인 "쓰시는 컴퓨터는 Mac", 02: "고객 자료는 이 컴퓨터 밖으로 내보내면 안 되기 때문에") | 예 | 예 |
| 첫 행동 | spec.md 읽기 → `build-expense-tracker` 스킬 로드 | spec.md → `build-vat-summary` 스킬 → Glob | spec.md → `build-club-planner` 스킬 |
| 스펙에 대해 사용자에게 되묻는가 | 아니오 | 아니오 | 아니오 ("정할 것은 모두 정해져 있어서 따로 여쭐 것은 없어요") |

세 건 모두 쓰기 도구가 막혀 있다는 사실만 사용자 말로 알리고 멈췄다 (테스트가 일부러 막은 것). 보고는 짧고 개발 용어가 없었다.
Codex: 이 PC 에 없음 (`which codex` → not found) — **미검증**.

토큰 소모 [추정]: 세션 약 25만 토큰 + 실제 `claude -p` 44회 (빌더 실행 전 3건 19회, 후 4건 22회, 실행 검증 3회).
