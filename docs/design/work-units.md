# 작업 단위 — worktree 별 분할

> 결정 (2026-11-12): `design.md` 의 그래프를 worktree 하나 = 세션 하나 = PR 하나로 나눈다.
> 각 세션은 자기 작업 단위의 범위만 구현하고, 루트 `AGENTS.md` "작업 절차"대로 `docs/work/<YYMMDD>-<작업명>/plan.md` 부터 쓴다.

## 순서

```
0 설계 문서 머지
└─▶ A 계약 + interview_user
     ├─▶ B select_stack + verify_stack ─┐
     ├─▶ C select_skills ───────────────┤
     ├─▶ D confirm_spec ────────────────┼─▶ F interview_design + 미리보기
     └─▶ E FastAPI + 프론트엔드 화면 ────┘   G interview_profile
```

- **0 → A 는 순서대로.** A 가 `develop` 에 머지되기 전에는 다른 작업 단위를 시작하지 않는다 — 전부 A 의 계약에 의존한다.
- **B · C · D · E 는 동시에** 진행할 수 있다. 모두 A 가 머지된 `develop` 에서 브랜치를 만든다.
- **F · G 는 그다음에 동시에** 진행할 수 있다. F 는 E 의 화면이, G 는 C 가 바꾼 `generate_artifacts` 가 있어야 한다.

## 작업 단위

| | 브랜치 | 범위 | 주로 건드리는 곳 | 먼저 끝나야 하는 것 |
|---|---|---|---|---|
| A | `feat/spec-items` | 스펙 항목과 `question-format.md` 의 규격 전부(질문 묶음·답 제출·확인 화면·`visual`·`preview`)를 빌더에 정의. `interview_user` 를 스펙 항목 기반으로 확장(질문 묶음, 종료 규칙, 종료 사유). 묻는 노드의 실행 규칙. `generate_artifacts` 가 스펙 항목을 받아 "사용자가 정한 것 / 작업자가 정하는 것"을 나눠 씀. CLI 가 질문 묶음을 그림 | `state/`, `nodes/interview_user.py`, `nodes/generate_artifacts.py`, `graph/`, `prompts/`, `tests/` | 0 |
| B | `feat/select-stack` | `select_stack`(버전까지 정함, 부족한 정보가 있으면 `interview_user` 로 돌아감), `verify_stack`(패키지 저장소 조회, 맞지 않으면 `select_stack` 으로 돌아감) | 새 노드 파일 2개와 그 프롬프트·테스트, 저장소 조회 모듈 | A |
| C | `feat/select-skills` | `select_skills`, 공통 스킬 목록과 첫 공통 스킬, `generate_artifacts` 가 스킬 목록을 받아 스킬 여러 개를 씀 | 새 노드 파일, `templates/`, `nodes/generate_artifacts.py` | A |
| D | `feat/confirm-spec` | `confirm_spec` 노드, 고칠 항목을 "아직 모름"으로 바꿔 돌아가는 경로, CLI 확인 화면 | 새 노드 파일, `graph/main.py` | A |
| E | `feat/web-ui` | FastAPI 로 그래프를 노출(시작, 질문 묶음 받기, 답 제출, 확인). OpenAPI 에서 프론트엔드 타입 생성. 프론트엔드 질문 화면과 확인 화면 | `api/`, `frontend/` | A |
| F | `feat/interview-design` | `interview_design` 노드, 색 견본·레이아웃 그림(`visual`), 미리보기(`preview`) | 새 노드 파일, `frontend/` | A, E |
| G | `feat/interview-profile` | `interview_profile` 노드, 프로필 저장과 재사용, 프로필을 작업자 컨텍스트로 번역 | 새 노드 파일, `nodes/generate_artifacts.py` | A, C |

## 충돌을 줄이는 규칙

- **규격은 A 가 전부 정의한다.** B~G 는 스펙 항목과 JSON 규격의 모델을 고치지 않는다. 고쳐야 하면 중단하고 묻는다 —
  동시에 도는 다른 세션이 같은 모델에 기대고 있다.
- **노드 하나 = 파일 하나**라서 노드 파일끼리는 겹치지 않는다. 겹치는 곳은 그래프 조립(`graph/build.py`)과 State 스키마다.
  각 작업 단위는 여기에 자기 노드의 등록·엣지·키만 추가하고 남의 줄을 고치지 않는다. 머지 충돌은 줄 추가끼리라 손으로 합친다.
- **`generate_artifacts` 는 A → C → G 순서로만 고친다.** B · D · E · F 는 건드리지 않는다.
- **`graph/main.py`(CLI)는 A → D 순서로만 고친다.**
- **아직 없는 노드는 지나간다.** B 가 머지되기 전에도 그래프가 끝까지 돌아야 한다. 각 작업 단위는 자기 노드가 없을 때의
  기존 흐름(`interview_user` → `generate_artifacts`)을 깨지 않는다.
- **`docs/design/` 은 각 작업 단위가 자기 "미결정"을 결정으로 바꿀 때만 고친다.** 다른 노드의 절은 건드리지 않는다.

## 작업 단위별로 계획 단계에서 정할 것

| | 정할 것 |
|---|---|
| A | 질문 묶음 수의 안전 상한. State 키 이름 |
| B | 지원할 패키지 저장소 목록. "함께 쓰는 것끼리 맞는가"의 판정 방법. 버전을 정하는 범위(주요 도구만 / 세부 라이브러리까지). 돌아가는 횟수 상한. 외부 저장소 조회에 쓸 의존성 |
| C | 공통 스킬 목록의 저장 형식과 첫 공통 스킬. 산출물에서 스킬을 두는 경로 |
| D | 없음 |
| E | 타입 생성 도구. 운영 checkpointer 는 이번에 정하지 않는다 |
| F | `layout` 의 `key` 목록 |
| G | 프로필 저장 위치. 프로필 질문 수 |

## 세션에 주는 지시

작업 단위마다 그 worktree 에서 세션을 열고 아래를 준다 (`<X>` 는 작업 단위 글자).

```
docs/design/design.md, docs/design/question-format.md, docs/design/work-units.md 를 읽고,
작업 단위 <X> 의 범위만 구현해 줘. 다른 작업 단위의 범위와 "충돌을 줄이는 규칙"에서 막은 파일은 건드리지 마.
AGENTS.md 의 작업 절차대로 분석과 계획부터 하고, 계획을 보여 준 뒤 승인받고 코딩해.
```

Codex 세션은 B · C · D · G 는 `builder/` 에서, 프론트엔드만 다룰 때는 `frontend/` 에서 시작한다.
