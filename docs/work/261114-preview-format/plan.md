# 작업 단위 I — 미리보기 규격 확장 · 레이아웃 틀 다시 그리기 (`feat/preview-format`)

제약: `constraints.md`. 설계: `docs/design/question-format.md` "preview" 의 "바꿀 규격", `docs/design/design.md` "interview_design".

## 1. 분석

- [확정] 기준선: `develop` 최신(`342b221`)과 이 브랜치가 같다. 작업 트리 깨끗함.
- [확정] 규격 원본은 `builder/src/specbuilder/state/question_format.py` — `Preview{layout, colors: list[HexColor], texts: PreviewTexts{title, menu}}`.
  OpenAPI 로 나가 `frontend/src/types/api.d.ts:231` 의 `Preview` 가 된다. `QuestionBundle.preview` 와 `assign_ids(preview=)` 가 쓴다.
- [확정] `nodes/interview_design.py`
  - LLM 응답 `DesignReply.preview` 가 `Preview` 타입 그대로다 (LLM 이 layout·colors·texts 를 다 쓴다).
  - `_build_preview` 는 사용자가 고른 값이 LLM 초안보다 우선 — `color-tone` 내용의 `#RRGGBB` 를 **순서대로** 뽑아 `colors` 로, `layout` 내용의 `[key]` 를 layout 으로.
  - `_describe` 가 색 톤 항목 내용을 `"차분한 남색 (#1E3A5F, #F5F7FA, #4A90D9)"` 로 쓴다 — 역할 이름이 없다. `_plain` 이 이 괄호를 떼어 CLI 문장에 쓴다.
- [확정] `prompts/interview_design.md` "미리보기" 절이 `colors` 를 [주색, 바탕색, 강조색], `texts` 를 title·menu 로 지시한다.
  `palette` 견본은 `[주색, 바탕색, 강조색]` 순서로 지시돼 있다 — 규격대로 견본은 바꾸지 않는다.
- [확정] 프론트엔드 `components/Preview.tsx` 는 `colors` 를 `[primary, background, accent]` 로 **순서를 추측**해 CSS 변수 3개로 쓰고,
  틀 6개는 제목·메뉴 외에는 회색 줄(`Lines`)뿐이다 — 문서가 말한 "빈 상자". 쓰는 곳은 `StudioPage.tsx:169` 한 곳(봇 말풍선 안).
- [확정] 옛 `preview` 를 쓰는 테스트: `builder/tests/state/test_question_format.py:62`, `builder/tests/nodes/test_interview_design.py`(초안·결과 비교 다수),
  `frontend/src/components/Preview.test.tsx`, `frontend/src/pages/StudioPage.test.tsx:170`. `tests/fakes/fake_llm.py`·`test_graph.py` 는 preview 를 쓰지 않는다.
- [확정] 옛 checkpoint 영향: 질문 묶음은 State `pending_bundle` 과 interrupt 값으로 checkpoint 에 남는다. API `RunView.bundle: QuestionBundle`
  (`api/schemas.py:25`)은 응답 검증을 하므로, 옛 형식(`colors` 가 목록, `texts` 에 heading 없음) 묶음이 걸린 실행을 다시 열면 **500** 이 난다.
  답 제출 검증(`validate_submission`)은 preview 를 보지 않아 영향 없다. 이 worktree 에는 `builder/.checkpoints.sqlite` 가 없다 (개발용, 다른 worktree 에만 있을 수 있음).
- [확정] CLI(`graph/main.py`)는 preview 를 그리지 않고 `run.json` 에도 남기지 않는다. 품질 회귀에서 미리보기 내용은 checkpoint(SqliteSaver)의 상태 기록을
  scratch 스크립트로 읽어 비교한다 (레포 파일 추가 없음).
- [확정] 화면 토큰: 페이지 바탕 `#0A0A0C`, 강조 `--ac`, 모션 `motion.css` 의 `msg`(pop) 가 말풍선에 이미 걸린다 — 미리보기는 그 말풍선 안에서 함께 나타난다.

## 2. 정할 것 (작업 단위 표 "계획 단계에서 정할 것" I 행)

### Q. 저장된 checkpoint 에 옛 `preview` 가 있을 때의 처리

1. **옛 형식이면 `preview` 를 `null` 로 읽는다 (추천)** — `Preview` 필드 앞에 검증기 하나(`BeforeValidator`): `colors` 가 목록이면 `None`.
   실행은 이어지고 "이 느낌이 맞나요? (배치: … / 색: …)" 질문은 그대로 보인다(문장에 배치·색이 적혀 있다). 그림만 빠진다. 코드 10줄 안쪽 + 테스트 1개.
2. 옛 형식을 새 형식으로 바꿔 읽는다 — 색은 순서로 역할을 붙이고 면·글자색은 계산하면 되지만, `heading`·`action`·`items` 문구는 없어서 지어내야 한다
   ("스펙 항목에서 가져온 실제 문구" 원칙과 어긋남).
3. 처리하지 않는다 — 개발용 checkpoint 뿐이니 옛 실행은 새로 시작한다. 옛 실행을 열면 500. 코드 0줄.
4. 네가 정해

## 3. 계획 — 건드릴 파일과 변경 요지

### 빌더

| 파일 | 변경 |
|---|---|
| `state/question_format.py` | `PreviewColors{background, surface, primary, accent, text}`(전부 HexColor), `PreviewItem{title, detail}`, `PreviewTexts` 에 `heading`·`action`·`items`(2~5개) 추가. `Preview.colors` → `PreviewColors`. Q 의 안 1 검증기 |
| `nodes/interview_design.py` | 아래 "노드" |
| `prompts/interview_design.md` | "미리보기" 절: LLM 은 `colors` 에 `primary`·`background`·`accent` 세 역할만 (면·글자색은 쓰지 않음), `texts` 에 heading·action·items 를 스펙 항목에서 뽑게. 색 톤 선택지 조건에 "강조색 위에 바탕색 글씨가 읽혀야 한다" 한 줄 |
| `tests/state/test_question_format.py` | 새 규격 통과·거부(역할 누락, items 1개/6개), 옛 형식 → `null` |
| `tests/nodes/test_interview_design.py` | 초안·기대값을 새 형식으로. 추가: 면·글자색 계산과 대비, 색 톤 내용에 역할별 색, 직접 입력 답은 초안 색 사용, LLM 이 쓴 면·글자색은 무시 |

**노드** (LLM 호출 수 변화 없음 — 같은 호출의 응답 모양만 바뀐다)

- LLM 초안 타입 `DraftPreview` 를 노드에 둔다: `layout`, `colors{primary, background, accent}`, `texts`(규격과 같음). 규격 `Preview` 는 빌더가 완성한 것만.
- `_derive_colors(primary, background, accent)` → 5역할. `surface`: 바탕이 밝으면 바탕을 흰색 쪽으로, 어두우면 밝은 쪽으로 조금 섞는다.
  `text`: 주색을 검정(밝은 바탕) 또는 흰색(어두운 바탕) 쪽으로 단계적으로 섞어 **바탕·면 둘 다에 대비 7:1 이상**이 되는 첫 색 — 주색 기운이 남은 본문색.
  대비 계산은 WCAG 상대 휘도 공식 (외부 의존성 없음).
- 색 톤 항목 내용: `"차분한 남색 (주색 #1E3A5F, 바탕 #F5F7FA, 강조 #4A90D9, 면 #FFFFFF, 글자 #1B2430)"` — 작업자가 미리보기와 같은 색을 그대로 쓴다.
  `_build_preview` 는 역할 이름으로 읽는다. 역할 이름이 없고 색이 3개면 순서로 읽는다(옛 내용 호환), 그것도 없으면 LLM 초안 색.
  `_plain` 은 이 괄호를 통째로 뗀다.
- 맡김(delegate) 답이면 지금처럼 추천 선택지의 견본으로 내용을 쓴다 — 역할 형식으로.

### 프론트엔드

| 파일 | 변경 |
|---|---|
| `src/types/api.d.ts` | `npm run gen:types` 재생성 (손으로 고치지 않음) |
| `src/components/Preview.tsx` | 틀 6개를 다시 그림. CSS 변수 5개(`--p-bg` `--p-surface` `--p-primary` `--p-accent` `--p-text`)를 역할 이름 그대로 받는다 — 순서 추측 제거. 각 틀에 제목·메뉴·첫 화면 제목·주 버튼·목록(제목+설명)을 배치. 문구는 글자로만 |
| `src/components/Preview.module.css` | 틀 스타일. 좁은 폭(말풍선 안, 폭 390px 화면)에서 틀이 무너지지 않게 컨테이너 쿼리로 줄임 — 예: `sidebar-left` 는 좁으면 메뉴 폭 축소, `list-detail` 은 상세를 접음, `dashboard` 카드 2열 |
| `src/components/Preview.test.tsx` | 6개 틀 × 문구 5종(제목·메뉴·heading·action·items) 표시, CSS 변수 5개, 마크업 해석 안 함 |
| `src/pages/StudioPage.test.tsx` | 170행 픽스처만 새 형식으로 |

틀 구성 (공통: 바탕=`background`, 카드·목록=`surface`, 머리·메뉴=`primary`, 버튼·고른 메뉴=`accent`, 본문=`text`):

| 틀 | 배치 |
|---|---|
| `single-column` | 위 제목줄 → heading + 주 버튼 → 목록 카드 세로 |
| `top-nav` | 위 primary 막대(제목 + 메뉴, 첫 메뉴 accent 밑줄) → heading·버튼 → 목록 카드 2열 |
| `sidebar-left` | 왼쪽 primary 메뉴(고른 메뉴 accent) → 오른쪽 heading·버튼 → 목록 표 |
| `list-detail` | 위 제목줄 → 왼쪽 목록(첫 항목 고름) + 오른쪽 상세(그 항목 title·detail, 버튼) |
| `dashboard` | 위 제목줄·메뉴 → 숫자 카드(items 앞 3개의 detail 을 숫자 자리에) → 표(나머지) |
| `mobile-tabs` | 휴대폰 테두리 안: 위 제목 → heading → 목록 → 떠 있는 주 버튼 → 아래 탭(menu) |

### 문서

- `docs/design/question-format.md` "바꿀 규격" → 구현됨으로 (제목의 "구현 전" 만 바꾸고, Q 결정 한 줄). 위쪽 옛 예시 블록은 새 예시로 합친다.
- `docs/design/design.md` interview_design 절의 "(구현 전 — 작업 단위 I)" 를 "구현" 으로.
- `docs/design/state.md` 는 건드리지 않는다 (호환 정책 전체는 미결정 그대로, I 는 preview 한 필드만 정함).
- `PROMPT.md` 삭제 (커밋 안 함).

## 4. 검증

1. `cd builder && uv run pytest -q`, `uv run ruff check . && uv run ruff format --check .`
2. `cd frontend && npm run gen:types`(서버 띄운 상태) → `npm run lint && npm run test && npm run build`
3. **브라우저 확인** — Claude in Chrome. 빌더·Vite 개발 서버를 띄우고, 틀 6개를 한 화면에 놓는 임시 확인용 진입점을 `frontend/` 에 만들어(커밋 안 함, 끝나면 삭제)
   어두운 페이지 바탕 위에서 폭 1280px·390px 로 스크린샷. 밝은 견본(차분한 남색)·어두운 견본 2가지. 추가로 실제 앱에서 01-short 하나를 미리보기 묶음까지 진행해 말풍선 안 모습 확인.
4. **품질 회귀** — 같은 모델 `claude-sonnet-5-5` (`claude -p`, CLI 기본), `evals/cases/` 4개 × 전(`342b221`, `git archive` 사본)/후,
   CLI 끝까지, 답은 빈 줄(추천), 저장된 프로필 고정(H 와 같은 방식). 비교: LLM 호출 수(같아야 함), 미리보기 문구(heading·action·items 가 스펙 항목에서 나왔는가),
   텍스트 대비(코드 계산이라 항상 7:1 이상), 색 톤 항목 내용에 역할별 색, 04 는 미리보기 없음. 약 70회 `claude -p` [추정: H 의 79회 기준, 요금제 내].
5. 실행 검증(산출물을 작업자로 돌리기)은 하지 않는다 — 산출물 서식은 그대로이고 색 톤 항목 내용 문장만 바뀐다.

## 5. 결정 (2026-11-14, 사용자)

- 저장된 checkpoint 의 옛 `preview` → **안 1: `null` 로 읽는다.** `QuestionBundle.preview` 앞의 `BeforeValidator` 하나 (`question_format._drop_old_preview`).

## 6. 검증 결과 (2026-11-14)

계획과 달라진 것:
- 계획 밖 파일은 건드리지 않았다. `frontend/preview-check.html`·`src/preview-check.tsx`(브라우저 확인용)는 확인 뒤 지웠다.
- `npm run gen:types` 는 8000 포트를 다른 프로세스(다른 worktree 의 서버로 보임 [추정])가 쓰고 있어, 이 브랜치 서버를 8001 에 띄우고
  같은 도구로 생성했다: `npx openapi-typescript http://localhost:8001/api/openapi.json -o src/types/api.d.ts`. 결과 파일·도구는 같다.
- 본문 글자색은 주색을 **40% 이상** 섞는 데서 시작한다 — 주색이 이미 읽히면 본문이 제목과 같은 색이 돼서 (계획에는 없던 세부).
- 실제 문구로 그려 보니 `detail` 이 길어 휴대폰 틀에서 잘렸다 → 목록 줄을 자르지 않고 줄바꿈하게, 좁으면 제목 위·설명 아래로 쌓게 고쳤다. 한글은 `word-break: keep-all`.

```
$ cd builder && uv run pytest -q
242 passed, 13 warnings            # 시작 전 233 → 9개 추가 (규격 2 · 노드 7). 경고는 기존 langsmith DeprecationWarning
$ uv run ruff check . && uv run ruff format --check .
All checks passed! / 73 files already formatted
$ cd frontend && npm run lint && npm run test && npm run build
eslint 오류 없음 / Test Files 5 passed, Tests 35 passed / ✓ built
```

### 브라우저 확인 (Claude in Chrome, 2026-11-14)

- 틀 6개 × 견본 3가지(밝은 남색 · 어두운 바탕 `#15131C` · 따뜻한 베이지)를 빌더의 어두운 페이지 바탕(`#0A0A0C`) 위에서 확인. 색은 `role_colors()` 가 실제로 계산한 값.
- 폭: 640px · 358px(폭 390px 화면에서 좌우 16px 뺀 값) · 296px(폭 390px 화면의 봇 말풍선 폭). 창을 673px 밑으로 줄일 수 없어 칸 폭을 줄여 확인했다 —
  틀은 컨테이너 쿼리라 창 폭이 아니라 칸 폭에 반응한다. 세 폭 모두 가로 넘침 0 [확정: DOM 측정]. 잘리는 글자는 대시보드의 작은 라벨(말줄임표, 의도)뿐.
- 실제 앱: 03-vague 를 API 로 추천 답만 골라 미리보기 묶음까지 진행 → `?run=` 으로 열어 말풍선 안 `mobile-tabs` 틀 확인. 이 실행에서 긴 `detail` 잘림을 발견해 위처럼 고침.
- 고친 것: `list-detail` 상세 칸이 늘어나 빈 상자로 보이던 것 → 내용 높이만큼.

### 품질 회귀 — 같은 모델 `claude-sonnet-5-5` (`claude -p`, 빌더 CLI 기본값), 2026-11-14

전 = `342b221` (`git archive` 사본), 후 = 이 브랜치 작업 트리 사본. 4케이스 × 전/후 8회 전부 exit 0.
프로필 고정(사무·행정·회계 / 해 본 것 없음 / 결과만 / 알아서 / Windows · Claude Pro), 답은 전부 빈 줄(= 추천), 확인 화면도 빈 줄.
미리보기는 `run.json` 에 없어 각 실행의 SqliteSaver 상태 기록에서 `pending_bundle.preview` 를 읽었다.

| 케이스 | | LLM 호출 | 디자인 질문 | 배치 | 미리보기 문구 |
|---|---|---|---|---|---|
| 01-short | 전 | 8 | 4 | single-column | 제목 "가계부" · 메뉴 3 (지출 입력 / 이번 달 총 지출 / 지출 내역) |
| | 후 | 9 | 4 | single-column | + heading "이번 달 총 지출" · action "지출 추가" · items 3 (점심 식사 — 11월 12일 · 9,000원 …) |
| 02-domain | 전 | 11 | 4 | sidebar-left | 제목 "부가세 집계" · 메뉴 4 |
| | 후 | 9 | 4 | single-column | + heading "2기 확정 매입 집계" · action "집계표 내려받기" · items 3 (한솔식당 (접대비·불공제) — 공급가액 450,000원 · 세액 45,000원 …) |
| 03-vague | 전 | 10 | 4 | mobile-tabs | 제목 "동아리 모임" · 메뉴 4 |
| | 후 | 9 | 4 | mobile-tabs | + heading "다가오는 모임" · action "후보 날짜 올리기" · items 3 (11월 정기 모임 — 투표 중 · 12명 참여 …) |
| 04-no-screen | 전 | 6 | 0 | — | 미리보기 없음 |
| | 후 | 7 | 0 | — | 미리보기 없음 |

- **문구:** 후의 heading·action·items 는 셋 다 그 프로그램의 기능 항목에서 나온 말이다 (02 는 불공제·공급가액·세액·미분류, 03 은 날짜 투표·회비) [확정: 미리보기 JSON].
  "항목 1" 같은 자리 채움 말은 없었다. 전에는 문구가 제목·메뉴뿐이었다.
- **색:** 3케이스 모두 사용자가 추천 견본 "차분한 남색" 을 골라 역할 색이 같다 — `background #F5F7FA · surface #FBFCFD · primary #1E3A5F · accent #4A90D9 · text #122339`.
  본문 대비 바탕 14.8:1 (코드 계산). 색 톤 항목 내용과 산출물 `spec.md` 에 역할별 색("주색 #1E3A5F, 바탕 …, 글자 #122339")이 들어갔다 [확정: 3케이스 spec.md].
- **LLM 호출:** 디자인 질문 수(4)와 묶음 수는 같다. 전체 호출 수 차이(+1 / −2 / −1 / +1)는 방향이 없고 interview_user 묶음 수의 실행마다 변동이다 [추정: H 의 회귀에서도 ±1~2].
  이번 변경은 같은 호출의 응답 모양만 바꿨다.
- **02 의 배치:** 전은 sidebar-left, 후는 single-column 이 추천돼 골라졌다. 배치 선택지 지시는 바꾸지 않았다 [추정: 실행마다의 변동 — 1회씩이라 단정 못 함].

산출물·checkpoint: `/private/tmp/claude-501/-Users-yujeonghyeon-orca-workspaces-SpecDrivenBuilder-feat-preview-format/ffce3f10-395c-452b-b9a0-edaefff02b6a/scratchpad/{before,after}/` (임시 폴더 — 재부팅하면 지워진다).

### 실행 검증

하지 않음 (계획 4-5) — 산출물 서식은 그대로이고 색 톤 항목 내용 문장만 바뀐다.

### 남은 것

- 강조색 버튼 위 글자는 바탕색이다. 규격의 다섯 역할에 "강조색 위 글자색" 이 없어서, 밝은 강조색(예: 베이지 `#D9A05B` 위 `#FAF6F0`, 약 2.2:1)이면 버튼 글자가 흐리다.
  지금은 프롬프트 한 줄("강조색 버튼 위에 바탕색 글씨가 잘 읽혀야 한다")만 막는다. 코드로 보장하려면 역할을 하나 늘리는 규격 변경이라 이번에 하지 않았다.
  → **이번 범위 밖 (2026-11-14 사용자 결정).** 다른 작업 단위에서 규격 변경(역할 추가)으로 다룬다.

### 토큰 소모

- [추정] 세션 약 25만 토큰 (문서·코드 읽기 + 구현 + 브라우저 확인 + 회귀 분석). 품질 회귀 8회 = `claude -p` 68회 (run.json `llm_calls` 합) + 실제 앱 확인 1회 약 5회, 요금제 내.
