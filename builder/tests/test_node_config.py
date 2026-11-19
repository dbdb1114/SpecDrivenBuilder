import json

import pytest

from specbuilder import node_config
from specbuilder.llm import AnthropicAPIClient, LLMCallError, for_node, trace
from tests.llm.test_client import FakeAnthropic, message


def write(path, settings):
    path.write_text(json.dumps(settings), encoding="utf-8")


def test_missing_file_means_defaults(node_config_file):
    assert node_config.load() == {}
    assert node_config.setting("select_stack") == {"model": None, "effort": None}


def test_repo_config_file_is_valid_and_lists_every_llm_node(monkeypatch):
    """레포에 든 파일은 고칠 수 있는 노드를 전부 보여 주고, 기본은 아무것도 덮어쓰지 않는다."""
    monkeypatch.setattr(
        node_config, "CONFIG_FILE", node_config.BUILDER_ROOT / "config" / "nodes.json"
    )

    settings = node_config.load()

    assert set(settings) == set(node_config.LLM_NODES)


@pytest.mark.parametrize(
    "settings",
    [
        {"select_stak": {"model": None, "effort": None}},
        {"select_stack": {"model": "", "effort": None}},
        {"select_stack": {"model": None, "effort": "extreme"}},
        {"select_stack": {"model": None}},
    ],
)
def test_bad_config_is_rejected(node_config_file, settings):
    write(node_config_file, settings)
    with pytest.raises(ValueError):
        node_config.load()


def test_node_model_and_effort_override_defaults_only_for_that_node(node_config_file):
    write(
        node_config_file,
        {"select_skills": {"model": "claude-haiku-5-5", "effort": "low"}},
    )
    fake = FakeAnthropic(message())
    client = AnthropicAPIClient(model="claude-sonnet-5-5", client=fake)

    for_node(client, "select_skills").complete("시스템", "입력")
    for_node(client, "select_stack").complete("시스템", "입력")

    skills, stack = fake.requests
    assert (skills["model"], skills["output_config"]["effort"]) == (
        "claude-haiku-5-5",
        "low",
    )
    assert (stack["model"], stack["output_config"]["effort"]) == (
        "claude-sonnet-5-5",
        "medium",
    )


def test_config_change_applies_to_the_next_call_without_restart(node_config_file):
    fake = FakeAnthropic(message())
    llm = for_node(
        AnthropicAPIClient(model="claude-sonnet-5-5", client=fake), "select_stack"
    )

    llm.complete("시스템", "입력")
    write(
        node_config_file, {"select_stack": {"model": "claude-opus-5-5", "effort": None}}
    )
    llm.complete("시스템", "입력")

    assert [r["model"] for r in fake.requests] == [
        "claude-sonnet-5-5",
        "claude-opus-5-5",
    ]


def test_bad_config_stops_the_call_instead_of_running_on_defaults(node_config_file):
    """설정이 틀렸는데 기본값으로 돌면 다른 모델로 돈 것을 모르고 결과를 믿게 된다."""
    node_config_file.write_text("{", encoding="utf-8")
    fake = FakeAnthropic(message())

    with pytest.raises(LLMCallError, match="nodes.json"):
        for_node(AnthropicAPIClient(client=fake), "select_stack").complete(
            "시스템", "입력"
        )

    assert fake.requests == []


def test_trace_records_the_model_and_effort_actually_used(
    node_config_file, monkeypatch, tmp_path
):
    monkeypatch.setenv(trace.TRACE_ENV, "1")
    monkeypatch.setenv(trace.TRACE_DIR_ENV, str(tmp_path / "traces"))
    write(
        node_config_file,
        {"select_skills": {"model": "claude-haiku-5-5", "effort": "low"}},
    )
    client = AnthropicAPIClient(
        model="claude-sonnet-5-5", client=FakeAnthropic(message())
    )

    for_node(client, "select_skills").complete("시스템", "입력")

    (call,) = trace.load(tmp_path / "traces" / "no-run.jsonl")
    assert (call["model"], call["effort"]) == ("claude-haiku-5-5", "low")


def test_save_writes_validated_settings_in_repo_shape(node_config_file):
    node_config.save(
        {
            "select_stack": {"model": "claude-haiku-5-5", "effort": "low"},
            "interview_user": {"model": None, "effort": None},
        }
    )

    # 사람이 git diff 로 보는 파일이라 노드 순서를 고정하고 한 줄에 하나씩 쓴다.
    assert node_config_file.read_text(encoding="utf-8") == (
        "{\n"
        '  "interview_user": { "model": null, "effort": null },\n'
        '  "select_stack": { "model": "claude-haiku-5-5", "effort": "low" }\n'
        "}\n"
    )
    assert node_config.setting("select_stack")["model"] == "claude-haiku-5-5"


def test_save_keeps_repo_file_byte_for_byte(node_config_file):
    repo_file = node_config.BUILDER_ROOT / "config" / "nodes.json"
    text = repo_file.read_text(encoding="utf-8")

    node_config.save(json.loads(text))

    assert node_config_file.read_text(encoding="utf-8") == text


def test_save_rejects_bad_settings_and_leaves_file(node_config_file):
    write(node_config_file, {})

    with pytest.raises(ValueError, match="모르는 노드"):
        node_config.save({"select_stak": {"model": None, "effort": None}})

    assert json.loads(node_config_file.read_text(encoding="utf-8")) == {}
