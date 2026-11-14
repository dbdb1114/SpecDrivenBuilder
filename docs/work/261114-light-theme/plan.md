# 밝은 테마 추가

## 1. 분석

- [확정] 색은 `frontend/src/index.css` 의 CSS 변수로 정의돼 있고 값은 어두운 테마 하나다.
- [확정] 모듈 CSS 에 토큰을 거치지 않은 색이 17곳 있었다 (`#2a2a31`, `#17171c`, `#ffffff` 등) — 테마를 바꿔도 따라오지 않는다.
- [확정] 강조색 `--ac`(`#D4FF3A`)가 글자·선과 채운 면 양쪽에 쓰이고, 채운 면 위 글자는 `--bg` 다.
  밝은 바탕에서는 형광색 글자가 읽히지 않고, `--bg` 가 밝아지면 채운 면 위 글자도 읽히지 않는다.

## 2. 변경

| 파일 | 변경 |
|---|---|
| `src/index.css` | 토큰 추가(`--ac-fill` `--on-ac` `--ac-hover` `--line-4` `--surface-4` `--hover` `--code-bg` `--muted-3` `--header-bg` `--scan`), `:root[data-theme="light"]` 값 |
| `index.html` | 첫 그리기 전에 `data-theme` 을 붙이는 스크립트 (저장된 선택 → 시스템 설정) |
| `src/hooks/useTheme.ts` (새 파일) | 바꾸기, 저장, 고른 적이 없으면 시스템 설정 따라가기 |
| `src/components/Header.tsx` · `.module.css` | 테마 버튼. 좁은 화면에서는 진행 단계를 아래 줄로 |
| `src/pages/*.module.css`, `src/motion.css`, `StudioPage.tsx` | 값으로 적힌 색을 토큰으로 |
| `frontend/AGENTS.md`, `docs/design/frontend-redesign/design-tokens.md` | 규칙과 밝은 테마 값 |

결정 (되돌릴 수 있는 선택이라 묻지 않고 정함):
- 처음 값은 시스템 설정을 따르고, 버튼으로 고르면 그 선택을 기억한다.
- 채운 면의 형광색은 밝은 테마에서도 그대로 두고, 글자·선으로 쓰는 강조색만 짙은 녹색으로 바꾼다 — 브랜드 색을 지키면서 읽힌다.
- `Preview` · `Visual` 은 건드리지 않았다 (사용자 프로그램의 색을 보여 주는 부분이고, 작업 단위 I 가 고치는 중).

## 3. 검증 결과

```
$ cd frontend && npm run lint && npm run test && npm run build
lint 출력 없음 / Tests 36 passed (36) / built
```

- 헤드리스 Chrome 스크린샷으로 확인 (2026-11-14): 홈·질문 화면을 어두운 테마와 밝은 테마로, 질문 화면을 폭 500px 로.
  시스템 설정에 따라 테마가 갈리고, 좁은 화면에서 테마 버튼과 진행 단계가 겹치지 않는다.

## 4. 안 한 것 / 남은 것

- 확인 화면 · 만드는 중 · 완료 화면은 밝은 테마로 직접 보지 않았다 `[미확인]` — 같은 토큰을 쓰지만 눈으로 본 것은 홈과 질문 화면뿐이다.
- 테마 버튼을 눌러 바뀌는 것과 새로고침 뒤 유지되는 것은 브라우저에서 눌러 보지 않았다 `[미확인]` (훅에 테스트 없음).
- 폭 390px 는 헤드리스 Chrome 의 최소 창 폭 때문에 500px 로 대신 확인했다.
