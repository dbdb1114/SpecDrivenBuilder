from specbuilder.nodes.verify_stack import MAX_VERIFY_RETURNS, make_verify_stack
from specbuilder.registry import Release
from specbuilder.registry.refs import PackageRef, parse_refs, render_content
from specbuilder.state import initial_state
from tests.fakes.fake_llm import FakeLLM, item
from tests.fakes.fake_registry import FakeRegistry, cycle

TODAY = "2026-11-13"


def tech_item(id: str, *refs: tuple[str, str, str]) -> dict:
    content = render_content("고른 것", [PackageRef(*r) for r in refs], "이유")
    return item(
        id, status="delegated", content=content, decided_by="worker", area="tech"
    )


def _state(*tech_items, **overrides):
    state = initial_state("가계부")
    state["spec_items"] = [item("purpose"), *tech_items]
    return state | overrides


def _run(state, registry=None):
    llm = FakeLLM()
    registry = registry or FakeRegistry()
    result = make_verify_stack(llm, registry, TODAY)(state)
    assert llm.calls == []  # 저장소 조회는 LLM 호출이 아니다
    return result, registry


def _content(result, item_id):
    return next(i for i in result.update["spec_items"] if i["id"] == item_id)["content"]


NEXT_STACK = (
    tech_item("tech-runtime", ("eol", "nodejs", "24")),
    tech_item("tech-web", ("npm", "next", "16.4.6"), ("npm", "react", "19.2.0")),
)


def test_valid_stack_gets_verify_line_and_goes_on():
    result, _ = _run(_state(*NEXT_STACK))

    assert result.goto == "select_skills"
    web = _content(result, "tech-web")
    verify = web.splitlines()[-1]
    assert verify.startswith(f"검증: {TODAY} 저장소 확인 [확인됨]")
    assert "next@16.4.6 있음·안정판·지원 중" in verify
    assert "요구 Node >=20.9.0 ↔ nodejs@24(24.11.1) — 맞음" in verify
    assert "피어 react ^18.2.0 || ^19.0.0 ↔ react@19.2.0 — 맞음" in verify
    assert "nodejs@24 지원 중" in _content(result, "tech-runtime")
    # 버전 표기는 그대로 남아 있어야 다음 노드·재검증이 읽는다
    assert [r.label for r in parse_refs(web)] == ["next@16.4.6", "react@19.2.0"]
    assert result.update["stack_mismatches"] == []


def test_reverify_replaces_previous_verify_line():
    first, _ = _run(_state(*NEXT_STACK))
    again, _ = _run(_state(*first.update["spec_items"][1:]))
    assert _content(again, "tech-web").count("검증: ") == 1


def test_nonexistent_version_goes_back_with_real_versions():
    result, _ = _run(_state(tech_item("tech-web", ("npm", "next", "17.0.0"))))

    assert result.goto == "select_stack"
    assert result.update["verify_returns"] == 1
    (mismatch,) = result.update["stack_mismatches"]
    assert mismatch["item_id"] == "tech-web"
    assert "next@17.0.0: 저장소에 없는 버전" in mismatch["reason"]
    assert "npm 최신 안정판 16.4.6" in mismatch["reason"]
    assert "spec_items" not in result.update


def test_prerelease_is_a_mismatch():
    result, _ = _run(_state(tech_item("tech-web", ("npm", "next", "16.5.0-canary.1"))))
    assert "안정판이 아님" in result.update["stack_mismatches"][0]["reason"]


def test_withdrawn_version_is_a_mismatch():
    registry = FakeRegistry(
        releases={
            ("npm", "react"): {"19.2.0": Release("19.2.0", withdrawn="보안 문제")}
        }
    )
    result, _ = _run(
        _state(tech_item("tech-web", ("npm", "react", "19.2.0"))), registry
    )
    assert (
        "쓰지 말라고 표시됨 (보안 문제)"
        in result.update["stack_mismatches"][0]["reason"]
    )


def test_end_of_life_runtime_is_a_mismatch_with_supported_cycles():
    result, _ = _run(_state(tech_item("tech-runtime", ("eol", "nodejs", "18"))))
    reason = result.update["stack_mismatches"][0]["reason"]
    assert "지원 종료된 계열" in reason and "지원 중인 계열: 26, 24" in reason


def test_end_of_life_framework_cycle_is_a_mismatch():
    registry = FakeRegistry(releases={("npm", "next"): {"13.5.11": Release("13.5.11")}})
    result, _ = _run(
        _state(tech_item("tech-web", ("npm", "next", "13.5.11"))), registry
    )
    assert "지원 종료된 계열 13" in result.update["stack_mismatches"][0]["reason"]


def test_unknown_package_is_a_mismatch():
    result, _ = _run(_state(tech_item("tech-web", ("npm", "nextt", "1.0.0"))))
    assert "npm 에 없는 이름" in result.update["stack_mismatches"][0]["reason"]


def test_node_engine_incompatibility_is_a_mismatch():
    registry = FakeRegistry(cycles={"nodejs": [cycle("20", "20.8.0")]})
    result, _ = _run(
        _state(*NEXT_STACK[1:], tech_item("tech-runtime", ("eol", "nodejs", "20"))),
        registry,
    )
    reason = result.update["stack_mismatches"][0]["reason"]
    assert "요구 Node >=20.9.0 ↔ nodejs@20(20.8.0) — 맞지 않음" in reason


def test_peer_incompatibility_is_a_mismatch():
    registry = FakeRegistry(releases={("npm", "react"): {"17.0.2": Release("17.0.2")}})
    result, _ = _run(
        _state(
            tech_item("tech-web", ("npm", "next", "16.4.6"), ("npm", "react", "17.0.2"))
        ),
        registry,
    )
    assert (
        "피어 react ^18.2.0 || ^19.0.0 ↔ react@17.0.2 — 맞지 않음"
        in result.update["stack_mismatches"][0]["reason"]
    )


def test_python_requirement_is_checked():
    registry = FakeRegistry(cycles={"python": [cycle("3.9", "3.9.25")]})
    result, _ = _run(
        _state(
            tech_item("tech-runtime", ("eol", "python", "3.9")),
            tech_item("tech-api", ("pypi", "fastapi", "0.162.5")),
        ),
        registry,
    )
    (mismatch,) = result.update["stack_mismatches"]
    assert mismatch["item_id"] == "tech-api"
    assert "요구 Python >=3.10 ↔ python@3.9(3.9.25) — 맞지 않음" in mismatch["reason"]


def test_spring_boot_java_compatibility_is_checked():
    ok, _ = _run(
        _state(
            tech_item("tech-runtime", ("eol", "eclipse-temurin", "21")),
            tech_item(
                "tech-web", ("maven", "org.springframework.boot:spring-boot", "4.1.2")
            ),
        )
    )
    assert ok.goto == "select_skills"
    assert "지원 Java 17 - 26 ↔ eclipse-temurin@21 — 맞음" in _content(ok, "tech-web")

    bad, _ = _run(
        _state(
            tech_item("tech-runtime", ("eol", "eclipse-temurin", "11")),
            tech_item(
                "tech-web", ("maven", "org.springframework.boot:spring-boot", "4.1.2")
            ),
        )
    )
    assert (
        "지원 Java 17 - 26 ↔ eclipse-temurin@11 — 맞지 않음"
        in bad.update["stack_mismatches"][0]["reason"]
    )


def test_without_compat_info_says_so():
    result, _ = _run(_state(tech_item("tech-api", ("pypi", "fastapi", "0.162.5"))))
    verify = _content(result, "tech-api").splitlines()[-1]
    assert "지원 종료 정보 없음" in verify
    assert "함께 쓰는 것끼리의 호환: 저장소에 정보 없음" in verify


def test_offline_is_recorded_as_unverified_not_verified():
    result, _ = _run(_state(*NEXT_STACK), FakeRegistry(offline=True))

    assert result.goto == "select_skills"
    verify = _content(result, "tech-web").splitlines()[-1]
    assert "[일부 검증하지 못함]" in verify
    assert "저장소에 접속하지 못해 검증하지 못함: next@16.4.6" in verify
    assert "[확인됨]" not in verify


def test_at_return_limit_replaces_with_latest_stable_and_records_why():
    result, _ = _run(
        _state(
            tech_item("tech-web", ("npm", "next", "17.0.0")),
            verify_returns=MAX_VERIFY_RETURNS,
        )
    )

    assert result.goto == "select_skills"
    web = _content(result, "tech-web")
    assert [r.label for r in parse_refs(web)] == ["next@16.4.6"]
    verify = web.splitlines()[-1]
    assert (
        "상한(2회)에 닿아 next@17.0.0 를 저장소 최신 안정판 next@16.4.6 로 바꿈"
        in verify
    )
    assert "[확인됨]" in verify


def test_at_return_limit_unfixable_mismatch_is_written_as_is():
    registry = FakeRegistry(releases={("npm", "react"): {"17.0.2": Release("17.0.2")}})
    result, _ = _run(
        _state(
            tech_item(
                "tech-web", ("npm", "next", "16.4.6"), ("npm", "react", "17.0.2")
            ),
            verify_returns=MAX_VERIFY_RETURNS,
        ),
        registry,
    )
    assert result.goto == "select_skills"
    verify = _content(result, "tech-web").splitlines()[-1]
    assert "[맞지 않음]" in verify and "react@17.0.2 — 맞지 않음" in verify


def test_lookups_are_deduplicated():
    _, registry = _run(
        _state(*NEXT_STACK, tech_item("tech-extra", ("npm", "next", "16.4.6")))
    )
    assert len(registry.lookups) == len(set(registry.lookups))


def test_no_tech_items_passes_through():
    result, registry = _run(_state())
    assert result.goto == "select_skills" and registry.lookups == []
