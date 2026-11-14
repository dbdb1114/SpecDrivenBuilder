import json
from types import SimpleNamespace

import anthropic
import httpx2
import pytest

from specbuilder.llm.client import (
    AnthropicAPIClient,
    ClaudeCLIClient,
    LLMCallError,
    _strict_schema,
    make_client,
)


class FakeAnthropic:
    """`client.beta.messages.stream(...)` 만 흉내 낸다 — 받은 요청을 기록하고 정해 둔 메시지를 돌려주거나 예외를 올린다."""

    def __init__(self, message=None, error=None):
        self.requests = []
        self._message = message
        self._error = error
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self._stream))

    def _stream(self, **params):
        self.requests.append(params)
        if self._error is not None:
            raise self._error
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        return self._message


def message(text="답", stop_reason="end_turn"):
    blocks = [SimpleNamespace(type="thinking", thinking="")]
    if text:
        blocks.append(SimpleNamespace(type="text", text=text))
    return SimpleNamespace(content=blocks, stop_reason=stop_reason)


def api_error(cls, status):
    response = httpx2.Response(
        status, request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    )
    return cls("실패", response=response, body=None)


def test_strict_schema_drops_discriminator_but_keeps_one_of():
    schema = {
        "type": "object",
        "properties": {
            "visual": {
                "oneOf": [{"$ref": "#/$defs/A"}, {"$ref": "#/$defs/B"}],
                "discriminator": {"propertyName": "type"},
            }
        },
    }

    strict = json.dumps(_strict_schema(schema))

    assert "discriminator" not in strict
    assert "oneOf" in strict


def test_api_client_sends_system_prompt_and_returns_text_only():
    fake = FakeAnthropic(message('{"a": 1}'))
    client = AnthropicAPIClient(model="claude-opus-5-5", client=fake)

    assert client.complete("시스템", "입력") == '{"a": 1}'

    request = fake.requests[0]
    assert request["model"] == "claude-opus-5-5"
    assert request["system"] == "시스템"
    assert request["messages"] == [{"role": "user", "content": "입력"}]
    assert "format" not in request["output_config"]


def test_api_client_converts_schema_to_api_form():
    schema = {
        "type": "object",
        "properties": {
            "visual": {
                "oneOf": [{"type": "string"}, {"type": "null"}],
                "discriminator": {"propertyName": "type"},
            },
            "name": {"type": "string", "maxLength": 5},
        },
        "required": ["visual", "name"],
    }
    fake = FakeAnthropic(message("{}"))

    AnthropicAPIClient(model="claude-opus-5-5", client=fake).complete("s", "p", schema)

    sent = fake.requests[0]["output_config"]["format"]
    assert sent["type"] == "json_schema"
    visual = sent["schema"]["properties"]["visual"]
    # SDK 는 뺀 키워드를 description 글로 옮겨 적는다 — 키로 남지 않았는지를 본다.
    assert "anyOf" in visual
    assert "oneOf" not in visual and "discriminator" not in visual
    assert "maxLength" not in sent["schema"]["properties"]["name"]
    assert sent["schema"]["additionalProperties"] is False


def test_api_client_asks_for_fallback_only_on_models_that_support_it():
    supported = FakeAnthropic(message())
    AnthropicAPIClient(model="claude-opus-5-5", client=supported).complete("s", "p")
    other = FakeAnthropic(message())
    AnthropicAPIClient(model="claude-haiku-5-5", client=other).complete("s", "p")

    assert supported.requests[0]["fallbacks"] == "default"
    assert "fallbacks" not in other.requests[0]
    assert "betas" not in other.requests[0]


@pytest.mark.parametrize(
    ("final", "expected"),
    [
        (message(stop_reason="refusal"), "거절"),
        (message(stop_reason="max_tokens"), "잘림"),
        (message(text=""), "글이 없음"),
    ],
)
def test_api_client_raises_on_unusable_reply(final, expected):
    client = AnthropicAPIClient(model="claude-opus-5-5", client=FakeAnthropic(final))

    with pytest.raises(LLMCallError, match=expected):
        client.complete("s", "p")


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (api_error(anthropic.AuthenticationError, 401), "인증 실패"),
        (api_error(anthropic.RateLimitError, 429), "한도 초과"),
        (api_error(anthropic.BadRequestError, 400), "오류 400"),
        (
            anthropic.APIConnectionError(
                request=httpx2.Request("POST", "https://api.anthropic.com")
            ),
            "연결 실패",
        ),
    ],
)
def test_api_client_wraps_sdk_errors(error, expected):
    client = AnthropicAPIClient(
        model="claude-opus-5-5", client=FakeAnthropic(error=error)
    )

    with pytest.raises(LLMCallError, match=expected):
        client.complete("s", "p")


def test_make_client_defaults_to_claude_cli(monkeypatch):
    monkeypatch.delenv("SPECBUILDER_LLM", raising=False)

    assert isinstance(make_client(), ClaudeCLIClient)


def test_make_client_picks_api_client(monkeypatch):
    monkeypatch.setenv("SPECBUILDER_LLM", "anthropic-api")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("SPECBUILDER_MODEL", "claude-opus-5-5")

    client = make_client()

    assert isinstance(client, AnthropicAPIClient)
    assert client.model == "claude-opus-5-5"


def test_make_client_rejects_unknown_kind(monkeypatch):
    monkeypatch.setenv("SPECBUILDER_LLM", "openai")

    with pytest.raises(ValueError, match="SPECBUILDER_LLM"):
        make_client()
