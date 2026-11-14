import json
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


SAVED_PROFILE = {
    "domain": "사무·행정·회계",
    "tech_exposure": "셋 다 해 본 적 없어요",
    "explanation": "결과만 짧게 알려 주세요",
    "environment": "운영체제: Mac / AI 도구·요금제: Claude Pro",
    "delegation": "알아서 정하고 결과만 알려 주세요",
}


@pytest.fixture(autouse=True)
def profile_file(tmp_path, monkeypatch):
    # 실제 ~/.specbuilder 를 읽거나 쓰지 않게 하고, 저장된 프로필이 있는 상태를 기본으로 둔다 —
    # 그래프 전체를 도는 테스트가 프로필 질문 없이 interview_user 부터 시작한다. 프로필이 없는 경우는 이 파일을 지워서 만든다.
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(SAVED_PROFILE, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("SPECBUILDER_PROFILE_PATH", str(path))
    return path
