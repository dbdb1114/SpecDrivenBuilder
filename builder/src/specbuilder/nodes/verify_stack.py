from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date

from langgraph.types import Command

from specbuilder.llm import LLMClient
from specbuilder.registry.client import (
    Cycle,
    HTTPRegistry,
    PackageNotFound,
    Registry,
    RegistryError,
    Release,
)
from specbuilder.registry.refs import (
    PackageRef,
    parse_refs,
    replace_ref,
    with_verify_line,
)
from specbuilder.registry.versions import (
    is_stable,
    java_satisfies,
    latest_in_major,
    latest_stable,
    npm_satisfies,
    python_satisfies,
    sort_key,
)
from specbuilder.state import State

NODE = "verify_stack"
NEXT = "select_skills"
BACK = "select_stack"
# 실제 버전 목록을 받으면 보통 1회에 고쳐진다. 2회 뒤에도 맞지 않으면 코드가 최신 안정판으로 바꾼다.
MAX_VERIFY_RETURNS = 2
# 패키지 저장소에는 지원 종료 정보가 없어서 endoflife.date 제품으로 대신 본다. 제품이 있는 것만 (2026-11-13 확인).
EOL_PRODUCTS = {
    ("npm", "next"): "nextjs",
    ("npm", "react"): "react",
    ("npm", "vue"): "vue",
    ("npm", "@angular/core"): "angular",
    ("npm", "nuxt"): "nuxt",
    ("npm", "svelte"): "svelte",
    ("npm", "express"): "express",
    ("pypi", "django"): "django",
    ("pypi", "Django"): "django",
}
SPRING_BOOT_GROUP = "org.springframework.boot"
JAVA_PRODUCTS = {"eclipse-temurin", "amazon-corretto", "oracle-jdk"}
LOOKUP_WORKERS = 8


@dataclass
class PackageCheck:
    ref: PackageRef
    problems: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    unverified: str | None = None
    fix: PackageRef | None = None
    # 호환 판정에 쓰는 실제 버전 — eol 계열("24")이면 그 계열의 최신 버전("24.13.1").
    effective: str | None = None
    release: Release | None = None
    cycle: Cycle | None = None


def _eol_product(ref: PackageRef) -> str | None:
    if ref.registry == "maven" and ref.name.split(":")[0] == SPRING_BOOT_GROUP:
        return "spring-boot"
    return EOL_PRODUCTS.get((ref.registry, ref.name))


def _keys(ref: PackageRef) -> list[tuple]:
    if ref.registry == "eol":
        return [("cycles", ref.name)]
    keys = [("releases", ref.registry, ref.name)]
    if product := _eol_product(ref):
        keys.append(("cycles", product))
    return keys


def _fetch(registry: Registry, refs: list[PackageRef]) -> dict:
    """조회 결과 또는 RegistryError 를 키별로 담는다. 한 패키지의 실패가 다른 패키지 검증을 막지 않게 예외를 값으로 둔다."""
    keys = list(dict.fromkeys(k for ref in refs for k in _keys(ref)))

    def lookup(key):
        try:
            if key[0] == "cycles":
                return registry.cycles(key[1])
            return registry.releases(key[1], key[2])
        except RegistryError as e:
            return e

    # 조회는 네트워크 대기가 대부분이라 스레드로 동시에 보낸다 (GIL 영향 없음).
    with ThreadPoolExecutor(max_workers=LOOKUP_WORKERS) as pool:
        return dict(zip(keys, pool.map(lookup, keys)))


def _match_cycle(cycles: list[Cycle], version: str) -> Cycle | None:
    matches = [
        c for c in cycles if version == c.name or version.startswith(c.name + ".")
    ]
    return max(matches, key=lambda c: len(c.name)) if matches else None


def _supported(cycles: list[Cycle]) -> list[Cycle]:
    return sorted(
        (c for c in cycles if not c.is_eol),
        key=lambda c: sort_key(c.name),
        reverse=True,
    )


def _cycle_names(cycles: list[Cycle]) -> str:
    return ", ".join(c.name for c in _supported(cycles)[:4]) or "없음"


def _check_eol_ref(check: PackageCheck, cycles: list[Cycle]) -> None:
    ref = check.ref
    supported = _supported(cycles)
    newest = (
        PackageRef(ref.registry, ref.name, supported[0].name) if supported else None
    )
    cycle = _match_cycle(cycles, ref.version)
    if cycle is None:
        check.problems.append(
            f"{ref.label}: endoflife.date 에 없는 계열. 지원 중인 계열: {_cycle_names(cycles)}"
        )
        check.fix = newest
        return
    check.cycle = cycle
    check.effective = (
        ref.version if ref.version.count(".") >= 2 else (cycle.latest or ref.version)
    )
    if cycle.is_eol:
        check.problems.append(
            f"{ref.label}: 지원 종료된 계열 (종료 {cycle.eol_from or '날짜 모름'}). 지원 중인 계열: {_cycle_names(cycles)}"
        )
        check.fix = newest
        return
    check.notes.append(
        f"{ref.label} 지원 중 (최신 {check.effective}, 종료 예정 {cycle.eol_from or '미정'})"
    )


def _check_package_ref(
    check: PackageCheck, releases: dict[str, Release], fetched: dict
) -> None:
    ref = check.ref
    usable = [v for v, r in releases.items() if not r.withdrawn]
    newest = latest_stable(ref.registry, usable)
    same_major = latest_in_major(ref.registry, usable, ref.version)
    hint = f"{ref.registry} 최신 안정판 {newest or '없음'}" + (
        f", 같은 메이저 최신 {same_major}"
        if same_major and same_major != newest
        else ""
    )
    fix = PackageRef(ref.registry, ref.name, newest) if newest else None
    release = releases.get(ref.version)
    if release is None:
        check.problems.append(f"{ref.label}: 저장소에 없는 버전. {hint}")
        check.fix = fix
        return
    if not is_stable(ref.registry, ref.version):
        check.problems.append(f"{ref.label}: 안정판이 아님 (프리릴리스). {hint}")
        check.fix = fix
        return
    if release.withdrawn:
        check.problems.append(
            f"{ref.label}: 저장소에서 쓰지 말라고 표시됨 ({release.withdrawn}). {hint}"
        )
        check.fix = fix
        return
    check.release = release
    check.effective = ref.version
    status = f"{ref.label} 있음·안정판"

    product = _eol_product(ref)
    if product is None:
        check.notes.append(f"{status}, 지원 종료 정보 없음")
        return
    cycles = fetched[("cycles", product)]
    if isinstance(cycles, RegistryError):
        check.notes.append(f"{status}, 지원 종료 여부는 확인하지 못함 ({cycles})")
        return
    cycle = _match_cycle(cycles, ref.version)
    if cycle is None:
        check.notes.append(f"{status}, endoflife.date 에 이 계열 정보 없음")
        return
    check.cycle = cycle
    if cycle.is_eol:
        check.problems.append(
            f"{ref.label}: 지원 종료된 계열 {cycle.name} (종료 {cycle.eol_from or '날짜 모름'}). "
            f"지원 중인 계열: {_cycle_names(cycles)}. {hint}"
        )
        check.fix = fix
        return
    check.notes.append(f"{status}·지원 중 (종료 예정 {cycle.eol_from or '미정'})")


def _check_ref(ref: PackageRef, fetched: dict) -> PackageCheck:
    check = PackageCheck(ref)
    data = fetched[_keys(ref)[0]]
    if isinstance(data, PackageNotFound):
        where = "endoflife.date" if ref.registry == "eol" else ref.registry
        check.problems.append(f"{ref.label}: {where} 에 없는 이름")
    elif isinstance(data, RegistryError):
        check.unverified = f"{ref.label} ({data})"
    elif ref.registry == "eol":
        _check_eol_ref(check, data)
    else:
        _check_package_ref(check, data, fetched)
    return check


def _check_compat(checks: dict[str, list[PackageCheck]]) -> dict[str, list[str]]:
    """저장소에 있는 정보로만 함께 쓰는 것끼리 맞는지 본다. 판정한 문장을 항목별로 돌려준다 (문제는 PackageCheck 에 붙인다)."""
    ok = [c for cs in checks.values() for c in cs if c.effective and not c.problems]
    runtime = {c.ref.name: c for c in ok if c.ref.registry == "eol"}
    npm = {c.ref.name: c for c in ok if c.ref.registry == "npm"}
    java = next((c for name, c in runtime.items() if name in JAVA_PRODUCTS), None)
    ok_ids = {id(c) for c in ok}
    notes = {}

    def judge(
        item_id: str, check: PackageCheck, text: str, result: bool | None
    ) -> None:
        if result is False:
            check.problems.append(f"{text} — 맞지 않음")
        else:
            notes.setdefault(item_id, []).append(
                f"{text} — {'맞음' if result else '범위를 해석하지 못함'}"
            )

    for item_id, item_checks in checks.items():
        for check in item_checks:
            if id(check) not in ok_ids:
                continue
            release, label = check.release, check.ref.label
            if release and release.node_range and "nodejs" in runtime:
                node = runtime["nodejs"]
                judge(
                    item_id, check,
                    f"{label} 의 요구 Node {release.node_range} ↔ {node.ref.label}({node.effective})",
                    npm_satisfies(node.effective, release.node_range),
                )  # fmt: skip
            if release:
                for peer, peer_range in release.peers.items():
                    if peer in npm:
                        judge(
                            item_id, check,
                            f"{label} 의 피어 {peer} {peer_range} ↔ {npm[peer].ref.label}",
                            npm_satisfies(npm[peer].effective, peer_range),
                        )  # fmt: skip
            if release and release.requires_python and "python" in runtime:
                python = runtime["python"]
                judge(
                    item_id, check,
                    f"{label} 의 요구 Python {release.requires_python} ↔ {python.ref.label}({python.effective})",
                    python_satisfies(python.effective, release.requires_python),
                )  # fmt: skip
            if check.cycle and check.cycle.supported_java and java:
                major = sort_key(java.effective)[0]
                judge(
                    item_id, check,
                    f"{label} 의 지원 Java {check.cycle.supported_java} ↔ {java.ref.label}",
                    java_satisfies(major, check.cycle.supported_java),
                )  # fmt: skip
    return notes


def _analyze(refs: dict[str, list[PackageRef]], fetched: dict):
    checks = {
        item_id: [_check_ref(ref, fetched) for ref in item_refs]
        for item_id, item_refs in refs.items()
    }
    return checks, _check_compat(checks)


def _verify_line(
    today: str, checks: list[PackageCheck], compat: list[str], fixed: list[str]
) -> str:
    problems = [p for c in checks for p in c.problems]
    unverified = [c.unverified for c in checks if c.unverified]
    if problems:
        status = "맞지 않음"
    elif unverified:
        status = "일부 검증하지 못함"
    else:
        status = "확인됨"
    parts = [f"{today} 저장소 확인 [{status}]"]
    parts += fixed
    parts += problems
    if unverified:
        parts.append("저장소에 접속하지 못해 검증하지 못함: " + ", ".join(unverified))
    parts += [n for c in checks for n in c.notes]
    parts += compat or ["함께 쓰는 것끼리의 호환: 저장소에 정보 없음"]
    return "; ".join(parts)


def make_verify_stack(
    llm: LLMClient, registry: Registry | None = None, today: str | None = None
):
    """verify_stack 노드를 만든다. LLM 은 쓰지 않는다 — 그래프 조립이 모든 노드에 같은 인자를 넘기므로 받기만 한다.

    registry 를 주지 않으면 실제 저장소(HTTP)에 묻는다. 테스트는 가짜를 주입한다.
    """
    source = registry or HTTPRegistry()

    def verify_stack(state: State) -> Command:
        items = state["spec_items"]
        refs = {
            item["id"]: parse_refs(item["content"])
            for item in items
            if item["area"] == "tech" and parse_refs(item["content"])
        }
        if not refs:
            return Command(update={"stack_mismatches": []}, goto=NEXT)

        fetched = _fetch(source, [r for rs in refs.values() for r in rs])
        checks, compat = _analyze(refs, fetched)
        mismatches = [
            {"item_id": item_id, "reason": "; ".join(p for c in cs for p in c.problems)}
            for item_id, cs in checks.items()
            if any(c.problems for c in cs)
        ]
        returns = state["verify_returns"]
        if mismatches and returns < MAX_VERIFY_RETURNS:
            return Command(
                update={"stack_mismatches": mismatches, "verify_returns": returns + 1},
                goto=BACK,
            )

        contents = {item["id"]: item["content"] for item in items}
        fixed = {}
        if mismatches:
            # 상한: 더 돌아가지 않고 저장소의 최신 안정판으로 바꾼다. 바꾼 버전으로 다시 판정해 남은 문제는 그대로 적는다.
            for item_id, cs in checks.items():
                for c in cs:
                    if c.problems and c.fix and c.fix != c.ref:
                        contents[item_id] = replace_ref(contents[item_id], c.ref, c.fix)
                        refs[item_id] = [
                            c.fix if r == c.ref else r for r in refs[item_id]
                        ]
                        fixed.setdefault(item_id, []).append(
                            f"검증 왕복 상한({MAX_VERIFY_RETURNS}회)에 닿아 {c.ref.label} 를 저장소 최신 안정판 {c.fix.label} 로 바꿈"
                        )
            fetched |= _fetch(
                source,
                [
                    r
                    for rs in refs.values()
                    for r in rs
                    if any(k not in fetched for k in _keys(r))
                ],
            )
            checks, compat = _analyze(refs, fetched)

        day = today or date.today().isoformat()
        updated = [
            {
                **item,
                "content": with_verify_line(
                    contents[item["id"]],
                    _verify_line(
                        day,
                        checks[item["id"]],
                        compat.get(item["id"], []),
                        fixed.get(item["id"], []),
                    ),
                ),
            }
            if item["id"] in checks
            else item
            for item in items
        ]
        return Command(
            update={"spec_items": updated, "stack_mismatches": []}, goto=NEXT
        )

    return verify_stack
