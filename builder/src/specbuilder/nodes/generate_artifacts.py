import re

from specbuilder.llm import LLMCallError, LLMClient
from specbuilder.nodes.interview_user import render_context
from specbuilder.paths import load_prompt
from specbuilder.state import State

REQUIRED_FILES = ("spec.md", "SKILL.md", "AGENTS.md")
# 긴 마크다운을 JSON 문자열로 받으면 이스케이프가 자주 깨진다 — 구분선 형식이 더 견고하다.
FILE_MARKER = re.compile(r"^=== FILE: (\S+) ===[ \t]*$", re.MULTILINE)


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
