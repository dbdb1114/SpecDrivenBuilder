import pytest
from langgraph.types import Command

from specbuilder.llm import LLMCallError
from specbuilder.nodes.interview_user import MAX_ROUNDS, make_interview_user
from specbuilder.state import initial_state
from specbuilder.state.question_format import assign_ids
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
    assert set(schema["properties"]) == {"items", "questions"}


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
