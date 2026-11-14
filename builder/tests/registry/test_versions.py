import pytest

from specbuilder.registry.client import _cycles, _maven, _npm, _pypi
from specbuilder.registry.versions import (
    is_stable,
    java_satisfies,
    latest_in_major,
    latest_stable,
    npm_satisfies,
    python_satisfies,
)


@pytest.mark.parametrize(
    ("version", "range_text", "expected"),
    [
        ("19.2.0", "^18.2.0 || ^19.0.0", True),
        ("17.0.2", "^18.2.0 || ^19.0.0", False),
        ("24.11.1", ">=20.9.0", True),
        ("20.8.0", ">=20.9.0", False),
        ("1.2.9", "~1.2.3", True),
        ("1.3.0", "~1.2.3", False),
        ("0.2.5", "^0.2.3", True),
        ("0.3.0", "^0.2.3", False),
        ("2.5.0", ">=1.2.3 <3.0.0", True),
        ("3.0.0", ">=1.2.3 <3.0.0", False),
        ("1.9.0", "1.x", True),
        ("2.0.0", "1.x", False),
        ("1.5.0", "1.2.3 - 1.8", True),
        ("1.9.0", "1.2.3 - 1.8", False),
        ("5.0.0", "*", True),
        ("19.0.0", "19.0.0-rc-de68d2f4-20241204 || ^19.0.0", True),
        ("18.0.0", "^18.2.0 || ^20", False),
    ],
)
def test_npm_satisfies(version, range_text, expected):
    assert npm_satisfies(version, range_text) is expected


def test_npm_unparseable_range_is_unknown():
    assert npm_satisfies("1.0.0", "workspace:*") is None
    # 해석 가능한 쪽이 맞으면 맞음
    assert npm_satisfies("1.0.0", "workspace:* || ^1.0.0") is True


def test_stability_per_registry():
    assert is_stable("npm", "16.4.6") and not is_stable("npm", "16.5.0-canary.1")
    assert is_stable("pypi", "0.162.5") and not is_stable("pypi", "2.0.0rc1")
    assert not is_stable("pypi", "1.0.dev3")
    assert is_stable("maven", "4.1.2") and is_stable("maven", "2.7.0.RELEASE")
    assert is_stable("maven", "33.0.0-jre")
    for unstable in ("4.2.0-RC2", "4.0.0-M3", "1.0-SNAPSHOT", "6.0.0.Beta1"):
        assert not is_stable("maven", unstable), unstable


def test_latest_stable_and_same_major():
    versions = ["15.5.0", "16.4.6", "16.10.0", "16.5.0-canary.1"]
    assert latest_stable("npm", versions) == "16.10.0"
    assert latest_in_major("npm", versions, "15.0.0") == "15.5.0"
    assert latest_stable("npm", ["1.0.0-rc.1"]) is None


def test_python_and_java():
    assert python_satisfies("3.14.10", ">=3.10") is True
    assert python_satisfies("3.9.25", ">=3.10") is False
    assert python_satisfies("3.9", "not a spec") is None
    assert java_satisfies(21, "17 - 26") is True
    assert java_satisfies(11, "17 - 26") is False
    assert java_satisfies(25, "17+") is True
    assert java_satisfies(11, "8, 11, 17") is True
    assert java_satisfies(21, "모름") is None


def test_parsers_read_real_response_shapes():
    # 2026-11-13 실제 응답에서 필요한 필드만 남긴 모양
    npm = _npm(
        {
            "versions": {
                "16.4.6": {
                    "engines": {"node": ">=20.9.0"},
                    "peerDependencies": {"react": "^19.0.0"},
                },
                "1.0.0": {"deprecated": "쓰지 마세요"},
            }
        }
    )
    assert npm["16.4.6"].node_range == ">=20.9.0" and npm["16.4.6"].peers == {
        "react": "^19.0.0"
    }
    assert npm["1.0.0"].withdrawn == "쓰지 마세요"

    pypi = _pypi(
        {
            "releases": {
                "0.162.5": [{"requires_python": ">=3.10", "yanked": False}],
                "0.1.0": [{"yanked": True, "yanked_reason": "깨짐"}],
                "0.0.1": [],
            }
        }
    )
    assert pypi["0.162.5"].requires_python == ">=3.10"
    assert pypi["0.1.0"].withdrawn == "깨짐"
    assert "0.0.1" not in pypi

    maven = _maven(
        b"<metadata><versioning><versions><version>4.1.2</version><version>4.2.0-RC2</version>"
        b"</versions></versioning></metadata>"
    )
    assert list(maven) == ["4.1.2", "4.2.0-RC2"]

    (spring,) = _cycles(
        {
            "result": {
                "releases": [
                    {
                        "name": "4.1",
                        "isEol": False,
                        "eolFrom": "2027-07-31",
                        "latest": {"name": "4.1.2"},
                        "custom": {"supportedJavaVersions": "17 - 26"},
                    }
                ]
            }
        }
    )
    assert (
        spring.latest == "4.1.2"
        and spring.supported_java == "17 - 26"
        and not spring.is_eol
    )
