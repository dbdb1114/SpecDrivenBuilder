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


def render_content(choice: str, refs: list[PackageRef], reason: str) -> str:
    lines = [CHOICE_PREFIX + choice]
    if refs:
        lines.append(VERSIONS_PREFIX + ", ".join(ref.render() for ref in refs))
    lines.append(REASON_PREFIX + reason)
    return "\n".join(lines)


def parse_refs(content: str) -> list[PackageRef]:
    return [PackageRef(*m) for m in _REF.findall(content)]


def replace_ref(content: str, old: PackageRef, new: PackageRef) -> str:
    return content.replace(old.render(), new.render())


def with_verify_line(content: str, line: str) -> str:
    """검증 줄을 붙인다. 이미 있으면 교체 — 다시 검증할 때 지난 결과가 남지 않게."""
    kept = [ln for ln in content.splitlines() if not ln.startswith(VERIFY_PREFIX)]
    return "\n".join([*kept, VERIFY_PREFIX + line])
