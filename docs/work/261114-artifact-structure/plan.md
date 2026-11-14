# 작업 단위 J — 산출물의 폴더 구성 (`feat/artifact-structure`)

승인 (2026-11-14): 2-1~2-4 추천안. 3 의 두 파일(공통 스킬 `verify-before-report`, 프론트엔드 `DonePage`)도 `docs/spec.md` 로 고친다.

## 1. 분석

- [확정] 산출물은 지금 루트에 `spec.md` · `AGENTS.md` · `CLAUDE.md` + 스킬(`.claude/skills`, `.agents/skills`)뿐이다
  (`nodes/generate_artifacts.py` `DOC_FILES`). LLM 1회 호출, `=== FILE: <이름> ===` 구분선으로 받는다.
- [확정] 기술 스펙 항목의 내용은 `선택:` / `버전:` / `이유:` (+ `verify_stack` 이 붙이는 `검증:`) 줄 형식이다 (`registry/refs.py`).
  `verify_stack` 은 `검증:` 줄만 바꾸고 나머지 줄은 그대로 둔다 (`with_verify_line`). 스펙 항목 모델은 `content: str` 하나.
- [확정] `select_stack` 은 기술 항목을 매번 통째로 다시 낸다. 프로그램이 어떤 부분으로 이뤄지는지는 지금 어디에도 없다.
- [확정] `confirm_spec` 은 기술 항목의 `content` 를 그대로 확인 화면에 싣는다 — 줄이 하나 늘면 화면에도 보인다.
- [확정] `spec.md` 경로에 기대는 곳 (`docs/spec.md` 로 옮기면 영향):
  - 테스트 `tests/test_graph.py:48`, `tests/test_main.py:74`, `tests/api/test_runs.py:127`, `tests/fakes/fake_llm.py:10`
  - 공통 스킬 `templates/skills/verify-before-report/SKILL.md:3,19` (+ 스냅샷) — `spec.md` 를 이름으로 가리킨다
  - 프론트엔드 `frontend/src/pages/DonePage.tsx:9,30,44` — 설명 문구, 안내 문장, 미리보기가 `artifacts["spec.md"]` 를 읽는다
- [확정] 템플릿 스냅샷 테스트(`tests/templates/test_templates.py`)는 새 스킬 서식과 공통 스킬만 본다. 폴더별 문서용 템플릿은 없다.
- [확정] 품질 회귀 세트는 4건 (`01-short`, `02-domain`, `03-vague`, `04-no-screen`). 04 는 화면 없는 스크립트형이라
  "부분이 하나도 없는 산출물" 경로를 확인할 수 있다.

## 2. 계획 단계에서 정할 것 (선택지와 추천)

### 2-1. 프로그램의 부분을 기술 스펙 항목에 적는 형식

1. **(추천) 기술 항목마다 `부분:` 줄** — `select_stack` 응답의 기술 항목에 `parts: ["frontend" | "backend" | "database"]`(0개 이상)를 받고,
   내용에 `부분: 화면, 서버` 줄로 적는다. 빌더 코드가 모든 기술 항목의 `부분:` 줄을 모아 폴더를 정한다.
   결과: 폴더별 `AGENTS.md` 에 "그 폴더에 해당하는 기술 항목" 만 넘길 수 있다. 런타임처럼 여러 부분이 같이 쓰는 항목은 `parts` 를 비운다.
   `버전:` 줄과 같은 방식이라 스펙 항목 모델을 고치지 않는다.
2. 별도 기술 항목 하나(`tech-parts`, "프로그램의 부분") — 응답 최상위에 `parts` 하나. 결과: 단순하지만 어느 기술이 어느 폴더 것인지 모른다.
3. 네가 정해

판정 기준(프롬프트에 적음): **부분 = 코드가 따로 사는 폴더.** 화면과 서버를 한 프레임워크로 만들면(Next.js 등) 화면 하나로 적는다.
데이터베이스는 표(테이블)를 설계하는 저장소가 있을 때만(SQLite 파일 포함). 엑셀·CSV·JSON 파일에 저장하면 넣지 않는다.
스크립트 하나짜리 프로그램은 부분이 없다 → 루트 문서와 `docs/` 만 받는다.

### 2-2. 구조도의 깊이와 표기

1. **(추천) LLM 이 쓰고 코드가 확인** — 루트 `AGENTS.md` 의 `## 구조` 절에 코드블록으로, 이 레포 루트 `AGENTS.md` "구조" 와 같은 꼴
   (`경로/   한 줄 설명`), 위에서 **두 단계**까지. 빌더가 넣는 파일(루트 문서, `docs/spec.md`, 폴더별 `AGENTS.md`, 스킬 폴더)과
   작업자가 만들 코드 폴더의 첫 단계(예: `frontend/src/`)까지. 넣을 폴더 목록은 코드가 계산해 입력에 준다.
   코드는 `## 구조` 절이 있는지, 넣은 폴더가 모두 구조도에 나오는지를 확인하고 아니면 `LLMCallError`.
2. 코드가 첫 단계 트리를 고정 생성하고 LLM 은 설명만 — 결과: 틀은 확실하지만 두 번째 단계(프레임워크마다 다름)를 못 그린다.
3. 네가 정해

### 2-3. `database/AGENTS.md` 에 담을 규칙의 범위

1. **(추천) 스키마·마이그레이션과 데이터 안전만** — 구조(스키마·마이그레이션 파일 위치), 명령어(마이그레이션 적용·처음부터 다시 만들기),
   코드 규칙(이름 규칙, 마이그레이션은 추가만 하고 지난 것을 고치지 않음), 하지 말 것(사용자 기록을 지우는 변경을 묻지 않고 실행,
   접속 비밀번호를 파일에 적기). 질의·ORM 코드 규칙은 그 코드가 사는 `backend/`(또는 `frontend/`) 쪽에 둔다.
2. 질의·ORM 규칙까지 — 결과: `backend/AGENTS.md` 와 겹쳐 작업자가 어느 쪽을 따를지 갈린다.
3. 네가 정해

### 2-4. 완료 화면에 구조도를 보여 줄지

1. **(추천) 이번에는 보여 주지 않는다** — 완료 화면은 이미 파일 목록을 탭으로 보여 준다. 구조도 화면은 프론트엔드 작업이라 J 범위 밖.
2. 보여 준다 — 결과: `frontend/` 를 고쳐야 해서 범위가 넓어진다.
3. 네가 정해

## 3. 범위 밖 파일 — 승인 때 같이 정할 것 (질문으로 묻는다)

`spec.md` → `docs/spec.md` 이동이 아래 두 곳을 깨거나 어긋나게 한다.

- 공통 스킬 `verify-before-report` 가 `spec.md` 를 가리킨다 → 문구를 `docs/spec.md` 로 바꾸고 스냅샷 갱신 (C 의 템플릿).
- 프론트엔드 완료 화면이 `artifacts["spec.md"]` 를 읽는다 → `docs/spec.md` 로 3줄 + 테스트 픽스처 (E 의 화면).

## 4. 건드릴 파일

| 파일 | 변경 |
|---|---|
| `builder/src/specbuilder/registry/refs.py` | `PARTS_PREFIX = "부분: "`, 부분 이름 ↔ 폴더 표, `render_content(..., parts)` 에 `부분:` 줄, `parse_parts(content)` |
| `builder/src/specbuilder/nodes/select_stack.py` | `DraftTechItem.parts: list[Literal["frontend","backend","database"]]`, 내용에 `부분:` 줄 |
| `builder/prompts/select_stack.md` | 부분 판정 기준과 `parts` 필드 설명, 출력 예시 |
| `builder/src/specbuilder/nodes/generate_artifacts.py` | `spec.md` → `docs/spec.md`, 기술 항목에서 폴더를 계산, 폴더별 `AGENTS.md` 요구·고정 섹션 확인·`CLAUDE.md` 고정, 루트 `## 구조` 확인, 입력에 "산출물 폴더" 블록 |
| `builder/prompts/generate_artifacts.md` | 폴더별 `AGENTS.md`(구조·명령어·코드 규칙·하지 말 것), 루트 `## 구조` 절, 작업 절차에 "그 폴더 파일을 고치기 전에 그 폴더의 `AGENTS.md` 를 읽는다", 스킬은 구조의 경로만 가리킴 |
| `builder/tests/nodes/test_select_stack.py` · `test_generate_artifacts.py` · `tests/fakes/fake_llm.py` | 부분·폴더·검증 테스트, fake 응답 경로 |
| `builder/tests/test_graph.py` · `tests/test_main.py` · `tests/api/test_runs.py` | `spec.md` → `docs/spec.md` 단언 |
| `builder/tests/templates/test_templates.py` + `snapshots/` | 산출물 폴더 구성 스냅샷 (부분 조합별 파일 목록 + 고정 파일 내용) |
| `docs/design/design.md` | "generate_artifacts" 의 J 절을 "구현 전" → 결정으로, 위 2-1~2-4 결정 기록 |
| (3 의 답에 따라) `templates/skills/verify-before-report/SKILL.md` + 스냅샷, `frontend/src/pages/DonePage.tsx` + 테스트 | `docs/spec.md` |

LLM 호출 수는 그대로 1회 (`generate_artifacts`). 한 번에 쓰는 파일이 늘어 뒤쪽 파일이 부실해지면 그때 묻는다 (설계 결정).

## 5. 검증 방법

1. `uv run pytest`, `uv run ruff check . && uv run ruff format --check .`
2. 품질 회귀: 4 케이스를 같은 모델(`claude-sonnet-5-5`, `claude -p`)로 전(`develop` `2f2da92`, 별도 체크아웃) / 후.
   답은 모두 빈 줄(= 추천), 프로필은 고정 사본(`SPECBUILDER_PROFILE_PATH`). 비교: 부분·폴더, 파일 수·줄 수, 고정 섹션, 구조도, 플레이스홀더 grep.
3. 실행 검증: 후 산출물을 빈 임시 폴더(git init)에 풀고 `echo 시작해 | claude -p --setting-sources project ...`.
   스킬 발견·로드, 루트 `AGENTS.md` 읽힘, 첫 작업이 되묻지 않고 시작되는가, 폴더 파일을 고치기 전에 그 폴더 `AGENTS.md` 를 읽는가.
   Codex 는 설치돼 있지 않으면 `[미확인]` 으로 남긴다.

## 6. 남은 `[미확인]`

없음 — 3 의 두 파일은 승인 질문으로 정한다.

## 7. 진행 중 바뀐 것

- 첫 "후" 실행(4건 중 3건)에서 구조도가 있지도 않은 `frontend/docs/spec.md` · `database/docs/spec.md` 를 그렸다. 프롬프트의
  "둘째 단계는 각 폴더 안의 …, `docs/spec.md`" 문장이 "폴더마다 `docs/spec.md`" 로 읽혔다 → 둘째 단계를 폴더별로 나눠 다시 쓰고
  "산출물 폴더 안에 `docs/` 나 `spec.md` 를 그리지 않는다", "(코딩 에이전트가 만듦)" 표시를 넣은 뒤 다시 돌렸다. 아래 "후" 는 다시 돌린 결과다.
- 승인받은 범위 밖 파일 2곳(3 절)을 고쳤다: `templates/skills/verify-before-report/SKILL.md`(+ 스냅샷), `frontend/src/pages/DonePage.tsx`(+ 테스트).
  DonePage 는 폴더별 `AGENTS.md`·`CLAUDE.md` 에도 설명이 붙도록 `=== "AGENTS.md"` 를 `endsWith` 로 바꿨다.

## 8. 검증 결과

```
$ cd builder && uv run pytest -q
207 passed, 13 warnings in 1.33s     # 경고는 기존 langsmith DeprecationWarning (Python 3.14)
$ uv run ruff check . && uv run ruff format --check .
All checks passed!
71 files already formatted
$ cd frontend && npx vitest run && npm run -s lint && npx tsc -b
Test Files 5 passed (5) / Tests 35 passed (35), lint·tsc 출력 없음
```

### 품질 회귀 — 같은 모델 `claude-sonnet-5-5`, `claude -p` 헤드리스(Claude Code 2.1.325), 2026-11-14

전 = `develop` `2f2da92` (별도 체크아웃), 후 = 이 브랜치. 답은 모든 질문에 빈 줄(= 추천), 프로필은 `~/.specbuilder/profile.json` 사본.
줄 수는 루트·`docs/`·폴더 문서 + 스킬(`.agents/skills` 한 벌만 셈).

| 케이스 | | LLM 호출 | 고른 기술 → 부분 | 산출물 문서 | 줄 수 | 루트 `## 구조` | 폴더 고정 섹션 4개 | 플레이스홀더·위험 명령 grep |
|---|---|---|---|---|---|---|---|---|
| 01-short | 전 | 7 | Python · Flask · SQLite (부분 없음) | spec · AGENTS · CLAUDE | 254 | 없음 | — | 스킬 예시의 `...` 2곳 |
| | 후 | 7 | Python · Tkinter→화면 · JSON 파일 | + `docs/spec.md`, `frontend/` | 283 | 있음 | 있음 | `frontend/AGENTS.md` 형식 예시의 `...` 1곳 |
| 02-domain | 전 | 9 | Python · Streamlit · pandas · SQLite | spec · AGENTS · CLAUDE | 289 | 없음 | — | 없음 |
| | 후 | 8 | Python · Streamlit→화면 · pandas · SQLite→데이터베이스 | + `frontend/`, `database/` | 331 | 있음 | 있음 (둘 다) | 없음 |
| 03-vague | 전 | 9 | Node · Next.js · SQLite | spec · AGENTS · CLAUDE | 282 | 없음 | — | 없음 |
| | 후 | 7 | Node · Next.js→화면 · SQLite→데이터베이스 | + `frontend/`, `database/` | 358 | 있음 | 있음 (둘 다) | 파일 이름 예시 `0002-....sql` 1곳 |
| 04-no-screen | 전 | 9 | Python · requests · launchd | spec · AGENTS · CLAUDE | 252 | 없음 | — | 없음 |
| | 후 | 7 | Python · requests · launchd (부분 없음) | `docs/spec.md` 만 | 235 | 있음 (루트에 코드 파일) | — | 없음 |

- 부분 판정은 4건 모두 프롬프트 기준대로였다: Next.js 는 화면 하나, SQLite 는 데이터베이스, JSON 파일 저장은 데이터베이스가 아님, 예약 실행 스크립트는 부분 없음.
  `backend/` 를 받은 케이스는 없다 (화면과 서버를 따로 두는 요청이 회귀 세트에 없다).
- 기술 선택 자체의 변동(01 Flask→Tkinter, 02 SQLite 유무)은 `select_stack` 의 실행마다 변동이다 — 전에도 실행마다 갈렸고, 이번 변경은 고르는 기준이 아니라 부분 표기만 더했다 `[추정]`.
- LLM 호출 수는 늘지 않았다 (`generate_artifacts` 1회 유지). 차이는 `interview_user` 묶음 수의 변동.
- 새 스킬 본문이 구조도의 경로(`frontend/app/`, `database/schema.sql` 등)를 가리킨다. 폴더 있는 3건 모두 루트 작업 절차에 "그 폴더의 `AGENTS.md` 를 읽는다" 가 들어갔다.
- `...` 3곳은 모두 형식·파일 이름 예시이고 채울 빈칸이 아니다. 프롬프트가 금지한 표기라 기록만 한다 (A·C 때와 같은 현상).

### 실행 검증 (인수 조건) — 2026-11-14, `claude-sonnet-5-5`, Claude Code 2.1.325

후 산출물을 빈 임시 폴더(git init)에 풀고 `echo 시작해 | claude -p --setting-sources project --tools Read,Glob,Grep,Skill --max-turns 10`.

| 케이스 | 스킬 발견 | 스킬 로드 | 읽은 문서 | 첫 작업 |
|---|---|---|---|---|
| 03-vague (화면 + 데이터베이스) | `build-club-app`, `verify-before-report` | `build-club-app` | `docs/spec.md`, `frontend/AGENTS.md`, `database/AGENTS.md` | 되묻지 않음. 쓰기 도구를 막아 둬서 "파일을 만들 수 없다" 고 사용자 말로 보고하고 멈춤 (예상한 결과) |
| 04-no-screen (부분 없음) | `build-morning-weather-bot`, `verify-before-report` | `build-morning-weather-bot` | `docs/spec.md` | 동네 이름과 텔레그램 봇 토큰을 물었다 |

- 루트 `AGENTS.md` 는 `CLAUDE.md` 의 `@AGENTS.md` 임포트로 읽혔다 (두 건 모두 규칙대로 사용자의 말로 답했다).
- 04 의 질문: 봇 토큰은 비밀값이라 산출물에 넣을 수 없어 사용자에게 받아야 한다. 동네는 빈 답(추천)이 "직접 입력" 선택지를 골라
  스펙에 이름 없이 남은 탓이다 (`interview_user` 의 선택지 문제, J 범위 밖 — 기본값 "서울 중구" 는 스펙에 있었고 작업자도 그것을 기본으로 제시했다).
- 공통 스킬 `verify-before-report` (경로 문구 변경 후) 재검증: 스킬 하나와 `docs/spec.md` 만 둔 폴더에서 "hello.txt 에 안녕이라고 적고 알려줘" →
  스킬 로드, `docs/spec.md` 의 완료 기준을 읽어 파일을 다시 확인한 뒤 "된 것 / 확인 못 한 것 / 써 보는 방법" 으로 보고. 통과.
- Codex: 이 PC 에 설치돼 있지 않아 `[미확인]`.

## 9. 안 한 것 / 남은 것

- Codex 실행 검증 — 설치돼 있지 않음 `[미확인]`.
- `backend/` 를 받는 경로는 단위 테스트·스냅샷으로만 확인했다. 회귀 세트에 화면과 서버를 따로 두는 요청이 없다.
- 04 의 "동네 이름" 재질문은 `interview_user` 의 범위 (빈 답이 "직접 입력" 을 고르는 문제).

토큰 소모 [추정]: 세션 약 20만 토큰 + 실제 `claude -p` 약 40회 (회귀 전 4건·후 4건 × 2회 = 실행당 7~10회 호출, 실행 검증 2, 공통 스킬 1).
