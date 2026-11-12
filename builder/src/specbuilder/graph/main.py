"""요청 원문 파일 → 질문/답 → output/<run_id>/ 산출물. 답은 터미널 입력 또는 stdin 파이프(한 줄 = 답 하나)."""

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


def ask(question: str) -> str:
    print(f"\n[질문] {question}", flush=True)
    try:
        answer = input("> ")
    except EOFError:
        sys.exit("답 입력이 끝났습니다 (stdin EOF). 질문 수만큼 답을 넣어 주세요.")
    if not sys.stdin.isatty():
        print(answer)
    return answer


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
    llm = ClaudeCLIClient()
    config = {"configurable": {"thread_id": run_id}}

    with SqliteSaver.from_conn_string(str(args.db)) as checkpointer:
        graph = build_graph(llm, checkpointer)
        result = graph.invoke(
            initial_state(args.request.read_text(encoding="utf-8")), config
        )
        while "__interrupt__" in result:
            answer = ask(result["__interrupt__"][0].value)
            result = graph.invoke(Command(resume=answer), config)

    run_dir = args.out / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    for name, content in result["artifacts"].items():
        (run_dir / name).write_text(content, encoding="utf-8")
    # #2 비교 표에 모델 ID·날짜·문답을 남기기 위한 실행 기록 — 산출물 자체는 아니다.
    meta = {
        "model": llm.model,
        "started_at": started.isoformat(timespec="seconds"),
        "request_file": str(args.request),
        "qa": result["qa"],
    }
    (run_dir / "run.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n산출물: {run_dir}  (모델 {llm.model})")


if __name__ == "__main__":
    main()
