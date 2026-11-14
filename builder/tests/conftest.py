import urllib.request

import pytest

from tests.fakes.fake_registry import FakeRegistry


@pytest.fixture(autouse=True)
def _no_real_registry(monkeypatch):
    # build_graph 는 make_verify_stack(llm) 로 저장소를 주입하지 않는다 — 그래프 전체를 도는 테스트도 실제 저장소에 접속하지 않게
    # 기본 저장소를 가짜로 바꾸고, 그래도 새는 HTTP 호출은 바로 실패시킨다.
    monkeypatch.setattr("specbuilder.nodes.verify_stack.HTTPRegistry", FakeRegistry)

    def blocked(*args, **kwargs):
        raise AssertionError("테스트에서 실제 네트워크 호출")

    monkeypatch.setattr(urllib.request, "urlopen", blocked)
