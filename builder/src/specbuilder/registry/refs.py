"""기술 스펙 항목 content 안의 패키지 표기. select_stack 이 쓰고 verify_stack 이 읽는다.

스펙 항목 모델(content: str)을 고치지 않고 버전을 넘기려고, 사람이 읽을 수 있고 코드도 읽을 수 있는 한 줄 형식을 쓴다:
    버전: (npm: next@16.4.6), (eol: nodejs@24)
"""

import re
from dataclasses import dataclass

CHOICE_PREFIX = "선택: "
VERSIONS_PREFIX = "버전: "
REASON_PREFIX = "이유: "
VERIFY_PREFIX = "검증: "
# 프로그램의 부분 → 산출물 폴더. 어느 폴더를 넣을지는 LLM 이 쓴 글이 아니라 이 줄을 보고 빌더 코드가 정한다
# (docs/design/design.md "generate_artifacts" 의 산출물 폴더 구성).
PARTS_PREFIX = "부분: "
PART_LABELS = {"frontend": "화면", "backend": "서버", "database": "데이터베이스"}

_REF = re.compile(r"\((npm|pypi|maven|eol): (@?[^\s@()]+)@([^\s()]+)\)")


@dataclass(frozen=True)
class PackageRef:
    registry: str
    name: str
    version: str

    def render(self) -> str:
        return f"({self.registry}: {self.name}@{self.version})"

    @property
    def label(self) -> str:
        return f"{self.name}@{self.version}"


def render_content(
    choice: str, refs: list[PackageRef], reason: str, parts: list[str] | None = None
) -> str:
    lines = [CHOICE_PREFIX + choice]
    if refs:
        lines.append(VERSIONS_PREFIX + ", ".join(ref.render() for ref in refs))
    if parts:
        lines.append(PARTS_PREFIX + ", ".join(PART_LABELS[p] for p in parts))
    lines.append(REASON_PREFIX + reason)
    return "\n".join(lines)


def parse_refs(content: str) -> list[PackageRef]:
    return [PackageRef(*m) for m in _REF.findall(content)]


def parse_parts(content: str) -> list[str]:
    """`부분:` 줄의 부분 이름을 폴더 키(frontend·backend·database)로 돌려준다. 줄이 없으면 빈 목록."""
    folders = {label: key for key, label in PART_LABELS.items()}
    for line in content.splitlines():
        if line.startswith(PARTS_PREFIX):
            labels = [p.strip() for p in line[len(PARTS_PREFIX) :].split(",")]
            return [folders[label] for label in labels if label in folders]
    return []


def replace_ref(content: str, old: PackageRef, new: PackageRef) -> str:
    return content.replace(old.render(), new.render())


def with_verify_line(content: str, line: str) -> str:
    """검증 줄을 붙인다. 이미 있으면 교체 — 다시 검증할 때 지난 결과가 남지 않게."""
    kept = [ln for ln in content.splitlines() if not ln.startswith(VERIFY_PREFIX)]
    return "\n".join([*kept, VERIFY_PREFIX + line])
