import json
import re
from string import Template

from specbuilder.common_skills import CommonSkill, load_common_skills
from specbuilder.llm import LLMCallError, LLMClient
from specbuilder.nodes.interview_design import PREVIEW_ITEM_ID
from specbuilder.paths import TEMPLATES_DIR, load_prompt
from specbuilder.registry.refs import PART_LABELS, parse_parts
from specbuilder.state import Profile, SkillEntry, SpecItem, State

SPEC_FILE = "docs/spec.md"
DOC_FILES = (SPEC_FILE, "AGENTS.md")
# 폴더별 AGENTS.md 의 고정 섹션 (docs/design/design.md "generate_artifacts" — builder/AGENTS.md 가 레퍼런스).
FOLDER_SECTIONS = ("구조", "명령어", "코드 규칙", "하지 말 것")
# 루트 AGENTS.md 에서 폴더 구조도를 담는 섹션. 새로 쓰는 스킬이 가리킬 경로가 여기서 정해진다.
STRUCTURE_SECTION = "구조"
CLAUDE_IMPORT = "@AGENTS.md\n"
# 스펙의 결정 두 절. 스펙 항목을 옮겨 적는 부분이라 LLM 이 아니라 빌더 코드가 쓴다 —
# 출력 토큰이 줄고(산출물의 약 12%), 옮기다 빠뜨리거나 사용자의 답을 바꿔 적을 수 없다.
USER_SECTION = "사용자가 정한 것"
WORKER_SECTION = "작업자가 정하는 것"
WORKER_LEAD = "이 절의 항목은 사용자에게 다시 묻지 않고 기본 방향대로 정한다."
# 두 작업자가 같이 읽는 경로가 없다 — Claude Code 는 .claude/skills, Codex 는 .agents/skills 만 발견한다.
# 그래서 같은 내용을 두 곳에 넣는다 (docs/design/design.md "select_skills").
SKILL_DIRS = (".claude/skills", ".agents/skills")
# AGENTS.md 가 스킬을 가리킬 때 쓰는 경로. 특정 작업자 이름이 들어가지 않은 쪽.
SKILL_REF_DIR = ".agents/skills"
LEADING_FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
# 긴 마크다운을 JSON 문자열로 받으면 이스케이프가 자주 깨진다 — 구분선 형식이 더 견고하다.
FILE_MARKER = re.compile(r"^=== FILE: (\S+) ===[ \t]*$", re.MULTILINE)


AREA_LABELS = {"function": "용도·기능", "design": "디자인", "tech": "기술"}
# 프로필 필드 → 수집 축 이름 (docs/design/interview-profile.md "수집 축"). 작업자 컨텍스트 번역의 입력.
PROFILE_LABELS = {
    "domain": "도메인 전문성",
    "tech_exposure": "기술 노출 정도",
    "explanation": "설명 선호",
    "environment": "환경",
    "delegation": "결정 위임 범위",
}


def _is_user_decision(item: SpecItem) -> bool:
    return item["decided_by"] == "user" and item["status"] == "confirmed"


def _render_item(item: SpecItem) -> str:
    # 기본 방향이 빈 맡김 항목(사용자가 "알아서"를 골랐거나 묻기를 그만둔 경우)은 여기서 정하라고 표시한다.
    content = item["content"].strip() or "(기본 방향 없음 — 정해서 적을 것)"
    return f"- [{AREA_LABELS[item['area']]}] {item['name']}: {content}"


def program_folders(items: list[SpecItem]) -> list[str]:
    """기술 스펙 항목의 `부분:` 줄에서 산출물에 넣을 폴더(frontend·backend·database 순)를 정한다."""
    found = {
        part
        for item in items
        if item["area"] == "tech"
        for part in parse_parts(item["content"])
    }
    return [folder for folder in PART_LABELS if folder in found]


def _render_folders(items: list[SpecItem], folders: list[str]) -> list[str]:
    if not folders:
        return ["(없음 — 루트 문서와 docs/ 만 쓴다)"]
    tech = [i for i in items if i["area"] == "tech"]
    shared = [i["name"] for i in tech if not parse_parts(i["content"])]
    lines = []
    for folder in folders:
        own = [i["name"] for i in tech if folder in parse_parts(i["content"])]
        lines.append(
            f"- `{folder}/` ({PART_LABELS[folder]}) — 이 폴더의 기술: "
            + ", ".join(own + [f"{name}(여러 부분 공통)" for name in shared])
        )
    left = [f"`{f}/`" for f in PART_LABELS if f not in folders]
    if left:
        lines.append(f"- 만들지 않는 폴더: {', '.join(left)}")
    return lines


def render_context(state: State) -> str:
    """요청 원문, "사용자가 정한 것 / 작업자가 정하는 것" 으로 나눈 스펙 항목, 산출물 폴더, 스킬 목록, 프로필을 데이터 블록으로 만든다."""
    items = state["spec_items"]
    user = [_render_item(i) for i in items if _is_user_decision(i)]
    worker = [_render_item(i) for i in items if not _is_user_decision(i)]
    return "\n".join(
        ["## 요청 원문", state["request"].strip(), "", "## 사용자가 정한 것"]
        + (user or ["(없음)"])
        + ["", "## 작업자가 정하는 것"]
        + (worker or ["(없음)"])
        + ["", "## 산출물 폴더"]
        + _render_folders(items, program_folders(items))
        + ["", "## 스킬 목록"]
        + ([_render_skill(s) for s in state["skills"]] or ["(없음)"])
        + ["", "## 사용자 프로필"]
        + _render_profile(state["profile"])
    )


def _render_profile(profile: Profile | None) -> list[str]:
    if not profile:
        return ["(없음)"]
    return [
        f"- {label}: {profile[field].strip() or '(모름)'}"
        for field, label in PROFILE_LABELS.items()
    ]


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


def _section(text: str, title: str) -> str | None:
    """`## <title>` 로 시작하는 절의 본문. 없으면 None. 제목 뒤에 덧붙인 말(`## 구조 (폴더)`)은 허용한다."""
    match = re.search(
        rf"^## {re.escape(title)}\b.*?$(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL
    )
    return match.group(1) if match else None


def check_structure(files: dict[str, str], folders: list[str]) -> None:
    """폴더별 AGENTS.md 의 고정 섹션과 루트 구조도를 확인한다. 빠지면 작업자가 경로를 매번 다르게 잡는다."""
    for folder in folders:
        name = f"{folder}/AGENTS.md"
        missing = [t for t in FOLDER_SECTIONS if _section(files[name], t) is None]
        if missing:
            raise LLMCallError(f"{name} 에 빠진 섹션: {missing}")
    structure = _section(files["AGENTS.md"], STRUCTURE_SECTION)
    if structure is None:
        raise LLMCallError(f"AGENTS.md 에 '## {STRUCTURE_SECTION}' 섹션이 없음")
    missing = [f"{p}/" for p in ["docs", *folders] if f"{p}/" not in structure]
    if missing:
        raise LLMCallError(f"AGENTS.md 구조도에 빠진 폴더: {missing}")


def _spec_line(item: SpecItem) -> str:
    # 기술 항목의 내용은 여러 줄(선택·버전·이유·검증)이다 — 항목 아래 목록으로 내려 적는다.
    lines = [
        line.strip() for line in item["content"].strip().splitlines() if line.strip()
    ]
    if len(lines) == 1:
        return f"- {item['name']}: {lines[0]}"
    return "\n".join([f"- {item['name']}", *(f"  - {line}" for line in lines)])


def with_decisions(spec: str, items: list[SpecItem]) -> str:
    """LLM 이 쓴 스펙 뒤에 결정 두 절을 스펙 항목에서 그대로 그려 붙인다.

    LLM 은 "작업자가 정하는 것" 절에 기본 방향이 비어 있던 항목과 스스로 더 정한 기본값만 쓴다. 그 줄들은 절 끝에 잇는다.
    """
    added = (_section(spec, WORKER_SECTION) or "").replace(WORKER_LEAD, "").strip()
    for title in (USER_SECTION, WORKER_SECTION):
        spec = re.sub(
            rf"^## {re.escape(title)}\b.*?(?=^## |\Z)",
            "",
            spec,
            flags=re.MULTILINE | re.DOTALL,
        )
    # 기본 방향이 비어 있던 항목을 LLM 이 빠뜨려도 실행을 멈추지 않는다 — 작업자가 되묻지 않도록 정하는 쪽을 적어 둔다.
    left = [
        f"- {i['name']}: 정해진 방향이 없다. {USER_SECTION}에 맞는 기본값을 정하고 무엇으로 정했는지 한 줄로 알린다."
        for i in items
        if not _is_user_decision(i)
        and not i["content"].strip()
        and i["name"] not in added
    ]
    # "미리보기 확인: 맞아요" 는 빌더 화면의 확인 절차일 뿐 프로그램에 대한 결정이 아니다 — 작업자에게 줄 내용이 없다.
    items = [i for i in items if i["id"] != PREVIEW_ITEM_ID]
    user = [_spec_line(i) for i in items if _is_user_decision(i)]
    worker = [
        _spec_line(i)
        for i in items
        if not _is_user_decision(i) and i["content"].strip()
    ]
    return (
        "\n".join(
            [spec.rstrip(), "", f"## {USER_SECTION}", *(user or ["(없음)"])]
            + ["", f"## {WORKER_SECTION}", WORKER_LEAD, "", *worker]
            + ([added] if added else [])
            + left
        )
        + "\n"
    )


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
    folders: list[str],
) -> dict[str, str]:
    """LLM 이 쓴 문서·스킬 본문과 공통 스킬 원문을 산출물 경로 → 내용으로 조립한다."""
    # CLAUDE.md 는 본문 없이 임포트 한 줄로 고정 (루트 "산출물 규칙") — LLM 에 맡기지 않는다.
    artifacts = {name: files[name] for name in _doc_files(folders)}
    for base in ["", *(f"{folder}/" for folder in folders)]:
        artifacts[f"{base}CLAUDE.md"] = CLAUDE_IMPORT
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


def _doc_files(folders: list[str]) -> list[str]:
    return [*DOC_FILES, *(f"{folder}/AGENTS.md" for folder in folders)]


def make_generate_artifacts(llm: LLMClient):
    """LLM 클라이언트를 주입한 generate_artifacts 노드를 만든다."""
    system = load_prompt("generate_artifacts")

    skill_template = (TEMPLATES_DIR / "SKILL.md").read_text(encoding="utf-8")

    def generate_artifacts(state: State) -> dict:
        skills = state["skills"]
        folders = program_folders(state["spec_items"])
        required = [
            *_doc_files(folders),
            *(_body_file(s) for s in skills if s["source"] == "new"),
        ]
        files = parse_files(llm.complete(system, render_context(state)), required)
        check_structure(files, folders)
        files[SPEC_FILE] = with_decisions(files[SPEC_FILE], state["spec_items"])
        return {
            "artifacts": assemble(
                skills, files, load_common_skills(), skill_template, folders
            )
        }

    return generate_artifacts
