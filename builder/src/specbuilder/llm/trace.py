"""LLM 호출 기록 — 한 실행에서 주고받은 프롬프트·응답·토큰 사용량을 파일로 남기고 표로 본다.

`SPECBUILDER_TRACE=1` 일 때만 남긴다. 프롬프트에는 사용자의 요청 원문과 답이 그대로 들어가므로 기본은 꺼 둔다.
파일은 `output/_traces/<run_id>.jsonl` (호출 하나가 한 줄). 보기: `uv run python -m specbuilder.llm.show_trace`.
"""

import json
import os
from datetime import datetime
from pathlib import Path

from specbuilder.paths import OUTPUT_DIR

TRACE_ENV = "SPECBUILDER_TRACE"
TRACE_DIR_ENV = "SPECBUILDER_TRACE_DIR"
# 100만 토큰당 달러: (입력, 출력, 캐시 쓰기, 캐시 읽기). 2026-11-14 Claude API 문서 기준 — 가격이 바뀌면 여기만 고친다.
# 표에 없는 모델은 토큰만 보여 준다.
PRICES = {
    "claude-sonnet-5-5": (2.0, 10.0, 2.5, 0.10),
    "claude-opus-5-5": (4.0, 20.0, 5.0, 0.20),
}
USAGE_KEYS = ("input", "output", "cache_write", "cache_read")


def trace_dir() -> Path:
    return Path(os.environ.get(TRACE_DIR_ENV) or OUTPUT_DIR / "_traces")


def enabled() -> bool:
    return os.environ.get(TRACE_ENV, "") not in ("", "0")


def _run_id() -> str:
    # 노드 안에서는 LangGraph 가 지금 실행의 config 를 알려 준다. 그래프 밖(직접 호출)에서는 없다.
    try:
        from langgraph.config import get_config

        return str(get_config()["configurable"]["thread_id"])
    except Exception:  # noqa: BLE001 — 기록 때문에 호출이 실패하면 안 된다. 어떤 이유든 실행 이름만 포기한다.
        return "no-run"


def record(call: dict) -> None:
    """호출 하나를 그 실행의 기록 파일 끝에 덧붙인다."""
    if not enabled():
        return
    path = trace_dir() / f"{_run_id()}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    line = {"at": datetime.now().isoformat(timespec="seconds"), **call}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")


def cost(model: str, usage: dict) -> float | None:
    """사용량을 달러로. 가격을 모르는 모델이나 사용량이 없는 호출은 None."""
    price = PRICES.get(model)
    if price is None or not usage:
        return None
    return sum(usage.get(k, 0) * p for k, p in zip(USAGE_KEYS, price)) / 1_000_000


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def summarize(calls: list[dict]) -> str:
    """호출별 표와 합계. 캐시가 맞았는지(cache_read)와 어디서 비용이 나가는지를 한눈에 본다."""
    head = f"{'#':>2}  {'노드':<20}{'입력':>7}{'캐시쓰기':>8}{'캐시읽기':>8}{'출력':>7}{'초':>7}{'달러':>9}"
    lines = [head]
    total = dict.fromkeys(USAGE_KEYS, 0)
    seconds = dollars = 0.0
    priced = True
    for n, call in enumerate(calls, 1):
        usage = call.get("usage") or {}
        c = cost(call.get("model", ""), usage)
        priced = priced and c is not None
        for k in USAGE_KEYS:
            total[k] += usage.get(k, 0)
        seconds += call.get("seconds", 0)
        dollars += c or 0
        mark = "  실패" if call.get("error") else ""
        lines.append(
            f"{n:>2}  {call.get('node', '-'):<20}{usage.get('input', 0):>9}{usage.get('cache_write', 0):>12}"
            f"{usage.get('cache_read', 0):>12}{usage.get('output', 0):>9}{call.get('seconds', 0):>8.1f}"
            f"{(f'{c:.4f}' if c is not None else '-'):>11}{mark}"
        )
    lines.append(
        f"    {'합계':<20}{total['input']:>9}{total['cache_write']:>12}{total['cache_read']:>12}"
        f"{total['output']:>9}{seconds:>8.1f}{(f'{dollars:.4f}' if priced else '-'):>11}"
    )
    return "\n".join(lines)


def show(call: dict) -> str:
    """호출 하나의 프롬프트와 응답 전문."""
    parts = [
        f"노드: {call.get('node')}   모델: {call.get('model')}   {call.get('at')}",
        f"사용량: {call.get('usage')}   {call.get('seconds')}초",
        "\n===== system =====",
        call.get("system", ""),
        "\n===== prompt =====",
        call.get("prompt", ""),
        "\n===== response =====",
        call.get("response") or f"(실패) {call.get('error')}",
    ]
    return "\n".join(parts)
