"""버전 비교·안정판 판정·범위 판정. 저장소마다 버전 문법이 달라서 저장소 이름을 같이 받는다."""

import re

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

_SEMVER = re.compile(
    r"^v?(\d+|[xX*])(?:\.(\d+|[xX*]))?(?:\.(\d+|[xX*]))?(?:-[0-9A-Za-z.-]+)?(?:\+\S*)?$"
)
# 구분자로 자른 조각 단위로 본다 — 부분 문자열로 찾으면 "RELEASE" 안의 "ea" 같은 것이 걸린다.
_MAVEN_UNSTABLE = {
    "alpha",
    "a",
    "beta",
    "b",
    "rc",
    "cr",
    "m",
    "milestone",
    "snapshot",
    "preview",
    "ea",
    "incubating",
    "dev",
}


def is_stable(registry: str, version: str) -> bool:
    """프리릴리스(rc·beta·canary·SNAPSHOT 등)가 아닌가."""
    if registry == "npm":
        return "-" not in version.split("+")[0]
    if registry == "pypi":
        try:
            parsed = Version(version)
        except InvalidVersion:
            return False
        return not (parsed.is_prerelease or parsed.is_devrelease)
    if registry == "maven":
        tokens = re.split(r"[.\-_]", version.lower())
        return not any(re.sub(r"^\d+|\d+$", "", t) in _MAVEN_UNSTABLE for t in tokens)
    return True


def sort_key(version: str) -> tuple:
    """저장소 공통 정렬 키. 숫자 부분만 비교한다 — 안정판끼리 최신을 고르는 데만 쓰므로 이걸로 충분하다."""
    return tuple(int(n) for n in re.findall(r"\d+", version.split("-")[0]))


def latest_stable(registry: str, versions: list[str]) -> str | None:
    stable = [v for v in versions if is_stable(registry, v)]
    return max(stable, key=sort_key) if stable else None


def latest_in_major(registry: str, versions: list[str], version: str) -> str | None:
    """고른 버전과 같은 메이저의 최신 안정판 — 고치는 쪽(select_stack)이 메이저를 바꾸지 않고 고칠 수 있게."""
    major = sort_key(version)[:1]
    same = [v for v in versions if sort_key(v)[:1] == major]
    return latest_stable(registry, same)


def python_satisfies(version: str, requires_python: str) -> bool | None:
    """PEP 440 `requires_python` 판정. 해석하지 못하면 None (모름)."""
    try:
        return SpecifierSet(requires_python).contains(Version(version))
    except InvalidSpecifier, InvalidVersion:
        return None


def java_satisfies(major: int, supported: str) -> bool | None:
    """endoflife.date 의 `supportedJavaVersions` ("17 - 26", "17+", "8, 11, 17") 판정. 해석하지 못하면 None."""
    text = supported.strip()
    if m := re.fullmatch(r"(\d+)\s*-\s*(\d+)", text):
        return int(m[1]) <= major <= int(m[2])
    if m := re.fullmatch(r"(\d+)\s*\+", text):
        return major >= int(m[1])
    if re.fullmatch(r"\d+(\s*,\s*\d+)*", text):
        return major in {int(n) for n in re.findall(r"\d+", text)}
    return None


def npm_satisfies(version: str, range_text: str) -> bool | None:
    """npm semver 범위 판정. `^ ~ >= > <= < = x * ||` 와 하이픈 범위만 다룬다. 해석하지 못하면 None (모름).

    고른 버전은 안정판이라는 전제 — 범위 안의 프리릴리스 표기는 숫자 부분만 비교한다.
    """
    target = _parse(version)
    if target is None or None in target:
        return None
    unknown = False
    for alternative in range_text.split("||"):
        bounds = _desugar(alternative.strip())
        if bounds is None:
            unknown = True
            continue
        if all(_compare(target, op, v) for op, v in bounds):
            return True
    return None if unknown else False


def _parse(text: str) -> tuple | None:
    m = _SEMVER.match(text.strip().lstrip("="))
    if not m:
        return None
    return tuple(
        None if part is None or part in "xX*" else int(part) for part in m.groups()
    )


def _desugar(text: str) -> list[tuple[str, tuple]] | None:
    if text in ("", "*", "x", "X", "latest"):
        return []
    if m := re.fullmatch(r"(\S+)\s+-\s+(\S+)", text):
        low, high = _parse(m[1]), _parse(m[2])
        if low is None or high is None:
            return None
        return _expand(">=", low) + _expand("<=", high)
    bounds = []
    for token in re.findall(r"(?:[<>]=?|=|\^|~>?)?\s*[^\s<>=^~]+", text):
        m = re.fullmatch(r"([<>]=?|=|\^|~>?)?\s*(.+)", token)
        parsed = _parse(m[2])
        if parsed is None:
            return None
        expanded = _expand(m[1] or "", parsed)
        if expanded is None:
            return None
        bounds += expanded
    return bounds


def _expand(op: str, v: tuple) -> list[tuple[str, tuple]] | None:
    major, minor, patch = v
    if major is None:
        return [] if op in ("", "=", ">=", "<=", "^", "~", "~>") else None
    filled = (major, minor or 0, patch or 0)
    if op in ("", "="):
        if minor is None:
            return [(">=", filled), ("<", (major + 1, 0, 0))]
        if patch is None:
            return [(">=", filled), ("<", (major, minor + 1, 0))]
        return [("=", filled)]
    if op == "^":
        if major > 0 or minor is None:
            return [(">=", filled), ("<", (major + 1, 0, 0))]
        if minor > 0 or patch is None:
            return [(">=", filled), ("<", (0, minor + 1, 0))]
        return [(">=", filled), ("<", (0, 0, patch + 1))]
    if op in ("~", "~>"):
        if minor is None:
            return [(">=", filled), ("<", (major + 1, 0, 0))]
        return [(">=", filled), ("<", (major, minor + 1, 0))]
    if op == ">=":
        return [(">=", filled)]
    if op == "<":
        return [("<", filled)]
    if op == ">":
        if minor is None:
            return [(">=", (major + 1, 0, 0))]
        if patch is None:
            return [(">=", (major, minor + 1, 0))]
        return [(">", filled)]
    if op == "<=":
        if minor is None:
            return [("<", (major + 1, 0, 0))]
        if patch is None:
            return [("<", (major, minor + 1, 0))]
        return [("<=", filled)]
    return None


def _compare(target: tuple, op: str, bound: tuple) -> bool:
    return {
        "=": target == bound,
        ">=": target >= bound,
        ">": target > bound,
        "<=": target <= bound,
        "<": target < bound,
    }[op]
