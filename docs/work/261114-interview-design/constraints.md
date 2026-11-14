# 제약 — 작업 단위 F (`feat/interview-design`)

출처: worktree 루트 `PROMPT.md` (사용자가 준 지시). 계획을 세우거나 고칠 때마다 다시 읽는다.

## 범위

- `interview_design`: 화면이 있는 프로그램일 때만 색 톤 · 레이아웃 등을 묻는다. 선택지에 `visual` 을 붙인다.
  답을 받으면 다음 질문 묶음에 `preview` 를 실어 "이 느낌이 맞나요?"를 묻는다.
- 프론트엔드: `visual` 의 색 견본 · 레이아웃 그림, `preview` 미리보기.
  미리 만들어 둔 레이아웃 틀에 색과 문구를 입혀 그린다. LLM 이 만든 화면 코드를 실행하지 않는다.
- 빌더는 목록에 없는 `layout` `key` 를 내보내지 않는다.

## 건드리지 않는 것

- 그래프 조립(`graph/build.py`), State 스키마, 스펙 항목 · JSON 규격 모델 — 고치지 않는다
  (예외: `question_format.py` 의 `LAYOUT_KEYS` 상수는 A 가 "F 가 이 상수만 바꾼다" 고 남겨 둠.
  2026-11-14 사용자 승인: `LayoutKey` 를 `Literal` 로 바꾸는 한 줄도 허용 — key 목록 원본을 빌더 한 곳에 두려고)
- `nodes/generate_artifacts.py`, `graph/main.py`, 다른 노드 파일
- E 가 만든 질문 화면의 구조 변경 (그림을 그리는 부분만 추가)
- 막힌 파일을 고쳐야 하거나 범위 밖으로 나가야 하면 중단하고 묻는다 (다른 worktree 에서 동시 작업 중).

## 그 밖에

- 프롬프트를 추가하므로 화면이 있는 요청과 없는 요청으로 실제 모델 실행 결과를 `plan.md` 에 적는다.
- `docs/work/lessons.md` 와 루트 `AGENTS.md` 용어사전은 줄 추가만. 기존 줄을 고치지 않는다.
- `docs/design/` 은 이 작업 단위의 "미결정"을 결정으로 바꿀 때만, 자기 노드의 절만 고친다.
- `PROMPT.md` 는 커밋하지 않고 작업 끝에 삭제한다.
