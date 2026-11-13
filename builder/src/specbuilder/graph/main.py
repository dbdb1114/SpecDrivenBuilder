"""요청 원문 파일 → 질문 묶음/답 → output/<run_id>/ 산출물.

답은 터미널 입력 또는 stdin 파이프(한 줄 = 질문 하나의 답).
번호(복수 선택은 `1,3`) / 그 밖의 글자 = 직접 입력 / 빈 줄 = 추천 선택지(없으면 맡김) / `그만` = 남은 질문을 맡기고 만들기.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from specbuilder.graph.build import build_graph
from specbuilder.llm import ClaudeCLIClient
from specbuilder.paths import CHECKPOINT_DB, OUTPUT_DIR
from specbuilder.state import initial_state
from specbuilder.state.question_format import (
    DELEGATE_LABEL,
    bundle_adapter,
    submission_adapter,
)

FINISH_WORD = "그만"


class CountingClient:
    """호출 수를 run.json 에 남기기 위한 얇은 래퍼 — LLM 호출 수 변화를 실제 실행으로 비교한다."""

    def __init__(self, inner):
        self.inner = inner
        self.model = inner.model
        self.calls = 0

    def complete(self, system: str, prompt: str, schema: dict | None = None) -> str:
        self.calls += 1
        return self.inner.complete(system, prompt, schema)


def read_line() -> str:
    try:
        line = input("> ").strip()
    except EOFError:
        sys.exit("답 입력이 끝났습니다 (stdin EOF). 질문 수만큼 답을 넣어 주세요.")
    if not sys.stdin.isatty():
        print(line)
    return line


def parse_answer(question: dict, line: str) -> dict | None:
    """한 줄 입력을 답 하나로 바꾼다. 잘못된 번호면 None (다시 묻는다)."""
    options = question["options"]
    delegate_no = len(options) + 1
    if not line:
        recommended = [o["id"] for o in options if o["recommended"]]
        if recommended:
            return {
                "question_id": question["id"],
                "kind": "option",
                "option_ids": recommended,
            }
        return {"question_id": question["id"], "kind": "delegate"}
    parts = [p.strip() for p in line.replace(" ", "").split(",")]
    if not all(p.isdigit() for p in parts):
        return {"question_id": question["id"], "kind": "custom", "text": line}
    numbers = [int(p) for p in parts]
    if numbers == [delegate_no]:
        return {"question_id": question["id"], "kind": "delegate"}
    if any(not 1 <= n <= len(options) for n in numbers):
        return None
    if not question["multiple"] and len(numbers) > 1:
        return None
    return {
        "question_id": question["id"],
        "kind": "option",
        "option_ids": [options[n - 1]["id"] for n in numbers],
    }


def ask_bundle(raw: object) -> dict:
    """질문 묶음을 번호 목록으로 그리고 답 제출을 만든다. `visual`·`preview` 는 그리지 않는다."""
    bundle = bundle_adapter.validate_python(raw)
    total = len(bundle["questions"])
    print(f"\n=== 질문 묶음 {bundle['round']} ({total}개) ===", flush=True)
    if bundle["can_finish"]:
        print(f"('{FINISH_WORD}' 을 입력하면 남은 질문은 알아서 정하고 바로 만듭니다)")
    answers = []
    for i, question in enumerate(bundle["questions"], 1):
        print(f"\n[질문 {i}/{total}] {question['text']}")
        if question["multiple"]:
            print("  (여러 개 고를 수 있어요 — 예: 1,3)")
        for n, option in enumerate(question["options"], 1):
            mark = " (추천)" if option["recommended"] else ""
            print(f"  {n}. {option['label']}{mark}")
        print(f"  {len(question['options']) + 1}. {DELEGATE_LABEL}")
        print("  (직접 입력해도 돼요. 빈 줄이면 추천)")
        while True:
            line = read_line()
            if bundle["can_finish"] and line == FINISH_WORD:
                return submission_adapter.validate_python(
                    {"action": "finish", "answers": answers}
                )
            answer = parse_answer(question, line)
            if answer is not None:
                break
            print("번호를 다시 확인해 주세요.")
        answers.append(answer)
    return submission_adapter.validate_python({"action": "submit", "answers": answers})


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m specbuilder.graph.main")
    parser.add_argument(
        "request", type=Path, help="요청 원문 파일 (예: evals/cases/01-short.md)"
    )
    parser.add_argument(
        "--out", type=Path, default=OUTPUT_DIR, help="산출물 상위 디렉토리"
    )
    parser.add_argument(
        "--db", type=Path, default=CHECKPOINT_DB, help="SqliteSaver 파일"
    )
    args = parser.parse_args(argv)

    started = datetime.now()
    run_id = f"{started:%y%m%d-%H%M%S}-{args.request.stem}"
    llm = CountingClient(ClaudeCLIClient())
    config = {"configurable": {"thread_id": run_id}}

    with SqliteSaver.from_conn_string(str(args.db)) as checkpointer:
        graph = build_graph(llm, checkpointer)
        result = graph.invoke(
            initial_state(args.request.read_text(encoding="utf-8")), config
        )
        while "__interrupt__" in result:
            submission = ask_bundle(result["__interrupt__"][0].value)
            result = graph.invoke(Command(resume=submission), config)

    run_dir = args.out / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    for name, content in result["artifacts"].items():
        (run_dir / name).write_text(content, encoding="utf-8")
    # 품질 회귀 비교용 실행 기록 — 산출물 자체는 아니다.
    meta = {
        "model": llm.model,
        "started_at": started.isoformat(timespec="seconds"),
        "request_file": str(args.request),
        "llm_calls": llm.calls,
        "interview_stops": result["interview_stops"],
        "qa": result["qa"],
        "spec_items": result["spec_items"],
    }
    (run_dir / "run.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n산출물: {run_dir}  (모델 {llm.model})")


if __name__ == "__main__":
    main()
