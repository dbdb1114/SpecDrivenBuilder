# 작업 단위 E — FastAPI · 질문 화면 · 확인 화면 (`feat/web-ui`)

제약: `constraints.md`. 설계: `docs/design/design.md`, `docs/design/question-format.md`.

## 분석

- [확정] A 가 `develop` 에 머지됨 (`2b13db7`). 규격 모델은 `state/question_format.py`·`state/spec_items.py` 에 TypedDict 로 있고,
  노드 8개가 `graph/build.py` 에 등록돼 있으며, `confirm_spec` 은 빈 노드(곧장 `generate_artifacts` 로 감). `FakeLLM` 은 노드별 응답. `uv run pytest` 44 passed.
- [확정] FastAPI 0.162.5 는 이 TypedDict(판별 유니온 `Answer`·`ConfirmReply` 포함)를 요청 본문·응답 모델로 그대로 받는다.
  OpenAPI 스키마 이름이 규격 이름 그대로 나온다 (`QuestionBundle`, `AnswerSubmission`, `ConfirmScreen`, `ReviseAction` …).
  잘못된 `kind` → 422. (`uv run --with fastapi` 임시 환경으로 확인, 프로젝트에 추가하지 않음)
- [확정] `graph.get_state(config).tasks[i].name` 으로 어느 노드가 interrupt 했는지 안다 (`interview_user`).
  잘못된 답으로 resume 하면 노드가 `ValueError` 를 내고, 체크포인트는 interrupt 상태 그대로 남아 다시 답할 수 있다.
  없는 thread_id 는 `values == {}`.
- [확정] `SqliteSaver.from_conn_string` 은 `check_same_thread=False` 로 연다 — FastAPI 동기 엔드포인트(스레드풀)에서 써도 된다.
- [확정] `frontend/` 는 `AGENTS.md`·`CLAUDE.md`·`src/.gitkeep` 뿐. Node 24.20.0, npm 11.19.0.
- [확정] `openapi-typescript` 7.13.0 과 `typescript-eslint` 는 TypeScript `^5` 만 지원 → TypeScript 는 7.x 가 아니라 5.9.3 을 쓴다.
- [확정] 이 작업 단위의 "미결정"은 `question-format.md` 의 "OpenAPI 에서 프론트엔드 타입을 생성하는 도구" 하나.
  스타일 방식은 `frontend/AGENTS.md` 에서 "첫 결정은 물어서" — 이번이 첫 프론트엔드 작업이므로 묻는다.

## API (`/api/**`)

| 메서드 · 경로 | 본문 | 하는 일 |
|---|---|---|
| `POST /api/runs` | `{ "request": str }` | thread_id 를 만들고 `initial_state` 로 invoke → `RunView` |
| `GET /api/runs/{run_id}` | — | 현재 상태 → `RunView` (새로고침 · 다시 열기용) |
| `POST /api/runs/{run_id}/answers` | `AnswerSubmission` | 대기 중인 질문 묶음으로 `validate_submission` 한 뒤 `Command(resume=…)` → `RunView` |
| `POST /api/runs/{run_id}/confirm` | `ConfirmReply` | 대기 중인 확인 화면이 맞는지, `item_ids` 가 `editable` 인지 확인한 뒤 resume → `RunView` |
| `POST /api/runs/{run_id}/retry` | — | 멈춘 실행(LLM 실패 등)을 `invoke(None)` 로 이어서 → `RunView` |
| `GET /api/runs/{run_id}/artifacts.zip` | — | 산출물 zip 다운로드 |

`RunView` (api 응답 전용 — 규격 모델은 고치지 않고 감싸기만):

```
run_id: str
status: "question" | "confirm" | "stalled" | "done"
bundle: QuestionBundle | None        # status == question
confirm: ConfirmScreen | None        # status == confirm
artifacts: dict[str, str]            # status == done 일 때 파일명 → 내용
```

- status 판정은 `get_state` 만 본다: interrupt 가 있으면 interrupt 한 노드가 `confirm_spec` 이면 `confirm`, 아니면 `question`.
  interrupt 없이 `next` 가 남아 있으면 `stalled`, 없으면 `done`. 직렬화이지 로직이 아니다 — 노드 이름 하나로 화면 종류만 고른다.
- 에러: 없는 run → 404, 다른 화면 상태에서 온 요청(질문 대기 중 confirm 등) → 409, 규격 · 묶음 불일치 → 422,
  `LLMCallError` → 502 (실행은 `stalled` 로 남아 `retry` 할 수 있음).
- thread_id = `<YYMMDD-HHMMSS>-web-<6hex>` (`state.md` 의 실행 ID 형식에 맞춤. 케이스 파일이 없으니 `web-` + 난수).
- 앱은 `create_app(graph=None)` 팩토리. 테스트는 FakeLLM + `InMemorySaver` 그래프를 넣고, 운영은 lifespan 에서
  `SqliteSaver(.checkpoints.sqlite)` + `ClaudeCLIClient` 로 `build_graph` 를 연다. OpenAPI 경로는 `/api/openapi.json` (`frontend/AGENTS.md`).
- 산출물을 디스크(`output/`)에 쓰지 않는다 — 파일 기록은 CLI 의 일이고 웹은 zip 으로 내려준다. `run.json` 도 CLI 만.
- `api/` 에서 `nodes/` 를 import 하지 않는다. 쓰는 것: `graph.build`, `state` 의 규격 모델과 `validate_submission`, `llm`, `paths`.

## 프론트엔드

- 스캐폴드: Vite 8 + React 19 + TypeScript 5.9, `npm run dev/build/lint/test/gen:types`. `/api` 는 `localhost:8000` 으로 프록시.
- 타입: `npm run gen:types` = `openapi-typescript http://localhost:8000/api/openapi.json -o src/types/api.d.ts`.
  `src/api/` 의 fetch 래퍼 하나가 이 타입(`components["schemas"][…]`)만 쓴다. 생성 결과는 커밋한다.
- 라우터 · 상태 관리 라이브러리를 넣지 않는다 — 화면은 `RunView.status` 하나로 갈린다. `run_id` 는 URL `?run=` 에 둬서 새로고침해도 이어진다.
- 화면
  - 시작: 요청 원문 입력 → `POST /api/runs`.
  - 질문 (`status: question`): 질문 카드 1~10개. 선택지는 번호 버튼 + `(추천)` 표시, 마지막에 고정 버튼 "알아서 정해 주세요",
    그리고 직접 입력란. `multiple` 이면 여러 개 토글. 답하지 않은 질문은 제출에서 빼서 맡김으로 처리(규격대로).
    "다음" = `submit`, `can_finish` 면 "그만 묻고 만들어 주세요" = 지금까지 고른 답과 함께 `finish`.
    `visual` · `preview` 는 그리지 않는다 — 값이 와도 무시하고 화면은 그대로.
  - 확인 (`status: confirm`): 영역별(용도·기능 / 디자인 / 기술) 요약, 상태 표시(확정 / 맡김).
    `editable` 항목만 "고칠래요" 체크. "이대로 만들어 주세요" = `confirm`, "고른 항목 다시 답할게요" = `revise`.
    기술 항목은 내용 한 줄만 보여 준다.
  - 완료 (`status: done`): 파일 목록과 내용 펼쳐 보기, zip 받기 링크.
  - 기다림 · 실패: LLM 호출 동안 "정리하고 있어요" 표시, 실패(`stalled` 또는 502)면 메시지와 "다시 시도"(`retry`).
- `confirm_spec` 이 빈 노드라 실제 흐름에서는 확인 화면이 나오지 않는다. 확인 화면은 `question-format.md` 의 예시 JSON 을
  고정 데이터로 컴포넌트 테스트 + API 테스트(테스트 안에서 `confirm_spec` 이름으로 interrupt 하는 작은 그래프)로 검증한다.

## 추가할 의존성 (승인 필요)

- builder: `fastapi`, `uvicorn` (`uv add`) · dev `httpx` (FastAPI `TestClient` 가 요구).
  `fastapi[standard]` 는 CLI·이메일 검증 등까지 끌고 오므로 쓰지 않는다.
- frontend dependencies: `react`, `react-dom`
- frontend devDependencies: `vite`, `@vitejs/plugin-react`, `typescript@~5.9`, `@types/react`, `@types/react-dom`,
  `openapi-typescript`, `vitest`, `jsdom`, `@testing-library/react`, `@testing-library/user-event`, `@testing-library/jest-dom`,
  `eslint`, `@eslint/js`, `typescript-eslint`, `eslint-plugin-react-hooks`, `globals`
- 스타일 방식에 따라 추가 (질문 참고): CSS Modules 는 Vite 내장이라 추가 없음.

## 건드릴 파일

- builder (신규): `src/specbuilder/api/__init__.py`, `api/main.py`(앱 · lifespan · 라우트), `api/schemas.py`(`RunView`, `StartRun`),
  `tests/api/__init__.py`, `tests/api/test_runs.py`
- builder (수정): `pyproject.toml`·`uv.lock` (`uv add` 로만)
- frontend (신규): `package.json`, `package-lock.json`, `index.html`, `vite.config.ts`, `tsconfig.json`, `eslint.config.js`,
  `src/main.tsx`, `src/App.tsx`, `src/api/client.ts`, `src/types/api.d.ts`(생성), `src/pages/` (시작 · 질문 · 확인 · 완료),
  `src/components/`(선택지 버튼 등 재사용분), 스타일 파일, 테스트 파일들, `src/test-setup.ts`. `src/.gitkeep` 삭제.
- docs: 이 폴더, `docs/design/question-format.md` "미결정"의 타입 생성 도구 줄 → 결정으로,
  `frontend/AGENTS.md` 스타일 방식 줄 → 결정으로 (질문 답에 따라).

안 건드리는 것: `graph/`, `state/`, `nodes/`, `prompts/`, `templates/`, `tests/fakes/`, 루트 `AGENTS.md`(용어 추가 없음).

## 검증

1. `uv run pytest` — 기존 44개 + API 테스트: 시작 → 질문 묶음, 답 제출 → 완료 · 산출물, `finish`, 잘못된 답 422 후 다시 답하기,
   없는 run 404, 상태가 맞지 않는 요청 409, LLM 실패 502 → `stalled` → `retry`, 확인 화면 confirm · revise(편집 불가 항목 422), zip 내용.
2. `uv run ruff check . && uv run ruff format --check .`
3. 프론트: `npm run lint`, `npm run test`(질문 화면 · 확인 화면 컴포넌트 테스트), `npm run build`(타입 검사 포함).
4. `npm run gen:types` 를 실제 서버에 대고 돌린 뒤 `git diff --exit-code src/types/api.d.ts` — 생성물과 서버 규격이 일치.
5. 실제 실행: `uvicorn` + `npm run dev` 로 띄워 브라우저에서 evals 케이스 하나를 시작 → 질문 묶음 답 → 산출물 zip 까지 한 번 돌린다
   (실제 `claude -p`, 모델 · 날짜를 아래에 기록). 이 작업은 프롬프트 · 노드 · 템플릿을 바꾸지 않으므로 품질 회귀 비교는 하지 않는다.

## 결정 (계획 승인 때, 2026-11-13)

- 스타일 방식: CSS Modules (사용자 선택). `frontend/AGENTS.md` 에 기록.
- 의존성 추가 승인. 타입 생성 도구 `openapi-typescript` 는 `question-format.md` "원칙" 에 결정으로 옮기고 "미결정" 에서 뺐다.

## 계획과 달라진 것

- `RunView` 에 `error: str | None` 추가. `LLMCallError` 를 502 로 돌려주면 시작 요청에서 실패했을 때 화면이 run_id 를 받지 못해
  "다시 시도" 를 붙일 수 없다. 그래서 200 + `status: stalled` + `error` 로 돌려준다 (error 는 저장하지 않음).
- 파일 목록에 없던 프론트 파일: `src/api/types.ts`(생성 타입에 짧은 이름만), `src/hooks/useRun.ts`(화면 상태),
  `src/components/Button`·`Notice`, `src/api/client.test.ts`. 모두 계획의 `src/api/`·`src/components/` 범위 안의 새 파일이다.
- `build` 스크립트는 `tsc -b` 대신 `tsc` (`noEmit` 단일 tsconfig).

## 검증 결과

- [확정] `uv run pytest` → 57 passed (기존 44 + `tests/api/test_runs.py` 13). 경고 13개는 기존과 같은 라이브러리 내부 `asyncio.iscoroutinefunction` 지원 종료 경고.
- [확정] `uv run ruff check .` → All checks passed. `uv run ruff format --check .` → 50 files already formatted.
- [확정] `npm run lint` → 오류 없음. `npm run test` → 3 files, 12 tests passed. `npm run build` → 성공.
- [확정] `npm run gen:types` 를 실행 중인 서버에 대고 다시 돌려 커밋할 `src/types/api.d.ts` 와 diff 없음.
- [확정] 실제 실행 (2026-11-13, `claude-sonnet-5-5` 기본값, `claude -p`): `uvicorn` + `npm run dev`, Chrome 에서 `evals/cases/01-short.md` 원문으로
  시작 → 질문 묶음 1(4문항: 선택 · 여러 개 · 직접 입력 · 비워 둠) → 질문 묶음 2 → 새로고침해도 같은 묶음 복원 → "그만 묻고 만들어 주세요"
  → 완료 화면 → zip(`spec.md`·`SKILL.md`·`AGENTS.md`·`CLAUDE.md`) 다운로드. 직접 입력한 "그래프로 보고 싶어요" 와 고른 답이 spec.md 에 반영됨.
  브라우저 콘솔 오류 없음. 첫 실행에서 질문 카드 제목(legend)이 테두리에 걸려 CSS 를 고친 뒤 새 실행으로 다시 확인.
- [확정] 확인 화면은 실제 흐름에서 나오지 않는다 (`confirm_spec` 빈 노드). 고정 데이터로 컴포넌트 테스트 3개 + API 테스트 2개로만 검증.
- 프롬프트 · 노드 · 템플릿을 바꾸지 않았으므로 품질 회귀 비교는 하지 않았다.
- [확정] `npm audit`: moderate 10건, 전부 eslint · typescript-eslint 가 쓰는 `minimatch`(ReDoS). lint 실행에만 쓰는 dev 의존성이고
  `audit fix --force` 는 eslint 메이저 다운그레이드라 그대로 둔다.

토큰 소모: [추정] 약 30~40만 토큰 (문서 · 코드 읽기, 브라우저 검증 스크린샷 포함. `/usage` 로 확인하지 않음). 실제 LLM 호출은 빌더 쪽 `claude -p` 약 5회.
