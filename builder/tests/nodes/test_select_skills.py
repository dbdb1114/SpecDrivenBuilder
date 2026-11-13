from langgraph.types import Command

from specbuilder.nodes.select_skills import make_select_skills
from specbuilder.state import initial_state
from tests.fakes.fake_llm import FakeLLM


def test_empty_node_passes_through_without_llm():
    llm = FakeLLM()
    assert make_select_skills(llm)(initial_state("가계부")) == Command(
        goto="confirm_spec"
    )
    assert llm.calls == []
