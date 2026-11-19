import json

import pytest

from specbuilder.llm import LLMCallError, for_node, show_trace, trace


class StubLLM:
    model = "claude-sonnet-5-5"

    def __init__(self, error=None):
        self._error = error

    def complete(self, system, prompt, schema=None):
        if self._error:
            raise self._error
        return "응답"


@pytest.fixture
def traces(monkeypatch, tmp_path):
    monkeypatch.setenv(trace.TRACE_ENV, "1")
    monkeypatch.setenv(trace.TRACE_DIR_ENV, str(tmp_path))
    return tmp_path


def test_nothing_is_written_unless_enabled(monkeypatch, tmp_path):
    """프롬프트에는 사용자의 요청과 답이 들어 있다 — 켜지 않으면 디스크에 남기지 않는다."""
    monkeypatch.delenv(trace.TRACE_ENV, raising=False)
    monkeypatch.setenv(trace.TRACE_DIR_ENV, str(tmp_path))

    for_node(StubLLM(), "select_stack").complete("시스템", "입력")

    assert list(tmp_path.glob("*.jsonl")) == []


def test_each_call_is_recorded_with_prompts(traces):
    llm = for_node(StubLLM(), "select_stack")

    llm.complete("시스템", "입력 1")
    llm.complete("시스템", "입력 2")

    # 그래프 밖에서 부르면 실행 이름이 없다.
    calls = trace.load(traces / "no-run.jsonl")
    assert [c["prompt"] for c in calls] == ["입력 1", "입력 2"]
    assert calls[0] | {"at": "", "seconds": 0} == {
        "at": "",
        "node": "select_stack",
        "model": "claude-sonnet-5-5",
        "effort": None,
        "response": "응답",
        "seconds": 0,
        "usage": None,
        "system": "시스템",
        "prompt": "입력 1",
    }


def test_failed_call_is_recorded_and_still_raises(traces):
    llm = for_node(StubLLM(error=LLMCallError("끊김")), "select_skills")

    with pytest.raises(LLMCallError):
        llm.complete("시스템", "입력")

    (call,) = trace.load(traces / "no-run.jsonl")
    assert call["error"] == "끊김"
    assert "response" not in call


def test_cost_and_summary():
    usage = {"input": 1000, "output": 2000, "cache_write": 4000, "cache_read": 8000}
    # (1000×2 + 2000×10 + 4000×2.5 + 8000×0.1) / 1e6
    assert trace.cost("claude-sonnet-5-5", usage) == pytest.approx(0.0328)
    assert trace.cost("모르는-모델", usage) is None

    calls = [
        {
            "node": "interview_user",
            "model": "claude-sonnet-5-5",
            "usage": usage,
            "seconds": 3.0,
        },
        {
            "node": "select_stack",
            "model": "claude-sonnet-5-5",
            "usage": None,
            "seconds": 1.0,
            "error": "끊김",
        },
    ]
    table = trace.summarize(calls).splitlines()

    assert "interview_user" in table[1] and "0.0328" in table[1]
    assert "실패" in table[2]
    assert "합계" in table[3] and "4.0" in table[3]


def test_cli_shows_latest_run_and_one_call(traces, monkeypatch, capsys):
    line = {
        "node": "interview_user",
        "model": "m",
        "system": "시스템 글",
        "prompt": "입력 글",
        "response": "응답 글",
    }
    (traces / "run-a.jsonl").write_text(
        json.dumps(line, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    monkeypatch.setattr("sys.argv", ["trace"])
    show_trace.main()
    assert "run-a.jsonl" in capsys.readouterr().out

    monkeypatch.setattr("sys.argv", ["trace", "run-a", "--show", "1"])
    show_trace.main()
    out = capsys.readouterr().out
    assert "시스템 글" in out and "입력 글" in out and "응답 글" in out


@pytest.mark.parametrize(
    "run_id", ["../secret", "/etc/passwd", "a/b", "secret.jsonl", ""]
)
def test_run_path_stays_inside_trace_dir(traces, run_id):
    """백오피스 화면이 보낸 실행 이름을 경로로 쓰기 전에 모양부터 본다 — 기록 폴더 밖을 읽지 못한다."""
    (traces.parent / "secret.jsonl").write_text("{}", encoding="utf-8")

    assert trace.run_path(run_id) is None


def test_run_path_finds_existing_run(traces):
    (traces / "261117-1-web-a").write_text("", encoding="utf-8")
    (traces / "261117-1-web-a.jsonl").write_text("", encoding="utf-8")

    assert trace.run_path("261117-1-web-a") == traces / "261117-1-web-a.jsonl"
    assert trace.run_path("261117-2-web-b") is None
