import json

import pytest
from fastapi.testclient import TestClient

from specbuilder.api import backoffice
from specbuilder.api.main import create_app
from specbuilder.llm import trace

RUN = "261117-191318-web-44837e"
CALLS = [
    {
        "at": "2026-11-17T19:13:24",
        "node": "interview_user",
        "model": "claude-sonnet-5-5",
        "effort": None,
        "response": "응답 1",
        "seconds": 6.1,
        "usage": {"input": 1000, "output": 100, "cache_write": 0, "cache_read": 0},
        "system": "시스템",
        "prompt": "운동 기록 앱을 만들고 싶어요",
    },
    {
        "at": "2026-11-17T19:13:52",
        "node": "select_stack",
        "model": "claude-sonnet-5-5",
        "effort": "low",
        "error": "시간 초과",
        "seconds": 2.0,
        "usage": None,
        "system": "시스템",
        "prompt": "입력 2",
    },
]


def write_trace(directory, run_id, calls):
    lines = [json.dumps(c, ensure_ascii=False) for c in calls]
    (directory / f"{run_id}.jsonl").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


@pytest.fixture
def traces(tmp_path, monkeypatch):
    directory = tmp_path / "_traces"
    directory.mkdir()
    monkeypatch.setenv(trace.TRACE_DIR_ENV, str(directory))
    write_trace(directory, RUN, CALLS)
    return directory


def local_client(**kwargs):
    return TestClient(
        create_app(graph=object()),
        base_url="http://localhost:8000",
        client=("127.0.0.1", 50000),
        **kwargs,
    )


@pytest.fixture
def client(monkeypatch, traces):
    monkeypatch.setenv(backoffice.BACKOFFICE_ENV, "1")
    return local_client()


PATHS = [
    "/api/backoffice/traces",
    f"/api/backoffice/traces/{RUN}",
    f"/api/backoffice/traces/{RUN}/calls/1",
    "/api/backoffice/nodes",
]


@pytest.mark.parametrize("value", [None, "", "0"])
def test_backoffice_is_not_registered_unless_enabled(monkeypatch, traces, value):
    """호출 기록에는 사용자의 요청과 답이 그대로 있다 — 켜지 않으면 어떤 주소로도 읽히지 않는다."""
    if value is None:
        monkeypatch.delenv(backoffice.BACKOFFICE_ENV, raising=False)
    else:
        monkeypatch.setenv(backoffice.BACKOFFICE_ENV, value)
    client = local_client()

    for path in PATHS:
        response = client.get(path)
        assert response.status_code == 404, path
        assert "운동 기록" not in response.text
    assert client.put("/api/backoffice/nodes", json={}).status_code in (404, 405)
    paths = client.get("/api/openapi.json").json()["paths"]
    assert not [p for p in paths if "backoffice" in p]


@pytest.mark.parametrize(
    ("base_url", "address"),
    [
        ("http://localhost:8000", "192.168.0.7"),  # 다른 컴퓨터
        (
            "http://evil.example:8000",
            "127.0.0.1",
        ),  # 이 컴퓨터를 가리키게 한 남의 도메인
        (
            "http://192.168.0.3:5173",
            "127.0.0.1",
        ),  # 개발 서버를 네트워크에 열고 프록시로 들어온 요청
    ],
)
def test_only_requests_from_this_computer_are_served(
    monkeypatch, traces, base_url, address
):
    monkeypatch.setenv(backoffice.BACKOFFICE_ENV, "1")
    client = TestClient(
        create_app(graph=object()), base_url=base_url, client=(address, 50000)
    )

    for path in PATHS:
        response = client.get(path)
        assert response.status_code == 403, path
        assert "운동 기록" not in response.text


def test_ipv6_loopback_is_local(monkeypatch, traces):
    monkeypatch.setenv(backoffice.BACKOFFICE_ENV, "1")
    client = TestClient(
        create_app(graph=object()), base_url="http://[::1]:8000", client=("::1", 50000)
    )

    assert client.get("/api/backoffice/traces").status_code == 200


def test_run_list_has_totals_and_cost(client, traces):
    write_trace(
        traces, "261118-090000-web-aaaaaa", [CALLS[0] | {"at": "2026-11-18T09:00:00"}]
    )

    runs = client.get("/api/backoffice/traces").json()

    assert [r["run_id"] for r in runs] == ["261118-090000-web-aaaaaa", RUN]
    assert runs[1] == {
        "run_id": RUN,
        "started_at": "2026-11-17T19:13:24",
        "calls": 2,
        "usage": {"input": 1000, "output": 100, "cache_write": 0, "cache_read": 0},
        "seconds": 8.1,
        # 실패한 호출은 사용량이 없어 값을 모른다 — 터미널 표(show_trace)처럼 합계도 모름으로 둔다.
        "dollars": None,
    }
    # 비용은 trace.cost 의 가격표로 계산한다.
    assert runs[0]["dollars"] == pytest.approx(
        trace.cost("claude-sonnet-5-5", CALLS[0]["usage"])
    )


def test_unknown_model_makes_total_cost_unknown(client, traces):
    write_trace(traces, RUN, [CALLS[0], CALLS[0] | {"model": "claude-haiku-5-5"}])

    body = client.get(f"/api/backoffice/traces/{RUN}").json()

    assert body["rows"][1]["dollars"] is None
    assert body["totals"]["dollars"] is None


def test_run_rows_leave_out_full_text(client):
    body = client.get(f"/api/backoffice/traces/{RUN}").json()

    assert [r["node"] for r in body["rows"]] == ["interview_user", "select_stack"]
    assert body["rows"][1] == {
        "n": 2,
        "at": "2026-11-17T19:13:52",
        "node": "select_stack",
        "model": "claude-sonnet-5-5",
        "effort": "low",
        "usage": {"input": 0, "output": 0, "cache_write": 0, "cache_read": 0},
        "seconds": 2.0,
        "dollars": None,
        "error": "시간 초과",
    }
    assert "운동 기록" not in json.dumps(body, ensure_ascii=False)


def test_call_detail_has_full_text(client):
    body = client.get(f"/api/backoffice/traces/{RUN}/calls/1").json()

    assert body["prompt"] == "운동 기록 앱을 만들고 싶어요"
    assert body["system"] == "시스템"
    assert body["response"] == "응답 1"
    assert body["n"] == 1


@pytest.mark.parametrize("n", [0, 3])
def test_call_number_out_of_range(client, n):
    assert client.get(f"/api/backoffice/traces/{RUN}/calls/{n}").status_code == 404


@pytest.mark.parametrize(
    "run_id", ["nope", "..%2F..%2Fsecret", "a.b", "%2Fetc%2Fpasswd"]
)
def test_unknown_or_unsafe_run_id_is_404(client, tmp_path, run_id):
    (tmp_path / "secret.jsonl").write_text(json.dumps(CALLS[0]), encoding="utf-8")

    assert client.get(f"/api/backoffice/traces/{run_id}").status_code == 404


def test_node_settings_view(client, node_config_file, monkeypatch):
    monkeypatch.setenv("SPECBUILDER_MODEL", "claude-opus-5-5")
    node_config_file.write_text(
        json.dumps({"select_stack": {"model": "claude-haiku-5-5", "effort": "low"}}),
        encoding="utf-8",
    )

    body = client.get("/api/backoffice/nodes").json()

    assert body["nodes"][2] == {
        "node": "select_stack",
        "model": "claude-haiku-5-5",
        "effort": "low",
    }
    assert body["nodes"][0] == {"node": "interview_user", "model": None, "effort": None}
    assert len(body["nodes"]) == 5
    assert body["efforts"] == ["low", "medium", "high", "xhigh", "max"]
    assert body["default_model"] == "claude-opus-5-5"
    assert body["known_models"] == list(trace.PRICES)
    assert body["error"] is None


def test_broken_settings_file_is_shown_not_raised(client, node_config_file):
    node_config_file.write_text("{", encoding="utf-8")

    body = client.get("/api/backoffice/nodes").json()

    assert "형식이 맞지 않음" in body["error"]


def test_save_node_settings(client, node_config_file):
    settings = {"select_stack": {"model": "claude-haiku-5-5", "effort": "low"}}

    response = client.put("/api/backoffice/nodes", json=settings)

    assert response.status_code == 200
    assert response.json()["nodes"][2]["model"] == "claude-haiku-5-5"
    assert json.loads(node_config_file.read_text(encoding="utf-8")) == settings


@pytest.mark.parametrize(
    "settings",
    [
        {"select_stak": {"model": None, "effort": None}},
        {"select_stack": {"model": "", "effort": None}},
        {"select_stack": {"model": None, "effort": "extreme"}},
    ],
)
def test_bad_settings_are_not_saved(client, node_config_file, settings):
    node_config_file.write_text("{}", encoding="utf-8")

    response = client.put("/api/backoffice/nodes", json=settings)

    assert response.status_code == 422
    assert node_config_file.read_text(encoding="utf-8") == "{}"


def test_save_writes_only_the_config_file(client, node_config_file, tmp_path):
    """요청에 경로를 실어도 쓰는 곳은 config/nodes.json 하나다."""
    before = {p for p in tmp_path.rglob("*")}

    client.put(
        "/api/backoffice/nodes?path=../../x.json",
        json={"select_stack": {"model": None, "effort": None}},
    )

    assert {p for p in tmp_path.rglob("*")} - before == {node_config_file}
