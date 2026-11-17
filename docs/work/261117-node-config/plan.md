# 노드 설정 파일 (작업 단위 K)

## 1. 분석

- [확정] 모델은 환경 변수 `SPECBUILDER_MODEL` 하나로 모든 노드에 같이 적용된다 (`llm/client.py`). effort 는 상수 `API_EFFORT = "medium"`.
- [확정] 한 사이클 비용은 노드마다 크게 다르다 — `generate_artifacts` 44%, `select_stack` · `interview_design` 각 18% (`docs/work/261114-prompt-cache/plan.md`, 실행 `261117-191318-web-44837e`).
- [확정] 클라이언트는 호출하는 노드를 `for_node` 껍데기로 안다 (`graph/build.py` 가 노드마다 씌운다).

## 2. 결정 (계획 단계에서 정할 것)

| 정할 것 | 결정 | 이유 |
|---|---|---|
| 파일 위치 | `builder/config/nodes.json` | 프롬프트(`prompts/`)도 산출물 서식(`templates/`)도 아닌 빌더 자신의 설정이라 폴더를 따로 둔다 |
| 형식 | JSON | 백오피스가 고쳐 써야 한다. Python 표준 라이브러리는 TOML 을 읽기만 한다 — 의존성을 늘리지 않는다 |
| 어떤 값까지 | 모델 · effort | 돌아가는 횟수 상한은 넣지 않았다. 노드 코드의 상수이고 테스트가 그 값에 묶여 있어, 옮기는 일이 이 작업보다 크다 |
| 읽는 때 | 호출할 때마다 | 고치면 서버를 다시 띄우지 않고 반영된다 (`backoffice.md` "그 뒤에 시작하는 실행부터") |
| 틀린 설정 | 그 호출을 실패시킨다 | 기본값으로 조용히 돌면 다른 모델로 돈 결과를 믿게 된다 |

`backoffice.md` 는 "돌아가는 횟수 상한"도 노드 설정으로 적었다 — 이번에는 넣지 않았으므로 그 문서의 표를 모델 · effort 로 고친다.

## 3. 변경

| 파일 | 변경 |
|---|---|
| `builder/config/nodes.json` (새 파일) | LLM 을 쓰는 노드 5개, 모두 `null` (지금 동작 그대로) |
| `builder/src/specbuilder/node_config.py` (새 파일) | 읽기와 검증 |
| `builder/src/specbuilder/llm/client.py` | 노드 설정의 모델 · effort 를 두 클라이언트가 따른다. 호출 기록에 실제 쓴 모델 · effort |
| `builder/tests/test_node_config.py` (새 파일), `tests/conftest.py`, `tests/llm/test_trace.py` | 위 동작. 테스트는 레포의 설정 파일을 읽지 않는다 |
| `builder/AGENTS.md`, `docs/design/backoffice.md` | 사용법, 표 수정 |

LLM 호출 수는 그대로다. 기본값이 모두 `null` 이라 동작도 그대로다.

## 4. 검증 결과

```
$ cd builder && uv run pytest -q
267 passed, 13 warnings          # 257 → 267
$ uv run ruff check . && uv run ruff format --check .
All checks passed!
```

실제 호출 2회 (2026-11-17, Claude API): `select_skills` 를 `claude-haiku-5-5` · `low` 로 설정한 임시 파일로 호출.

```
llm usage node=select_skills model=claude-haiku-5-5 input=30 output=5 …
llm usage node=select_stack  model=claude-sonnet-5-5 input=30 output=5 …
```

설정한 노드만 다른 모델로 돌았다.

## 5. 안 한 것 / 남은 것

- 어느 노드를 싼 모델로 돌려도 되는지는 재지 않았다. 이 작업은 고를 수 있게만 한다. 품질은 기록 재생 비교(작업 단위 N)나 품질 회귀로 판정한다.
- `claude -p`(기본 수단)는 모델만 따른다. effort 는 Claude API 일 때만 적용된다.
- 돌아가는 횟수 상한은 설정으로 빼지 않았다.

토큰 소모 [추정]: 세션 약 5만 토큰 + Claude API 호출 2회.
