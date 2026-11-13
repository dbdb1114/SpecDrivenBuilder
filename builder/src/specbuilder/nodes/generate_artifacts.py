import re

from specbuilder.llm import LLMCallError, LLMClient
from specbuilder.paths import load_prompt
from specbuilder.state import SpecItem, State

REQUIRED_FILES = ("spec.md", "SKILL.md", "AGENTS.md")
# 긴 마크다운을 JSON 문자열로 받으면 이스케이프가 자주 깨진다 — 구분선 형식이 더 견고하다.
FILE_MARKER = re.compile(r"^=== FILE: (\S+) ===[ \t]*$", re.MULTILINE)


AREA_LABELS = {"function": "용도·기능", "design": "디자인", "tech": "기술"}


def _is_user_decision(item: SpecItem) -> bool:
    return item["decided_by"] == "user" and item["status"] == "confirmed"


def _render_item(item: SpecItem) -> str:
    # 기본 방향이 빈 맡김 항목(사용자가 "알아서"를 골랐거나 묻기를 그만둔 경우)은 여기서 정하라고 표시한다.
    content = item["content"].strip() or "(기본 방향 없음 — 정해서 적을 것)"
    return f"- [{AREA_LABELS[item['area']]}] {item['name']}: {content}"


def render_context(state: State) -> str:
    """요청 원문과 스펙 항목을 "사용자가 정한 것 / 작업자가 정하는 것" 으로 나눈 데이터 블록으로 만든다."""
    items = state["spec_items"]
    user = [_render_item(i) for i in items if _is_user_decision(i)]
    worker = [_render_item(i) for i in items if not _is_user_decision(i)]
    return "\n".join(
        ["## 요청 원문", state["request"].strip(), "", "## 사용자가 정한 것"]
        + (user or ["(없음)"])
        + ["", "## 작업자가 정하는 것"]
        + (worker or ["(없음)"])
    )


def parse_files(text: str) -> dict[str, str]:
    """`=== FILE: <이름> ===` 구분선으로 나뉜 응답을 파일명 → 내용으로 바꾼다."""
    parts = FILE_MARKER.split(text)
    files = {name: body.strip() + "\n" for name, body in zip(parts[1::2], parts[2::2])}
    missing = [f for f in REQUIRED_FILES if f not in files]
    if missing:
        raise LLMCallError(f"응답에 빠진 파일: {missing}")
    return {name: files[name] for name in REQUIRED_FILES}


def make_generate_artifacts(llm: LLMClient):
    """LLM 클라이언트를 주입한 generate_artifacts 노드를 만든다."""
    system = load_prompt("generate_artifacts")

    def generate_artifacts(state: State) -> dict:
        files = parse_files(llm.complete(system, render_context(state)))
        # CLAUDE.md 는 본문 없이 임포트 한 줄로 고정 (루트 "산출물 규칙") — LLM 에 맡기지 않는다.
        files["CLAUDE.md"] = "@AGENTS.md\n"
        return {"artifacts": files}

    return generate_artifacts
