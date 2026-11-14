import json

import pytest

from specbuilder import common_items
from specbuilder.common_items import add_selected, fill_defaults, load_common_items
from tests.fakes.fake_llm import item


def test_first_three_common_items():
    catalog = load_common_items()
    assert {i: (c["area"], c["decided_by"]) for i, c in catalog.items()} == {
        "input-validation": ("function", "user"),
        "text-size": ("design", "user"),
        "basic-accessibility": ("design", "worker"),
    }
    assert set(load_common_items("function")) == {"input-validation"}
    assert set(load_common_items("design")) == {"text-size", "basic-accessibility"}


def test_default_of_asked_items_is_the_recommended_option():
    # "알아서 정해 주세요"와 추천을 고른 것이 같은 결과여야 사용자에게 추천의 뜻이 맞는다.
    for common in load_common_items().values():
        if "question" in common:
            [recommended] = [
                o for o in common["question"]["options"] if o.get("recommended")
            ]
            assert recommended["content"] == common["default"]


def bad(**change):
    base = {
        "id": "x",
        "name": "엑스",
        "area": "function",
        "when": "늘",
        "decided_by": "worker",
        "default": "기본",
    }
    return {**base, **change}


QUESTION = {
    "text": "물을까요?",
    "options": [
        {"label": "가", "content": "가 내용", "recommended": True},
        {"label": "나", "content": "나 내용", "recommended": True},
    ],
}


@pytest.mark.parametrize(
    "items",
    [
        [bad(), bad()],  # id 중복
        [bad(decided_by="user")],  # 사용자 항목인데 질문 없음
        [
            bad(question={**QUESTION, "options": QUESTION["options"][:1] * 2})
        ],  # 작업자 항목인데 질문
        [bad(decided_by="user", question=QUESTION)],  # 추천 둘
        [bad(area="tech")],
    ],
)
def test_rejects_bad_catalog(tmp_path, monkeypatch, items):
    path = tmp_path / "common_items.json"
    path.write_text(json.dumps({"items": items}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(common_items, "COMMON_ITEMS_FILE", path)
    with pytest.raises(ValueError):
        load_common_items()


def test_add_selected_skips_present_and_unknown_ids():
    catalog = load_common_items()
    items = [item("text-size", area="design")]
    added = add_selected(
        items,
        ["text-size", "nope", "basic-accessibility", "basic-accessibility"],
        catalog,
    )
    assert [i["id"] for i in added] == ["text-size", "basic-accessibility"]
    assert added[0] == items[0]


def test_fill_defaults_only_touches_empty_delegated_common_items():
    catalog = load_common_items()
    items = [
        item("input-validation", "delegated", ""),
        item("text-size", "delegated", "이미 있음", area="design"),
        item("other", "delegated", ""),
    ]
    filled = fill_defaults(items, catalog)
    assert filled[0]["content"] == catalog["input-validation"]["default"]
    assert filled[1:] == items[1:]
