# builder/AGENTS.md — Python · LangGraph · FastAPI

루트 `AGENTS.md` 의 공통 규칙이 먼저다. 여기는 Python 쪽 세부만. `builder/CLAUDE.md`는 `@AGENTS.md` 한 줄.

## 구조

```
src/specbuilder/     코드 패키지 (src 레이아웃 — graph·state·llm 같은 일반명이 다른 패키지와 충돌하지 않도록)
  graph/             LangGraph 그래프 조립 (노드 등록, 엣지, 조건 분기) · main.py 가 CLI
  nodes/             노드 함수 — 노드 하나 = 파일 하나
  state/             State 스키마 (TypedDict / Pydantic)
  llm/               LLM 클라이언트 래퍼 — 노드는 여기만 통해서 호출
  api/               FastAPI 라우터 (`/api/**`) — 그래프를 HTTP 로 노출만 함, 로직 없음
  paths.py           builder/ 기준 데이터 디렉토리 경로
prompts/      노드별 시스템 프롬프트 (.md) — 코드에 하드코딩 금지
templates/    산출물 템플릿 — SKILL.md(새로 쓰는 스킬의 서식), skills/<이름>/SKILL.md(공통 스킬. 폴더가 곧 목록)
output/       생성 결과 — git 추적 안 함
tests/        nodes/ 와 1:1 대응. fakes/fake_llm.py
evals/        품질 회귀 세트 — cases/ 에 비개발자식 요청 원문 (루트 "품질 판정")
```

## 명령어

```bash
uv sync                          # 의존성
uv run python -m specbuilder.graph.main evals/cases/01-short.md   # 그래프 CLI 실행 (답은 터미널 입력 또는 stdin 파이프)
uv run uvicorn specbuilder.api.main:app --reload   # FastAPI 개발 서버
uv run --env-file .env uvicorn specbuilder.api.main:app --reload   # .env 의 설정(Claude API 키 등)으로 띄울 때
uv run pytest                    # 테스트
uv run ruff check . && uv run ruff format .
```

LLM 호출 수단은 환경 변수 `SPECBUILDER_LLM` 으로 고른다 (`llm/client.py` 의 `make_client()`).
- `claude-cli` (기본) — `claude -p` 서브프로세스(`ClaudeCLIClient`). API 키 없이 로그인된 요금제로 돈다. 품질 회귀 기록은 이 수단 기준이다.
- `anthropic-api` — Claude API(`AnthropicAPIClient`, 공식 SDK `anthropic`). `ANTHROPIC_API_KEY` 가 필요하고 호출마다 과금된다.

모델은 `SPECBUILDER_MODEL` (기본 `claude-sonnet-5-5`). `.env` 자동 로드는 없다 — `uv run --env-file .env <명령>` 으로 넘기거나 셸에서 export.
키는 `.env` 에만 적는다 (커밋되지 않음). 변수를 추가하면 `.env.example` 을 갱신할 것.

## 코드 규칙

- 노드 함수 이름은 `동사_명사` (`collect_requirements`, `generate_skill`). 시그니처는 `(state: State) -> dict` —
  **바꿀 키만 담은 부분 업데이트를 반환**한다. State 전체를 반환하면 reducer가 걸린 키(리스트)가 중복 누적된다.
  분기와 이동을 한 번에 하면 `Command`를 반환.
- 사용자 응답을 기다리는 노드는 `interrupt()`를 쓴다. 그래서 checkpointer는 처음부터 필수 —
  개발 `SqliteSaver`(`--reload`해도 상태 유지), 테스트 `InMemorySaver`(`MemorySaver`는 구 별칭, 쓰지 않음), 운영 미결정.
  상세: `docs/design/state.md`.
- State 키는 `snake_case`. **키 추가/삭제 시** `state/` 스키마, 해당 노드, 테스트 픽스처를 함께 수정.
- 노드를 추가하면 반드시 함께 수정: `graph/` 등록, `prompts/<노드명>.md`, `tests/nodes/test_<노드명>.py`.
- LLM 호출은 `llm/client.py` 를 통해서만. 노드에서 SDK를 직접 import 하지 말 것.
- LLM 호출 실패는 `LLMCallError` 로 감싸서 올림. 노드 안에서 `except Exception: pass` 금지.
- `api/` 는 요청 파싱 → 그래프 호출 → 응답 직렬화만. 비즈니스 로직이 `api/` 에 생기면 `nodes/` 로 옮길 것.
- 타입 힌트는 함수 시그니처에만. 지역 변수에는 붙이지 않음.
- 주석은 "왜" 만. "무엇" 은 적지 말 것. docstring 은 public 함수에만.
- 의존성 추가는 `uv add` 로. `pyproject.toml` 직접 편집 금지. `uv.lock` 커밋.
- 코드는 `src/specbuilder/` 아래, import 는 `specbuilder.` 로 시작 (2026-11-06 결정, #1). 테스트는 `tests.fakes` 처럼 `tests.` 로.
- LLM 을 쓰는 노드는 `make_<노드명>(llm)` 팩토리로 클라이언트를 주입받고, 반환된 함수가 `(state) -> dict | Command` 다.

## 하지 말 것

- 테스트에서 실제 LLM 호출
- `prompts/` 외부에 프롬프트 문자열
- `api/` 에서 `nodes/` 함수를 직접 호출 (항상 `graph/` 를 통해서)
