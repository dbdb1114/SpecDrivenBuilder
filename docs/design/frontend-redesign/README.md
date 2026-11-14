# frontend-redesign — 작업자 전달용 패키지

SpecDrivenBuilder 프론트엔드(`frontend/`, React 19 · Vite) 리디자인 시안과, 작업자(Claude Code / Codex)에게
그대로 넘길 프롬프트 묶음.

## 사용법

1. 이 폴더를 레포의 `docs/design/frontend-redesign/` 에 둔다.
2. `frontend/` 에서 Claude Code 를 실행한다. (루트 AGENTS.md 규칙: 스택별 세션은 하위 디렉토리에서 시작)
3. `PROMPT.md` 의 **0. 시작 프롬프트** 를 붙여 넣는다.
4. 화면 하나가 끝날 때마다 `PROMPT.md` 의 다음 번호 프롬프트를 붙여 넣는다. (화면 단위로 끊어서 리뷰)

## 들어 있는 것

| 파일 | 내용 |
|---|---|
| `PROMPT.md` | 작업자에게 순서대로 붙여 넣는 프롬프트 (시작 → 화면별 → 마무리) |
| `flow.md` | 화면 5개, 화면 이동 조건, 이동할 때 넘기는 데이터, 전환 연출 |
| `screens.md` | 화면별 구성 요소 · 상태 · 빈/오류 상태 |
| `api-contract.md` | 프론트가 기대하는 `/api/**` 형태 — **[추정] 백엔드 미구현, 확정 필요** |
| `design-tokens.md` | 색 · 폰트 · 간격 · 모서리 · 모션 값 |
| `motion.css` | 시안에 쓴 키프레임과 유틸 클래스 원본 |
| `design-source/*.dc.html` | 시안 원본. **참고용 — 그대로 실행되지 않음** (디자인 툴 런타임 문법) |

## 결정이 필요한 것 (작업자가 먼저 묻게 되어 있음)

- 스타일 방식: CSS Modules / Tailwind — `frontend/AGENTS.md` 에서 미결정
- 라우팅: react-router 추가 여부 (시안은 화면 전환을 URL 로 분리하는 것을 전제)
- 질문 구조화: 지금 백엔드 질문은 `"질문\n1. … (추천)\n2. …"` 문자열 하나. 프론트에서 파싱할지,
  백엔드가 `options[]` 를 주게 바꿀지 → `api-contract.md` 참고
