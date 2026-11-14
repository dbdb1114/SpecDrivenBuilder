# API 계약 (프론트가 기대하는 형태)

> **전부 [추정].** 현재 `builder/` 에는 FastAPI 엔드포인트가 없다 (CLI + LangGraph `interrupt` 만 있음).
> 아래는 프론트 시안을 돌리기 위한 제안이며, 백엔드 작업에서 확정한다. 확정되면 `npm run gen:types` 로
> `src/types/api.d.ts` 를 생성하고 이 문서 대신 그 타입을 따른다. 그 전까지는 `src/api/` 에 목(mock)을 둔다.

## 현재 백엔드와의 연결 [확정]

- `State.request` ← 홈에서 입력한 아이디어
- `State.pending_question` → 인터뷰 질문 (지금은 문자열 하나에 선택지가 섞여 있음)
- `State.qa[]` → 지난 문답 (새로고침 복원용)
- `State.artifacts: dict[파일명, 내용]` → 산출물 (`spec.md`, `AGENTS.md`, `CLAUDE.md`, `SKILL.md`, `run.json`)
- 답변 = LangGraph `interrupt` 에 대한 resume 값

## 질문 형태 — 결정 필요

지금 질문 문자열 예:

```
가계부를 어디서 쓰실 건가요?
1. 컴퓨터에서 열어 쓰는 화면 (웹 페이지 형태) (추천)
2. 스마트폰에서 바로 쓰는 앱
3. 엑셀 파일 같은 표 형태로 정리해서 받기
4. 알아서 정해 주세요
```

선택지 A — 백엔드가 구조화해서 준다 (권장: 파싱 규칙을 프론트에 복제하지 않기 위해, `frontend/AGENTS.md` "백엔드 로직 복제 금지"):

```ts
type Question = {
  text: string            // "가계부를 어디서 쓰실 건가요?"
  key?: string            // "환경" — 화면의 "Q2 · 환경" 라벨. 없으면 숨김
  options: { label: string; recommended: boolean }[]
  allowFree: true         // "직접 입력" 항상 표시
}
```

선택지 B — 프론트가 `^\d+\.\s` 줄을 선택지로, `(추천)` 을 배지로 파싱. 빠르지만 규칙이 두 곳에 생긴다.

## 엔드포인트 제안

```ts
POST /api/sessions                       { request: string }
  → { id: string, status: "interviewing", question: Question, progress: { asked: number, expected?: number } }

POST /api/sessions/:id/answers           { answer: string }
  → { status: "interviewing", question: Question, progress }
  | { status: "generating" }

GET  /api/sessions/:id
  → { id, request, status: "interviewing" | "generating" | "done" | "error",
      qa: { question: string, answer: string }[],
      question?: Question,
      files: { name: string, state: "waiting" | "writing" | "done" }[],
      version: number }

GET  /api/sessions/:id/artifacts         → { version: number, files: { name: string, content: string }[] }

POST /api/sessions/:id/revisions         { file?: string, line?: number, instruction: string }
  → { id: string, file: string, reply: string,
      diff: { op: "keep" | "add" | "del", text: string }[] }

POST /api/sessions/:id/revisions/:rid/accept   → { version: number }
POST /api/sessions/:id/revisions/:rid/reject   → {}

GET  /api/sessions/:id/download          → application/zip  (파일명: <slug>.zip, 최신 version)
```

- 생성 진행: 우선 `GET /api/sessions/:id` 1초 폴링. SSE 는 필요해지면.
- `progress.expected` 는 인터뷰 질문 수가 고정이 아니므로 선택. 없으면 진행 바는 "질문 n개째" 표시로 대체.
- 리뷰의 칩 3개("알림 추가" 등)는 시안용 예시. 실제로는 `GET /api/sessions/:id` 응답에
  `suggestions: string[]` 로 받거나, 고정 문구 3개로 둔다 — [미확인].
