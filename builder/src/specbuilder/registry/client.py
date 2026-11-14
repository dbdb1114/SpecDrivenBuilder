"""패키지 저장소 조회. verify_stack 이 LLM 의 기억 대신 쓰는 실제 버전 정보의 출처."""

import json
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Literal, Protocol

RegistryName = Literal["npm", "pypi", "maven", "eol"]

# 이름 형식을 먼저 검사한다 — LLM 이 낸 문자열이 URL 경로에 그대로 들어가므로.
NAME_PATTERNS = {
    "npm": re.compile(r"^(@[a-z0-9][a-z0-9._~-]*/)?[a-z0-9][a-z0-9._~-]*$"),
    "pypi": re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$"),
    "maven": re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*:[A-Za-z0-9][A-Za-z0-9._-]*$"),
    "eol": re.compile(r"^[a-z0-9][a-z0-9-]*$"),
}
VERSION_PATTERN = re.compile(r"^[0-9A-Za-z][0-9A-Za-z.+_-]*$")

TIMEOUT_SECONDS = 10


class RegistryError(Exception):
    """저장소에 접속하지 못했거나 응답을 읽지 못함 — 검증하지 못한 것으로 다룬다."""


class PackageNotFound(RegistryError):
    """저장소가 그런 패키지는 없다고 답함 — 검증 실패(맞지 않음)로 다룬다."""


# dataclass(frozen) — 조회 결과는 State 에 들어가지 않는 내부 값이라 TypedDict 보다 속성 접근·불변이 편하다.
@dataclass(frozen=True)
class Release:
    version: str
    # npm 의 deprecated 메시지, PyPI 의 yanked 사유. 있으면 쓰면 안 되는 버전.
    withdrawn: str | None = None
    node_range: str | None = None
    peers: dict[str, str] = field(default_factory=dict)
    requires_python: str | None = None


@dataclass(frozen=True)
class Cycle:
    """endoflife.date 의 릴리스 사이클 하나 (예: nodejs 24, spring-boot 4.1)."""

    name: str
    is_eol: bool
    eol_from: str | None
    latest: str | None
    supported_java: str | None = None


class Registry(Protocol):
    def releases(self, registry: RegistryName, name: str) -> dict[str, Release]:
        """npm·pypi·maven 패키지의 발행된 버전 전부. 없는 패키지면 PackageNotFound."""
        ...

    def cycles(self, product: str) -> list[Cycle]:
        """endoflife.date 제품의 릴리스 사이클. 없는 제품이면 PackageNotFound."""
        ...


class HTTPRegistry:
    """실제 저장소에 HTTP 로 묻는다. 표준 라이브러리만 쓴다 (조회 몇 건에 HTTP 클라이언트 의존성을 늘리지 않으려고)."""

    def releases(self, registry: RegistryName, name: str) -> dict[str, Release]:
        if registry == "npm":
            return _npm(self._json(f"https://registry.npmjs.org/{_quote(name)}"))
        if registry == "pypi":
            return _pypi(self._json(f"https://pypi.org/pypi/{_quote(name)}/json"))
        if registry == "maven":
            group, artifact = name.split(":")
            url = (
                "https://repo1.maven.org/maven2/"
                f"{_quote(group).replace('.', '/')}/{_quote(artifact)}/maven-metadata.xml"
            )
            return _maven(self._get(url))
        raise ValueError(f"releases 로 조회할 수 없는 저장소: {registry}")

    def cycles(self, product: str) -> list[Cycle]:
        data = self._json(f"https://endoflife.date/api/v1/products/{_quote(product)}")
        return _cycles(data)

    def _get(self, url: str) -> bytes:
        request = urllib.request.Request(url, headers={"User-Agent": "specbuilder"})
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                return response.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise PackageNotFound(f"{url} 없음 (404)") from e
            raise RegistryError(f"{url} HTTP {e.code}") from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise RegistryError(f"{url} 접속 실패: {e}") from e

    def _json(self, url: str) -> dict:
        try:
            return json.loads(self._get(url))
        except json.JSONDecodeError as e:
            raise RegistryError(f"{url} 응답이 JSON 이 아님") from e


def _quote(part: str) -> str:
    return urllib.parse.quote(part, safe="@")


def _npm(data: dict) -> dict[str, Release]:
    try:
        return {
            version: Release(
                version=version,
                withdrawn=meta.get("deprecated") or None,
                node_range=(meta.get("engines") or {}).get("node"),
                peers=dict(meta.get("peerDependencies") or {}),
            )
            for version, meta in data["versions"].items()
        }
    except (KeyError, AttributeError, TypeError) as e:
        raise RegistryError(f"npm 응답 형식이 예상과 다름: {e}") from e


def _pypi(data: dict) -> dict[str, Release]:
    result = {}
    try:
        for version, files in data["releases"].items():
            if not files:
                continue  # 파일 없는 릴리스는 설치할 수 없다
            yanked = [f for f in files if f.get("yanked")]
            result[version] = Release(
                version=version,
                withdrawn=(
                    (yanked[0].get("yanked_reason") or "yanked")
                    if len(yanked) == len(files)
                    else None
                ),
                requires_python=files[0].get("requires_python") or None,
            )
    except (KeyError, AttributeError, TypeError) as e:
        raise RegistryError(f"PyPI 응답 형식이 예상과 다름: {e}") from e
    return result


def _maven(body: bytes) -> dict[str, Release]:
    try:
        root = ET.fromstring(body)
    except ET.ParseError as e:
        raise RegistryError("Maven 메타데이터가 XML 이 아님") from e
    versions = [
        v.text for v in root.iterfind("./versioning/versions/version") if v.text
    ]
    return {v: Release(version=v) for v in versions}


def _cycles(data: dict) -> list[Cycle]:
    try:
        return [
            Cycle(
                name=r["name"],
                is_eol=bool(r.get("isEol")),
                eol_from=r.get("eolFrom"),
                latest=(r.get("latest") or {}).get("name"),
                supported_java=(r.get("custom") or {}).get("supportedJavaVersions"),
            )
            for r in data["result"]["releases"]
        ]
    except (KeyError, AttributeError, TypeError) as e:
        raise RegistryError(f"endoflife.date 응답 형식이 예상과 다름: {e}") from e
