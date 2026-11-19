"""백오피스 — 호출 기록을 보고 노드 설정을 고치는 로컬 전용 라우터 (`/api/backoffice/**`, docs/design/backoffice.md).

`SPECBUILDER_BACKOFFICE=1` 일 때만 앱에 붙는다 (`api/main.py`). 호출 기록에는 사용자의 요청과 답이 그대로 들어 있어,
켜져 있어도 이 컴퓨터에서 온 요청만 받는다. 요청 파싱 → `llm/trace` · `node_config` 호출 → 응답 직렬화만 한다.
"""

import os
from typing import get_args

from fastapi import APIRouter, Depends, HTTPException, Request

from specbuilder import node_config
from specbuilder.api.schemas import (
    CallDetail,
    NodeSettingsView,
    RunSummary,
    RunTrace,
)
from specbuilder.llm import trace
from specbuilder.llm.client import DEFAULT_MODEL

BACKOFFICE_ENV = "SPECBUILDER_BACKOFFICE"
_LOCAL_ADDRESSES = {"127.0.0.1", "::1"}
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def enabled() -> bool:
    return os.environ.get(BACKOFFICE_ENV, "") not in ("", "0")


def _local_only(request: Request) -> None:
    # 보내는 쪽 주소만 보면, 다른 사이트가 자기 도메인을 127.0.0.1 로 돌려(DNS rebinding) 이 컴퓨터의 브라우저로 읽어 갈 수 있다.
    # 그래서 브라우저가 붙이는 Host 도 이 컴퓨터 이름이어야 한다.
    address = request.client.host if request.client else ""
    if address not in _LOCAL_ADDRESSES or request.url.hostname not in _LOCAL_HOSTS:
        raise HTTPException(403, "백오피스는 이 컴퓨터에서만 열 수 있음")


router = APIRouter(
    prefix="/api/backoffice",
    tags=["backoffice"],
    dependencies=[Depends(_local_only)],
)


def _calls(run_id: str) -> list[dict]:
    path = trace.run_path(run_id)
    if path is None:
        raise HTTPException(404, f"없는 기록: {run_id}")
    return trace.load(path)


@router.get("/traces")
def list_traces() -> list[RunSummary]:
    return trace.runs()


@router.get("/traces/{run_id}")
def get_trace(run_id: str) -> RunTrace:
    rows = [trace.row(n, c) for n, c in enumerate(_calls(run_id), 1)]
    return {"run_id": run_id, "rows": rows, "totals": trace.totals(rows)}


@router.get("/traces/{run_id}/calls/{n}")
def get_call(run_id: str, n: int) -> CallDetail:
    calls = _calls(run_id)
    if not 1 <= n <= len(calls):
        raise HTTPException(404, f"호출 번호는 1~{len(calls)}")
    call = calls[n - 1]
    return trace.row(n, call) | {
        "system": call.get("system", ""),
        "prompt": call.get("prompt", ""),
        "response": call.get("response"),
    }


def _node_view(settings: dict, error: str | None = None) -> NodeSettingsView:
    return {
        "nodes": [
            {"node": node} | settings.get(node, node_config.DEFAULT)
            for node in node_config.LLM_NODES
        ],
        "efforts": list(get_args(node_config.Effort)),
        # llm/client.py 가 model 이 null 일 때 쓰는 값과 같은 규칙.
        "default_model": os.environ.get("SPECBUILDER_MODEL", DEFAULT_MODEL),
        "known_models": list(trace.PRICES),
        "error": error,
    }


@router.get("/nodes")
def get_nodes() -> NodeSettingsView:
    try:
        return _node_view(node_config.load())
    except ValueError as e:
        return _node_view({}, str(e))


@router.put("/nodes")
def put_nodes(body: dict[str, node_config.NodeSetting]) -> NodeSettingsView:
    # 쓰는 곳은 config/nodes.json 하나다 — 경로는 요청에서 받지 않는다.
    try:
        return _node_view(node_config.save(body))
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
