from langgraph.types import Command, interrupt
from pydantic import ValidationError

from specbuilder.state import State
from specbuilder.state.question_format import (
    ConfirmReply,
    ConfirmScreen,
    confirm_reply_adapter,
    confirm_screen_adapter,
)
from specbuilder.state.spec_items import SpecItem

NEXT = "generate_artifacts"
# 돌아가는 경로 3. 고른 항목을 아직 모름으로 바꾸기만 하면 묻는 노드의 실행 규칙이 그 영역의 노드에서 다시 묻는다.
REVISE_TO = "interview_user"
# 확인 화면은 영역별로 묶어 그린다 — CLI·프론트엔드가 같은 순서를 받도록 여기서 정렬한다.
AREA_ORDER = ("function", "design", "tech")


def is_editable(item: SpecItem) -> bool:
    """사용자가 정하는 항목만 고칠 수 있다. 기술 항목은 사용자가 판단할 수 없고, 아직 모름으로 바꿔도 다시 묻는 노드가 없다."""
    return item["decided_by"] == "user" and item["area"] != "tech"


def build_screen(items: list[SpecItem]) -> ConfirmScreen:
    """스펙 항목을 확인 화면 규격으로 만든다 (question-format.md "확인 화면")."""
    unknown = [item["id"] for item in items if item["status"] == "unknown"]
    if unknown:
        # 묻는 노드가 아직 모름을 남기지 않고 나가므로 여기 오면 앞 노드의 버그다. 빼고 보여 주면 모르는 채로 산출물이 나간다.
        raise ValueError(f"확인 화면에 아직 모름 항목이 있음: {unknown}")
    ordered = sorted(items, key=lambda item: AREA_ORDER.index(item["area"]))
    return confirm_screen_adapter.validate_python(
        {
            "items": [
                {
                    "id": item["id"],
                    "area": item["area"],
                    "name": item["name"],
                    "status": item["status"],
                    "content": item["content"],
                    "editable": is_editable(item),
                }
                for item in ordered
            ]
        }
    )


def validate_reply(screen: ConfirmScreen, raw: object) -> ConfirmReply:
    """확인 화면의 답을 규격과 이 화면에 맞는지 검증한다. 맞지 않으면 ValueError."""
    try:
        reply = confirm_reply_adapter.validate_python(raw)
    except ValidationError as e:
        raise ValueError(f"확인 화면 답이 규격에 맞지 않음: {e}") from e
    if reply["action"] == "revise":
        editable = {i["id"]: i["editable"] for i in screen["items"]}
        missing = [i for i in reply["item_ids"] if i not in editable]
        if missing:
            raise ValueError(f"확인 화면에 없는 항목: {missing}")
        locked = [i for i in reply["item_ids"] if not editable[i]]
        if locked:
            raise ValueError(f"고칠 수 없는 항목: {locked}")
    return reply


def reopen(items: list[SpecItem], item_ids: list[str]) -> list[SpecItem]:
    """고른 항목을 아직 모름으로 되돌린다. 이전 답은 `qa` 에 남아 있어 다시 물을 때 LLM 이 본다."""
    targets = set(item_ids)
    return [
        {**item, "status": "unknown", "content": ""} if item["id"] in targets else item
        for item in items
    ]


def confirm_spec(state: State) -> Command:
    """스펙 항목 요약을 보여 주고 확인받는다 (LLM 없음). 갈 곳: generate_artifacts | interview_user.

    resume 하면 처음부터 다시 돌지만 interrupt 앞에는 계산만 있어 다시 돌아도 같다.
    """
    items = state["spec_items"]
    screen = build_screen(items)
    reply = validate_reply(screen, interrupt(screen))
    if reply["action"] == "confirm":
        return Command(goto=NEXT)
    return Command(
        update={"spec_items": reopen(items, reply["item_ids"])}, goto=REVISE_TO
    )
