import json

import pytest
from langgraph.types import Command

from specbuilder.nodes import interview_profile as node
from specbuilder.nodes.interview_profile import (
    build_bundle,
    load_questions,
    make_interview_profile,
)
from specbuilder.profile_store import load_profile
from specbuilder.state import initial_state
from tests.conftest import SAVED_PROFILE
from tests.fakes.fake_llm import FakeLLM


def asked_state():
    """질문 묶음을 체크포인트에 남긴 뒤(두 번째 진입)의 State."""
    state = initial_state("가계부")
    state["pending_bundle"] = build_bundle(load_questions())
    return state


def answer(monkeypatch, submission):
    monkeypatch.setattr(node, "interrupt", lambda bundle: submission)
    llm = FakeLLM()
    return make_interview_profile(llm)(asked_state()), llm


def test_saved_profile_skips_questions_without_llm():
    llm = FakeLLM()
    result = make_interview_profile(llm)(initial_state("가계부"))

    assert result == Command(update={"profile": SAVED_PROFILE}, goto="interview_user")
    assert llm.calls == []


def test_no_saved_profile_stores_fixed_bundle_then_returns_to_itself(profile_file):
    profile_file.unlink()
    llm = FakeLLM()
    result = make_interview_profile(llm)(initial_state("가계부"))

    assert result.goto == "interview_profile"
    bundle = result.update["pending_bundle"]
    assert len(bundle["questions"]) == 6
    assert bundle["round"] == 1 and bundle["can_finish"] is True
    assert [q["id"] for q in bundle["questions"]] == [f"q{i}" for i in range(1, 7)]
    assert [q["multiple"] for q in bundle["questions"]] == [
        False,
        True,
        False,
        False,
        False,
        True,
    ]
    # 요금은 토큰이 아니라 도구와 요금제로 묻는다
    assert all("토큰" not in q["text"] for q in bundle["questions"])
    assert llm.calls == []


@pytest.mark.parametrize("content", ["{깨진 json", json.dumps({"domain": "사무"})])
def test_broken_saved_profile_is_asked_again(profile_file, content):
    profile_file.write_text(content, encoding="utf-8")
    result = make_interview_profile(FakeLLM())(initial_state("가계부"))

    assert result.goto == "interview_profile"
    assert result.update["pending_bundle"] is not None


def test_answers_become_profile_and_are_saved(monkeypatch, profile_file):
    profile_file.unlink()
    result, llm = answer(
        monkeypatch,
        {
            "action": "submit",
            "answers": [
                {"question_id": "q1", "kind": "custom", "text": "세무 업무"},
                {"question_id": "q2", "kind": "option", "option_ids": ["o1", "o3"]},
                {"question_id": "q3", "kind": "delegate"},
                {"question_id": "q4", "kind": "option", "option_ids": ["o2"]},
                {"question_id": "q5", "kind": "option", "option_ids": ["o2"]},
                # q6 은 답 없음 → 기본값
            ],
        },
    )

    profile = result.update["profile"]
    assert profile == {
        "domain": "세무 업무",
        "tech_exposure": "터미널(검은 창)에 명령어를 입력해 봤어요, 엑셀 함수나 노코드 도구(노션 등)를 써 봤어요",
        "explanation": "결과만 짧게",
        "delegation": "선택지가 있으면 물어봐 주세요",
        "environment": "운영체제: Windows / AI 도구·요금제: 모름 — 가장 작은 요금제로 보고 대화 왕복을 아낀다",
    }
    assert load_profile() == profile
    assert result.goto == "interview_user"
    assert result.update["pending_bundle"] is None
    assert result.update["question_round"] == 0
    assert result.update["interview_stops"] == [
        {"node": "interview_profile", "reason": "resolved", "rounds": 1}
    ]
    # 프로필 문답은 스펙 문답(qa)에 섞지 않는다
    assert "qa" not in result.update
    assert llm.calls == []


def test_finish_fills_rest_with_defaults(monkeypatch):
    result, _ = answer(
        monkeypatch,
        {
            "action": "finish",
            "answers": [{"question_id": "q1", "kind": "custom", "text": "식당 운영"}],
        },
    )

    defaults = {q["field"]: q["default"] for q in load_questions()}
    profile = result.update["profile"]
    assert profile["domain"] == "식당 운영"
    assert profile["delegation"] == defaults["delegation"]
    assert profile["tech_exposure"] == defaults["tech_exposure"]
    assert result.update["interview_stops"][0]["reason"] == "user_finished"


def test_bad_submission_is_rejected(monkeypatch):
    with pytest.raises(ValueError, match="답 제출이 규격에 맞지 않음"):
        answer(
            monkeypatch,
            {
                "action": "submit",
                "answers": [
                    {"question_id": "q3", "kind": "option", "option_ids": ["o1", "o2"]}
                ],
            },
        )


def test_unknown_keys_in_saved_file_are_dropped(profile_file):
    profile_file.write_text(
        json.dumps({**SAVED_PROFILE, "name": "홍길동"}, ensure_ascii=False),
        encoding="utf-8",
    )
    assert load_profile() == SAVED_PROFILE


def test_questions_cover_every_profile_field(monkeypatch, tmp_path):
    broken = tmp_path / "q.json"
    questions = [
        q
        for q in json.loads(node.QUESTIONS_FILE.read_text())["questions"]
        if q["field"] != "delegation"
    ]
    broken.write_text(json.dumps({"questions": questions}, ensure_ascii=False))
    monkeypatch.setattr(node, "QUESTIONS_FILE", broken)

    with pytest.raises(ValueError, match="delegation"):
        load_questions()
