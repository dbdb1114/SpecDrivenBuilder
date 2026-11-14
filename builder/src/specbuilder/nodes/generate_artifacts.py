import json
import re
from string import Template

from specbuilder.common_skills import CommonSkill, load_common_skills
from specbuilder.llm import LLMCallError, LLMClient
from specbuilder.paths import TEMPLATES_DIR, load_prompt
from specbuilder.state import SkillEntry, SpecItem, State

DOC_FILES = ("spec.md", "AGENTS.md")
# 두 작업자가 같이 읽는 경로가 없다 — Claude Code 는 .claude/skills, Codex 는 .agents/skills 만 발견한다.
# 그래서 같은 내용을 두 곳에 넣는다 (docs/design/design.md "select_skills").
SKILL_DIRS = (".claude/skills", ".agents/skills")
# AGENTS.md 가 스킬을 가리킬 때 쓰는 경로. 특정 작업자 이름이 들어가지 않은 쪽.
SKILL_REF_DIR = ".agents/skills"
LEADING_FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
# 긴 마크다운을 JSON 문자열로 받으면 이스케이프가 자주 깨진다 — 구분선 형식이 더 견고하다.
FILE_MARKER = re.compile(r"^=== FILE: (\S+) ===[ \t]*$", re.MULTILINE)


AREA_LABELS = {"function": "용도·기능", "design": "디자인", "tech": "기술"}


def _is_user_decision(item: SpecItem) -> bool:
    return item["decided_by"] == "user" and item["status"] == "confirmed"


def _render_item(item: SpecItem) -> str:
    # 기본 방향이 빈 맡김 항목(사용자가 "알아서"를 골랐거나 묻기를 그만둔 경우)은 여기서 정하라고 표시한다.
    content = item["content"].strip() or "(기본 방향 없음 — 정해서 적을 것)"
    return f"- [{AREA_LABELS[item['area']]}] {item['name']}: {content}"


def render_context(state: State) -> str:
    """요청 원문과 스펙 항목을 "사용자가 정한 것 / 작업자가 정하는 것" 으로 나눈 데이터 블록으로 만든다."""
    items = state["spec_items"]
    user = [_render_item(i) for i in items if _is_user_decision(i)]
    worker = [_render_item(i) for i in items if not _is_user_decision(i)]
    return "\n".join(
        ["## 요청 원문", state["request"].strip(), "", "## 사용자가 정한 것"]
        + (user or ["(없음)"])
        + ["", "## 작업자가 정하는 것"]
        + (worker or ["(없음)"])
        + ["", "## 스킬 목록"]
        + ([_render_skill(s) for s in state["skills"]] or ["(없음)"])
    )


def _render_skill(skill: SkillEntry) -> str:
    kind = (
        "공통 스킬 — 이미 있음, 쓰지 않는다"
        if skill["source"] == "common"
        else f"새로 씀 — `{_body_file(skill)}` 로 본문을 쓴다"
    )
    return f"- `{skill['name']}` ({kind}): {skill['when']} / 위치: `{SKILL_REF_DIR}/{skill['name']}/SKILL.md`"


def _body_file(skill: SkillEntry) -> str:
    return f"skills/{skill['name']}.md"


def parse_files(text: str, required: list[str]) -> dict[str, str]:
    """`=== FILE: <이름> ===` 구분선으로 나뉜 응답을 파일명 → 내용으로 바꾼다. 요구하지 않은 파일은 버린다."""
    parts = FILE_MARKER.split(text)
    files = {name: body.strip() + "\n" for name, body in zip(parts[1::2], parts[2::2])}
    missing = [f for f in required if f not in files]
    if missing:
        raise LLMCallError(f"응답에 빠진 파일: {missing}")
    return {name: files[name] for name in required}


def render_skill(skill: SkillEntry, body: str, template: str) -> str:
    """새로 쓰는 스킬의 SKILL.md 를 만든다. frontmatter 는 LLM 이 아니라 스킬 목록 값으로 채운다 — 필수 필드가 빠질 수 없다."""
    # LLM 이 본문 앞에 frontmatter 를 또 붙이면 두 겹이 돼 작업자가 스킬을 못 읽는다.
    body = LEADING_FRONTMATTER.sub("", body.lstrip(), count=1).strip()
    if not body:
        raise LLMCallError(f"스킬 본문이 비어 있음: {skill['name']}")
    # string.Template 은 값 안의 `$`·`{}` 를 다시 해석하지 않는다 (str.format 은 본문의 중괄호에서 깨진다).
    return Template(template).substitute(
        name=skill["name"],
        # JSON 문자열은 YAML 큰따옴표 문자열로도 유효하다 — 콜론·따옴표가 섞인 문장이 frontmatter 를 깨지 못한다.
        description=json.dumps(skill["when"], ensure_ascii=False),
        body=body,
    )


def assemble(
    skills: list[SkillEntry],
    files: dict[str, str],
    common: dict[str, CommonSkill],
    template: str,
) -> dict[str, str]:
    """LLM 이 쓴 문서·스킬 본문과 공통 스킬 원문을 산출물 경로 → 내용으로 조립한다."""
    artifacts = {name: files[name] for name in DOC_FILES}
    for skill in skills:
        if skill["source"] == "common":
            if skill["name"] not in common:
                raise ValueError(f"공통 스킬 목록에 없는 스킬: {skill['name']}")
            content = common[skill["name"]]["content"]
        else:
            content = render_skill(skill, files[_body_file(skill)], template)
        for base in SKILL_DIRS:
            artifacts[f"{base}/{skill['name']}/SKILL.md"] = content
    return artifacts


def make_generate_artifacts(llm: LLMClient):
    """LLM 클라이언트를 주입한 generate_artifacts 노드를 만든다."""
    system = load_prompt("generate_artifacts")

    skill_template = (TEMPLATES_DIR / "SKILL.md").read_text(encoding="utf-8")

    def generate_artifacts(state: State) -> dict:
        skills = state["skills"]
        required = [
            *DOC_FILES,
            *(_body_file(s) for s in skills if s["source"] == "new"),
        ]
        files = assemble(
            skills,
            parse_files(llm.complete(system, render_context(state)), required),
            load_common_skills(),
            skill_template,
        )
        # CLAUDE.md 는 본문 없이 임포트 한 줄로 고정 (루트 "산출물 규칙") — LLM 에 맡기지 않는다.
        files["CLAUDE.md"] = "@AGENTS.md\n"
        return {"artifacts": files}

    return generate_artifacts
