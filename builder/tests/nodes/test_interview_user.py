import pytest
from langgraph.types import Command

from specbuilder.common_items import fixed_questions, load_common_items
from specbuilder.llm import LLMCallError
from specbuilder.nodes.interview_user import MAX_ROUNDS, make_interview_user
from specbuilder.state import initial_state
from specbuilder.state.question_format import assign_ids
from tests.conftest import SAVED_PROFILE
from tests.fakes.fake_llm import FakeLLM, interview_reply, item, question


def run(replies, state=None):
    llm = FakeLLM({"interview_user": replies})
    return make_interview_user(llm)(state or initial_state("가계부 만들어줘")), llm


def test_first_entry_asks_purpose_first_and_stores_bundle_before_interrupt():
    reply = interview_reply(
        [
            item("input-data", "unknown", ""),
            item("storage", "delegated", "내 컴퓨터 파일", decided_by="worker"),
        ],
        [question("input-data"), question("purpose")],
    )
    result, llm = run([reply])

    assert result.goto == "interview_user"
    bundle = result.update["pending_bundle"]
    assert [q["item_id"] for q in bundle["questions"]] == ["purpose", "input-data"]
    assert [q["id"] for q in bundle["questions"]] == ["q1", "q2"]
    assert bundle["round"] == 1 and bundle["can_finish"] is True
    assert {i["id"] for i in result.update["spec_items"]} == {
        "purpose",
        "input-data",
        "storage",
    }
    assert "가계부 만들어줘" in llm.calls_for("interview_user")[0]


def test_resolved_when_no_user_unknown_left():
    state = initial_state("가계부")
    state["question_round"] = 2
    result, _ = run([interview_reply([item("purpose")], [question("purpose")])], state)

    assert result.goto == "interview_design"
    assert result.update["interview_stops"] == [
        {"node": "interview_user", "reason": "resolved", "rounds": 2}
    ]
    assert result.update["question_round"] == 0


def test_passes_through_without_llm_when_nothing_to_ask():
    state = initial_state("가계부")
    state["spec_items"] = [item("purpose")]
    result, llm = run([], state)

    assert result == Command(goto="interview_design")
    assert llm.calls == []


def test_round_limit_delegates_without_llm():
    state = initial_state("가계부")
    state["question_round"] = MAX_ROUNDS
    result, llm = run([], state)

    assert result.update["interview_stops"][0]["reason"] == "round_limit"
    assert result.update["spec_items"][0]["status"] == "delegated"
    assert llm.calls == []


@pytest.mark.parametrize(
    "reply",
    [
        "질문 없음",
        interview_reply([], []),  # 아직 모름이 남았는데 질문이 없음
        interview_reply([], [question("purpose"), question("purpose")]),
        interview_reply(
            [item("stray")], [question("purpose"), question("stray")]
        ),  # 확정 항목을 물음
        interview_reply(
            [item("look", "unknown", "", area="design")], [question("purpose")]
        ),
        interview_reply(
            [item("db", "unknown", "", decided_by="worker")], [question("purpose")]
        ),
    ],
)
def test_rejects_bad_replies(reply):
    with pytest.raises(LLMCallError):
        run([reply])


def test_finish_from_bundle_stops_with_user_finished(monkeypatch):
    state = initial_state("가계부")
    state["spec_items"] += [item("other", "unknown", "")]
    state["pending_bundle"] = assign_ids([question("purpose")], 1, True)
    monkeypatch.setattr(
        "specbuilder.nodes.interview_user.interrupt",
        lambda _: {"action": "finish", "answers": []},
    )
    result, llm = run([], state)

    assert result.goto == "interview_design"
    assert result.update["interview_stops"][0]["reason"] == "user_finished"
    assert {i["status"] for i in result.update["spec_items"]} == {"delegated"}
    assert llm.calls == []


def test_passes_reply_json_schema_to_llm():
    _, llm = run([interview_reply([item("purpose")])])
    schema = llm.schemas[0][1]
    assert set(schema["properties"]) == {"items", "questions", "common_items"}


def reopened_state() -> dict:
    """확인 화면에서 용도를 고르고 돌아온 상태 — 용도는 아직 모름인데 지난 답이 있다."""
    state = initial_state("가계부")
    state["spec_items"] = [item("purpose", "unknown", ""), item("input-data")]
    state["qa"] = [
        {
            "node": "interview_user",
            "round": 1,
            "item_id": "purpose",
            "question": "누가 쓰나요?",
            "answer": "저 혼자요",
        }
    ]
    return state


def test_reopened_item_is_asked_again_even_if_llm_fills_it():
    reply = interview_reply(
        [item("purpose", content="혼자 쓰는 가계부")], [question("purpose")]
    )
    result, llm = run([reply], reopened_state())

    assert result.goto == "interview_user"
    assert [q["item_id"] for q in result.update["pending_bundle"]["questions"]] == [
        "purpose"
    ]
    by_id = {i["id"]: i for i in result.update["spec_items"]}
    assert by_id["purpose"]["status"] == "unknown"
    assert (
        "## 사용자가 고치기로 고른 항목\npurpose" in llm.calls_for("interview_user")[0]
    )


def test_reopened_item_cannot_be_resolved_silently():
    reply = interview_reply([item("purpose", content="혼자 쓰는 가계부")], [])
    with pytest.raises(LLMCallError, match="질문이 없음"):
        run([reply], reopened_state())


def test_first_entry_context_has_no_reopened_section():
    _, llm = run([interview_reply([item("purpose")])])
    assert "고치기로 고른" not in llm.calls_for("interview_user")[0]


def test_context_has_delegation_scope_from_profile():
    state = initial_state("가계부")
    state["profile"] = {**SAVED_PROFILE, "delegation": "선택지가 있으면 물어봐 주세요"}
    _, llm = run([interview_reply([item("purpose")])], state)

    prompt = llm.calls_for("interview_user")[0]
    assert "## 결정 위임 범위\n선택지가 있으면 물어봐 주세요" in prompt


def test_context_delegation_scope_unknown_without_profile():
    _, llm = run([interview_reply([item("purpose")])])
    assert "## 결정 위임 범위\n(모름)" in llm.calls_for("interview_user")[0]


# --- 공통 항목 (design.md "공통 항목")

VALIDATION = load_common_items()["input-validation"]


def validation_bundle(round=1):
    return assign_ids(
        fixed_questions(
            [item("input-validation", "unknown", "")], {"input-validation": VALIDATION}
        ),
        round,
        True,
    )


def answered_state(submission, monkeypatch):
    state = initial_state("가계부")
    state["spec_items"] = [item("purpose"), item("input-validation", "unknown", "")]
    state["pending_bundle"] = validation_bundle()
    monkeypatch.setattr(
        "specbuilder.nodes.interview_user.interrupt", lambda _: submission
    )
    return state


def test_selected_common_item_is_added_and_asked_with_fixed_question():
    reply = interview_reply(
        [item("purpose", "unknown", "")], [question("purpose")], ["input-validation"]
    )
    result, llm = run([reply])

    added = next(
        i for i in result.update["spec_items"] if i["id"] == "input-validation"
    )
    assert added == {
        "id": "input-validation",
        "name": VALIDATION["name"],
        "area": "function",
        "decided_by": "user",
        "status": "unknown",
        "content": "",
    }
    asked = result.update["pending_bundle"]["questions"]
    assert [q["item_id"] for q in asked] == ["purpose", "input-validation"]
    assert asked[1]["text"] == VALIDATION["question"]["text"]
    assert [o["label"] for o in asked[1]["options"]] == [
        o["label"] for o in VALIDATION["question"]["options"]
    ]
    assert [o["recommended"] for o in asked[1]["options"]] == [True, False, False]
    assert len(llm.calls) == 1


def test_context_lists_function_common_items_only():
    _, llm = run(
        [interview_reply([item("purpose", "unknown", "")], [question("purpose")])]
    )
    context = llm.calls_for("interview_user")[0]
    assert "## 공통 항목 목록" in context
    assert "`input-validation`" in context and VALIDATION["when"] in context
    assert "text-size" not in context


def test_llm_written_common_item_and_question_are_discarded():
    reply = interview_reply(
        [item("purpose"), item("input-validation", content="LLM 이 쓴 내용")],
        [question("input-validation", ("LLM 선택지", "또 다른"))],
        ["input-validation"],
    )
    result, _ = run([reply])

    added = next(
        i for i in result.update["spec_items"] if i["id"] == "input-validation"
    )
    assert added["status"] == "unknown" and added["content"] == ""
    # LLM 질문은 버려지고 고정 질문 하나만 남는다 — 질문 0개 + 고정 질문만인 묶음도 허용.
    [only] = result.update["pending_bundle"]["questions"]
    assert only["text"] == VALIDATION["question"]["text"]


def test_unknown_or_other_area_common_ids_are_ignored():
    reply = interview_reply([item("purpose")], [], ["no-such-item", "text-size"])
    result, _ = run([reply])

    assert result.goto == "interview_design"
    assert [i["id"] for i in result.update["spec_items"]] == ["purpose"]


def test_fixed_question_waits_for_next_bundle_when_bundle_is_full():
    ids = [f"thing-{n}" for n in range(10)]
    reply = interview_reply(
        [item("purpose"), *(item(i, "unknown", "") for i in ids)],
        [question(i) for i in ids],
        ["input-validation"],
    )
    result, _ = run([reply])

    asked = [q["item_id"] for q in result.update["pending_bundle"]["questions"]]
    assert asked == ids
    added = next(
        i for i in result.update["spec_items"] if i["id"] == "input-validation"
    )
    assert added["status"] == "unknown"


@pytest.mark.parametrize(
    ("answers", "status", "content"),
    [
        (
            [{"question_id": "q1", "kind": "option", "option_ids": ["o2"]}],
            "confirmed",
            VALIDATION["question"]["options"][1]["content"],
        ),
        (
            [{"question_id": "q1", "kind": "custom", "text": "빨간 테두리만"}],
            "confirmed",
            "빨간 테두리만",
        ),
        (
            [{"question_id": "q1", "kind": "delegate"}],
            "delegated",
            VALIDATION["default"],
        ),
        ([], "delegated", VALIDATION["default"]),
    ],
)
def test_answer_to_fixed_question_sets_worker_content(
    monkeypatch, answers, status, content
):
    state = answered_state({"action": "submit", "answers": answers}, monkeypatch)
    result, llm = run([], state)

    common = next(
        i for i in result.update["spec_items"] if i["id"] == "input-validation"
    )
    assert (common["status"], common["content"]) == (status, content)
    # 문답 기록에는 사용자가 본 말이 남는다.
    if answers and answers[0]["kind"] == "option":
        assert (
            result.update["qa"][0]["answer"]
            == VALIDATION["question"]["options"][1]["label"]
        )
    assert llm.calls == []


def test_finish_fills_common_item_default(monkeypatch):
    state = answered_state({"action": "finish", "answers": []}, monkeypatch)
    result, _ = run([], state)

    common = next(
        i for i in result.update["spec_items"] if i["id"] == "input-validation"
    )
    assert (common["status"], common["content"]) == ("delegated", VALIDATION["default"])


def test_round_limit_fills_common_item_default():
    state = initial_state("가계부")
    state["spec_items"] = [item("purpose"), item("input-validation", "unknown", "")]
    state["question_round"] = MAX_ROUNDS
    result, _ = run([], state)

    common = next(
        i for i in result.update["spec_items"] if i["id"] == "input-validation"
    )
    assert common["content"] == VALIDATION["default"]


def test_revised_common_item_is_asked_again_with_fixed_question():
    state = initial_state("가계부")
    state["spec_items"] = [item("purpose"), item("input-validation", "unknown", "")]
    state["qa"] = [
        {
            "node": "interview_user",
            "round": 1,
            "item_id": "input-validation",
            "question": VALIDATION["question"]["text"],
            "answer": "입력한 그 자리에서 바로 알려 줘요",
        }
    ]
    result, llm = run([interview_reply()], state)

    [asked] = result.update["pending_bundle"]["questions"]
    assert asked["text"] == VALIDATION["question"]["text"]
    # 코드가 다시 묻는 항목이라 LLM 에게 "고치기로 고른 항목"으로 알리지 않는다.
    assert "## 사용자가 고치기로 고른 항목" not in llm.calls_for("interview_user")[0]
