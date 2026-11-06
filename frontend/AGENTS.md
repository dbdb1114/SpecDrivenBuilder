# frontend/AGENTS.md — React 19 · Vite

루트 `AGENTS.md` 의 공통 규칙이 먼저다. 여기는 프론트엔드 세부만. `frontend/CLAUDE.md`는 `@AGENTS.md` 한 줄.

## 역할

빌더 백엔드(`/api/**`)를 호출해 interview → 스펙 확인 → 산출물 다운로드 흐름을 사용자에게 보여주는 화면.
**비즈니스 로직은 백엔드에.** 프론트는 상태 표시와 입력 수집만 한다.

## 명령어

```bash
npm install
npm run dev        # Vite 개발 서버 (`/api` 는 builder 로 프록시)
npm run build
npm run lint
npm run test
npm run gen:types   # openapi-typescript (builder 서버가 떠 있어야 함)
```

## 구조

```
src/
  api/          백엔드 호출 함수 — fetch 래퍼 하나, 엔드포인트별 함수
  pages/        라우트 단위 화면
  components/   재사용 컴포넌트 — 페이지에 종속된 건 pages/ 아래에
  hooks/
  types/        백엔드 응답 타입 — `openapi-typescript`로 `/api/openapi.json`에서 **생성**, 손으로 쓰지 않음
```

## 코드 규칙

- 함수 컴포넌트 + hooks 만. 클래스 컴포넌트 금지.
- 백엔드 호출은 `src/api/` 를 통해서만. 컴포넌트에서 `fetch` 직접 호출 금지.
- 백엔드 응답 타입은 생성한다 (`npm run gen:types` → `src/types/api.d.ts`). 백엔드 스키마가 바뀌면 재생성하고
  생성 결과 diff를 커밋에 포함한다. 손으로 고치거나 `any` 로 때우지 말 것.
- 질문 UI: 백엔드가 선택지를 주면 **번호 버튼 + 추천 표시 + "직접 입력"** 으로 렌더한다. 자유 텍스트만 주지 말 것.
  (루트 AGENTS.md "질문 규칙" 의 UI 구현)
- 상태 관리 라이브러리는 필요해지기 전까지 추가하지 않는다. 추가가 필요하면 먼저 물을 것.
- 스타일 방식(CSS Modules / Tailwind 등)은 **미결정**. 첫 결정은 물어서 정한다.

## 하지 말 것

- 컴포넌트 안에서 `fetch`
- 백엔드 로직 복제 (검증·변환은 백엔드가 한다)
- 요청받지 않은 UI 리디자인
