from langgraph.types import Command

from specbuilder.nodes.interview_design import make_interview_design
from specbuilder.state import initial_state
from tests.fakes.fake_llm import FakeLLM


def test_empty_node_passes_through_without_llm():
    llm = FakeLLM()
    assert make_interview_design(llm)(initial_state("가계부")) == Command(
        goto="select_stack"
    )
    assert llm.calls == []
