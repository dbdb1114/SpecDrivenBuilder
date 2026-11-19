# 백오피스 뼈대 · 호출 기록 · 노드 설정 (작업 단위 L)

## 1. 분석

- [확정] 호출 기록은 `output/_traces/<run_id>.jsonl`, 한 줄이 호출 하나. 키는 `at · node · model · effort · response | error · seconds · usage{input,output,cache_write,cache_read} · system · prompt` (`llm/client.py` 의 `trace.record`). 위치는 `trace.trace_dir()` (`SPECBUILDER_TRACE_DIR` 로 바꿀 수 있음).
- [확정] 비용 계산은 `trace.cost(model, usage)` — 가격표에 없는 모델은 `None`. 표·합계 로직은 `trace.summarize()` 안에 문자열 만들기와 섞여 있다.
- [확정] 실행마다 쓴 노드 설정(모델 · effort)은 이미 호출마다 기록된다 (작업 단위 K). 이 작업에서 기록 형식은 바꾸지 않는다.
- [확정] 노드 설정 검증은 `node_config.load()` 안에 파일 읽기와 섞여 있다 (`_adapter` + 모르는 노드 거부). 쓰는 함수는 없다.
- [확정] `api/main.py` 의 `create_app(graph=None)` 이 앱을 만든다. 라우터 분리는 아직 없다.
- [확정] 프론트엔드는 라우터 없이 `App.tsx` 하나가 `RunView.status` 로 화면을 고른다. 테마는 `useTheme` + `index.css` 의 토큰 (`:root` / `[data-theme="light"]`).
- [확정] Starlette `TestClient(client=("127.0.0.1", …))` 로 요청 주소를 바꿀 수 있다 — "이 컴퓨터에서 온 요청만" 을 테스트할 수 있다. 기본값은 `"testclient"`.
- [확정] 확인용 기록: 이 worktree 에는 없고 원본 레포에 `261117-191318-web-44837e.jsonl` (호출 11회) 한 개가 있다. 복사해 쓴다.

## 2. 계획 단계에서 정할 것

> 결정 (2026-11-17, 사용자 승인): 환경 변수 `SPECBUILDER_BACKOFFICE`, 화면 주소 `/backoffice/` 별도 진입점. 둘 다 추천안.

### 2-1. 백오피스를 켜는 환경 변수 이름

1. **`SPECBUILDER_BACKOFFICE=1` (추천)** — 다른 설정과 같은 `SPECBUILDER_` 접두사, `SPECBUILDER_TRACE` 와 같은 켜기 규칙(빈 값·`0` 이면 꺼짐).
2. `SPECBUILDER_DEV_TOOLS=1` — 범위가 넓어 보여서, 나중에 다른 개발 도구가 생기면 하나로 같이 켜진다.
3. 네가 정해

### 2-2. 화면 주소

1. **`/backoffice/` — Vite 의 두 번째 진입점 (`frontend/backoffice/index.html`) (추천)** — 사용자 화면 번들에 백오피스 코드가 아예 들어가지 않는다. 라우터 라이브러리 없이 주소가 갈린다. 백오피스 안의 탭(호출 기록 · 노드 설정)과 실행 선택은 `#traces/<run_id>` 같은 해시로 둔다 (새로고침해도 그 화면).
2. 같은 진입점에서 `?backoffice` 로 분기 — 파일은 적지만 사용자 화면 번들에 백오피스 코드가 섞이고, `App.tsx` 에 분기가 생긴다.
3. 네가 정해

## 3. 변경

### 백엔드

| 파일 | 변경 |
|---|---|
| `builder/src/specbuilder/llm/trace.py` | 읽기 함수 추가: `list_runs()` (실행 이름 · 시작 시각 · 호출 수 · 토큰 합 · 달러), `run_rows(run_id)` (호출별 행: 번호 · 노드 · 모델 · effort · 토큰 4개 · 초 · 달러 · 실패 여부), `call(run_id, n)` (전문). `run_id` 는 `[A-Za-z0-9_-]+` 만 받고 `trace_dir()` 안의 파일로 바꾼다. 비용은 기존 `cost()` 를 쓴다. 기존 `summarize()`/`show()`(터미널 표)는 그대로 |
| `builder/src/specbuilder/node_config.py` | `load()` 의 검증 부분을 `validate(data)` 로 떼어 내고 `save(settings)` 추가 (검증 통과한 것만 `CONFIG_FILE` 에 씀). `load()` 동작은 그대로 |
| `builder/src/specbuilder/api/backoffice.py` (새 파일) | `APIRouter(prefix="/api/backoffice")`. 의존성: 요청 주소가 `127.0.0.1`/`::1` 이 아니면 403, `Host` 헤더가 `localhost`/`127.0.0.1`/`[::1]` 가 아니면 403 (다른 사이트가 DNS 로 이 컴퓨터를 가리켜 브라우저로 읽어 가는 경우를 막는다). 엔드포인트: `GET /traces`, `GET /traces/{run_id}`, `GET /traces/{run_id}/calls/{n}`, `GET /nodes`, `PUT /nodes`. 파싱 → `trace`/`node_config` 호출 → 직렬화만 |
| `builder/src/specbuilder/api/schemas.py` | 위 응답 모양 TypedDict (`RunSummary`, `CallRow`, `CallDetail`, `NodeSettingsView` — 노드 목록 · effort 선택지 · 기본 모델 · 파일이 틀렸을 때의 오류 문구) |
| `builder/src/specbuilder/api/main.py` | `create_app` 에서 환경 변수가 켜졌을 때만 `include_router`. 꺼져 있으면 라우터도 OpenAPI 에도 없다 |
| `builder/tests/api/test_backoffice.py` (새 파일) | 꺼져 있으면 백오피스 모든 주소 404 + OpenAPI 에 없음 · 이 컴퓨터가 아닌 주소/Host 는 403 · 기록 목록·표·전문 · 없는 실행 404 · `../` 같은 run_id 거부 · 설정 저장 성공 / 틀린 값 422 이고 파일 그대로 |
| `builder/tests/llm/test_trace.py`, `builder/tests/test_node_config.py` | 새 읽기 함수, `save()` |
| `builder/.env.example`, `builder/AGENTS.md`, `docs/design/backoffice.md` | 켜는 법 한 줄씩, backoffice.md 의 "구현 전" 을 L 반영으로 |

### 프론트엔드

| 파일 | 변경 |
|---|---|
| `frontend/backoffice/index.html`, `frontend/vite.config.ts` | 두 번째 진입점 (`build.rollupOptions.input`). 첫 그리기 전 테마 스크립트는 기존 `index.html` 의 것을 그대로 |
| `frontend/src/backoffice/main.tsx`, `BackofficeApp.tsx` (+ `.module.css`) | 머리줄(제목 · 탭 · 테마 전환), 해시로 화면 선택. 백오피스가 꺼져 있으면(404) 켜는 법을 보여 준다 |
| `frontend/src/backoffice/TracesPage.tsx`, `NodesPage.tsx` (+ `.module.css`, `.test.tsx`) | 실행 목록 → 호출 표 → 호출 전문(system · prompt · response 접기). 노드 설정 표(모델 입력 + 기본값 비우기, effort 선택), 저장, 서버 검증 오류 표시 |
| `frontend/src/api/backoffice.ts`, `frontend/src/api/types.ts` | 백오피스 호출 함수, 생성 타입 별칭 |
| `frontend/src/types/api.d.ts` | 재생성. `gen:types` 스크립트는 8000 고정이라 고치지 않고, 백오피스를 켠 이 브랜치 서버(다른 포트)를 향해 같은 `openapi-typescript` 명령을 주소만 바꿔 실행 |

색은 전부 `index.css` 토큰만 쓴다. 사용자 화면(`App.tsx` · `Header` · pages)은 건드리지 않는다.

LLM 호출 추가 없음. 의존성 추가 없음.

## 4. 검증

- `cd builder && uv run pytest -q`, `uv run ruff check . && uv run ruff format --check .`
- `cd frontend && npm run lint && npm run test && npm run build`
- 브라우저: 원본 레포의 기록을 `builder/output/_traces/` 로 복사 → 백오피스 켠 서버(다른 포트) + `npm run dev` → `/backoffice/` 에서 실행 목록 · 표 · 전문 · 설정 저장 후 `git diff builder/config/nodes.json` 확인 → 되돌림. 두 테마, 좁은 폭(390px). 백오피스를 끈 서버에서 `/api/backoffice/traces` 404.

## 5. 검증 결과

```
$ cd builder && uv run ruff check . && uv run ruff format --check . && uv run pytest -q
All checks passed! / 80 files already formatted
300 passed, 13 warnings          # 267 → 300
$ cd frontend && npm run lint && npm run test && npm run build
eslint 경고 0 / Test Files 8 passed, Tests 52 passed / built
```

- 타입: 백오피스를 켠 이 브랜치 서버(8011)에서 `openapi-typescript` 로 `src/types/api.d.ts` 재생성. 마지막 코드로 다시 뽑아 diff 없음 확인.
- 빌드: `dist/backoffice/index.html` 이 따로 나오고, 사용자 화면 번들(`main-*.js`)에는 백오피스 문자열이 없다.
- 끈 서버(8012, 환경 변수 없음): `/api/backoffice/{traces, traces/<run>, traces/<run>/calls/1, nodes}` 모두 404, OpenAPI 에 `backoffice` 0건.
  켠 서버에 `Host: evil.example` 로 요청하면 403.
- 브라우저 (Chrome 헤드리스, Playwright, 2026-11-17): 원본 레포의 기록 `261117-191318-web-44837e.jsonl` 을 `builder/output/_traces/` 로 복사.
  실행 목록 · 호출 표(11행, 합계 $0.2597 — `show_trace` 와 같은 값) · 11번째 호출 전문 · 노드 설정을
  어두운/밝은 테마 × 1280px/390px 로 확인. 페이지 가로 넘침 0 (390px 노드 설정이 217px 넘쳤던 것을 고침 — 그리드 칸의 `min-width`).
  콘솔 오류는 favicon 404 하나 (사용자 화면과 같음). 홈 화면에 백오피스로 가는 링크 0개.
- 저장: 화면에서 `select_stack` effort `low`, `select_skills` 모델 `claude-haiku-5-5` 저장 → `git diff builder/config/nodes.json` 이 그 두 줄만 바뀜 → 되돌림.

## 6. 계획과 다른 점 / 안 한 것

- 계획의 폴더 안에서 파일을 더 나눴다: `src/backoffice/` 에 `route.ts`(해시 주소) · `useRoute.ts` · `useLoad.ts`(읽기 훅) · `format.ts` · `route.test.ts`,
  CSS 는 화면별이 아니라 `backoffice.module.css` 하나.
- `src/api/backoffice.ts` 는 `client.ts` 의 오류 문구 함수를 쓰지 않고 짧게 따로 둔다 — `client.ts` 를 고치지 않으려고 (계획 밖 파일).
- 실패한 호출(사용량 없음)이 섞인 실행은 달러 합계를 "—" 로 둔다. 터미널 `show_trace` 와 같은 규칙.
- `frontend/AGENTS.md` 의 구조 · "라우터는 두지 않는다" 항목에 백오피스 진입점을 적지 않았다 (계획 밖).
- 화면에서 고친 `effort` 는 `claude -p`(기본 수단)로 돌 때는 적용되지 않는다 (작업 단위 K 그대로). 화면 문구로만 알린다.

토큰 소모 [추정]: 세션 약 15만 토큰. LLM 새 호출 없음.
