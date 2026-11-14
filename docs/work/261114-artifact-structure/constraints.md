# 제약 — 작업 단위 J (PROMPT.md 에서 옮김, 2026-11-14)

## 범위
- 산출물의 폴더 구성: `docs/spec.md`, 고른 기술에 있는 부분만 `frontend/` · `backend/` · `database/` 의 `AGENTS.md`(구조·명령어·코드 규칙·하지 말 것) · `CLAUDE.md`, 루트 `AGENTS.md` 의 "구조" 섹션.
- `select_stack` 이 프로그램의 부분을 기술 스펙 항목에 밝힌다.
- 주로 건드리는 곳: `prompts/generate_artifacts.md`, `nodes/generate_artifacts.py`, `prompts/select_stack.md`, `nodes/select_stack.py`, 템플릿 스냅샷 테스트.

## 건드리지 않는 것
- 다른 작업 단위의 범위 (H · I 가 동시에 돌 수 있음 — `interview_design`, `state/question_format.py`, 프론트엔드 미리보기)
- 스펙 항목 · JSON 규격 모델, 그래프 조립(`graph/build.py`), State 스키마
- 범위 밖 파일을 고쳐야 하면 중단하고 묻는다

## 그 밖에
- 분석 → `plan.md` → 승인 후 코딩. "계획 단계에서 정할 것"은 선택지와 추천안을 계획과 함께 보여 준다.
- 품질 회귀 세트(`builder/evals/cases/`)를 바꾸기 전과 후에 같은 모델로 돌려 `plan.md` 에 나란히 붙인다.
- 실행 검증(루트 `AGENTS.md` "품질 판정" 1번)을 하고 템플릿 스냅샷 테스트를 갱신한다.
- 커밋·푸시는 요청받았을 때만. 커밋 메시지에 AI 생성 흔적 금지.
- 마치면 `PROMPT.md` 를 지운다. 커밋하지 않는다.
- `docs/work/lessons.md`, 루트 `AGENTS.md` 용어사전 — 줄 추가만. `docs/design/` — 이 작업 단위의 절만.
