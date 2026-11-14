# 선택지 없는 질문 허용

## 1. 분석

- [확정] 04-no-screen 실행 검증에서 작업자(Claude Code · Codex 둘 다)가 동네 이름을 되물었다 (`docs/work/261114-artifact-structure/plan.md` 실행 검증).
- [확정] 그 실행의 `run.json`: `location` 질문 "어느 동네의 날씨와 미세먼지를 보내 드릴까요?" 의 추천 선택지가
  "집 근처 동네 하나만 알려 주면 돼요 (아래 직접 입력에 동네 이름을 적어 주세요)" 였고, 이 문장이 그대로 항목 내용이 돼 "확정"됐다.
- [확정] 규격은 질문마다 선택지 2~4개를 요구한다 (`state/question_format.py` `MIN_OPTIONS = 2`, 프롬프트 "선택지는 2~4개").
  답이 이름·장소·숫자인 질문은 고를 선택지가 없어 LLM 이 답이 아닌 선택지를 지어낸다.
- [확정] 화면에서도 같다 — 사용자가 그 선택지를 누르면 `kind: option` 으로 제출돼 같은 내용이 확정된다 (`frontend/src/pages/StudioPage.tsx` `choose`).
- [추정] 빈도는 낮다 (저장된 실행 기록 12건 중 1건). 근거: 기록을 "직접/입력/알려" 낱말로 훑은 결과.

## 2. 결정 (2026-11-14, 사용자 승인)

규격을 "선택지 0개 또는 2~4개"로 바꾼다. 0개면 직접 입력만 받는 질문이다. 화면은 입력 칸과 "알아서 정해 주세요"만 보여 준다.

## 3. 건드릴 파일

| 파일 | 변경 |
|---|---|
| `builder/src/specbuilder/state/question_format.py` | 선택지 수 검증을 0 또는 2~4 로. 선택지가 없으면 `multiple` 은 `false` |
| `builder/src/specbuilder/graph/main.py` | CLI: 선택지 없는 질문은 번호 목록 없이 받고, 숫자만 적어도 답으로 받는다. 빈 줄은 맡김 |
| `builder/prompts/interview_user.md`, `interview_design.md` | 직접 적어야 하는 답이면 `options` 를 비운다. 선택지는 그 자체로 답이어야 한다 |
| `builder/tests/state/test_question_format.py`, `tests/test_main.py` | 위 동작 |
| `frontend/src/pages/StudioPage.tsx` (+ 테스트), `src/types/api.d.ts` | 선택지 없는 질문의 입력 칸 안내. 타입 다시 생성 |
| `docs/design/question-format.md` | 규격 표와 설명 |

LLM 호출 수는 그대로다. `visual` · `preview` · 답 제출 규격은 바꾸지 않는다.

## 4. 검증 방법

1. `uv run pytest`, `uv run ruff check .`, 프론트엔드 lint · test · build.
2. 품질 회귀: 같은 모델(`claude-sonnet-5-5`, `claude -p`)로 04-no-screen · 03-vague 를 전(`develop`)/후로 돌려 선택지 없는 질문 수, 답이 아닌 선택지 수를 비교한다.
   답은 빈 줄(추천, 없으면 맡김), 저장된 프로필 고정.

## 5. 검증 결과

```
$ cd builder && uv run pytest -q
238 passed, 13 warnings          # 233 → 238 (선택지 없는 질문 1, CLI 4)
$ uv run ruff check . && uv run ruff format --check .
All checks passed! / 73 files already formatted
$ cd frontend && npm run lint && npm run test && npm run build
lint 출력 없음 / Tests 36 passed (36) / built
```

`npm run gen:types` 결과는 차이가 없다 — 선택지 수 제한은 생성 타입에 드러나지 않는다.

### 품질 회귀 — 같은 모델 `claude-sonnet-5-5` (`claude -p`), 2026-11-14, 전 = `develop` 342b221

답은 빈 줄(추천, 없으면 맡김), 저장된 프로필 고정, CLI 끝까지. 케이스당 1회.

| 케이스 | | LLM 호출 | 질문 수 | 선택지 없는 질문 | 동네 질문과 결과 |
|---|---|---|---|---|---|
| 04-no-screen | 전 | 9 | 2 | 0 | 선택지 "서울 · 부산 · 인천 · 대구" (질문문에 "구·동 단위로 직접 적어 주세요") → 추천 "서울" 로 확정 |
| | 후 | 6 | 1 | 1 | 선택지 없음 "(예: 서울 마포구 합정동)" → 빈 줄 = 맡김, 기본값 "서울특별시 중구" 와 "설정 값 하나로 바꿀 수 있게" 가 스펙에 들어감 |
| 03-vague | 전 | — | 7 | 0 | 해당 없음 |
| | 후 | — | 7 | 0 | 해당 없음 (선택지 없는 질문을 남발하지 않는다) |

- 전: 이번 실행에서는 "직접 입력" 선택지는 나오지 않았지만, 동네를 고를 수 없는 질문에 광역시 4개를 억지로 댔다 — 구·동을 원하는 질문에 "서울" 이 확정된다.
- 후: 고를 것이 없는 질문만 선택지 없이 나왔다. 03 은 전과 같이 모든 질문에 선택지가 있었다.
- 04 의 호출 수 차이(9 → 6)는 질문 묶음이 하나 줄어든 것과 실행마다의 흔들림이다 `[추정: 1회씩 실행]`.

## 6. 안 한 것 / 남은 것

- 케이스당 1회만 돌렸다. 01 · 02 는 돌리지 않았다.
- 화면에서 선택지 없는 질문은 테스트로만 확인했다 (브라우저에서 직접 보지 않음).
- "직접 입력" 을 가리키는 선택지를 코드로 걸러 내는 검사는 넣지 않았다 — 원인(선택지 강제)을 없앴고, 낱말 검사는 정상 선택지를 잘못 지울 수 있다.

토큰 소모 [추정]: 세션 약 8만 토큰 + `claude -p` 약 30회 (회귀 4건).
