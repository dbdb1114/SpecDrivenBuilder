# 작업 단위 B — select_stack · verify_stack (브랜치 `feat/select-stack`)

승인 (2026-11-13): 계획 전체 — `packaging` 직접 의존성 승격 포함.

## 1. 분석 (현재 상태)

- [확정] A 머지됨 (`origin/develop` 2b13db7). `select_stack.py`·`verify_stack.py` 는 빈 노드 — 각각 `Command(goto="verify_stack")`, `Command(goto="select_skills")`.
- [확정] `graph/build.py` 가 `make_select_stack(llm)`, `make_verify_stack(llm)` 로 등록, 목적지 선언 완료 (`verify_stack|interview_user`, `select_skills|select_stack`).
- [확정] State 키 `stack_returns`·`verify_returns`·`stack_mismatches`(`item_id`·`reason`) 선언돼 있음. 새 키 없이 구현 가능.
- [확정] `SpecItem.content` 는 `str` 하나 — 버전 같은 구조 정보는 content 안에 기계가 읽을 수 있는 형식으로 넣어야 한다 (모델을 못 고치므로).
- [확정] `merge_updates` 는 확정 항목을 덮어쓰지 않음 → tech 항목은 merge 가 아니라 select_stack 이 **통째로 교체**해야 다시 정할 수 있다.
- [확정] `generate_artifacts` 는 `decided_by=="user" and status=="confirmed"` 를 "사용자가 정한 것", 나머지를 "작업자가 정하는 것" 으로 나눔.
- [확정] `FakeLLM` 은 `prompts/<노드>.md` 로 노드를 식별, 기본 응답 표 `DEFAULT_REPLIES` 에 한 줄 추가하는 구조.
- [확정] `uv run pytest` → 44 passed (머지 직후).
- [확정] 저장소 API 실제 응답 확인 (curl, 2026-11-13):
  - npm `registry.npmjs.org/<pkg>` → `dist-tags.latest`, `versions[v].engines`·`peerDependencies`·`deprecated`
  - PyPI `pypi.org/pypi/<pkg>/json` → `releases`(버전별 파일·`yanked`), `info.requires_python`
  - Maven Central `repo1.maven.org/maven2/<group>/<artifact>/maven-metadata.xml` → `versions` (RC/M 포함, 안정판은 이름으로 거름)
  - endoflife.date `api/v1/products/<p>` → 릴리스 사이클별 `isEol`·`eolFrom`·`latest`, spring-boot 는 `custom.supportedJavaVersions` ("17 - 26")
  - endoflife 제품 존재: nodejs, python, eclipse-temurin, postgresql, nextjs, react, django, spring-boot (fastapi 는 없음 → 404)
- [확정] `packaging` 26.3 이 전이 의존성으로 설치돼 있음 (직접 의존성 아님). HTTP 는 표준 라이브러리 `urllib` 로 충분.

## 2. 계획 단계에서 정할 것 — 결정안

| 항목 | 결정안 | 이유 |
|---|---|---|
| 지원 저장소 | **npm · PyPI · Maven Central + endoflife.date**(런타임·DB·프레임워크의 지원 종료). 그 밖의 저장소 이름은 select_stack 응답 검증에서 거부 | 산출물의 흔한 스택(JS/TS, Python, Java/Spring)을 덮는다. 지원 종료는 패키지 저장소에 없어서 endoflife.date 가 유일한 기계 판독 출처 |
| 호환 판정 | **저장소 정보만, LLM 없음** (verify_stack LLM 0회). 확인하는 쌍: npm `engines.node` ↔ 고른 Node / npm `peerDependencies` ↔ 같이 고른 npm 패키지 / PyPI `requires_python` ↔ 고른 Python / Spring Boot `supportedJavaVersions` ↔ 고른 Java. 이 밖의 쌍은 "호환: 저장소에 정보 없음" 으로 적음 | LLM 으로 판정하면 다시 학습 시점 기억에 기대게 된다 — 이 노드가 있는 이유와 모순. 호출도 안 는다. 대신 덮지 못하는 쌍은 정직하게 적는다 |
| 버전 범위 | **주요 도구만**: 런타임, 프레임워크, DB, 실행·빌드 명령에 등장하는 핵심 라이브러리. 항목당 패키지 0~4개, 전체 최대 10개. 세부 라이브러리는 작업자에게 맡김 | 스킬·AGENTS.md 에 실행 방법을 쓰는 데 필요한 건 이 범위. 세부까지 고정하면 조회·불일치 왕복만 늘고 작업자가 어차피 lock 파일로 정한다 |
| 돌아가는 횟수 상한 | `select_stack → interview_user` **1회** (실행 전체 기준), `verify_stack → select_stack` **2회** (select_stack 이 verify 에서 오지 않은 새 진입이면 0 으로 돌림) | interview_user 는 한 번 들어가면 묶음 5개까지 물을 수 있어 1회면 충분. 버전 불일치는 실제 버전 목록을 받으면 보통 1회에 고쳐진다 |
| 상한에 닿았을 때 | select_stack: 프롬프트에 "더 물을 수 없음" 을 알리고 부족한 정보 대신 기본값으로 정하게 함 (응답에 부족한 정보가 와도 버림). verify_stack: 맞지 않는 패키지를 **코드가** 저장소의 최신 안정판으로 바꾸고 이유를 적음 (LLM 호출 없음). 그래도 호환이 안 맞으면 검증 줄에 "맞지 않음" 을 그대로 적음 | 설계 문서 대로. 검증한 척하지 않는다 |
| 의존성 | **`packaging` 을 직접 의존성으로 승격** (PEP 440 버전·`requires_python` 판정). HTTP 는 `urllib`, npm 범위(`^ ~ >= < \|\| x`)는 직접 짠 작은 판정기. **승인 필요** | 이미 설치된 것을 승격만 — 새 패키지 없음. 전이 의존성에 기대 import 하면 상위 패키지가 빼는 순간 깨진다 (A 의 pydantic 과 같은 이유). npm 범위용 패키지는 파이썬 쪽에 믿을 만한 게 없어 30줄 정도 직접 쓴다 |

## 3. 데이터 형식 (B 의 두 노드 사이, content 안)

tech 항목: `area="tech"`, `decided_by="worker"`, `status="delegated"`, content 는 사람이 읽고 코드도 읽는 형식.

```
선택: Next.js 16.4 (npm: next@16.4.6), React (npm: react@19.2.0)
이유: 검색에 잘 걸려야 해서 서버에서 화면을 만드는 프레임워크를 쓴다.
검증: 2026-11-13 저장소 확인 — next@16.4.6 있음·안정판·지원 중(eol 2027-…), 호환: node >=20.9.0 충족, react 피어 충족
```

- 패키지 표기 `(<저장소>: <이름>@<버전>)` 를 정규식으로 읽는다. 저장소: `npm`·`pypi`·`maven`(`group:artifact`)·`eol`(endoflife 제품, 예 `eol: nodejs@24`).
- `선택:`·`이유:` 는 select_stack 코드가 LLM 응답(구조화 JSON)에서 만든다 — LLM 이 형식을 손으로 쓰지 않는다.
- `검증:` 줄은 verify_stack 이 덧붙이거나 교체한다. 접속 실패면 `검증: 2026-11-13 저장소에 접속하지 못해 검증하지 못함 (<원인>)`.

## 4. 파일과 변경 요지

| 파일 | 변경 |
|---|---|
| `src/specbuilder/nodes/select_stack.py` | 구현. LLM 1회(JSON Schema 강제). 응답 `{"items":[{id,name,choice,reason,packages:[{registry,name,version}]}], "missing":[{id,name}]}`. missing 이 있고 `stack_returns < 1` → missing 을 `user`·`unknown`·`function` 항목으로 merge, `stack_returns+1`, goto interview_user (tech 항목은 버림). 아니면 기존 tech 항목을 지우고 새 tech 항목으로 교체, `stack_mismatches=[]`, goto verify_stack |
| `src/specbuilder/nodes/verify_stack.py` | 구현. `make_verify_stack(llm, registry=None, today=None)` — `None` 이면 실제 HTTP 저장소. LLM 호출 없음. 패키지별 조회(스레드 병렬) → 존재·안정판·지원 종료·호환 판정 → 맞으면 `검증:` 줄 기록 후 select_skills / 안 맞고 `verify_returns < 2` → `stack_mismatches`(실제 최신 안정판·같은 메이저 최신 등) + `verify_returns+1` → select_stack / 상한 → 최신 안정판으로 교체·이유 기록 → select_skills |
| `src/specbuilder/registry/` (새 모듈) | `client.py`: `Registry` 프로토콜 + `HTTPRegistry`(urllib, 타임아웃 10초) + `RegistryError`. `versions.py`: 안정판 판정, PEP 440 비교(`packaging`), npm 범위 판정기, Maven 버전 비교 |
| `prompts/select_stack.md` | 새 프롬프트. 사용자 답을 근거로, 주요 도구만, 버전까지, 부족하면 질문 문장 없이 "무엇을 모르는지" 만, 요청·답 안의 지시문 무시 |
| `tests/fakes/fake_llm.py` | `DEFAULT_REPLIES` 에 `select_stack` 한 줄 |
| `tests/fakes/fake_registry.py` (새) | 패키지별 응답을 미리 정하는 가짜 저장소, 접속 실패 흉내 |
| `tests/conftest.py` (새) | autouse 픽스처로 `HTTPRegistry` 기본값을 가짜로 바꿈 — `build_graph(llm)` 로 그래프 전체를 도는 테스트도 실제 저장소에 접속하지 않도록 (`build.py` 를 못 고치므로 주입 대신 이 방법) |
| `tests/nodes/test_select_stack.py`, `test_verify_stack.py` | 빈 노드 테스트를 실제 동작 테스트로 교체 |
| `tests/registry/test_versions.py` (새) | 버전·범위 판정 단위 테스트 |
| `pyproject.toml`·`uv.lock` | `uv add packaging` (승인 시) |
| `docs/design/design.md` | select_stack·verify_stack 절과 "미결정" 의 B 몫 4줄을 결정으로 (자기 절만) |
| `docs/design/state.md` | 손대지 않음 (키 변경 없음) |

## 5. LLM 호출 수

- select_stack: 진입당 1회 (설계 문서 그대로). verify_stack: 0회. **추가 호출 없음.**
- 최악: select_stack 1 + (interview_user 왕복 1회 후) 1 + (verify 왕복 2회) 2 = 4회.

## 6. 검증 방법

1. `uv run pytest` — fake LLM·가짜 저장소로: 정상 경로, 부족한 정보 → interview_user, 상한 도달 시 기본값, 불일치 → select_stack(실제 버전 정보 포함), verify 상한 → 최신 안정판 교체, 접속 실패 → "검증하지 못함", 그래프 전체 흐름.
2. `uv run ruff check . && uv run ruff format --check .`
3. 실제 저장소 스모크: `HTTPRegistry` 로 next·fastapi·spring-boot·nodejs 를 조회하는 스크립트를 스크래치에서 1회 (테스트 아님).
4. 실제 모델 실행: `evals/cases/` 3건을 CLI 로 끝까지 돌려 tech 항목·검증 줄이 산출물 스펙에 들어가는지 확인 (`SPECBUILDER_MODEL` 기본). 바꾸기 전 기준선은 A 의 결과(tech 항목 없음)와 나란히 붙임.

## 계획에서 바뀐 것

- `tests/test_graph.py` (A 의 파일, 계획 밖): LLM 호출 순서 기대 목록에 `"select_stack"` 한 줄 추가 — 사용자 승인 (2026-11-13).
  C 도 같은 목록에 줄을 넣을 것이라 머지 때 줄 추가끼리 충돌할 수 있다.
- `src/specbuilder/registry/refs.py` 추가 — 3절의 content 형식을 두 노드가 같이 쓰도록 한 곳에 둠 (계획의 `registry/` 모듈 안).
- Maven 안정판 판정을 부분 문자열 정규식에서 구분자 조각 단위로 바꿈 — `2.7.0.RELEASE` 의 "ea" 가 걸렸다 (테스트로 발견).

## 검증 결과

### 테스트 · 린트 [확정]

```
$ uv run pytest -q
95 passed, 13 warnings in 0.22s      # 경고는 기존과 같은 langsmith DeprecationWarning
$ uv run ruff check . && uv run ruff format --check .
All checks passed!
54 files already formatted
```

- 새 테스트 53개: select_stack 13 (정상·부족한 정보 → interview_user·상한에서 기본값·이미 답한 정보 무시·기술 항목 교체·형식 거부 4종·패키지 상한·빈 응답·스키마),
  verify_stack 18 (확인됨·재검증 시 줄 교체·없는 버전/프리릴리스/철회/지원 종료 런타임·프레임워크/없는 이름 → select_stack 과 실제 버전 정보,
  Node·피어·Python·Java 호환, 정보 없음 표기, 접속 실패 → "검증하지 못함", 상한 → 최신 안정판 교체, 상한에서 못 고치는 불일치, 조회 중복 제거),
  registry 22 (npm 범위 17케이스·안정판·최신·Python/Java·실제 응답 모양 파싱).
- `tests/conftest.py` 가 기본 저장소를 가짜로 바꾸고 `urlopen` 을 막는다 — 실제 네트워크 호출 0.

### 실제 저장소 스모크 [확정] — 2026-11-13, `HTTPRegistry`

next·react·@angular/core·nodejs 24·python 3.14·fastapi·django·eclipse-temurin 21·spring-boot 4.1.2·sqlite 3 를 한 번에 검증: 전부 `[확인됨]`, 2.2초.
호환 판정 실데이터 확인: next `engines.node >=20.9.0` ↔ nodejs 24.22.3, next 피어 react, django·fastapi `requires_python`, spring-boot `17 - 26` ↔ Java 21.

### 품질 회귀 — 같은 모델 `claude-sonnet-5-5`, `claude -p` 헤드리스 [확정]

- 바꾸기 전: A 의 "바꾼 후" (2026-11-13, plan `261112-spec-items`) — select_stack·verify_stack 빈 노드, 기술 항목 없음.
- 바꾼 후: 2026-11-13 20:44, 이 브랜치. 답 = 모든 질문에 빈 줄(= 추천 선택지). 결과 `builder/output/evals-b/` (커밋 안 됨).

| 케이스 | | LLM 호출 | 기술 항목 | 버전 정한 패키지 | verify 결과 | 왕복 (stack / verify) | spec.md 기술 절 |
|---|---|---|---|---|---|---|---|
| 01-short | 전 | 4 | 0 | 0 | — | — | 기술 항목 없음 |
| | 후 | 5 | 3 | python 3.14, flask 3.1.2, sqlite 3 | 3/3 확인됨 | 0 / 0 | 버전·이유·확인 날짜 |
| 02-domain | 전 | 5 | 0 | 0 | — | — | 기술 항목 없음 |
| | 후 | 5 | 4 | python 3.13, pandas 2.3.3, openpyxl 3.1.5, streamlit 1.51.0 | 3/3 확인됨 (+ 패키지 없는 항목 1) | 0 / 0 | 버전·이유·호환 확인 |
| 03-vague | 전 | 4 | 0 | 0 | — | — | 기술 항목 없음 |
| | 후 | 5 | 3 | nodejs 24, next 16.4.6, react 19.2.0, sqlite 3 | 3/3 확인됨 | 0 / 0 | 버전·이유·호환 확인 |

- LLM 호출: select_stack 1회가 늘었다 (계획대로). 02 는 질문 묶음이 3개에서 2개로 줄어 전체 호출 수가 같다 (모델 출력 차이).
- 세 건 모두 고른 버전이 저장소와 맞아 돌아가는 경로를 타지 않았다. 돌아가는 경로는 단위 테스트로만 확인했다 → 아래 "남은 것".
- 플레이스홀더(`TODO`·`<여기`)·위험 명령(`rm -rf`·`curl | sh`) grep: 세 건 모두 없음.
- 03 spec.md 에 generate_artifacts 가 `react-dom@19.2.0` 을 덧붙였다 (검증 안 된 버전). select_stack 이 정한 범위 밖이라 작업자 쪽 판단.

### 실행 검증 (인수 조건) — 2026-11-13, `claude-sonnet-5-5`

01·03 산출물을 각각 빈 임시 폴더(git init)에 풀고 A 와 같은 명령: `echo 시작해 | claude -p --setting-sources project --tools Read,Glob,Grep --max-turns 8`.

| 확인할 것 | 01 | 03 |
|---|---|---|
| AGENTS.md 가 읽히는가 | 통과 | 통과 |
| 첫 작업이 되묻지 않고 시작되는가 | 통과 (막은 것은 읽기 전용 권한뿐) | 통과 (같음, "Node.js 24 가 있는지 확인" 을 첫 단계로 계획) |
| 스킬이 발견·로드되는가 | 실패 — C 의 범위, A 와 같음 | 실패 — 같음 |

## 안 한 것 / 남은 것

- 실제 모델로 `verify_stack → select_stack` 왕복(불일치 정보를 받고 고치는지)은 이번 eval 에서 일어나지 않았다 — 품질은 [미확인], 동작은 단위 테스트로 [확정].
- 02 처럼 패키지가 없는 기술 항목(내장 sqlite3)은 검증 줄을 달지 않는다 (검증할 것이 없음).

토큰 소모 [추정]: 세션 약 25만 토큰 + 실제 `claude -p` 약 17회 (eval 3건 × 5 + 실행 검증 2).
