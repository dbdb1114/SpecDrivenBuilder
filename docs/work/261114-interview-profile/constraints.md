# 제약 — 작업 단위 G (PROMPT.md 에서 옮김, 2026-11-14)

## 범위
- `interview_profile`: 프로필(도메인 전문성 · 기술 노출 정도 · 설명 선호 · 환경 · 결정 위임 범위)을 질문 묶음 규격으로 수집한다.
  저장된 프로필이 있으면 건너뛴다. 요금은 토큰을 직접 묻지 않고 쓰는 도구와 요금제만 묻는다.
- 프로필 저장과 재사용.
- 프로필을 입력으로 넣기: `interview_user`(결정 위임 범위가 "누가 정하는가"의 경계를 옮긴다), `select_stack`(환경),
  `generate_artifacts`(산출물 AGENTS.md 의 "작업자 컨텍스트"로 번역).
- 프로필에 이름 · 소속 · 연락처를 넣지 않는다 (커밋되는 파일이 된다).

## 건드리지 않는 것
- 그래프 조립(`graph/build.py`), State 스키마, 스펙 항목 · JSON 규격 모델 — 고치지 않는다
- `graph/main.py`, 위에 적지 않은 노드 파일 (고칠 수 있는 노드 파일: `interview_profile.py`, `interview_user.py`,
  `select_stack.py`, `generate_artifacts.py`)
- 막힌 파일을 고쳐야 하거나 범위 밖으로 나가야 하면 중단하고 묻는다 (다른 worktree 에서 동시 작업 중)

## 그 밖에
- `docs/work/lessons.md`, 루트 `AGENTS.md` 용어사전 — 줄 추가만, 기존 줄 수정 금지
- `docs/design/` 은 이 작업 단위의 "미결정"을 결정으로 바꿀 때만, 자기 노드의 절만 고친다
- 계획을 보여 주고 승인받은 뒤 코딩한다. 이번 세션은 분석과 plan.md 까지만 (develop-2 세션 지시, 2026-11-14)
- 결정이 필요한 것은 AskUserQuestion 을 띄우지 않고 plan.md 와 화면에 글로 정리한다 (develop-2 세션이 사용자에게 모아서 묻는다)
- 작업을 마치면 `PROMPT.md` 를 삭제한다. 커밋하지 않는다

## 승인 때 받은 제약 (develop-2 세션, 2026-11-14)
- D 가 넣은 `interview_user` 의 "고치기로 고른 항목" 가드와 프롬프트 규칙을 지우지 않는다 — 그 위에 위임 범위 블록을 더한다
- 그래프 테스트는 확인 화면에서 멈추는 흐름을 따른다
- 로컬 커밋까지만. 푸시와 PR 생성은 하지 않는다 (develop-2 세션이 한다)
- 계획 밖 파일을 고쳐야 하거나 의존성이 필요해지면 AskUserQuestion 을 띄우지 말고 화면에 글로 적고 멈춘다
