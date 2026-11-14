import contextvars
import json
import logging
import os
import re
import subprocess
import tempfile
import time
from typing import Protocol

import anthropic

from specbuilder.llm import trace

DEFAULT_MODEL = "claude-sonnet-5-5"
# 어떤 클라이언트로 호출할지 고르는 환경 변수. 비우면 claude-cli.
LLM_ENV = "SPECBUILDER_LLM"
# 스트리밍으로 받으므로 HTTP 타임아웃 걱정 없이 넉넉히 둔다 — generate_artifacts 는 파일 여러 개를 한 번에 쓴다.
API_MAX_TOKENS = 64000
# 모델마다 기본 effort 가 다르다 (opus-5-5 는 medium, sonnet-5-5 는 high) — 모델을 바꿔도 깊이가 같도록 고정한다.
API_EFFORT = "medium"
# 안전 분류기가 요청을 거절했을 때 서버가 다른 모델로 같은 요청을 다시 돌리게 하는 기능을 지원하는 모델.
API_FALLBACK_MODELS = frozenset({"claude-opus-5-5", "claude-sonnet-5-5"})
API_FALLBACK_BETA = "server-side-fallback-2026-07-01"

logger = logging.getLogger(__name__)
# 지금 호출하는 노드 이름. 클라이언트는 누가 부르는지 모르므로 for_node 가 호출 동안만 적어 둔다 (사용량 줄에 쓴다).
_node = contextvars.ContextVar("llm_node", default="-")
# 방금 끝난 호출의 사용량. 감싼 클라이언트가 적어 두면 for_node 의 껍데기가 호출 기록에 싣는다.
_usage = contextvars.ContextVar("llm_usage", default=None)


class LLMCallError(Exception):
    """LLM 호출 실패 또는 응답 형식 오류."""


class LLMClient(Protocol):
    model: str

    def complete(self, system: str, prompt: str, schema: dict | None = None) -> str:
        """schema(JSON Schema) 를 주면 그 형식의 JSON 문자열을 돌려준다."""
        ...


class ClaudeCLIClient:
    """`claude -p` 헤드리스로 호출한다. API 키 없이 로그인된 요금제로 돈다 (스파이크용, 운영용 아님)."""

    def __init__(self, model: str | None = None, timeout: float = 600):
        self.model = model or os.environ.get("SPECBUILDER_MODEL", DEFAULT_MODEL)
        self.timeout = timeout

    def complete(self, system: str, prompt: str, schema: dict | None = None) -> str:
        # 도구·설정·MCP·스킬을 모두 끄고 빈 임시 디렉토리에서 돌린다 — 이 레포의 CLAUDE.md 나
        # 사용자 훅이 섞이면 같은 입력에 다른 출력이 나와 비교 실험이 무의미해진다.
        cmd = [
            "claude", "-p",
            "--model", self.model,
            "--system-prompt", system,
            "--tools", "",
            "--setting-sources", "",
            "--strict-mcp-config",
            "--disable-slash-commands",
            "--no-session-persistence",
            "--output-format", "json",
        ]  # fmt: skip
        if schema is not None:
            # 모델이 손으로 쓴 JSON 은 따옴표가 빠지는 등 약 1/3 확률로 깨졌다 (작업 A eval) — CLI 가 형식을 강제하게 한다.
            cmd += [
                "--json-schema",
                json.dumps(_strict_schema(schema), ensure_ascii=False),
            ]
        with tempfile.TemporaryDirectory() as cwd:
            try:
                proc = subprocess.run(
                    cmd,
                    input=prompt,
                    capture_output=True,
                    text=True,
                    cwd=cwd,
                    timeout=self.timeout,
                    check=False,  # 종료 코드는 아래에서 stderr 와 함께 LLMCallError 로 올린다
                )
            except (OSError, subprocess.TimeoutExpired) as e:
                raise LLMCallError(f"claude -p 실행 실패: {e}") from e
        if proc.returncode != 0:
            raise LLMCallError(
                f"claude -p 종료 코드 {proc.returncode}: {proc.stderr.strip()[:500]}"
            )
        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError as e:
            raise LLMCallError(
                f"claude -p 출력이 JSON 이 아님: {proc.stdout[:200]}"
            ) from e
        usage = data.get("usage") or {}
        if usage:
            _usage.set(
                {
                    "input": usage.get("input_tokens", 0),
                    "output": usage.get("output_tokens", 0),
                    "cache_write": usage.get("cache_creation_input_tokens", 0),
                    "cache_read": usage.get("cache_read_input_tokens", 0),
                }
            )
        if data.get("is_error"):
            raise LLMCallError(f"claude -p 오류 응답: {data.get('result')}")
        if schema is not None:
            if "structured_output" not in data:
                raise LLMCallError(
                    f"claude -p 응답에 structured_output 이 없음: {data.get('result')!r:.200}"
                )
            return json.dumps(data["structured_output"], ensure_ascii=False)
        return data["result"]


class AnthropicAPIClient:
    """Claude API(Messages)로 호출한다. `ANTHROPIC_API_KEY` 가 필요하고 호출마다 과금된다."""

    def __init__(
        self,
        model: str | None = None,
        timeout: float = 600,
        client: anthropic.Anthropic | None = None,
    ):
        self.model = model or os.environ.get("SPECBUILDER_MODEL", DEFAULT_MODEL)
        # 키는 SDK 가 환경(ANTHROPIC_API_KEY)에서 읽는다 — 코드와 로그에 키를 남기지 않는다.
        self._client = client or anthropic.Anthropic(timeout=timeout)

    def complete(self, system: str, prompt: str, schema: dict | None = None) -> str:
        output_config = {"effort": API_EFFORT}
        if schema is not None:
            # pydantic 이 만든 스키마에는 API 가 받지 않는 키워드(oneOf, discriminator, 길이 제약 등)가 있다.
            # SDK 가 API 형식으로 바꿔 주고, 빠진 제약은 응답을 받은 뒤 노드의 pydantic 검증이 다시 본다.
            output_config["format"] = {
                "type": "json_schema",
                "schema": anthropic.transform_schema(schema),
            }
        params = {
            "model": self.model,
            "max_tokens": API_MAX_TOKENS,
            # 노드 프롬프트는 호출마다 같다 — 캐시 표시를 붙이면 5분 안의 다음 호출부터 이 부분을 싸게 읽는다.
            # 캐시는 앞부분이 글자 하나까지 같아야 맞으므로 system 에는 바뀌는 값을 넣지 않는다 (바뀌는 것은 전부 prompt 로).
            "system": [
                {
                    "type": "text",
                    "text": system,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            "messages": [{"role": "user", "content": prompt}],
            "output_config": output_config,
        }
        if self.model in API_FALLBACK_MODELS:
            params |= {"betas": [API_FALLBACK_BETA], "fallbacks": "default"}
        started = time.monotonic()
        try:
            # 긴 출력은 스트리밍으로 받아야 중간에 연결이 끊기지 않는다. 조각은 쓰지 않고 완성된 메시지만 꺼낸다.
            with self._client.beta.messages.stream(**params) as stream:
                message = stream.get_final_message()
        except anthropic.AuthenticationError as e:
            raise LLMCallError(
                "Claude API 인증 실패: ANTHROPIC_API_KEY 를 확인할 것"
            ) from e
        except anthropic.RateLimitError as e:
            raise LLMCallError(f"Claude API 요청 한도 초과: {e.message}") from e
        except anthropic.APIStatusError as e:
            raise LLMCallError(
                f"Claude API 오류 {e.status_code}: {e.message[:500]}"
            ) from e
        except anthropic.APIConnectionError as e:
            raise LLMCallError(f"Claude API 연결 실패: {e}") from e
        _log_usage(self.model, message, time.monotonic() - started)
        if message.stop_reason == "refusal":
            raise LLMCallError("Claude API 가 요청을 거절함 (stop_reason: refusal)")
        if message.stop_reason == "max_tokens":
            raise LLMCallError(f"응답이 max_tokens({API_MAX_TOKENS})에서 잘림")
        text = "".join(block.text for block in message.content if block.type == "text")
        if not text:
            raise LLMCallError(
                f"Claude API 응답에 글이 없음 (stop_reason: {message.stop_reason})"
            )
        return text


def _log_usage(model: str, message: object, seconds: float) -> None:
    """호출 한 번의 토큰 사용량을 남긴다 — 어디서 비용이 나가는지, 캐시가 맞았는지는 이 숫자로만 알 수 있다."""
    raw = getattr(message, "usage", None)
    if raw is None:
        return
    usage = {
        "input": raw.input_tokens,
        "output": raw.output_tokens,
        # 캐시를 쓰지 않은 호출에서는 SDK 가 None 을 준다.
        "cache_write": raw.cache_creation_input_tokens or 0,
        "cache_read": raw.cache_read_input_tokens or 0,
    }
    _usage.set(usage)
    logger.info(
        "llm usage node=%s model=%s input=%s output=%s cache_write=%s cache_read=%s seconds=%.1f",
        _node.get(),
        model,
        *usage.values(),
        seconds,
    )


class _NodeClient:
    """호출하는 동안 노드 이름을 적어 두는 얇은 껍데기. 나머지는 감싼 클라이언트 그대로다."""

    def __init__(self, inner: LLMClient, node: str):
        self._inner = inner
        self._node_name = node
        self.model = inner.model

    def complete(self, system: str, prompt: str, schema: dict | None = None) -> str:
        token = _node.set(self._node_name)
        _usage.set(None)
        started = time.monotonic()
        call = {"node": self._node_name, "model": self.model}
        try:
            call["response"] = self._inner.complete(system, prompt, schema)
            return call["response"]
        except LLMCallError as e:
            call["error"] = str(e)
            raise
        finally:
            _node.reset(token)
            # 기록은 SPECBUILDER_TRACE 가 켜져 있을 때만 남는다 (llm/trace.py).
            trace.record(
                call
                | {
                    "seconds": round(time.monotonic() - started, 1),
                    "usage": _usage.get(),
                    "system": system,
                    "prompt": prompt,
                }
            )


def for_node(llm: LLMClient, node: str) -> LLMClient:
    """사용량 줄에 노드 이름이 찍히도록 클라이언트를 감싼다 (graph/build.py 가 노드마다 쓴다)."""
    return _NodeClient(llm, node)


def make_client() -> LLMClient:
    """환경 변수 `SPECBUILDER_LLM` 으로 클라이언트를 고른다. 비우면 `claude -p` (요금제 안에서 돈다)."""
    kind = os.environ.get(LLM_ENV) or "claude-cli"
    if kind == "claude-cli":
        return ClaudeCLIClient()
    if kind == "anthropic-api":
        # uvicorn 과 CLI 는 이 로거를 설정하지 않아 INFO 가 버려진다 — 사용량 줄이 터미널(stderr)에 보이게 한 번만 붙인다.
        if not logger.handlers:
            logger.addHandler(logging.StreamHandler())
            logger.setLevel(logging.INFO)
        return AnthropicAPIClient()
    raise ValueError(f"{LLM_ENV} 는 claude-cli 또는 anthropic-api 여야 함: {kind!r}")


def _strict_schema(node):
    # pydantic 은 판별 유니온에 OpenAPI 전용 키워드 `discriminator` 를 넣는데, claude -p 의 strict 검증이 이를 거부한다.
    # oneOf 는 남으므로 형식 강제는 그대로이고, 판별은 응답을 받은 뒤 pydantic 이 다시 한다.
    if isinstance(node, dict):
        return {k: _strict_schema(v) for k, v in node.items() if k != "discriminator"}
    if isinstance(node, list):
        return [_strict_schema(v) for v in node]
    return node


def parse_json_reply(text: str) -> dict:
    """응답에서 첫 JSON 객체를 꺼낸다. 모델이 코드펜스나 설명을 덧붙여도 견디도록."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise LLMCallError(f"응답에 JSON 객체가 없음: {text[:200]}")
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as e:
        raise LLMCallError(f"응답 JSON 파싱 실패: {text[:200]}") from e
