# 질문 묶음 · 답 제출 · 확인 화면 규격

> 결정 (2026-11-12): 빌더가 사용자에게 보내는 질문과 사용자가 돌려주는 답의 JSON 규격.
> 묻는 노드(`interview_profile`, `interview_user`, `interview_design`)가 모두 이 규격을 쓴다. 큰 그림은 `design.md`.

## 원칙

- **규격의 원본은 빌더에 한 곳만 둔다.** 빌더는 LLM 응답을 이 규격으로 검증한 뒤에만 내보낸다.
  프론트엔드 타입은 FastAPI 가 내놓는 OpenAPI 문서에서 생성한다 — 양쪽에 손으로 따로 적으면 한쪽만 바뀐다.
  생성 도구는 `openapi-typescript` (2026-11-13 결정, 작업 단위 E) — `frontend/` 의 `npm run gen:types` 가 `/api/openapi.json` 에서 `src/types/api.d.ts` 를 만든다.
- **CLI 도 같은 규격을 쓴다.** 터미널은 이 JSON 을 번호 목록으로 그리는 화면일 뿐이다.
- **`id` 는 LLM 이 아니라 빌더 코드가 붙인다.** LLM 이 만든 id 는 중복되거나 형식이 달라질 수 있다.

## 질문 묶음 (빌더 → 프론트엔드)

```json
{
  "round": 1,
  "can_finish": true,
  "preview": null,
  "questions": [
    {
      "id": "q1",
      "item_id": "who-uses",
      "text": "이 프로그램은 누가 쓰나요?",
      "multiple": false,
      "options": [
        { "id": "o1", "label": "저 혼자 써요", "recommended": true, "visual": null },
        { "id": "o2", "label": "우리 팀 여러 명이 써요", "recommended": false, "visual": null }
      ]
    }
  ]
}
```

| 필드 | 뜻 |
|---|---|
| `round` | 몇 번째 질문 묶음인가 |
| `can_finish` | "그만 묻고 만들어 주세요" 버튼을 보여 줄지 |
| `preview` | 디자인 미리보기. 없으면 `null` |
| `questions` | 1~10개. 중요한 순서로 정렬 |
| `questions[].item_id` | 이 질문이 채우는 스펙 항목 |
| `questions[].multiple` | 여러 개를 고를 수 있는 질문인가 |
| `questions[].options` | LLM 이 만든 선택지 2~4개, 또는 빈 목록 (직접 입력만 받는 질문) |
| `options[].recommended` | 추천 선택지. 질문당 최대 1개 |
| `options[].visual` | 선택지에 붙는 그림. 없으면 `null` |

- 화면에는 고정 선택지 **"알아서 정해 주세요"** 가 붙어서 선택지가 3~5개로 보인다. 이 선택지는 `options` 에 넣지 않는다 —
  LLM 이 매번 생성하면 문구가 흔들리거나 빠질 수 있다. 프론트엔드가 항상 같은 버튼으로 그린다.
- 직접 입력은 모든 질문에 열려 있다.
- **선택지 없는 질문** (2026-11-14 결정): 답이 이름·장소·숫자·날짜처럼 사용자가 직접 적어야 하는 것이면 `options` 를 빈 목록으로 둔다.
  화면은 입력 칸과 "알아서 정해 주세요"만 보여 준다. 선택지를 강제하면 LLM 이 "직접 적어 주세요" 같은 답이 아닌 선택지를 지어내고,
  그것을 고르면 그 문장이 항목 내용으로 확정된다 (`docs/work/261114-open-question/plan.md`). 선택지 1개는 받지 않는다. 이 질문의 `multiple` 은 항상 `false`.
- 한 묶음에는 서로 독립인 질문만 넣는다.

### visual

디자인 질문의 선택지에 쓴다. 프론트엔드는 이 필드가 있으면 그림으로 그린다.

```json
{ "type": "palette", "colors": ["#1E3A5F", "#F5F7FA", "#4A90D9"] }
```

```json
{ "type": "layout", "key": "sidebar-left" }
```

- `palette` — 색상 값 목록. 프론트엔드가 색 견본으로 그린다.
- `layout` — 미리 정해 둔 레이아웃 종류 중 하나의 이름. 프론트엔드가 종류별 작은 그림을 갖고 있다.
  빌더는 목록에 없는 `key` 를 내보내지 않는다.
  목록 (2026-11-14 결정, 작업 단위 F): `single-column` `top-nav` `sidebar-left` `list-detail` `dashboard` `mobile-tabs`.
  원본은 빌더 `state/question_format.py` 의 `LayoutKey`(Literal) 하나 — OpenAPI enum 으로 나가 프론트엔드 생성 타입이 되고,
  프론트엔드는 key 별 그림·틀을 `Record<LayoutKey, …>` 로 두어 key 가 늘면 타입 검사가 실패한다.

### preview

`interview_design` 이 색 톤과 레이아웃 답을 받은 뒤의 질문 묶음에 싣는다.
같은 묶음의 질문은 "이 느낌이 맞나요?"다 (맞아요 / 색을 바꿀래요 / 배치를 바꿀래요).

```json
{
  "layout": "sidebar-left",
  "colors": ["#1E3A5F", "#F5F7FA", "#4A90D9"],
  "texts": { "title": "가계부", "menu": ["이번 달", "내역", "설정"] }
}
```

- `texts` 는 스펙 항목에서 가져온 실제 문구다. 사용자가 자기 프로그램처럼 보이는 화면을 본다.
- 프론트엔드가 미리 만들어 둔 레이아웃 틀에 색과 문구를 입혀 그린다. LLM 이 화면 코드를 만들지 않는다.

#### 바꿀 규격 (2026-11-14 결정, 구현 전 — 작업 단위 I)

지금 규격은 색이 순서만 있는 목록이고 문구가 제목과 메뉴뿐이라, 틀이 빈 상자로 그려져 실제 화면처럼 보이지 않는다.
배치와 색만 정한다는 범위는 그대로 두고 두 가지를 넓힌다.

```json
{
  "layout": "sidebar-left",
  "colors": {
    "background": "#F5F7FA", "surface": "#FFFFFF",
    "primary": "#1E3A5F", "accent": "#4A90D9", "text": "#1B2430"
  },
  "texts": {
    "title": "가계부",
    "menu": ["이번 달", "내역", "설정"],
    "heading": "이번 달 지출",
    "action": "내역 추가",
    "items": [
      { "title": "점심", "detail": "9,000원" },
      { "title": "교통비", "detail": "1,450원" }
    ]
  }
}
```

| 필드 | 뜻 |
|---|---|
| `colors.background` | 화면 바탕 |
| `colors.surface` | 카드·목록 같은 면 |
| `colors.primary` | 메뉴·제목 같은 주색 |
| `colors.accent` | 버튼·고른 메뉴 같은 강조 |
| `colors.text` | 본문 글자 |
| `texts.heading` | 첫 화면의 제목 |
| `texts.action` | 가장 자주 누를 버튼의 이름 |
| `texts.items` | 첫 화면에 보일 목록 2~5개 (`title`, `detail`) |

- `colors` 가 목록에서 역할 이름으로 바뀐다. 프론트엔드가 "몇 번째 색이 무엇인지" 추측하지 않는다.
- `surface` 와 `text` 는 LLM 이 아니라 빌더 코드가 고른 색에서 계산한다 — 바탕 위 글자가 읽히는 대비를 코드가 보장한다.
- `palette` 견본(`visual`)은 그대로 둔다. 선택지에서는 색 세 개면 충분하다.
- 문구는 미리보기를 만드는 같은 LLM 호출에서 나온다. 호출 수는 늘지 않는다.
- 색 톤 항목의 내용에는 역할별 색을 적는다. 작업자가 미리보기와 같은 색을 그대로 쓴다.

## 답 제출 (프론트엔드 → 빌더)

```json
{
  "action": "submit",
  "answers": [
    { "question_id": "q1", "kind": "option", "option_ids": ["o1"] },
    { "question_id": "q2", "kind": "custom", "text": "매주 월요일에만 써요" },
    { "question_id": "q3", "kind": "delegate" }
  ]
}
```

| 필드 | 뜻 |
|---|---|
| `action` | `submit` 이번 묶음 제출 / `finish` 남은 항목을 전부 맡기고 종료 |
| `answers[].kind` | `option` 선택지를 고름 / `custom` 직접 입력 / `delegate` "알아서 정해 주세요" |
| `answers[].option_ids` | `kind` 가 `option` 일 때. `multiple` 이 `false` 인 질문은 1개 |
| `answers[].text` | `kind` 가 `custom` 일 때 |

## 답이 스펙 항목을 바꾸는 방식

| 답 | 스펙 항목 상태 |
|---|---|
| `option`, `custom` | 확정 |
| `delegate` | 작업자에게 맡김 |
| `answers` 에 없는 질문 | 작업자에게 맡김 (`delegate` 와 같다) |
| `action: finish` | `answers` 에 담긴 답을 반영한 뒤, 남은 "아직 모름" 항목을 전부 작업자에게 맡김으로 바꾸고 종료 |

## 확인 화면 (`confirm_spec`)

산출물을 만들기 직전에 스펙 항목 요약을 보여 주고 확인받는다.

빌더 → 프론트엔드:

```json
{
  "items": [
    { "id": "who-uses", "area": "function", "name": "누가 쓰는가",
      "status": "confirmed", "content": "저 혼자 써요", "editable": true },
    { "id": "share", "area": "function", "name": "다른 사람과 나누는 방법",
      "status": "delegated", "content": "나누는 기능은 넣지 않는다", "editable": true },
    { "id": "framework", "area": "tech", "name": "만드는 방식",
      "status": "confirmed", "content": "내 컴퓨터에서만 도는 프로그램 — 혼자 쓰고 인터넷이 필요 없어서", "editable": false }
  ]
}
```

| 필드 | 뜻 |
|---|---|
| `area` | `function` 용도·기능 / `design` 디자인 / `tech` 기술 |
| `status` | `confirmed` 확정 / `delegated` 작업자에게 맡김 |
| `content` | 확정된 답, 또는 작업자가 따를 기본 방향. 기술 항목은 선택과 이유 |
| `editable` | 결정 주체가 사용자인 항목만 `true` |

프론트엔드 → 빌더:

```json
{ "action": "confirm" }
```

```json
{ "action": "revise", "item_ids": ["who-uses"] }
```

- `revise` 는 고칠 내용을 담지 않는다. 고를 항목만 보내면 빌더가 그 항목을 "아직 모름"으로 바꾸고 질문 묶음으로 다시 묻는다 —
  고치는 화면을 따로 만들지 않고 질문 화면을 다시 쓴다.
- `item_ids` 에는 `editable` 이 `true` 인 항목만 넣을 수 있다.

## 미결정

- 규격 버전 필드를 둘지 — 저장된 checkpoint 와 규격이 어긋날 때의 호환 정책과 함께 (`state.md` "미결정").
