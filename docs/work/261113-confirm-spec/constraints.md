# 제약 — 작업 단위 D (confirm_spec)

출처: 세션 지시(PROMPT.md, 2026-11-13). 계획을 세우거나 고칠 때마다 다시 읽는다.

## 범위

- `confirm_spec`: 스펙 항목을 `question-format.md` "확인 화면" 규격으로 내보내고 `interrupt()` 로 답을 기다린다.
  `confirm` 이면 `generate_artifacts` 로, `revise` 이면 고른 항목을 "아직 모름"으로 바꾸고 `interview_user` 로 돌아간다.
  `editable` 이 `false` 인 항목은 고칠 수 없다. LLM 을 호출하지 않는다.
- CLI(`graph/main.py`)에 확인 화면: 스펙 항목 요약을 보여 주고 확인 또는 고칠 항목 번호를 받는다.

## 건드리지 않는 것

- 그래프 조립(`graph/build.py`), State 스키마, 스펙 항목 · JSON 규격 모델 (A 가 만든 것)
- `nodes/generate_artifacts.py`, 다른 노드 파일
- 막힌 파일을 고쳐야 하거나 범위 밖으로 나가야 하면 중단하고 묻는다 (다른 worktree 에서 동시 작업 중).

## 그 밖에

- 부수 효과를 `interrupt()` 앞에 두지 않는다 (resume 하면 노드가 처음부터 다시 돈다).
- `docs/work/lessons.md` 와 루트 `AGENTS.md` 용어사전은 줄 추가만. 기존 줄을 고치지 않는다.
- `docs/design/` 은 이 작업 단위의 "미결정"을 결정으로 바꿀 때만, 자기 노드의 절만 고친다.
- `PROMPT.md` 는 커밋하지 않고, 작업을 마치면 삭제한다.

## 범위 확장 (2026-11-14, 사용자 승인)

- 실제 모델 실행에서 고친 항목을 `interview_user` 가 다시 묻지 않고 지난 답으로 다시 확정하는 문제가 나왔다.
  이 PR 에서 `nodes/interview_user.py`(코드 가드)와 `prompts/interview_user.md`(규칙 한 줄), 그 테스트를 고친다.
  프롬프트가 바뀌므로 품질 회귀 세트 3건을 같은 모델로 전·후 실행한다.
- 그 밖의 "건드리지 않는 것"(build.py, State, 스펙 항목·JSON 규격 모델, 다른 노드)은 그대로다.
