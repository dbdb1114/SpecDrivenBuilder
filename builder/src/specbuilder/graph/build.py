from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from specbuilder.llm import LLMClient
from specbuilder.nodes.confirm_spec import confirm_spec
from specbuilder.nodes.generate_artifacts import make_generate_artifacts
from specbuilder.nodes.interview_design import make_interview_design
from specbuilder.nodes.interview_profile import make_interview_profile
from specbuilder.nodes.interview_user import make_interview_user
from specbuilder.nodes.select_skills import make_select_skills
from specbuilder.nodes.select_stack import make_select_stack
from specbuilder.nodes.verify_stack import make_verify_stack
from specbuilder.state import State


def build_graph(llm: LLMClient, checkpointer: BaseCheckpointSaver):
    """8노드 그래프를 컴파일한다 (docs/design/design.md "그래프"). interrupt 때문에 checkpointer 는 필수."""
    builder = StateGraph(State)
    # 모든 노드가 Command(goto=...) 로 직접 이동한다. 갈 수 있는 곳(돌아가는 경로 포함)을 지금 전부 선언해 두면
    # 각 작업 단위는 자기 노드 파일의 goto 만 바꾸면 된다 — 이 파일을 고치지 않는다.
    builder.add_node(
        "interview_profile",
        make_interview_profile(llm),
        destinations=("interview_profile", "interview_user"),
    )
    builder.add_node(
        "interview_user",
        make_interview_user(llm),
        destinations=("interview_user", "interview_design"),
    )
    builder.add_node(
        "interview_design",
        make_interview_design(llm),
        destinations=("interview_design", "select_stack"),
    )
    # 돌아가는 경로 1: 부족한 정보가 있으면 interview_user 로
    builder.add_node(
        "select_stack",
        make_select_stack(llm),
        destinations=("verify_stack", "interview_user"),
    )
    # 돌아가는 경로 2: 버전이 맞지 않으면 select_stack 으로
    builder.add_node(
        "verify_stack",
        make_verify_stack(llm),
        destinations=("select_skills", "select_stack"),
    )
    builder.add_node(
        "select_skills", make_select_skills(llm), destinations=("confirm_spec",)
    )
    # 돌아가는 경로 3: 사용자가 고칠 항목을 고르면 interview_user 로
    builder.add_node(
        "confirm_spec",
        confirm_spec,
        destinations=("generate_artifacts", "interview_user"),
    )
    builder.add_node("generate_artifacts", make_generate_artifacts(llm))
    builder.add_edge(START, "interview_profile")
    builder.add_edge("generate_artifacts", END)
    return builder.compile(checkpointer=checkpointer)
