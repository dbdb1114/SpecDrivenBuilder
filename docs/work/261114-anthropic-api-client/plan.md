# LLM 호출을 Claude API 로도 할 수 있게 (브랜치 `feat/anthropic-api-client`)

## 1. 분석 (현재 상태)

- [확정] 노드는 `LLMClient.complete(system, prompt, schema)` 만 호출한다. 클라이언트를 만드는 곳은 CLI(`graph/main.py`)와 API(`api/main.py`) 두 곳이고 둘 다 `ClaudeCLIClient()` 고정.
- [확정] `ClaudeCLIClient` 는 `claude -p` 서브프로세스다. 호출 1회에 수 초~수십 초가 걸리고, 운영에 쓸 수단이 아니다 (`261106-spike-scaffold/plan.md` Q2).
- [확정] `.env` 자동 로드 코드는 없다. `.env` 는 `.gitignore` 에 있다.
- [확정] 노드가 넘기는 JSON Schema 는 pydantic 이 만든 것이라 `oneOf` · `discriminator` · 길이 제약이 들어 있다. Claude API 의 형식 강제는 이 키워드를 받지 않는다.

## 2. 결정

- 사용자 요청: Claude API 키로 연결 (2026-11-14). 처음에는 OpenAI 를 말했다가 Claude API 로 바꿈.
- 공식 SDK `anthropic` 를 의존성으로 추가한다 (`uv add anthropic` → 2.8.0). 재시도(429 · 5xx) · 시간 초과 · 오류 구분을 SDK 가 한다.
  [사용자에게 SDK / 직접 호출 중 무엇을 쓸지 물었으나 답이 키 전달로 왔다 — 추천안이던 SDK 로 진행하고 보고에 적음.]
- 기본값은 `claude-cli` 그대로. `SPECBUILDER_LLM=anthropic-api` 일 때만 Claude API 를 쓴다 — 기존 테스트와 품질 회귀 기록이 유효하게 남는다.
- 스키마는 SDK 의 `anthropic.transform_schema()` 로 API 형식으로 바꾼다. 빠진 제약은 노드의 pydantic 검증이 응답을 받은 뒤 다시 본다 (지금도 하는 일).
- 스트리밍으로 받고 완성된 메시지만 꺼낸다 — `generate_artifacts` 출력이 길어 비스트리밍은 연결이 끊길 수 있다. `max_tokens` 64000.
- effort 는 `medium` 고정 — 모델마다 기본값이 달라(opus-5-5 medium, sonnet-5-5 high) 모델을 바꿔도 깊이가 같게.
- 거절 대비 서버 측 대체 실행(`fallbacks: "default"`, beta `server-side-fallback-2026-07-01`)을 지원 모델(opus-5-5, sonnet-5-5)에서 켠다.
- `.env` 는 코드로 읽지 않고 `uv run --env-file .env` 로 넘긴다 — 의존성과 코드가 늘지 않는다.
- LLM 호출 수는 변하지 않는다. 호출 수단만 바뀐다.

## 3. 건드린 파일

| 파일 | 변경 |
|---|---|
| `builder/src/specbuilder/llm/client.py` | `AnthropicAPIClient`, `make_client()` |
| `builder/src/specbuilder/llm/__init__.py` | 내보내기 추가 |
| `builder/src/specbuilder/graph/main.py`, `api/main.py` | `ClaudeCLIClient()` → `make_client()` (각 2줄) |
| `builder/tests/llm/test_client.py` | 가짜 SDK 클라이언트로 요청 모양 · 스키마 변환 · 오류 감싸기 · 클라이언트 선택 테스트 (실제 호출 없음) |
| `builder/tests/test_main.py` | CLI 테스트가 바꿔 끼우는 이름 `ClaudeCLIClient` → `make_client` (1줄) |
| `builder/pyproject.toml`, `builder/uv.lock` | `anthropic` 추가 |
| `builder/.env.example`, `builder/AGENTS.md` | 새 환경 변수와 실행 명령 |

## 4. 검증 결과 (2026-11-14)

```
$ cd builder && uv run pytest -q
197 passed, 13 warnings in 1.26s     # 경고는 기존과 같은 langsmith DeprecationWarning
$ uv run ruff check . && uv run ruff format --check .
All checks passed!
```

실제 호출 [확정] — `SPECBUILDER_LLM=anthropic-api`, 모델 `claude-opus-5-5`, `anthropic` 2.8.0:

- `interview_user` 프롬프트 + 스키마로 1회: 18.2초, 응답이 `interview_reply_adapter` 검증 통과 (스펙 항목 12개, 질문 8개).
  `transform_schema` 로 바꾼 스키마, 형식 강제, 대체 실행 옵션이 한 요청에서 함께 받아들여졌다.
- 스키마 없는 호출 1회: 1.5초.
