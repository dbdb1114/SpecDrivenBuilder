# src 레이아웃이라 패키지 위치와 데이터 디렉토리(prompts·output)가 떨어져 있다 — builder/ 루트를 기준으로 계산한다.
from pathlib import Path

BUILDER_ROOT = Path(__file__).resolve().parents[2]
PROMPTS_DIR = BUILDER_ROOT / "prompts"
OUTPUT_DIR = BUILDER_ROOT / "output"
CHECKPOINT_DB = BUILDER_ROOT / ".checkpoints.sqlite"


def load_prompt(name: str) -> str:
    """`prompts/<name>.md` 를 읽어 시스템 프롬프트로 돌려준다."""
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
