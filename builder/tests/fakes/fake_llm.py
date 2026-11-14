import json

from specbuilder.llm import LLMCallError
from specbuilder.paths import PROMPTS_DIR


def files_reply(**overrides: str) -> str:
    """generate_artifacts 가 기대하는 구분선 형식의 응답을 만든다."""
    files = {
        "spec.md": "# 스펙\n\n가계부 프로그램.",
        "AGENTS.md": "# AGENTS\n\n## 용어사전\n",
        "skills/build-ledger.md": "# 가계부 만들기\n\n1. 화면을 만든다.",
    } | overrides
    return "\n".join(f"=== FILE: {name} ===\n{body}" for name, body in files.items())


def skill(
    name: str = "build-ledger",
    source: str = "new",
    when: str = "가계부를 만들 때 쓴다",
    basis: tuple[str, ...] = ("purpose",),
) -> dict:
    return {"name": name, "when": when, "source": source, "basis": list(basis)}


def skills_reply(*skills: dict) -> str:
    """select_skills 가 기대하는 JSON 응답을 만든다. 비우면 새로 쓰는 스킬 하나."""
    return json.dumps({"skills": list(skills) or [skill()]}, ensure_ascii=False)


def interview_reply(
    items: list[dict] | None = None, questions: list[dict] | None = None
) -> str:
    """묻는 노드가 기대하는 JSON 응답을 만든다."""
    return json.dumps(
        {"items": items or [], "questions": questions or []}, ensure_ascii=False
    )


def item(
    id: str,
    status: str = "confirmed",
    content: str = "정함",
    decided_by: str = "user",
    area: str = "function",
) -> dict:
    return {
        "id": id,
        "name": f"{id} 항목",
        "area": area,
        "decided_by": decided_by,
        "status": status,
        "content": content,
    }


def question(
    item_id: str, labels: tuple[str, ...] = ("가", "나"), multiple: bool = False
) -> dict:
    return {
        "item_id": item_id,
        "text": f"{item_id} 는요?",
        "multiple": multiple,
        "options": [
            {"label": label, "recommended": i == 0} for i, label in enumerate(labels)
        ],
    }


# 노드별 기본 응답. 테스트가 그 노드의 응답을 준비하지 않았을 때 쓴다 —
# 빈 노드가 실제 노드로 바뀌어도(LLM 호출이 생겨도) 그 노드를 다루지 않는 테스트는 그대로 돈다.
# 새 노드가 프롬프트를 추가하면 여기에 한 줄 추가한다.
DEFAULT_REPLIES = {
    "interview_user": lambda: interview_reply(
        [item("purpose", content="혼자 쓰는 가계부")]
    ),
    "select_skills": skills_reply,
    "generate_artifacts": files_reply,
}


class FakeLLM:
    """노드별로 미리 정한 응답을 돌려주고, 받은 호출을 노드 이름과 함께 기록한다.

    어느 노드의 호출인지는 시스템 프롬프트를 `prompts/<노드명>.md` 와 대조해 알아낸다 — LLMClient 프로토콜을 바꾸지 않기 위해서.
    """

    model = "fake"

    def __init__(self, replies: dict[str, list[str]] | None = None):
        self.replies = {node: list(r) for node, r in (replies or {}).items()}
        self.calls: list[tuple[str, str, str]] = []
        self.schemas: list[tuple[str, dict | None]] = []
        self._nodes = {
            p.read_text(encoding="utf-8"): p.stem for p in PROMPTS_DIR.glob("*.md")
        }
        unknown = set(self.replies) - set(self._nodes.values())
        if unknown:
            raise ValueError(f"FakeLLM: 프롬프트가 없는 노드의 응답: {sorted(unknown)}")

    def complete(self, system: str, prompt: str, schema: dict | None = None) -> str:
        node = self._nodes.get(system)
        if node is None:
            raise LLMCallError("FakeLLM: prompts/ 에 없는 시스템 프롬프트")
        self.calls.append((node, system, prompt))
        self.schemas.append((node, schema))
        queue = self.replies.get(node)
        if queue:
            return queue.pop(0)
        if node in DEFAULT_REPLIES:
            return DEFAULT_REPLIES[node]()
        raise LLMCallError(f"FakeLLM: {node} 의 응답이 없음")

    def calls_for(self, node: str) -> list[str]:
        """그 노드가 받은 사용자 프롬프트 목록."""
        return [prompt for n, _, prompt in self.calls if n == node]
