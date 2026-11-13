from langgraph.types import Command

from specbuilder.nodes.confirm_spec import confirm_spec
from specbuilder.state import initial_state


def test_empty_node_passes_through():
    assert confirm_spec(initial_state("가계부")) == Command(goto="generate_artifacts")
