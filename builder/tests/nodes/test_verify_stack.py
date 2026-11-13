from langgraph.types import Command

from specbuilder.nodes.verify_stack import make_verify_stack
from specbuilder.state import initial_state
from tests.fakes.fake_llm import FakeLLM


def test_empty_node_passes_through_without_llm():
    llm = FakeLLM()
    assert make_verify_stack(llm)(initial_state("가계부")) == Command(
        goto="select_skills"
    )
    assert llm.calls == []
