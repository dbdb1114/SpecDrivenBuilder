import pytest
from pydantic import ValidationError

from specbuilder.state.question_format import (
    apply_submission,
    assign_ids,
    bundle_adapter,
    confirm_reply_adapter,
    confirm_screen_adapter,
    interview_reply_adapter,
    submission_adapter,
    validate_submission,
)
from specbuilder.state.spec_items import purpose_item
from tests.fakes.fake_llm import item, question


def make_bundle():
    return assign_ids(
        [
            question("purpose"),
            question("features", ("a", "b", "c"), multiple=True),
            question("rules"),
        ],
        round=1,
        can_finish=True,
    )


def test_assign_ids_numbers_questions_and_options():
    bundle = make_bundle()
    assert [q["id"] for q in bundle["questions"]] == ["q1", "q2", "q3"]
    assert [o["id"] for o in bundle["questions"][1]["options"]] == ["o1", "o2", "o3"]
    assert bundle["questions"][0]["options"][0]["visual"] is None


@pytest.mark.parametrize(
    "options",
    [
        [{"label": "하나"}],
        [{"label": str(i)} for i in range(5)],
        [{"label": "a", "recommended": True}, {"label": "b", "recommended": True}],
    ],
)
def test_draft_option_limits(options):
    reply = {
        "items": [],
        "questions": [{"item_id": "x", "text": "?", "options": options}],
    }
    with pytest.raises(ValidationError):
        interview_reply_adapter.validate_python(reply)


def test_bundle_question_count_limits():
    bundle = make_bundle()
    with pytest.raises(ValidationError):
        bundle_adapter.validate_python({**bundle, "questions": []})
    with pytest.raises(ValidationError):
        bundle_adapter.validate_python({**bundle, "questions": bundle["questions"] * 4})


def test_visual_and_preview():
    bundle = make_bundle()
    option, other = bundle["questions"][0]["options"]
    palette = {"type": "palette", "colors": ["#1E3A5F", "#F5F7FA"]}
    layout = {"type": "layout", "key": "sidebar-left"}
    preview = {
        "layout": "sidebar-left",
        "colors": ["#1E3A5F"],
        "texts": {"title": "가계부", "menu": ["내역"]},
    }
    for visual in (palette, layout):
        q = {
            **bundle["questions"][0],
            "options": [{**option, "visual": visual}, other],
        }
        bundle_adapter.validate_python({**bundle, "preview": preview, "questions": [q]})
    for bad in (
        {"type": "layout", "key": "없는-틀"},
        {"type": "palette", "colors": ["red"]},
    ):
        q = {**bundle["questions"][0], "options": [{**option, "visual": bad}, other]}
        with pytest.raises(ValidationError):
            bundle_adapter.validate_python({**bundle, "questions": [q]})


@pytest.mark.parametrize(
    "answers",
    [
        [{"question_id": "q9", "kind": "delegate"}],
        [{"question_id": "q1", "kind": "option", "option_ids": ["o9"]}],
        [{"question_id": "q1", "kind": "option", "option_ids": ["o1", "o2"]}],
        [
            {"question_id": "q1", "kind": "delegate"},
            {"question_id": "q1", "kind": "delegate"},
        ],
        [{"question_id": "q1", "kind": "custom", "text": "  "}],
        [{"question_id": "q1", "kind": "option", "option_ids": []}],
    ],
)
def test_validate_submission_rejects(answers):
    with pytest.raises((ValueError, ValidationError)):
        validate_submission(make_bundle(), {"action": "submit", "answers": answers})


def test_apply_submission_table():
    items = [
        purpose_item(),
        item("features", "unknown", ""),
        item("rules", "unknown", ""),
        item("other", "unknown", ""),
    ]
    submission = validate_submission(
        make_bundle(),
        {
            "action": "submit",
            "answers": [
                {"question_id": "q1", "kind": "custom", "text": "혼자 써요"},
                {"question_id": "q2", "kind": "option", "option_ids": ["o1", "o3"]},
            ],
        },
    )
    result, qa = apply_submission(
        items, make_bundle(), submission, "interview_user", "function"
    )
    by_id = {i["id"]: i for i in result}

    assert (by_id["purpose"]["status"], by_id["purpose"]["content"]) == (
        "confirmed",
        "혼자 써요",
    )
    assert (by_id["features"]["status"], by_id["features"]["content"]) == (
        "confirmed",
        "a, c",
    )
    assert by_id["rules"]["status"] == "delegated"  # 답이 없는 질문 → 맡김
    assert by_id["other"]["status"] == "unknown"  # 이 묶음에 없던 항목은 그대로
    assert [q["answer"] for q in qa] == ["혼자 써요", "a, c", "알아서 정해 주세요"]


def test_apply_finish_delegates_remaining_unknown():
    items = [purpose_item(), item("other", "unknown", "")]
    submission = validate_submission(
        make_bundle(),
        {
            "action": "finish",
            "answers": [{"question_id": "q1", "kind": "option", "option_ids": ["o2"]}],
        },
    )
    result, _ = apply_submission(
        items, make_bundle(), submission, "interview_user", "function"
    )
    assert [(i["status"], i["content"]) for i in result] == [
        ("confirmed", "나"),
        ("delegated", ""),
    ]


def test_confirm_screen_and_reply():
    confirm_screen_adapter.validate_python(
        {
            "items": [
                {
                    "id": "who-uses",
                    "area": "function",
                    "name": "누가",
                    "status": "confirmed",
                    "content": "나",
                    "editable": True,
                }
            ]
        }
    )
    assert confirm_reply_adapter.validate_python({"action": "confirm"}) == {
        "action": "confirm"
    }
    confirm_reply_adapter.validate_python(
        {"action": "revise", "item_ids": ["who-uses"]}
    )
    with pytest.raises(ValidationError):
        confirm_reply_adapter.validate_python({"action": "revise", "item_ids": []})
    with pytest.raises(ValidationError):
        submission_adapter.validate_python({"action": "skip", "answers": []})
