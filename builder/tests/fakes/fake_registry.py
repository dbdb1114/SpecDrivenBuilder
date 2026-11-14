from specbuilder.registry import Cycle, PackageNotFound, RegistryError, Release


def cycle(name: str, latest: str, eol: bool = False, java: str | None = None) -> Cycle:
    return Cycle(
        name=name,
        is_eol=eol,
        eol_from="2020-01-01" if eol else "2028-04-30",
        latest=latest,
        supported_java=java,
    )


# 기본 저장소 내용. fake_llm 의 select_stack 기본 응답(next@16.4.6 + react@19.2.0 + nodejs 24)이 그대로 통과하도록 맞춰 둔다.
DEFAULT_RELEASES = {
    ("npm", "next"): {
        "15.5.0": Release("15.5.0", node_range=">=18.18.0"),
        "16.4.6": Release(
            "16.4.6",
            node_range=">=20.9.0",
            peers={"react": "^18.2.0 || ^19.0.0", "react-dom": "^18.2.0 || ^19.0.0"},
        ),
        "16.5.0-canary.1": Release("16.5.0-canary.1"),
    },
    ("npm", "react"): {"18.3.1": Release("18.3.1"), "19.2.0": Release("19.2.0")},
    ("pypi", "fastapi"): {
        "0.162.5": Release("0.162.5", requires_python=">=3.10"),
        "0.99.0": Release("0.99.0", requires_python=">=3.7"),
    },
    ("maven", "org.springframework.boot:spring-boot"): {
        "3.5.7": Release("3.5.7"),
        "4.1.2": Release("4.1.2"),
        "4.2.0-RC2": Release("4.2.0-RC2"),
    },
}
DEFAULT_CYCLES = {
    "nodejs": [
        cycle("26", "26.13.1"),
        cycle("24", "24.11.1"),
        cycle("18", "18.20.8", eol=True),
    ],
    "python": [cycle("3.14", "3.14.10"), cycle("3.9", "3.9.25", eol=True)],
    "eclipse-temurin": [
        cycle("25", "25.0.1"),
        cycle("21", "21.0.9"),
        cycle("11", "11.0.29"),
    ],
    "nextjs": [
        cycle("16", "16.4.6"),
        cycle("15", "15.5.0"),
        cycle("13", "13.5.11", eol=True),
    ],
    "react": [cycle("19", "19.2.0"), cycle("18", "18.3.1")],
    "spring-boot": [
        cycle("4.1", "4.1.2", java="17 - 26"),
        cycle("3.5", "3.5.7", java="17 - 25"),
        cycle("2.7", "2.7.18", eol=True, java="8 - 21"),
    ],
}


class FakeRegistry:
    """미리 정한 버전 목록을 돌려주는 가짜 저장소. `offline=True` 면 모든 조회가 접속 실패를 흉내 낸다."""

    def __init__(
        self,
        releases: dict | None = None,
        cycles: dict | None = None,
        offline: bool = False,
    ):
        self._releases = DEFAULT_RELEASES | (releases or {})
        self._cycles = DEFAULT_CYCLES | (cycles or {})
        self.offline = offline
        self.lookups: list[tuple] = []

    def releases(self, registry: str, name: str) -> dict[str, Release]:
        self.lookups.append(("releases", registry, name))
        if self.offline:
            raise RegistryError("접속 실패 (가짜)")
        if (registry, name) not in self._releases:
            raise PackageNotFound(f"{registry} {name} 없음")
        return self._releases[(registry, name)]

    def cycles(self, product: str) -> list[Cycle]:
        self.lookups.append(("cycles", product))
        if self.offline:
            raise RegistryError("접속 실패 (가짜)")
        if product not in self._cycles:
            raise PackageNotFound(f"endoflife {product} 없음")
        return self._cycles[product]
