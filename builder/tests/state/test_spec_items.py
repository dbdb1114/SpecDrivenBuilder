import pytest
from pydantic import ValidationError

from specbuilder.state.spec_items import (
    delegate_open,
    merge_updates,
    needs_asking,
    purpose_item,
    spec_items_adapter,
)
from tests.fakes.fake_llm import item


def test_needs_asking_only_for_user_unknown_in_area():
    assert needs_asking([purpose_item()], "function")
    assert not needs_asking([purpose_item()], "design")
    assert not needs_asking([item("a", status="delegated")], "function")


def test_delegate_open_keeps_other_areas():
    items = [purpose_item(), item("look", status="unknown", content="", area="design")]
    result = delegate_open(items, "function")
    assert [i["status"] for i in result] == ["delegated", "unknown"]


def test_merge_keeps_confirmed_updates_only_content_of_delegated_and_adds_new():
    items = [item("a"), item("b", status="delegated", content=""), purpose_item()]
    updates = [
        item("a", content="LLM 이 덮어씀"),
        item("b", status="confirmed", content="기본 방향"),
        item("purpose", content="혼자 씀"),
        item("new", status="unknown", content=""),
    ]
    by_id = {i["id"]: i for i in merge_updates(items, updates)}

    assert by_id["a"]["content"] == "정함"
    assert (by_id["b"]["status"], by_id["b"]["content"]) == ("delegated", "기본 방향")
    assert by_id["purpose"]["status"] == "confirmed"
    assert "new" in by_id


@pytest.mark.parametrize("bad", [[item("Bad_ID")], [item("a"), item("a")]])
def test_rejects_bad_or_duplicate_ids(bad):
    with pytest.raises(ValidationError):
        spec_items_adapter.validate_python(bad)
