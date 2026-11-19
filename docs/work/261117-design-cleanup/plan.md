# `interview_design` 정리 — 버튼 위 글자색 · 끝 확인 호출 생략 (`feat/design-cleanup`)

제약: `constraints.md`. 설계: `docs/design/question-format.md` "preview", `docs/design/design.md` "interview_design".

## 1. 분석

### 버튼 위 글자색

- [확정] 규격 원본 `builder/src/specbuilder/state/question_format.py:59` `PreviewColors{background, surface, primary, accent, text}`.
  OpenAPI → `frontend/src/types/api.d.ts` → `frontend/src/api/types.ts` 의 `Preview`.
- [확정] 면·글자색은 `nodes/interview_design.py` 의 `role_colors()` 가 계산한다 (WCAG 휘도·`contrast()` 가 같은 파일에 있음).
  `_describe()` 가 색 톤 항목 내용을 `"라벨 (주색 #…, 바탕 #…, 강조 #…, 면 #…, 글자 #…)"` 로 쓰고, `_build_preview()` 는 내용의 앞 세 HEX 만 읽는다 —
  뒤에 색을 하나 더 붙여도 읽기는 그대로다.
- [확정] 프론트 `Preview.module.css:83` `.button { background: var(--p-accent); color: var(--p-bg); }`. 강조색을 채운 면 위에 글자가 있는 곳은 `.button` 하나
  (`.logo` 는 글자 없음, 나머지 accent 는 선·그림자). `.button` 은 틀 6개 모두에 나온다 (`TitleRow` 4개, `list-detail` 상세, `mobile-tabs` 의 `fab`).
- [확정] 대비 실측 (`contrast()`): 베이지 강조 `#D9A05B` 위 바탕 `#FAF6F0` 2.14:1 → 검정 9.13:1 / 흰색 2.30:1.
  남색 예시 강조 `#4A90D9` 위 `#F5F7FA` 3.11:1 → 검정 6.28:1 / 흰색 3.34:1. 검정·흰색 중 나은 쪽은 수학적으로 항상 ≥ 4.58:1.
- [확정] 옛 미리보기 처리: `_drop_old_preview` (BeforeValidator) 가 `colors` 가 목록인 옛 형식을 `null` 로 읽는다. 질문 묶음은 checkpoint 의
  `pending_bundle` 과 API `RunView.bundle` 응답 검증을 지나므로, 새 필드를 필수로 하면 옛 묶음이 걸린 실행을 다시 열 때 처리가 필요하다.
- [확정] 새 필드를 쓰는 테스트 픽스처: `builder/tests/state/test_question_format.py:90`, `builder/tests/nodes/test_interview_design.py` (`tone()` 헬퍼 등),
  `frontend/src/components/Preview.test.tsx:8`, **`frontend/src/pages/StudioPage.test.tsx:188`** — `tsconfig` 가 `src` 전체를 포함하므로 `npm run build`(tsc)가
  이 픽스처에서 실패한다. StudioPage 는 다른 세션 범위 → **질문 Q1**.
- [확정] 프롬프트 `prompts/interview_design.md:47` "강조색 버튼 위에 바탕색 글씨가 잘 읽혀야 한다" — 바뀐 뒤엔 버튼 글자가 바탕색이 아니므로 문장이 낡지만,
  LLM 이 바탕과 구분되는 강조색을 고르게 하는 효과는 여전히 쓸모 있다 (고른 메뉴 선·로고). **프롬프트는 바꾸지 않는다** (아래 4).

### 끝 확인 호출

- [확정] 흐름: 미리보기 묶음 답 제출 → `interview_design` 이 답을 반영하고 `goto=NODE` → 다시 들어와 `rounds != 0` 이므로 LLM 호출
  → LLM 이 갱신·질문 없이 응답 → `needs_asking` 거짓 → `_stop(..., "resolved")`. 이 마지막 호출이 "끝났다는 확인"이다.
- [확정] 그 호출이 실제로 하는 일 두 가지: (a) 직접 적은 답(`custom`)을 읽고 항목을 새로 만듦, (b) 맡김(`delegate`)으로 내용이 빈 LLM 항목의 기본 방향을 채움.
  공통 항목 맡김은 `fill_defaults`, 색·배치 맡김은 `_record_choices` 가 추천 선택지로 이미 코드에서 채운다. 질문이 아예 없는 답도 맡김 취급.
- [확정] 생략하면 안 되는 경우가 하나 더 있다: 색·배치를 막 고른 묶음 직후. 미리보기 문구(`texts`)는 LLM 초안에서 나오므로 그 호출은 필요하다.
  `_build_preview()` 앞부분의 조건(색·배치 결정됨, 하나라도 사용자 결정, `preview-check` 없음 또는 아직 모름)이 곧 "미리보기를 그려야 함" 이다.
- [확정] `test_change_color_reasks_only_color_then_previews_again` 이 `interview_design` 호출 5회(묶음 4 + 마지막 반영 1)를 고정한다 → 4회로 바뀐다.
  `interview_stops` 의 `rounds: 4` 는 그대로 (생략 경로도 `rounds + 1` 로 멈춘다).
- [확정] `design.md:252` LLM 호출 수 표 "실행하면 질문 묶음 하나당 1회".

## 2. 정한 것

### 옛 checkpoint 의 미리보기 (새 역할이 없는 것)

**기존 방식대로 `null` 로 읽는다** (그림만 빠지고 질문 문장은 그대로). `_drop_old_preview` 조건에 "`colors` 에 `on_accent` 없음" 을 더한다.
이유: 없는 역할을 채우려면 휘도 계산을 규격 모듈(`state/`)로 옮기거나 복제해야 하는데, 영향은 개발용 SqliteSaver 에 남은 진행 중 묶음뿐이다
(운영 checkpointer 미결정). 한 번 그림이 빠지는 비용이 코드 이동보다 작다.

### 이름

- 필드 `colors.on_accent` — 프론트 토큰 `--on-ac`(강조 면 위 글자)와 같은 말. CSS 변수 `--p-on-accent`.
- 색 톤 항목 내용 끝에 `, 강조 위 글자 #000000` 를 붙인다. 용어사전에 새 용어는 넣지 않는다 (색 조합의 "글자" 의 한 갈래).

### 생략 조건 (`interview_design` 답 반영 직후, `finish` 가 아닌 `submit` 일 때)

모두 참이면 LLM 을 부르지 않고 `_stop(items, "resolved", rounds + 1, qa)`:
1. 이 묶음의 모든 질문의 답이 `option` 또는 `delegate` (답 없는 질문 = 맡김). `custom` 이 하나라도 있으면 호출.
2. 디자인 영역에 물을 항목 없음 (`needs_asking` 거짓).
3. 디자인 영역에 내용이 빈 맡김 항목 없음.
4. 미리보기를 그려야 하는 상태가 아님 (`_build_preview` 의 앞 조건을 `_preview_due()` 로 꺼내 둘이 같이 쓴다).

## 3. 건드릴 파일

| 파일 | 변경 |
|---|---|
| `builder/src/specbuilder/state/question_format.py` | `PreviewColors.on_accent` 추가, `_drop_old_preview` 에 "on_accent 없음" 조건 |
| `builder/src/specbuilder/nodes/interview_design.py` | `on_accent()` (검정/흰색 중 대비 높은 쪽), `role_colors` 가 채움, `_describe` 에 "강조 위 글자", `_preview_due()` 분리, 생략 조건 |
| `builder/tests/nodes/test_interview_design.py` | `tone()` 갱신, 호출 수 5→4, 추가: on_accent 대비 ≥4.5 (밝은·어두운 강조), "맞아요"만이면 호출 0, **미리보기에 직접 적은 답 → LLM 호출 → 새 항목(차트)이 생김**, 빈 맡김 항목이면 호출 |
| `builder/tests/state/test_question_format.py` | 픽스처에 `on_accent`, 옛 형식(on_accent 없음) → `null` |
| `frontend/src/types/api.d.ts` | `gen:types` 재생성 (서버는 8001 포트, `openapi-typescript` 에 그 URL 을 직접 넘김 — `package.json` 은 그대로) |
| `frontend/src/components/Preview.tsx` · `Preview.module.css` | `--p-on-accent` 변수, `.button` 글자색 |
| `frontend/src/components/Preview.test.tsx` | 픽스처에 `on_accent`, 변수 전달 확인 |
| `frontend/src/pages/StudioPage.test.tsx` | **Q1 답에 따라** — 픽스처 한 줄에 `on_accent` |
| `docs/design/question-format.md` | `preview` 예시·필드 표·계산 설명·옛 형식 문단에 `on_accent` |
| `docs/design/design.md` | `interview_design` 계약에 생략 조건 한 줄, LLM 호출 수 표 |
| `docs/work/261114-preview-format/plan.md` | "남은 것" 의 버튼 글자 항목에 "→ 261117-design-cleanup 에서 처리" 한 줄 |

프롬프트(`builder/prompts/`)는 바꾸지 않는다.

## 4. 검증

- `uv run pytest`, `uv run ruff check . && uv run ruff format --check .` (builder)
- `npm run test`, `npm run lint`, `npm run build` (frontend)
- 호출 수 3 → 2: 그래프 테스트(`FakeLLM` 호출 수)로 고정. 실제 모델로도 웹 실행 1회 (`SPECBUILDER_TRACE=1`, 8001 포트) — 색·배치 고르기 → "맞아요" 경로에서
  `interview_design` 호출 수를 `show_trace` 로 확인.
- 직접 적은 답 → 항목: 단위 테스트로 고정 (FakeLLM 응답이 차트 항목을 만들면 그 항목이 묶음에 들어가는가).
- 대비: 단위 테스트 (여러 강조색에서 `contrast(on_accent, accent) >= 4.5`).
- 브라우저: Vite 개발 서버 + 헤드리스 브라우저(스크래치패드에 임시 설치한 Playwright, 레포 의존성 아님)에서 `/api` 응답을 가로채
  베이지 `#D9A05B`·하늘색 `#4A90D9` 등 밝은 강조색 미리보기 6틀을 띄우고 스크린샷 + 버튼 글자의 계산된 색·대비를 읽는다.
- 품질 회귀: 프롬프트를 바꾸지 않으므로 돌리지 않는다. 색 톤 항목 내용 문장이 한 조각 늘어나는 것은 산출물 서식 변화가 아니다
  (스냅샷 테스트가 있으면 함께 갱신).

## 5. 결과

계획 밖 파일: 없음. `StudioPage.test.tsx` 는 Q1 결정(2026-11-17, "픽스처 한 줄 수정")대로 188행 한 줄만.

### 검증 (2026-11-17)

- [확정] `uv run pytest -q` → 280 passed. `uv run ruff check .` → All checks passed, `ruff format --check .` → 78 files already formatted.
- [확정] `npm run test` → 5 files / 36 tests passed. `npm run lint` → 오류 없음. `npm run build` (tsc + vite) → built.
- [확정] 타입 재생성: 이 브랜치 서버를 8001 에 띄우고 `npx openapi-typescript http://localhost:8001/api/openapi.json -o src/types/api.d.ts` — diff 는 `on_accent` 필드와 설명뿐.
- [확정] 직접 적은 답 → 항목: `test_typed_preview_feedback_still_calls_llm_and_adds_item`. `_settled` 의 custom 검사를 일부러 끄면 이 테스트만 실패함을 확인 (되돌림).
- [확정] 대비: `test_on_accent_is_black_or_white_readable_on_accent` (베이지·하늘·노랑·회색·남색·라벤더·검정 강조색 모두 ≥ 4.5).

### LLM 호출 수 (실제 모델, `claude-cli` 기본 모델, `SPECBUILDER_TRACE=1`, 8001 포트, 질문마다 추천 선택지를 고르는 스크립트)

| 실행 | 케이스 | 경로 | `interview_design` 호출 |
|---|---|---|---|
| `261117-214157-web-729e6a` | 03-vague | 색·배치·글자 크기 묻기 → 미리보기 "맞아요" → 확인 화면 | **2회** (바꾸기 전 이 경로는 3회 — 마지막이 확인만 하는 호출) |
| `261117-214013-web-277eb3` | 01-short | LLM 이 색·배치를 맡김으로 채우고 바로 미리보기 + 글자 크기 → "맞아요" | **1회** (바꾸기 전 2회) |

- [확정] 두 실행 모두 "맞아요" 뒤 바로 `select_stack`. 색 톤 내용: `차분한 남색 (주색 #1E3A5F, 바탕 #F5F7FA, 강조 #4A90D9, 면 #FBFCFD, 글자 #122339, 강조 위 글자 #000000)`.
- [확정] **발견:** PROMPT 가 예로 든 `261117-191318-web-44837e` 의 3번째 `interview_design` 호출은 확인만 하는 호출이 아니라
  미리보기에 직접 적은 답("차트 … 시각화하면 좋을 것 같은데")을 읽어 `progress-chart` 항목을 만든 호출이다 (trace 응답으로 확인).
  그 실행을 다시 돌려도 3회가 맞다 — 생략 규칙이 지켜야 할 경로 그대로다. 3 → 2 는 "맞아요" 로 끝나는 경로(위 03-vague)에서 확인했다.

### 브라우저 (미리보기 틀 6개, 밝은 강조색)

Vite 개발 서버(5199) + 시스템 Chrome 헤드리스(스크래치패드의 `playwright-core`, 레포 의존성 아님). `/api/runs/*` 응답을 가로채
빌더 코드(`role_colors`)로 만든 미리보기를 실제 `StudioPage` 에 띄우고, `.button` 의 계산된 글자색·배경색으로 대비를 쟀다.

| 틀 | 강조색 | 버튼 글자 | 대비 (전: 바탕색 글자) |
|---|---|---|---|
| single-column | 베이지 `#D9A05B` | `#000000` | 9.13 (2.14) |
| top-nav | 하늘 `#4A90D9` | `#000000` | 6.28 (3.11) |
| sidebar-left | 노랑 `#F2C94C` | `#000000` | 13.23 (1.56) |
| list-detail | 민트 `#7FD1B9` | `#000000` | 11.72 (1.70) |
| dashboard | 코랄 `#FF9E80` | `#000000` | 10.45 (1.91) |
| mobile-tabs | 라벤더 `#C3B1E1` | `#000000` | 10.70 (1.86) |

스크린샷은 스크래치패드(임시)에만 있다.

### 품질 회귀

프롬프트(`builder/prompts/`)를 바꾸지 않아 돌리지 않았다. 산출물 템플릿도 그대로 (스냅샷 테스트 갱신 없음).

### 안 한 것 / 남은 것

- 프롬프트 `interview_design.md:47` "강조색 버튼 위에 바탕색 글씨가 잘 읽혀야 한다" 는 이제 사실과 다르다 (버튼 글자는 `on_accent`).
  바탕과 구분되는 강조색을 고르게 하는 효과는 남아 있어 그대로 뒀다 — 고치면 품질 회귀를 돌려야 하는 프롬프트 변경이다.
- 강조색을 **글자색**으로 쓰는 곳(`mobile-tabs` 의 고른 탭 이름 등)은 밝은 강조색에서 바탕 대비가 낮다 (라벤더 위 흰 바탕 약 1.9:1). 이번 범위(버튼 위 글자) 밖.

### 토큰 소모

- [추정] 세션 약 15만 토큰 (문서·코드 읽기 + 구현 + 브라우저 확인). 실제 실행 2회 = `claude -p` 12회, 요금제 내.
