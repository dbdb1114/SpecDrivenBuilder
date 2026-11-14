"""템플릿 스냅샷 — 템플릿을 바꾸면 `SNAPSHOT_UPDATE=1 uv run pytest tests/templates` 로 갱신하고 diff 를 확인한다."""

import os
import re
from pathlib import Path

import pytest

from specbuilder.common_skills import load_common_skills
from specbuilder.nodes.generate_artifacts import render_skill
from specbuilder.paths import TEMPLATES_DIR

SNAPSHOTS = Path(__file__).parent / "snapshots"
# 루트 AGENTS.md "산출물 규칙": 플레이스홀더, 위험 명령·권한 우회·비밀값 금지.
FORBIDDEN = re.compile(
    r"TODO|<여기에|\.\.\.|rm -rf|curl[^\n]*\|\s*(ba)?sh|sudo |--dangerously|bypassPermissions|api[_-]?key",
    re.IGNORECASE,
)
COMMON_SKILLS = load_common_skills()


def assert_snapshot(name: str, content: str) -> None:
    path = SNAPSHOTS / name
    if os.environ.get("SNAPSHOT_UPDATE"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    assert path.exists(), f"스냅샷 없음: {name} (SNAPSHOT_UPDATE=1 로 만든다)"
    assert content == path.read_text(encoding="utf-8")


def test_new_skill_template_snapshot():
    rendered = render_skill(
        {
            "name": "build-ledger",
            "when": '가계부를 만들 때 쓴다: "처음부터" 만들 때',
            "source": "new",
            "basis": ["purpose"],
        },
        "# 가계부 만들기\n\n1. 화면을 만든다. 금액은 ${amount} 처럼 적지 않는다.\n",
        (TEMPLATES_DIR / "SKILL.md").read_text(encoding="utf-8"),
    )
    assert_snapshot("new-skill.SKILL.md", rendered)


def test_common_skill_list_is_not_empty():
    assert "verify-before-report" in COMMON_SKILLS


@pytest.mark.parametrize("name", sorted(COMMON_SKILLS))
def test_common_skill_snapshot_and_rules(name):
    skill = COMMON_SKILLS[name]

    assert_snapshot(f"common-{name}.SKILL.md", skill["content"])
    # description 에는 "언제 쓰는지" 가 들어가야 한다.
    assert "쓴다" in skill["description"]
    assert not FORBIDDEN.search(skill["content"])
    # Claude 전용 문법(@임포트, 슬래시 명령)에 기대지 않는다 — Codex 도 같은 파일을 읽는다.
    assert not re.search(
        r"^@|(?<![\w/.])/[a-z][a-z-]+\b", skill["content"], re.MULTILINE
    )
