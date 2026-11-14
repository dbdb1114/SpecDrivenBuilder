"""LLM 호출 기록 보기 — `uv run python -m specbuilder.llm.show_trace [run_id] [--show N]`.

기록을 남기는 쪽(`trace.py`)과 파일을 나눈 이유: `trace` 는 `llm` 패키지가 뜰 때 함께 import 되므로
`python -m` 으로 다시 실행하면 같은 모듈이 두 번 올라온다.
"""

import argparse
import sys
from pathlib import Path

from specbuilder.llm import trace


def main() -> None:
    parser = argparse.ArgumentParser(description="LLM 호출 기록 보기")
    parser.add_argument(
        "run", nargs="?", help="run_id 또는 파일 경로. 비우면 가장 최근 실행"
    )
    parser.add_argument(
        "--show", type=int, metavar="N", help="N번째 호출의 프롬프트와 응답 전문"
    )
    args = parser.parse_args()

    if args.run and Path(args.run).is_file():
        path = Path(args.run)
    elif args.run:
        path = trace.trace_dir() / f"{args.run}.jsonl"
    else:
        files = sorted(
            trace.trace_dir().glob("*.jsonl"), key=lambda p: p.stat().st_mtime
        )
        if not files:
            sys.exit(
                f"기록이 없습니다 ({trace.trace_dir()}). {trace.TRACE_ENV}=1 로 실행했는지 확인하세요."
            )
        path = files[-1]
    if not path.is_file():
        sys.exit(f"없는 기록: {path}")
    calls = trace.load(path)
    print(f"{path}  (호출 {len(calls)}회)\n")
    if args.show is None:
        print(trace.summarize(calls))
    elif 1 <= args.show <= len(calls):
        print(trace.show(calls[args.show - 1]))
    else:
        sys.exit(f"호출 번호는 1~{len(calls)}")


if __name__ == "__main__":
    main()
