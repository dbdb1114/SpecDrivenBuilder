# 스파이크 준비: CLI로 그래프→산출물 뼈대 (#1)

브랜치 `feat/spike-scaffold` · 이슈 https://github.com/dbdb1114/SpecDrivenBuilder/issues/1

## 1. 분석 (현재 상태)

- [확정] `builder/` 에는 `.gitkeep`만 있는 빈 디렉토리들(graph, nodes, state, prompts, templates, llm, api, output, tests/{nodes,fakes,templates})뿐이다. `pyproject.toml` 없음.
- [확정] `builder/evals/` 디렉토리 없음 (builder/AGENTS.md 구조에는 있음).
- [확정] 도구: uv 0.13.1, Python 3.14.7 / 3.15.0 설치됨, `claude` CLI 2.1.319 있음.
- [확정] `ANTHROPIC_API_KEY`·`OPENAI_API_KEY` 미설정, `.env` 없음 → SDK 직접 호출은 지금 불가.
- [확정] `claude -p` 는 `--model`, `--system-prompt`, `--tools`, `--output-format json`, `--no-session-persistence` 를 지원 (`claude --help`). `--bare` 는 OAuth 를 건너뛰므로 Max 로그인으로는 못 씀.
- [확정] `docs/design/state.md`: interrupt → checkpointer 필수, 개발 SqliteSaver / 테스트 InMemorySaver. State 스키마는 미결정.
- [확정] builder/AGENTS.md: 최상위 `graph`·`state`·`api`·`llm` 이름 충돌 위험 → `src/<패키지>/` 여부를 이번에 결정.
- [확정] "가이드 vs 템플릿"은 미결정 → 이번 작업에서 `templates/` 를 채우지 않고, generate 프롬프트는 중립 기준선으로만 둔다 (두 방식은 #2에서 변형으로 추가).

## 2. 결정 (2026-11-06 사용자 승인)

- [확정] Q1 → 1 `builder/src/specbuilder/`
- [확정] Q2 → 1 `claude -p` 서브프로세스

선택지 기록:

**Q1. 패키지 레이아웃**
1. `builder/src/specbuilder/` (추천) — 코드 패키지(graph·nodes·state·llm·api)만 src 아래로 옮기고, 데이터 디렉토리(prompts·templates·evals·output·tests)는 `builder/` 에 남긴다. 실행 명령은 `uv run python -m specbuilder.graph.main` 로 바뀌고 builder/AGENTS.md 의 구조·명령어를 고친다. 이름 충돌이 없고 테스트가 설치된 패키지를 import 하는 표준 구조. 나중에 옮기려면 import 전부를 고쳐야 하므로 지금 정하는 게 싸다.
2. 평평한 구조 유지 — 현재 디렉토리·문서 그대로, `python -m graph.main`. 변경이 가장 적지만 `llm`(PyPI 패키지 존재)·`graph` 같은 이름과 충돌할 위험이 남는다.

**Q2. 실제 LLM 호출 수단** (`llm/client.py` 뒤에 숨기므로 나중에 교체 가능)
1. `claude -p` 서브프로세스 (추천) — Max 요금제로 돌아가므로 추가 비용과 API 키가 없다. #2의 실행 검증도 같은 CLI 를 쓰고, `--model` 로 모델을 고정할 수 있다. 호출당 수 초가 더 걸리고, 운영에 쓸 수단은 아니다.
2. Anthropic SDK + API 키 — 운영 구조와 같다. 하지만 키 발급과 종량 과금이 필요하고, 의존성 `anthropic` 이 추가된다.

## 3. 계획

### 건드릴 파일 (Q1=1 기준. Q1=2 이면 `src/specbuilder/` 를 빼고 `builder/` 바로 아래에 둔다)

| 파일 | 변경 요지 |
|---|---|
| `builder/pyproject.toml`, `builder/uv.lock`, `builder/.python-version` | `uv init --package` (Python 3.14) + `uv add langgraph langgraph-checkpoint-sqlite`, `uv add --dev pytest ruff` |
| `builder/src/specbuilder/state/schema.py` | `State` TypedDict: `request: str`, `qa: Annotated[list[QA], operator.add]`, `artifacts: dict[str, str]` |
| `builder/src/specbuilder/nodes/interview.py` | `interview_user`: LLM이 다음 질문 1개 또는 "충분함"을 판정 → 질문이면 `interrupt(question)` 후 `{"qa": [...]}` 반환. 최대 3문항. 분기는 `Command(goto=...)` |
| `builder/src/specbuilder/nodes/generate.py` | `generate_artifacts`: LLM 1회 호출로 spec.md · SKILL.md · AGENTS.md 를 JSON 으로 받아 `{"artifacts": {...}}` 반환 + CLAUDE.md(`@AGENTS.md`) 추가 |
| `builder/src/specbuilder/graph/build.py`, `graph/main.py` | 그래프 조립(checkpointer 주입) / CLI: 요청 파일 경로 인자 → interrupt 질문을 터미널에 출력하고 stdin 으로 답을 받아 `Command(resume=...)` → `output/<run_id>/` 에 기록. stdin 파이프로 답을 미리 넣을 수 있어 #2의 반복 실행이 가능 |
| `builder/src/specbuilder/llm/client.py` | `LLMClient` 프로토콜 + `ClaudeCLIClient`(Q2=1) · `LLMCallError`. 모델 ID 는 환경변수 `SPECBUILDER_MODEL`, 기본값 `claude-sonnet-5-5` |
| `builder/src/specbuilder/paths.py` | `builder/` 루트 기준 prompts·output 경로 (src 레이아웃이라 `__file__` 기준 계산이 필요) |
| `builder/prompts/interview.md`, `builder/prompts/generate.md` | 노드 시스템 프롬프트. generate 는 루트 "산출물 규칙"만 반영한 중립 기준선 |
| `builder/tests/fakes/fake_llm.py` | 미리 정한 응답을 순서대로 돌려주고 호출을 기록하는 fake |
| `builder/tests/nodes/test_interview.py`, `test_generate.py`, `builder/tests/test_graph.py` | 노드 단위 + 그래프 끝단 테스트 (InMemorySaver, interrupt→resume→artifacts 4개, 실제 호출 0건) |
| `builder/evals/cases/01-short.md`, `02-domain.md`, `03-vague.md` | 비개발자식 요청 원문 3개 (짧은 것 / 도메인 용어 / 모호한 것) |
| `builder/.env.example` | `SPECBUILDER_MODEL` (Q2=2 면 `ANTHROPIC_API_KEY` 추가) |
| `builder/AGENTS.md` | Q1 결정 반영: 구조도·명령어·"미결정" 줄을 확정 문구로 교체 |
| `docs/design/state.md` | State 스키마 확정 내용 기록 (미결정 → 결정) |
| `.gitignore` | 개발용 sqlite 파일(`builder/*.sqlite`) 추가 |

빈 디렉토리의 `.gitkeep` 은 실파일이 생기면 지운다 (`templates/`, `api/`, `tests/templates/` 의 `.gitkeep` 은 남김).

### 범위 밖 (이번에 안 함)
- 프로필 수집(interview-profile.md) — interview 는 요구사항 질문만 한다.
- 템플릿 / 가이드 방식 구현, SKILL.md 를 어디에 둬야 작업자가 발견하는지 — #2.
- FastAPI · 프론트엔드.

### 검증
1. `cd builder && uv run pytest` 그린, `uv run ruff check .` 통과
2. `uv run python -m specbuilder.graph.main evals/cases/01-short.md` → 질문에 답 → `output/<run_id>/` 에 spec.md · SKILL.md · AGENTS.md · CLAUDE.md 생성 확인 (모델 ID·날짜 기록)
3. 산출물에 플레이스홀더(`TODO`, `<여기에`, `...`)가 없는지 grep

LLM 호출 수: 실행 1회당 interview ≤ 4회 + generate 1회.

## 4. 계획과 달라진 점

- 노드·프롬프트·테스트 파일명을 builder/AGENTS.md 규칙(`동사_명사`, `prompts/<노드명>.md`, `test_<노드명>.py`)에 맞춤:
  `nodes/interview_user.py`, `nodes/generate_artifacts.py`, `prompts/interview_user.md`, `prompts/generate_artifacts.md`,
  `tests/nodes/test_interview_user.py`, `tests/nodes/test_generate_artifacts.py`.
- State 에 `pending_question` 추가 — resume 시 LLM 재호출을 막기 위해 (`docs/design/state.md` 에 이유 기록).
- `pyproject.toml` 직접 수정 2줄: `uv init` 이 만든 `[project.scripts]` 진입점(`specbuilder:main` → `specbuilder.graph.main:main`)과
  `description`. 의존성은 전부 `uv add` 로 추가.
- `tests/__init__.py`, `tests/nodes/__init__.py`, `tests/fakes/__init__.py` 추가 — `from tests.fakes.fake_llm import ...` 용.
- 산출물 디렉토리에 `run.json`(모델 ID·시작 시각·문답) 추가 — #2 비교표 기록용, 산출물 자체는 아님.
- generate 응답 형식은 JSON 대신 `=== FILE: <이름> ===` 구분선 (긴 마크다운의 JSON 이스케이프가 깨지기 쉬움).

## 5. 검증 결과 (2026-11-06)

```
$ cd builder && uv run pytest -q
7 passed, 13 warnings in 0.08s        # 경고는 langsmith 내부 asyncio.iscoroutinefunction DeprecationWarning (Python 3.14)
$ uv run ruff check . && uv run ruff format --check .
All checks passed!
26 files already formatted
```

실제 실행 [확정] — 모델 `claude-sonnet-5-5`, 2026-11-06 21:45, `claude -p` 2.1.319:

```
$ printf '저 혼자 써요. 컴퓨터에서요.\n카드랑 현금 둘 다요. ...\n알아서 정해 주세요\n' \
    | uv run python -m specbuilder.graph.main evals/cases/01-short.md
→ 질문 3개(번호 선택지 + (추천) + "알아서 정해 주세요" 형식) → output/261106-214531-01-short/
   AGENTS.md 89줄 · SKILL.md 54줄 · spec.md 97줄 · CLAUDE.md(@AGENTS.md) · run.json
```

- SKILL.md frontmatter `name`·`description`(언제 쓰는지 포함) 있음. AGENTS.md 섹션: 용어사전 · 작업자 컨텍스트 · 작업 절차 · 질문 규칙 · 완료 보고 규칙.
- `grep -nE 'TODO|<여기에|\.\.\.|rm -rf|curl .*\| *sh'` → 해당 없음.
- `git status` 에 `builder/output/` 없음 (무시됨).
- LLM 호출 수: interview 3회(질문 3개를 만든 뒤 상한 `MAX_QUESTIONS=3` 에 걸려 판정 호출 없이 종료) + generate 1회 = 4회.

## 6. 안 한 것 / 남은 것

- 산출물 `claude -p` 실행 검증(스킬 로드·AGENTS.md 읽힘·되묻지 않음) — #2 범위. SKILL.md 를 어느 경로에 둬야 작업자가 발견하는지도 #2.
- `evals/cases/` 는 3개 — 루트 "품질 판정"의 5~10개 기준에는 못 미침 (#2 이후 보강).
- `.env` 자동 로드 없음 (현재 변수 1개라 불필요).
- 개발 SqliteSaver 파일은 실행마다 thread 가 쌓인다 — 정리 정책 없음.

토큰 소모 [추정]: 세션 약 15만 토큰 + 실제 실행 `claude -p` 4회.
