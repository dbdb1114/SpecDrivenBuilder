import pytest
from langgraph.types import Command

from specbuilder.nodes import confirm_spec as node
from specbuilder.nodes.confirm_spec import build_screen, confirm_spec, validate_reply
from specbuilder.state import initial_state
from specbuilder.state.question_format import confirm_screen_adapter
from tests.fakes.fake_llm import item


def spec_items() -> list[dict]:
    return [
        item(
            "framework",
            content="웹 페이지 — 어디서나 열려서",
            decided_by="worker",
            area="tech",
        ),
        item("color", "delegated", "차분한 파랑", area="design"),
        item("purpose", content="혼자 쓰는 가계부"),
        item("share", "delegated", ""),
        item("backup-way", "delegated", "매일 자동 백업", decided_by="worker"),
    ]


def state_with(items: list[dict]) -> dict:
    return {**initial_state("가계부"), "spec_items": items}


def run_node(monkeypatch, items: list[dict], reply: dict) -> tuple[Command, list]:
    """interrupt 를 가로채 화면을 기록하고 미리 정한 답을 돌려준다 — 그래프 없이 노드만 돌린다."""
    shown = []

    def fake_interrupt(value):
        shown.append(value)
        return reply

    monkeypatch.setattr(node, "interrupt", fake_interrupt)
    return confirm_spec(state_with(items)), shown


def test_screen_matches_format_with_editable_rule_and_area_order():
    screen = build_screen(spec_items())

    assert confirm_screen_adapter.validate_python(screen) == screen
    assert [(i["id"], i["editable"]) for i in screen["items"]] == [
        ("purpose", True),
        ("share", True),
        ("backup-way", False),
        ("color", True),
        ("framework", False),
    ]
    by_id = {i["id"]: i for i in screen["items"]}
    assert by_id["share"] == {
        "id": "share",
        "area": "function",
        "name": "share 항목",
        "status": "delegated",
        "content": "",
        "editable": True,
    }


def test_tech_item_is_not_editable_even_if_user_decides():
    screen = build_screen([item("runtime", area="tech")])
    assert screen["items"][0]["editable"] is False


def test_unknown_item_stops_before_showing():
    with pytest.raises(ValueError, match="아직 모름"):
        build_screen([item("purpose"), item("input-data", "unknown", "")])


def test_confirm_goes_to_generate_without_changing_items(monkeypatch):
    command, shown = run_node(monkeypatch, spec_items(), {"action": "confirm"})

    assert command == Command(goto="generate_artifacts")
    assert shown == [build_screen(spec_items())]


def test_revise_reopens_chosen_items_and_returns_to_interview_user(monkeypatch):
    command, _ = run_node(
        monkeypatch,
        spec_items(),
        {"action": "revise", "item_ids": ["purpose", "color"]},
    )

    assert command.goto == "interview_user"
    by_id = {i["id"]: i for i in command.update["spec_items"]}
    assert by_id["purpose"]["status"] == "unknown"
    assert by_id["purpose"]["content"] == ""
    assert by_id["color"]["status"] == "unknown"
    # 고르지 않은 항목은 그대로
    assert by_id["share"] == item("share", "delegated", "")
    assert by_id["framework"]["status"] == "confirmed"
    assert list(command.update) == ["spec_items"]


@pytest.mark.parametrize(
    "reply, message",
    [
        ({"action": "revise", "item_ids": ["framework"]}, "고칠 수 없는"),
        ({"action": "revise", "item_ids": ["backup-way"]}, "고칠 수 없는"),
        ({"action": "revise", "item_ids": ["nope"]}, "없는 항목"),
        ({"action": "revise", "item_ids": []}, "규격"),
        ({"action": "ok"}, "규격"),
    ],
)
def test_invalid_reply_is_rejected(reply, message):
    with pytest.raises(ValueError, match=message):
        validate_reply(build_screen(spec_items()), reply)
