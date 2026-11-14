"""그래프를 `/api/**` 로 노출하는 FastAPI 앱 — 요청 파싱 → 그래프 호출 → 응답 직렬화만 한다.

개발 서버: `uv run uvicorn specbuilder.api.main:app --reload`
"""

import io
import secrets
import zipfile
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Annotated

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import Response
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command
from pydantic import ValidationError

from specbuilder.api.schemas import RunView, StartRun
from specbuilder.graph.build import build_graph
from specbuilder.llm import ClaudeCLIClient, LLMCallError
from specbuilder.paths import CHECKPOINT_DB
from specbuilder.state import AnswerSubmission, initial_state
from specbuilder.state.question_format import ConfirmReply, validate_submission

# 이 노드의 interrupt 만 확인 화면이고, 나머지(묻는 노드)는 모두 질문 묶음이다.
CONFIRM_NODE = "confirm_spec"


def _config(run_id: str) -> dict:
    return {"configurable": {"thread_id": run_id}}


def _view(graph, run_id: str, error: str | None = None) -> RunView:
    snapshot = graph.get_state(_config(run_id))
    if not snapshot.values:
        raise HTTPException(404, f"없는 실행: {run_id}")
    view = {
        "run_id": run_id,
        "status": "done",
        "bundle": None,
        "confirm": None,
        "artifacts": {},
        "error": error,
    }
    pending = [(task.name, i.value) for task in snapshot.tasks for i in task.interrupts]
    if pending:
        node, value = pending[0]
        if node == CONFIRM_NODE:
            view |= {"status": "confirm", "confirm": value}
        else:
            view |= {"status": "question", "bundle": value}
    elif snapshot.next:
        view["status"] = "stalled"
    else:
        view["artifacts"] = snapshot.values.get("artifacts", {})
    return view


def _run(graph, run_id: str, payload) -> RunView:
    """그래프를 다음 interrupt(또는 끝)까지 돌리고 현재 화면을 돌려준다.

    LLM 실패는 HTTP 오류로 만들지 않는다 — 실행은 체크포인트에 남아 있으므로 run_id 와 함께 stalled 로 돌려줘야
    화면이 "다시 시도" 를 붙일 수 있다.
    """
    try:
        graph.invoke(payload, _config(run_id))
    except LLMCallError as e:
        return _view(graph, run_id, error=str(e))
    return _view(graph, run_id)


def _expect(view: RunView, status: str) -> RunView:
    if view["status"] != status:
        raise HTTPException(
            409, f"지금은 {view['status']} 상태라 이 요청을 받을 수 없음"
        )
    return view


def create_app(graph=None) -> FastAPI:
    """앱을 만든다. graph 를 주지 않으면 개발 SqliteSaver + `claude -p` 클라이언트로 그래프를 연다 (테스트는 fake 그래프를 넣는다)."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if graph is not None:
            app.state.graph = graph
            yield
        else:
            with SqliteSaver.from_conn_string(str(CHECKPOINT_DB)) as checkpointer:
                app.state.graph = build_graph(ClaudeCLIClient(), checkpointer)
                yield

    app = FastAPI(
        title="SpecDrivenBuilder",
        lifespan=lifespan,
        openapi_url="/api/openapi.json",
        docs_url="/api/docs",
        redoc_url=None,
    )

    # 엔드포인트를 async 가 아닌 def 로 둔다 — graph.invoke 는 `claude -p` 를 기다리는 동기 호출이라
    # FastAPI 가 스레드풀에서 돌려야 이벤트 루프가 막히지 않는다.

    @app.post("/api/runs")
    def start_run(body: StartRun, request: Request) -> RunView:
        run_id = f"{datetime.now():%y%m%d-%H%M%S}-web-{secrets.token_hex(3)}"
        return _run(request.app.state.graph, run_id, initial_state(body["request"]))

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str, request: Request) -> RunView:
        return _view(request.app.state.graph, run_id)

    @app.post("/api/runs/{run_id}/answers")
    def submit_answers(
        run_id: str, body: AnswerSubmission, request: Request
    ) -> RunView:
        graph = request.app.state.graph
        view = _expect(_view(graph, run_id), "question")
        try:
            submission = validate_submission(view["bundle"], body)
        except (ValidationError, ValueError) as e:
            raise HTTPException(422, str(e)) from e
        return _run(graph, run_id, Command(resume=submission))

    @app.post("/api/runs/{run_id}/confirm")
    def reply_confirm(
        run_id: str, body: Annotated[ConfirmReply, Body()], request: Request
    ) -> RunView:
        graph = request.app.state.graph
        view = _expect(_view(graph, run_id), "confirm")
        if body["action"] == "revise":
            editable = {i["id"] for i in view["confirm"]["items"] if i["editable"]}
            locked = [i for i in body["item_ids"] if i not in editable]
            if locked:
                raise HTTPException(422, f"고칠 수 없는 항목: {locked}")
        return _run(graph, run_id, Command(resume=body))

    @app.post("/api/runs/{run_id}/retry")
    def retry_run(run_id: str, request: Request) -> RunView:
        graph = request.app.state.graph
        _expect(_view(graph, run_id), "stalled")
        # 입력 None 으로 invoke 하면 마지막 체크포인트에서 멈춘 노드부터 다시 돈다.
        return _run(graph, run_id, None)

    @app.get(
        "/api/runs/{run_id}/artifacts.zip",
        response_class=Response,
        responses={200: {"content": {"application/zip": {}}}},
    )
    def download_artifacts(run_id: str, request: Request) -> Response:
        view = _expect(_view(request.app.state.graph, run_id), "done")
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, content in view["artifacts"].items():
                archive.writestr(name, content)
        return Response(
            buffer.getvalue(),
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{run_id}.zip"'},
        )

    return app


app = create_app()
