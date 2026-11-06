from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from specbuilder.graph.build import build_graph
from specbuilder.state import initial_state
from tests.fakes.fake_llm import FakeLLM, files_reply


def test_interview_interrupt_resume_then_generate():
    llm = FakeLLM(['{"question": "누가 쓰나요?"}', '{"question": null}', files_reply()])
    graph = build_graph(llm, InMemorySaver())
    config = {"configurable": {"thread_id": "t1"}}

    first = graph.invoke(initial_state("가계부 만들어줘"), config)
    assert first["__interrupt__"][0].value == "누가 쓰나요?"

    final = graph.invoke(Command(resume="저 혼자요"), config)

    assert final["qa"] == [{"question": "누가 쓰나요?", "answer": "저 혼자요"}]
    assert set(final["artifacts"]) == {"spec.md", "SKILL.md", "AGENTS.md", "CLAUDE.md"}
    # resume 때 질문 생성 LLM 을 다시 부르지 않아야 한다: 질문 1 + 판정 1 + 생성 1
    assert len(llm.calls) == 3
    assert "저 혼자요" in llm.calls[2][1]
