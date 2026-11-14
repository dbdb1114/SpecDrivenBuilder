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
  pages/        화면 단위 — HomePage(아이디어) · StudioPage(질문 묶음 · 확인 화면 · 생성 중) · DonePage(다운로드)
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
- 스타일은 CSS Modules (2026-11-13 결정, 작업 단위 E — Vite 내장이라 의존성이 없고 컴포넌트별로 스코프가 나뉜다).
  컴포넌트 옆에 `*.module.css`, 공통 색·간격 토큰은 `src/index.css` 의 CSS 변수. 강조색은 `--ac` 하나.
- 여러 화면이 같이 쓰는 모션은 `src/motion.css` 의 전역 클래스(`rise` · `msg` · `btn` 등)로 쓴다 — CSS Modules 는 키프레임 이름을
  파일마다 따로 묶는다. 시안과 토큰 원본은 `docs/design/frontend-redesign/`.
- 라우터는 두지 않는다 (2026-11-14 결정). 화면은 서버 상태 `RunView.status` 하나로 정해지고, 실행은 주소의 `?run=<id>` 로 이어 간다.
- 질문 묶음은 대화처럼 한 질문씩 보여 주되, 묶음을 다 답했을 때 한 번에 보낸다 — 서버 왕복은 묶음당 한 번이다.

## 하지 말 것

- 컴포넌트 안에서 `fetch`
- 백엔드 로직 복제 (검증·변환은 백엔드가 한다)
- 요청받지 않은 UI 리디자인
