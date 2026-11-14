"""공통 스킬 목록 — `templates/skills/<이름>/SKILL.md` 폴더가 곧 목록이다 (docs/design/design.md "select_skills").

이름과 "언제 쓰는지"를 각 SKILL.md 의 frontmatter 에서 읽는다 — 별도 목록 파일을 두면 본문과 어긋날 수 있다.
"""

import re
from typing import TypedDict

from specbuilder.paths import TEMPLATES_DIR

COMMON_SKILLS_DIR = TEMPLATES_DIR / "skills"
# 우리가 쓴 템플릿만 읽으므로 YAML 파서 없이 한 줄짜리 `키: 값` 만 다룬다 (형식은 tests/templates 가 고정).
_FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
_FIELD = re.compile(r"^(name|description):[ \t]*(.+?)[ \t]*$", re.MULTILINE)


class CommonSkill(TypedDict):
    name: str
    description: str
    # 산출물에 그대로 들어가는 SKILL.md 전문
    content: str


def load_common_skills() -> dict[str, CommonSkill]:
    """공통 스킬을 이름 → 스킬로 읽는다. 이름순이라 LLM 입력과 테스트가 실행마다 같다."""
    skills = {}
    for path in sorted(COMMON_SKILLS_DIR.glob("*/SKILL.md")):
        content = path.read_text(encoding="utf-8")
        match = _FRONTMATTER.match(content)
        fields = dict(_FIELD.findall(match.group(1))) if match else {}
        if set(fields) != {"name", "description"}:
            raise ValueError(
                f"공통 스킬 frontmatter 에 name·description 이 없음: {path}"
            )
        if fields["name"] != path.parent.name:
            raise ValueError(f"공통 스킬 이름과 폴더 이름이 다름: {path}")
        skills[fields["name"]] = {**fields, "content": content}
    return skills
