from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from specbuilder.llm import LLMClient
from specbuilder.nodes.generate_artifacts import make_generate_artifacts
from specbuilder.nodes.interview_user import make_interview_user
from specbuilder.state import State


def build_graph(llm: LLMClient, checkpointer: BaseCheckpointSaver):
    """interview_user → generate_artifacts 그래프를 컴파일한다. interrupt 때문에 checkpointer 는 필수."""
    builder = StateGraph(State)
    # interview_user 는 Command(goto=...) 로 직접 이동하므로 나가는 엣지 대신 destinations 로 그래프에 알린다.
    builder.add_node(
        "interview_user",
        make_interview_user(llm),
        destinations=("interview_user", "generate_artifacts"),
    )
    builder.add_node("generate_artifacts", make_generate_artifacts(llm))
    builder.add_edge(START, "interview_user")
    builder.add_edge("generate_artifacts", END)
    return builder.compile(checkpointer=checkpointer)
