# 제약 — 작업 단위 H (`feat/common-items`)

출처: worktree 루트 `PROMPT.md` (사용자가 준 지시). 계획을 세우거나 고칠 때마다 다시 읽는다.

## 범위

- 공통 항목 목록과 첫 공통 항목 3개 (`input-validation`, `text-size`, `basic-accessibility`).
- `interview_user` · `interview_design` 이 해당하는 공통 항목의 id 를 고르고, 빌더 코드가 고정 질문·선택지·기본 방향을 붙인다.
- 계획 단계에서 정할 것: 공통 항목 목록의 저장 위치와 형식, 첫 3개의 질문 문구·선택지·기본 방향.

## 건드리지 않는 것

- 다른 작업 단위의 범위. 범위 밖 파일을 고쳐야 하면 중단하고 묻는다.
- 그래프 조립(`graph/build.py`), State 스키마, 스펙 항목 · JSON 규격 모델(`state/`) — 고치지 않는다.
- `nodes/generate_artifacts.py`, `graph/main.py`, 다른 노드 파일, `frontend/`.
- `docs/work/lessons.md` · 루트 `AGENTS.md` 용어사전은 줄 추가만.
- `docs/design/` 은 이 작업 단위의 "구현 전"을 구현으로 바꿀 때만, 자기 절만.

## 그 밖에

- 프롬프트를 바꾸므로 품질 회귀 세트(`builder/evals/cases/`)를 바꾸기 전과 후에 **같은 모델**로 돌려 `plan.md` 에 나란히 붙인다.
- 커밋·푸시는 요청받았을 때만. 커밋 메시지에 AI 생성 흔적 없음.
- 작업을 마치면 `PROMPT.md` 를 지운다. 커밋하지 않는다.

## 2026-11-14 추가 (사용자 지시)

- `input-validation` 의 "언제 넣는가"를 "화면에 사용자가 글자나 숫자를 직접 쳐 넣는 칸이 있다"로 좁힌다. 파일 올리기만 있는 프로그램은 고르지 않는다.
- 파일 입력용 공통 항목은 이번에 만들지 않는다 (plan.md "남은 것"에 적는다).
- 고친 뒤 품질 회귀는 `02-domain` 만 다시 돌려 표에 추가한다.
- 커밋은 한 커밋 한 가지 변경으로 나눈다. 푸시와 PR 은 하지 않는다 (다른 세션에서 한다).
