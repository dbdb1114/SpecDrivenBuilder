import pytest
from langgraph.types import Command

from specbuilder.llm import LLMCallError
from specbuilder.nodes.interview_user import MAX_QUESTIONS, make_interview_user
from specbuilder.state import initial_state
from tests.fakes.fake_llm import FakeLLM


def test_stores_question_before_interrupt():
    llm = FakeLLM(['{"question": "누가 쓰나요?"}'])
    result = make_interview_user(llm)(initial_state("가계부 만들어줘"))

    assert result == Command(
        update={"pending_question": "누가 쓰나요?"}, goto="interview_user"
    )
    assert "가계부 만들어줘" in llm.calls[0][1]


def test_goes_to_generate_when_llm_says_enough():
    llm = FakeLLM(['설명 ```json\n{"question": null}\n```'])
    result = make_interview_user(llm)(initial_state("가계부"))

    assert result == Command(goto="generate_artifacts")


def test_stops_asking_at_max_without_llm_call():
    llm = FakeLLM([])
    state = initial_state("가계부")
    state["qa"] = [{"question": f"q{i}", "answer": "a"} for i in range(MAX_QUESTIONS)]

    assert make_interview_user(llm)(state) == Command(goto="generate_artifacts")
    assert llm.calls == []


def test_rejects_non_json_reply():
    with pytest.raises(LLMCallError):
        make_interview_user(FakeLLM(["질문 없음"]))(initial_state("가계부"))
