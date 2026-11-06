from specbuilder.llm import LLMCallError


class FakeLLM:
    """미리 정한 응답을 순서대로 돌려주고, 받은 (system, prompt) 를 기록한다."""

    model = "fake"

    def __init__(self, replies: list[str]):
        self.replies = list(replies)
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, prompt: str) -> str:
        self.calls.append((system, prompt))
        if not self.replies:
            raise LLMCallError("FakeLLM: 준비된 응답이 없음 (예상보다 많이 호출됨)")
        return self.replies.pop(0)


def files_reply(**overrides: str) -> str:
    """generate_artifacts 가 기대하는 구분선 형식의 응답을 만든다."""
    files = {
        "spec.md": "# 스펙\n\n가계부 프로그램.",
        "SKILL.md": "---\nname: build-ledger\ndescription: 가계부를 만들 때 쓴다\n---\n\n1. 화면을 만든다.",
        "AGENTS.md": "# AGENTS\n\n## 용어사전\n",
    } | overrides
    return "\n".join(f"=== FILE: {name} ===\n{body}" for name, body in files.items())
