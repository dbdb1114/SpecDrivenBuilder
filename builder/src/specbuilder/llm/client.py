import json
import os
import re
import subprocess
import tempfile
from typing import Protocol

DEFAULT_MODEL = "claude-sonnet-5-5"


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
        if data.get("is_error"):
            raise LLMCallError(f"claude -p 오류 응답: {data.get('result')}")
        if schema is not None:
            if "structured_output" not in data:
                raise LLMCallError(
                    f"claude -p 응답에 structured_output 이 없음: {data.get('result')!r:.200}"
                )
            return json.dumps(data["structured_output"], ensure_ascii=False)
        return data["result"]


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
