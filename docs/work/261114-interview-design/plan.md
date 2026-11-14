# 작업 단위 F — interview_design · visual · preview (`feat/interview-design`)

제약: `constraints.md`. 설계: `docs/design/design.md` "interview_design", `docs/design/question-format.md` "visual"·"preview".

## 분석

- [확정] A·E 가 `develop` 에 머지됨 (`4cec316`, B 도 포함). 기준선: `uv run pytest` 108 passed, `npm run test` 12 passed.
- [확정] `nodes/interview_design.py` 는 빈 노드(곧장 `select_stack`). `graph/build.py` 에 `destinations=("interview_design", "select_stack")` 로
  이미 등록돼 있어 그래프 조립은 고칠 필요 없음.
- [확정] 규격 모델(`state/question_format.py`)에 `PaletteVisual`·`LayoutVisual`·`Preview`·`PreviewTexts` 가 있다.
  `LAYOUT_KEYS = ("sidebar-left",)` 이고 A 의 주석이 "F 가 이 상수만 바꾼다". `LayoutKey` 는 `str` + `AfterValidator` 라
  OpenAPI 에는 `key: string`, `layout: string` 으로만 나온다 (`frontend/src/types/api.d.ts:192,230`) — 프론트엔드는 key 목록을 모른다.
- [확정] `InterviewReply`(items + questions)는 `preview` 문구를 담을 자리가 없다. `assign_ids(..., preview=)` 는 받는다.
- [확정] `apply_submission` 은 option 답의 `content` 에 **라벨만** 남긴다 — 고른 색 값·레이아웃 key 는 버려진다.
  State 에 디자인 전용 키를 둘 수 없으므로(State 스키마 고치지 않음) 고른 값을 다음 묶음까지 들고 갈 곳은 스펙 항목의 `content` 뿐.
- [확정] 첫 진입 때 디자인 항목은 없다. 실행 규칙(`needs_asking(items, "design")`)만 쓰면 항상 지나간다 → 첫 진입은 LLM 이 화면 유무와 항목을 정해야 한다.
- [확정] `graph/main.py`(CLI)는 `visual`·`preview` 를 그리지 않는다 (`main.py:83`). 고치지 않는다 (A → D 순서).
- [확정] `tests/test_graph.py:57` 이 LLM 호출 순서를 그대로 비교한다 → interview_design 이 LLM 을 부르면 깨진다. B 가 `select_stack` 줄을 넣은 것처럼 한 줄 추가.
- [확정] `tests/fakes/fake_llm.py` 의 `DEFAULT_REPLIES` 는 "새 노드가 프롬프트를 추가하면 여기에 한 줄 추가한다" 고 돼 있다.
- [확정] 프론트엔드 `QuestionPage.tsx:92` 에 "visual·preview 는 F 가 그린다" 자리가 있다. 스타일은 CSS Modules, 토큰은 `src/index.css`.

## 결정

### 1. `layout` key 목록 — 6개

| key | 사용자에게 보이는 뜻 | 어울리는 프로그램 |
|---|---|---|
| `single-column` | 한 줄로 위에서 아래로 | 입력 폼, 간단한 도구 |
| `top-nav` | 위쪽에 메뉴 | 소개·안내 위주, 메뉴 3~5개 |
| `sidebar-left` | 왼쪽에 메뉴 | 관리 화면, 메뉴가 많을 때 |
| `list-detail` | 왼쪽 목록 + 오른쪽 상세 | 거래처·내역처럼 하나씩 열어 보는 것 |
| `dashboard` | 숫자 카드 여러 개 + 표 | 집계·현황 |
| `mobile-tabs` | 휴대폰 화면, 아래쪽 탭 | 휴대폰으로 주로 쓰는 것 |

이유: 비개발자가 그림으로 구분할 수 있을 만큼 서로 다르고, `evals/cases` 3개(가계부·세무 집계·동아리 휴대폰)가 각각 2개 이상의 선택지를 갖는다.
늘리면 프론트엔드 틀을 하나씩 더 만들면 된다.

### 2. key 목록의 원본 — 빌더 `LAYOUT_KEYS` 하나, 프론트엔드는 OpenAPI 생성 타입으로 받음 **(물어볼 것 — 아래 Q)**

- 안 A (추천): `LayoutKey` 를 `Literal[LAYOUT_KEYS 의 값들]` 로 바꾼다. OpenAPI 에 enum 으로 나가고 `gen:types` 로 TS 유니온이 된다.
  프론트엔드는 `Record<LayoutKey, …>` 로 틀을 두므로 key 를 추가하고 틀을 안 만들면 **타입 검사에서 실패**한다. 원본이 한 곳.
  대신 규격 모델의 타입 한 줄을 고친다 (constraints "규격 모델 고치지 않는다" 의 예외 승인 필요). 검증 동작(목록 밖 key 거부)은 같다.
- 안 B: 상수만 바꾼다. 프론트엔드에 같은 목록을 손으로 한 벌 더 두고, 모르는 key 는 기본 그림으로 그린다. 두 목록이 어긋나도 테스트가 못 잡는다.

### 3. interview_design 흐름 (노드 하나, 묻는 키는 interview_user 와 같음)

1. **첫 진입** (디자인 영역 항목이 하나도 없음) — LLM 1회. 화면이 없으면 LLM 이 디자인 항목을 내지 않고, 코드가
   `screen` 항목(디자인 · 작업자 · 맡김 · "화면이 없는 프로그램이라 디자인 결정이 없다")을 넣고 지나간다. 이 항목이 있으면 돌아오는 경로에서 다시 판정하지 않는다.
   (`interview_stops` 에 기록을 남기는 방식은 `InterviewStop.reason` 에 "화면 없음" 이 없어 State 스키마를 고쳐야 하므로 쓰지 않음)
2. **화면이 있으면** LLM 이 디자인 항목을 뽑는다. 색 톤은 id `color-tone`, 배치는 id `layout` 로 고정(프롬프트 + 코드 검증):
   `color-tone` 질문의 선택지에는 전부 `palette`, `layout` 질문의 선택지에는 전부 `layout` visual 이 있어야 한다. 다른 디자인 질문(글씨 크기 등)은 visual 없음.
3. **답 반영** — `apply_submission` 뒤에 코드가 visual 값을 `content` 에 붙인다: `"차분한 남색 (#1E3A5F, #F5F7FA, #4A90D9)"`, `"왼쪽에 메뉴 [sidebar-left]"`.
   "알아서 정해 주세요" 면 추천 선택지(없으면 첫 선택지)를 기본 방향으로 같은 형식으로 넣는다. → 스펙에 실제 색 값과 배치가 남아 작업자가 되묻지 않는다.
4. **미리보기** — `color-tone`·`layout` 이 둘 다 아직 모름이 아니고 `preview-check` 가 아직 확정·맡김이 아니면, 코드가 `preview-check` 항목(디자인·사용자·아직 모름)을 만들고
   다음 묶음 맨 앞에 고정 질문 "이 느낌이 맞나요?" (맞아요 / 색을 바꿀래요 / 배치를 바꿀래요)를 넣는다. 질문 문장에 배치·색 이름을 넣어 CLI 에서도 뜻이 통하게 한다.
   - `preview.layout`·`colors` 는 `content` 에서 코드가 읽는다. 직접 입력("파스텔톤")이라 값이 없으면 LLM 이 낸 값을 쓴다 (LayoutKey 검증 통과한 것만).
   - `preview.texts`(제목·메뉴)는 LLM 이 스펙 항목에서 뽑는다. 이 노드의 LLM 응답 형식은 `InterviewReply` + `preview`(선택)로,
     **노드 파일 안에** 정의한다 (규격 모델은 그대로 — LLM 응답 형식이지 사용자와 주고받는 규격이 아님).
   - "색을 바꿀래요" → `color-tone` 을 아직 모름으로 되돌림 → 다음 묶음에서 색만 다시 묻고 → 다시 미리보기. "배치를 바꿀래요" 도 같다.
5. **종료** — interview_user 와 같은 규칙·상한(진입 1회당 5묶음)·종료 기록(`interview_stops`).

LLM 호출 수: design.md 대로 "질문 묶음 하나당 1회" + 마지막 답 반영 1회. 화면이 없는 요청은 판정 1회가 는다 —
화면 유무는 요청 원문을 읽어야 알 수 있어 코드로 판정할 수 없다 (커밋 메시지에도 적음).

### 4. 프론트엔드

- `components/Visual.tsx` — `PaletteSwatch`(색 칸), `LayoutThumb`(key 별 작은 그림, CSS 로 그린 상자). 선택지 버튼 안 라벨 옆에 붙인다.
- `components/Preview.tsx` — key 별 틀 6개. `colors[0]` 주색, `[1]` 바탕, `[2]` 강조(없으면 앞 색 재사용), `texts.title`·`texts.menu` 를 글자로만 넣는다
  (`dangerouslySetInnerHTML` 없음 — LLM 문구를 마크업으로 해석하지 않는다).
- `QuestionPage.tsx` — `bundle.preview` 가 있으면 질문 위에 `<Preview>`, 선택지에 `option.visual` 이 있으면 그림. 구조는 그대로.

## 건드릴 파일

| 파일 | 변경 |
|---|---|
| `builder/src/specbuilder/nodes/interview_design.py` | 노드 구현 |
| `builder/prompts/interview_design.md` | 새 프롬프트 |
| `builder/src/specbuilder/state/question_format.py` | `LAYOUT_KEYS` 6개 (+ 안 A 면 `LayoutKey` 를 Literal 로 한 줄) |
| `builder/tests/nodes/test_interview_design.py` | 빈 노드 테스트를 실제 테스트로 교체 |
| `builder/tests/fakes/fake_llm.py` | `DEFAULT_REPLIES` 에 한 줄 (화면 없음 응답) |
| `builder/tests/test_graph.py` | 호출 순서 목록에 `interview_design` 한 줄 |
| `builder/tests/state/test_question_format.py` | layout key 검증 테스트가 `sidebar-left` 외 key 를 가정하면 맞춤 (있을 때만) |
| `frontend/src/types/api.d.ts` | `gen:types` 재생성 (안 A 일 때 enum) |
| `frontend/src/api/types.ts` | `LayoutKey`·`Preview`·`Visual` 별칭 추가 |
| `frontend/src/components/Visual.tsx` · `.module.css` | 새 파일 |
| `frontend/src/components/Preview.tsx` · `.module.css` | 새 파일 |
| `frontend/src/components/Preview.test.tsx` | 새 테스트 |
| `frontend/src/pages/QuestionPage.tsx` | 그림 그리는 부분만 추가 |
| `frontend/src/pages/QuestionPage.test.tsx` | visual·preview 렌더 테스트 추가 |
| `docs/design/question-format.md` | "미결정"의 layout key 목록 → 결정 (자기 절만) |
| `docs/design/design.md` | interview_design 절에 화면 없음 판정·고정 id 한두 줄 (자기 절만) |

## 검증

- `uv run pytest`, `uv run ruff check . && uv run ruff format --check .`
- fake LLM 테스트: 화면 없음 → `screen` 항목·LLM 1회·지나감 / 색·배치 질문의 visual 검증 / 목록 밖 key 거부 / 답 → content 에 색 값·key /
  미리보기 묶음 (preview 값·고정 질문) / 색을 바꿀래요 → 색만 다시 묻기 / 맞아요 → 종료 기록 / 돌아오는 경로에서 다시 판정 안 함 / resume 시 LLM 재호출 없음
- `npm run lint && npm run test && npm run build`
- 실제 모델: `SPECBUILDER_MODEL` 기본값으로 화면 있는 요청(`03-vague`)과 없는 요청(새로 쓰지 않고 CLI 입력 — "폴더 안 사진 파일 이름을 찍은 날짜로 바꿔 주는 거")을
  `interview_design` 까지 돌려 묶음 JSON 을 여기에 붙인다. 화면 있는 요청은 FastAPI + 프론트엔드로 띄워 미리보기를 눈으로 확인(스크린샷).

## 검증 결과 (2026-11-14)

### 계획 대비 변경

- 계획 표의 `builder/tests/state/test_question_format.py` 는 고칠 필요가 없었다 (기존 `sidebar-left`·`없는-틀` 테스트가 Literal 로도 그대로 통과).
- 실제 모델 실행 후 추가: 미리보기 질문 문장에서 색 값·`[key]` 를 뺀다 (`_plain`). 웹 화면에서 `[mobile-tabs] / #5C4033…` 이 사용자에게 그대로 보였기 때문. 스펙 항목 내용에는 남긴다.

### 명령

- [확정] `uv run pytest` → 125 passed (기준선 108 + interview_design 17). `uv run ruff check .` 통과, `ruff format --check` 60 files already formatted.
- [확정] `npm run lint` 오류 없음, `npm run test` → 21 passed (기준선 12), `npm run build` 성공.
- [확정] `npm run gen:types` 재생성 — `LayoutVisual.key`·`Preview.layout` 이 `string` → 6개 key 유니온.

### 실제 모델 (`claude-sonnet-5-5`, `claude -p`, 2026-11-14)

스크립트로 `interview_user` → `interview_design` 를 돌리고 `select_stack` 앞에서 멈춤. 답은 추천 선택지, 단 색 톤은 두 번째 선택지, 미리보기는 "맞아요".

| 요청 | 화면 판정 | interview_design 묶음 | LLM 호출 (design) | 결과 디자인 항목 |
|---|---|---|---|---|
| `03-vague` (동아리, 휴대폰) | 있음 | 1: 색 4안(palette)·배치 4안(`mobile-tabs` 추천, `top-nav`, `dashboard`, `list-detail`) / 2: preview + "이 느낌이 맞나요?" | 3 | `color-tone` 따뜻한 베이지 (#5C4033, #FAF6F0, #D9A05B) · `layout` … [mobile-tabs] · `preview-check` 맞아요 |
| "매일 아침 7시 날씨·미세먼지를 텔레그램으로" | 없음 | 없음 | 1 | `screen` (작업자 · 맡김 · "화면이 없는 프로그램이라 디자인 결정이 없다") |
| "폴더 안 사진 이름을 찍은 날짜로 바꿔 주는 거" | **있음** | 1: 색·배치(`single-column` 추천) / 2: preview | 3 | 베이지 · single-column · 맞아요 |

- 동아리 미리보기: `{"layout": "mobile-tabs", "colors": ["#5C4033", "#FAF6F0", "#D9A05B"], "texts": {"title": "동아리 모임", "menu": ["모임 날짜", "회비", "멤버"]}}` — 사용자가 고른 색이 LLM 초안보다 우선 적용됨, 메뉴는 기능 항목에서 뽑힘.
- 사진 이름 바꾸기를 "화면 있음" 으로 본 것: `[추정]` 타당. 비개발자는 터미널 명령을 못 쓰고, interview_user 단계에서 "바꾸기 전에 미리보기" 같은 선택지가 나와 화면을 전제했다.
  화면 없음 판정의 경계 사례라 품질 회귀 세트에 넣을지는 아래 "남은 것".
- 화면 확인: 실제 모델의 묶음 JSON 을 임시 페이지(작업 후 삭제)로 `QuestionPage` 에 넣어 Chrome 에서 봄 — 색 견본·배치 그림, 휴대폰 틀 미리보기,
  6개 틀 전부(밝은/어두운 팔레트) 깨지지 않음을 [확정]. FastAPI 를 거친 전체 흐름(시작 → 질문 → 미리보기)은 돌리지 않음 [미확인] — API 는 묶음을 그대로 넘기기만 한다.

### 남은 것

- CLI(`graph/main.py`)는 `visual`·`preview` 를 그리지 않는다 (A → D 순서 파일). 미리보기 질문 문장에 배치·색 이름을 넣어 글자로는 통한다.
- 품질 회귀 세트(`evals/cases/`)에 화면 없는 요청이 없다. 위 텔레그램 요청을 넣을지 결정 필요 — 이번 범위 밖이라 추가하지 않음.
- 확인 화면에서 기능 항목만 고쳐 프로그램이 "화면 있음 ↔ 없음" 으로 바뀌는 경우는 다시 판정하지 않는다 (`screen` 항목이 남아 있으면 지나감). 확인 화면에서 `screen` 은 작업자 항목이라 고칠 수 없다.

### 토큰 소모

- [추정] 세션 약 25~30만 토큰 (문서·코드 읽기 + 구현 + 실제 모델 실행 대화). 실제 모델 실행 3회 = `claude -p` 약 14회 호출 (요금제 내).
