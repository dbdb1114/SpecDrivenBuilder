from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from specbuilder.graph.build import build_graph
from specbuilder.state import initial_state
from tests.fakes.fake_llm import FakeLLM, interview_reply, item, question


def test_full_graph_bundle_interrupt_resume_then_generate():
    llm = FakeLLM(
        {
            "interview_user": [
                interview_reply(
                    [item("input-data", "unknown", "")],
                    [question("purpose"), question("input-data")],
                ),
                interview_reply(
                    [item("input-data", "delegated", "카드·현금 모두")], []
                ),
            ]
        }
    )
    graph = build_graph(llm, InMemorySaver())
    config = {"configurable": {"thread_id": "t1"}}

    first = graph.invoke(initial_state("가계부 만들어줘"), config)
    bundle = first["__interrupt__"][0].value
    assert [q["item_id"] for q in bundle["questions"]] == ["purpose", "input-data"]

    final = graph.invoke(
        Command(
            resume={
                "action": "submit",
                "answers": [
                    {"question_id": "q1", "kind": "custom", "text": "저 혼자요"},
                    {"question_id": "q2", "kind": "delegate"},
                ],
            }
        ),
        config,
    )

    assert set(final["artifacts"]) == {"spec.md", "SKILL.md", "AGENTS.md", "CLAUDE.md"}
    assert final["interview_stops"] == [
        {"node": "interview_user", "reason": "resolved", "rounds": 1}
    ]
    by_id = {i["id"]: i for i in final["spec_items"]}
    assert by_id["purpose"]["content"] == "저 혼자요"
    assert by_id["input-data"] == {
        **by_id["input-data"],
        "status": "delegated",
        "content": "카드·현금 모두",
    }
    # resume 때 질문 생성 LLM 을 다시 부르지 않아야 한다: 묶음 1 + 마지막 답 반영 1
    assert len(llm.calls_for("interview_user")) == 2
    assert "저 혼자요" in llm.calls_for("generate_artifacts")[0]
    assert [n for n, _, _ in llm.calls] == [
        "interview_user",
        "interview_user",
        "interview_design",
        "select_stack",
        "generate_artifacts",
    ]


def test_graph_runs_end_to_end_on_node_defaults():
    llm = FakeLLM()
    final = build_graph(llm, InMemorySaver()).invoke(
        initial_state("가계부"), {"configurable": {"thread_id": "t2"}}
    )

    assert "CLAUDE.md" in final["artifacts"]
    assert final["interview_stops"][0]["reason"] == "resolved"
