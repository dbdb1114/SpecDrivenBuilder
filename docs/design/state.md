# LangGraph 상태 · checkpointer

## 결정 (2026-11-06)

- interview 노드는 `interrupt()`로 사용자 응답을 기다린다 → checkpointer는 첫 그래프부터 필수.
- 개발: `SqliteSaver` (파일 하나, `--reload`해도 상태 유지)
- 테스트: `InMemorySaver` (`MemorySaver`는 구 별칭 — 쓰지 않는다)
- 운영 저장소: 미결정 (`PostgresSaver` 후보). 외부 사용자가 생길 때 결정.

## 미결정

- State 스키마 자체 (TypedDict 기준, 기본값 필요하면 dataclass. Pydantic은 느리므로 이유 있을 때만)
- 저장된 checkpoint의 스키마 변경 시 호환 정책
