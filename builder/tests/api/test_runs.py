import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from specbuilder.api.main import create_app
from specbuilder.graph.build import build_graph
from specbuilder.llm import LLMCallError
from specbuilder.state import State
from tests.fakes.fake_llm import FakeLLM, interview_reply, item, question

TWO_QUESTIONS = interview_reply(
    [item("input-data", "unknown", "")],
    [question("purpose"), question("input-data", ("카드", "현금", "계좌"), True)],
)
RESOLVED = interview_reply([item("input-data", "delegated", "카드·현금 모두")])

# question-format.md "확인 화면" 예시 그대로 — confirm_spec(D) 이 아직 빈 노드라 고정 데이터로 검증한다.
CONFIRM_SCREEN = {
    "items": [
        {
            "id": "who-uses",
            "area": "function",
            "name": "누가 쓰는가",
            "status": "confirmed",
            "content": "저 혼자 써요",
            "editable": True,
        },
        {
            "id": "framework",
            "area": "tech",
            "name": "만드는 방식",
            "status": "confirmed",
            "content": "내 컴퓨터에서만 도는 프로그램 — 혼자 쓰고 인터넷이 필요 없어서",
            "editable": False,
        },
    ]
}


class FlakyLLM(FakeLLM):
    """처음 n 번은 실패하고 그다음부터 FakeLLM 처럼 답한다."""

    def __init__(self, failures: int, replies=None):
        super().__init__(replies)
        self.failures = failures

    def complete(self, system, prompt, schema=None):
        if self.failures:
            self.failures -= 1
            raise LLMCallError("claude -p 시간 초과")
        return super().complete(system, prompt, schema)


def client_for(graph) -> TestClient:
    return TestClient(create_app(graph))


def full_graph(llm) -> object:
    return build_graph(llm, InMemorySaver())


def confirm_graph():
    """confirm_spec 이름으로 확인 화면을 interrupt 하는 작은 그래프. 받은 답을 산출물에 적는다."""

    def confirm_spec(state: State) -> dict:
        reply = interrupt(CONFIRM_SCREEN)
        return {"artifacts": {"reply.json": json.dumps(reply, ensure_ascii=False)}}

    builder = StateGraph(State)
    builder.add_node("confirm_spec", confirm_spec)
    builder.add_edge(START, "confirm_spec")
    builder.add_edge("confirm_spec", END)
    return builder.compile(checkpointer=InMemorySaver())


@pytest.fixture
def two_questions():
    llm = FakeLLM({"interview_user": [TWO_QUESTIONS, RESOLVED]})
    with client_for(full_graph(llm)) as client:
        yield client, llm


def test_start_returns_question_bundle(two_questions):
    client, _ = two_questions
    view = client.post("/api/runs", json={"request": "가계부 만들어줘"}).json()

    assert view["status"] == "question"
    assert [q["item_id"] for q in view["bundle"]["questions"]] == [
        "purpose",
        "input-data",
    ]
    assert view["confirm"] is None and view["error"] is None
    assert client.get(f"/api/runs/{view['run_id']}").json() == view


def test_submit_answers_then_download_artifacts(two_questions):
    client, llm = two_questions
    run_id = client.post("/api/runs", json={"request": "가계부"}).json()["run_id"]

    view = client.post(
        f"/api/runs/{run_id}/answers",
        json={
            "action": "submit",
            "answers": [
                {"question_id": "q1", "kind": "custom", "text": "저 혼자요"},
                {"question_id": "q2", "kind": "option", "option_ids": ["o1", "o3"]},
            ],
        },
    ).json()

    assert view["status"] == "done"
    assert set(view["artifacts"]) == {
        "spec.md",
        "AGENTS.md",
        "CLAUDE.md",
        ".claude/skills/build-ledger/SKILL.md",
        ".agents/skills/build-ledger/SKILL.md",
    }
    assert "저 혼자요" in llm.calls_for("generate_artifacts")[0]

    response = client.get(f"/api/runs/{run_id}/artifacts.zip")
    assert response.headers["content-type"] == "application/zip"
    archive = zipfile.ZipFile(io.BytesIO(response.content))
    assert archive.read("CLAUDE.md").decode() == view["artifacts"]["CLAUDE.md"]


def test_finish_skips_remaining_questions(two_questions):
    client, llm = two_questions
    run_id = client.post("/api/runs", json={"request": "가계부"}).json()["run_id"]

    view = client.post(
        f"/api/runs/{run_id}/answers", json={"action": "finish", "answers": []}
    ).json()

    assert view["status"] == "done"
    assert len(llm.calls_for("interview_user")) == 1


@pytest.mark.parametrize(
    "answers",
    [
        [{"question_id": "q9", "kind": "delegate"}],
        [{"question_id": "q1", "kind": "option", "option_ids": ["o1", "o2"]}],
        [{"question_id": "q1", "kind": "maybe"}],
    ],
    ids=["unknown-question", "multiple-on-single", "bad-kind"],
)
def test_bad_answers_are_rejected_and_run_stays_answerable(two_questions, answers):
    client, _ = two_questions
    run_id = client.post("/api/runs", json={"request": "가계부"}).json()["run_id"]

    bad = client.post(
        f"/api/runs/{run_id}/answers", json={"action": "submit", "answers": answers}
    )
    assert bad.status_code == 422

    assert client.get(f"/api/runs/{run_id}").json()["status"] == "question"
    good = client.post(
        f"/api/runs/{run_id}/answers", json={"action": "submit", "answers": []}
    )
    assert good.json()["status"] == "done"


def test_unknown_run_is_404(two_questions):
    client, _ = two_questions
    assert client.get("/api/runs/nope").status_code == 404
    assert client.get("/api/runs/nope/artifacts.zip").status_code == 404


def test_request_for_other_screen_is_409(two_questions):
    client, _ = two_questions
    run_id = client.post("/api/runs", json={"request": "가계부"}).json()["run_id"]

    assert (
        client.post(
            f"/api/runs/{run_id}/confirm", json={"action": "confirm"}
        ).status_code
        == 409
    )
    assert client.post(f"/api/runs/{run_id}/retry").status_code == 409
    assert client.get(f"/api/runs/{run_id}/artifacts.zip").status_code == 409


def test_empty_request_is_422(two_questions):
    client, _ = two_questions
    assert client.post("/api/runs", json={"request": "  "}).status_code == 422


def test_llm_failure_stalls_then_retry_continues():
    with client_for(
        full_graph(FlakyLLM(1, {"interview_user": [TWO_QUESTIONS]}))
    ) as client:
        view = client.post("/api/runs", json={"request": "가계부"}).json()

        assert view["status"] == "stalled"
        assert "시간 초과" in view["error"]
        assert client.get(f"/api/runs/{view['run_id']}").json()["error"] is None

        view = client.post(f"/api/runs/{view['run_id']}/retry").json()
        assert view["status"] == "question"


def test_confirm_screen_confirm():
    with client_for(confirm_graph()) as client:
        view = client.post("/api/runs", json={"request": "가계부"}).json()
        assert view["status"] == "confirm"
        assert view["confirm"] == CONFIRM_SCREEN

        view = client.post(
            f"/api/runs/{view['run_id']}/confirm", json={"action": "confirm"}
        ).json()
        assert view["status"] == "done"
        assert json.loads(view["artifacts"]["reply.json"]) == {"action": "confirm"}


def test_confirm_screen_revise_only_editable_items():
    with client_for(confirm_graph()) as client:
        run_id = client.post("/api/runs", json={"request": "가계부"}).json()["run_id"]
        url = f"/api/runs/{run_id}/confirm"

        assert (
            client.post(
                url, json={"action": "revise", "item_ids": ["framework"]}
            ).status_code
            == 422
        )
        assert (
            client.post(url, json={"action": "revise", "item_ids": []}).status_code
            == 422
        )

        view = client.post(
            url, json={"action": "revise", "item_ids": ["who-uses"]}
        ).json()
        assert json.loads(view["artifacts"]["reply.json"]) == {
            "action": "revise",
            "item_ids": ["who-uses"],
        }


def test_openapi_exposes_spec_models():
    with client_for(confirm_graph()) as client:
        schemas = client.get("/api/openapi.json").json()["components"]["schemas"]
    assert {
        "RunView",
        "QuestionBundle",
        "AnswerSubmission",
        "ConfirmScreen",
        "ConfirmAction",
        "ReviseAction",
    } <= set(schemas)
