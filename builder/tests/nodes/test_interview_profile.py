from langgraph.types import Command

from specbuilder.nodes.interview_profile import make_interview_profile
from specbuilder.state import initial_state
from tests.fakes.fake_llm import FakeLLM


def test_empty_node_passes_through_without_llm():
    llm = FakeLLM()
    assert make_interview_profile(llm)(initial_state("가계부")) == Command(
        goto="interview_user"
    )
    assert llm.calls == []
