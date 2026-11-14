import json

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from specbuilder.common_items import fixed_questions, load_common_items
from specbuilder.graph.build import build_graph
from specbuilder.llm import LLMCallError
from specbuilder.nodes.interview_design import make_interview_design
from specbuilder.state import initial_state
from specbuilder.state.question_format import LAYOUT_KEYS, assign_ids
from tests.fakes.fake_llm import FakeLLM, interview_reply, item

NAVY = ["#1E3A5F", "#F5F7FA", "#4A90D9"]
BEIGE = ["#5C4033", "#FAF6F0", "#D9A05B"]
TEXTS = {"title": "동아리 모임", "menu": ["모임 날짜", "회비"]}


def design(id, status="unknown", content="", decided_by="user"):
    return item(id, status, content, decided_by=decided_by, area="design")


def color_question():
    return {
        "item_id": "color-tone",
        "text": "화면 색은 어떤 느낌이 좋으세요?",
        "options": [
            {
                "label": "차분한 남색",
                "recommended": True,
                "visual": {"type": "palette", "colors": NAVY},
            },
            {"label": "따뜻한 베이지", "visual": {"type": "palette", "colors": BEIGE}},
        ],
    }


def layout_question(keys=("mobile-tabs", "single-column")):
    return {
        "item_id": "layout",
        "text": "화면 배치는요?",
        "options": [
            {
                "label": f"{key} 모양",
                "recommended": i == 0,
                "visual": {"type": "layout", "key": key},
            }
            for i, key in enumerate(keys)
        ],
    }


def design_reply(items=None, questions=None, preview=None):
    data = json.loads(interview_reply(items, questions))
    return json.dumps({**data, "preview": preview}, ensure_ascii=False)


def draft_preview(layout="top-nav", colors=("#000000",)):
    return {"layout": layout, "colors": list(colors), "texts": TEXTS}


def state_with(items, **extra):
    state = initial_state("동아리 사람들이 휴대폰으로 같이 쓰는 거")
    state["spec_items"] = [item("purpose"), *items]
    return {**state, **extra}


def run(replies, state):
    llm = FakeLLM({"interview_design": replies})
    return make_interview_design(llm)(state), llm


def answer(monkeypatch, submission):
    monkeypatch.setattr(
        "specbuilder.nodes.interview_design.interrupt", lambda bundle: submission
    )


def test_layout_keys_are_the_decided_six():
    assert LAYOUT_KEYS == (
        "single-column",
        "top-nav",
        "sidebar-left",
        "list-detail",
        "dashboard",
        "mobile-tabs",
    )


def test_no_screen_adds_screen_item_and_passes_with_one_call():
    result, llm = run([design_reply()], state_with([]))

    assert result.goto == "select_stack"
    screen = [i for i in result.update["spec_items"] if i["id"] == "screen"]
    assert (
        screen
        and screen[0]["decided_by"] == "worker"
        and screen[0]["status"] == "delegated"
    )
    assert "interview_stops" not in result.update
    assert len(llm.calls) == 1


def test_returning_without_open_design_items_passes_without_llm():
    for items in (
        [design("screen", "delegated", "화면 없음", "worker")],
        [design("color-tone", "confirmed", "남색")],
    ):
        result, llm = run([], state_with(items))
        assert result == Command(goto="select_stack")
        assert llm.calls == []


def test_first_bundle_has_visuals_and_no_preview():
    reply = design_reply(
        [
            design("color-tone"),
            design("layout"),
            design("font", "delegated", "읽기 쉬운 고딕", "worker"),
        ],
        [color_question(), layout_question()],
    )
    result, _ = run([reply], state_with([]))

    bundle = result.update["pending_bundle"]
    assert result.goto == "interview_design"
    assert bundle["preview"] is None
    assert [q["item_id"] for q in bundle["questions"]] == ["color-tone", "layout"]
    assert bundle["questions"][0]["options"][0]["visual"] == {
        "type": "palette",
        "colors": NAVY,
    }
    assert bundle["questions"][1]["options"][0]["visual"] == {
        "type": "layout",
        "key": "mobile-tabs",
    }


@pytest.mark.parametrize(
    "question",
    [
        {**color_question(), "options": [{"label": "남색"}, {"label": "베이지"}]},
        {
            **layout_question(),
            "options": [
                {"label": "아무거나", "visual": {"type": "palette", "colors": NAVY}},
                {"label": "다른 것"},
            ],
        },
        {**color_question(), "multiple": True},
    ],
)
def test_rejects_color_or_layout_question_without_matching_visual(question):
    reply = design_reply([design("color-tone"), design("layout")], [question])
    with pytest.raises(LLMCallError):
        run([reply], state_with([]))


def test_rejects_unknown_layout_key():
    reply = design_reply(
        [design("layout")], [layout_question(("mobile-tabs", "없는-틀"))]
    )
    with pytest.raises(LLMCallError):
        run([reply], state_with([]))


def test_rejects_non_design_items():
    reply = design_reply([item("who-uses", "unknown", "")], [])
    with pytest.raises(LLMCallError):
        run([reply], state_with([]))


def test_llm_cannot_touch_code_owned_items():
    reply = design_reply(
        [
            design("preview-check", "confirmed", "맞아요"),
            design("screen", "delegated", "x", "worker"),
        ]
    )
    result, _ = run([reply], state_with([]))
    # LLM 이 낸 preview-check·screen 은 버려진다. 남는 디자인 항목이 없으니 화면 없음으로 판정되고 screen 은 코드가 쓴다.
    by_id = {i["id"]: i for i in result.update["spec_items"]}
    assert set(by_id) == {"purpose", "screen"}
    assert by_id["screen"]["content"] != "x"


def test_answers_keep_chosen_colors_and_layout_key_and_delegate_uses_recommended(
    monkeypatch,
):
    first, _ = run(
        [
            design_reply(
                [design("color-tone"), design("layout")],
                [color_question(), layout_question()],
            )
        ],
        state_with([]),
    )
    answer(
        monkeypatch,
        {
            "action": "submit",
            "answers": [
                {"question_id": "q1", "kind": "option", "option_ids": ["o2"]},
                {"question_id": "q2", "kind": "delegate"},
            ],
        },
    )
    result, llm = run(
        [],
        state_with(
            first.update["spec_items"], pending_bundle=first.update["pending_bundle"]
        ),
    )

    by_id = {i["id"]: i for i in result.update["spec_items"]}
    assert by_id["color-tone"] == {
        **by_id["color-tone"],
        "status": "confirmed",
        "content": f"따뜻한 베이지 ({', '.join(BEIGE)})",
    }
    assert by_id["layout"] == {
        **by_id["layout"],
        "status": "delegated",
        "content": "mobile-tabs 모양 [mobile-tabs]",
    }
    assert result.goto == "interview_design" and llm.calls == []


def test_preview_bundle_uses_user_choices_over_llm_draft():
    items = [
        design("color-tone", "confirmed", f"차분한 남색 ({', '.join(NAVY)})"),
        design("layout", "confirmed", "아래 탭 [mobile-tabs]"),
    ]
    result, _ = run(
        [design_reply([], [], draft_preview())], state_with(items, question_round=1)
    )

    bundle = result.update["pending_bundle"]
    assert bundle["preview"] == {
        "layout": "mobile-tabs",
        "colors": NAVY,
        "texts": TEXTS,
    }
    q = bundle["questions"][0]
    assert q["item_id"] == "preview-check"
    # 사용자에게 보이는 문장에는 색 값·key 가 없다 (스펙 항목에만 남는다).
    assert q["text"] == "이 느낌이 맞나요? (배치: 아래 탭 / 색: 차분한 남색)"
    assert [o["label"] for o in q["options"]] == [
        "맞아요",
        "색을 바꿀래요",
        "배치를 바꿀래요",
    ]
    assert "preview-check" in {i["id"] for i in result.update["spec_items"]}


def test_preview_falls_back_to_llm_values_for_custom_answers():
    items = [
        design("color-tone", "confirmed", "파스텔톤"),
        design("layout", "delegated", "알아서", "user"),
    ]
    result, _ = run(
        [design_reply([], [], draft_preview("top-nav", BEIGE))],
        state_with(items, question_round=1),
    )

    assert result.update["pending_bundle"]["preview"]["layout"] == "top-nav"
    assert result.update["pending_bundle"]["preview"]["colors"] == BEIGE


def test_missing_preview_draft_is_an_error():
    items = [
        design("color-tone", "confirmed", "남색"),
        design("layout", "confirmed", "탭"),
    ]
    with pytest.raises(LLMCallError):
        run([design_reply([], [], None)], state_with(items, question_round=1))


def test_change_color_reasks_only_color_then_previews_again():
    """그래프 전체로: 색·배치 묻기 → 미리보기 → 색을 바꿀래요 → 색만 다시 → 미리보기 → 맞아요 → select_stack."""
    first_items = [design("color-tone"), design("layout")]
    llm = FakeLLM(
        {
            "interview_design": [
                design_reply(first_items, [color_question(), layout_question()]),
                design_reply([], [], draft_preview()),
                design_reply([], [color_question()]),
                design_reply([], [], draft_preview()),
                design_reply(),
            ]
        }
    )
    graph = build_graph(llm, InMemorySaver())
    config = {"configurable": {"thread_id": "d1"}}
    pick = lambda *pairs: Command(
        resume={
            "action": "submit",
            "answers": [
                {"question_id": q, "kind": "option", "option_ids": [o]}
                for q, o in pairs
            ],
        }
    )

    bundle = graph.invoke(initial_state("동아리 휴대폰 앱"), config)["__interrupt__"][
        0
    ].value
    assert [q["item_id"] for q in bundle["questions"]] == ["color-tone", "layout"]

    bundle = graph.invoke(pick(("q1", "o1"), ("q2", "o1")), config)["__interrupt__"][
        0
    ].value
    assert (
        bundle["preview"]["colors"] == NAVY
        and bundle["preview"]["layout"] == "mobile-tabs"
    )

    bundle = graph.invoke(pick(("q1", "o2")), config)["__interrupt__"][
        0
    ].value  # 색을 바꿀래요
    assert bundle["preview"] is None
    assert [q["item_id"] for q in bundle["questions"]] == ["color-tone"]

    bundle = graph.invoke(pick(("q1", "o2")), config)["__interrupt__"][
        0
    ].value  # 베이지
    assert (
        bundle["preview"]["colors"] == BEIGE
        and bundle["preview"]["layout"] == "mobile-tabs"
    )

    screen = graph.invoke(pick(("q1", "o1")), config)["__interrupt__"][
        0
    ].value  # 맞아요
    # 확인 화면에서 디자인 항목은 사용자가 고칠 수 있다 (screen·작업자 항목은 아님)
    editable = {i["id"] for i in screen["items"] if i["editable"]}
    assert {"color-tone", "layout", "preview-check"} <= editable
    final = graph.invoke(Command(resume={"action": "confirm"}), config)
    by_id = {i["id"]: i for i in final["spec_items"]}
    assert by_id["preview-check"]["status"] == "confirmed"
    assert by_id["color-tone"]["content"] == f"따뜻한 베이지 ({', '.join(BEIGE)})"
    assert {"node": "interview_design", "reason": "resolved", "rounds": 4} in final[
        "interview_stops"
    ]
    # resume 마다 LLM 을 다시 부르지 않는다: 묶음 4 + 마지막 답 반영 1
    assert len(llm.calls_for("interview_design")) == 5
    assert final.get("artifacts")


def test_finish_with_change_request_does_not_wipe_choice(monkeypatch):
    items = [
        design("color-tone", "confirmed", "남색 (#1E3A5F)"),
        design("layout", "confirmed", "탭 [mobile-tabs]"),
    ]
    preview_result, _ = run(
        [design_reply([], [], draft_preview())], state_with(items, question_round=1)
    )
    answer(
        monkeypatch,
        {
            "action": "finish",
            "answers": [{"question_id": "q1", "kind": "option", "option_ids": ["o2"]}],
        },
    )
    result, _ = run(
        [],
        state_with(
            preview_result.update["spec_items"],
            pending_bundle=preview_result.update["pending_bundle"],
            question_round=1,
        ),
    )

    by_id = {i["id"]: i for i in result.update["spec_items"]}
    assert by_id["color-tone"]["content"] == "남색 (#1E3A5F)"
    assert result.update["interview_stops"][0]["reason"] == "user_finished"


def test_revised_color_reopens_preview():
    items = [
        design("color-tone"),
        design("layout", "confirmed", "탭 [mobile-tabs]"),
        design("preview-check", "confirmed", "맞아요"),
    ]
    result, _ = run([design_reply([], [color_question()])], state_with(items))

    by_id = {i["id"]: i for i in result.update["spec_items"]}
    assert by_id["preview-check"]["status"] == "unknown"
    assert [q["item_id"] for q in result.update["pending_bundle"]["questions"]] == [
        "color-tone"
    ]


def test_passes_reply_json_schema_with_layout_enum():
    _, llm = run([design_reply()], state_with([]))
    schema = json.dumps(llm.schemas[0][1])
    assert '"preview"' in schema and '"mobile-tabs"' in schema


def test_reopened_item_is_asked_again_even_if_llm_reconfirms_it():
    """확인 화면에서 고친 색 톤: 아직 모름 + 지난 답이 있음 → LLM 이 지난 답으로 확정해도 버리고 다시 묻는다."""
    items = [
        design("color-tone"),
        design("layout", "confirmed", "탭 [mobile-tabs]"),
        design("preview-check", "confirmed", "맞아요"),
    ]
    qa = [
        {
            "node": "interview_design",
            "round": 1,
            "item_id": "color-tone",
            "question": "색은요?",
            "answer": "차분한 남색",
        },
        {
            "node": "interview_design",
            "round": 2,
            "item_id": "preview-check",
            "question": "이 느낌이 맞나요?",
            "answer": "맞아요",
        },
    ]
    reply = design_reply(
        [design("color-tone", "confirmed", f"차분한 남색 ({', '.join(NAVY)})")],
        [color_question()],
    )
    result, llm = run([reply], state_with(items, qa=qa))

    by_id = {i["id"]: i for i in result.update["spec_items"]}
    assert by_id["color-tone"]["status"] == "unknown"
    assert (
        by_id["preview-check"]["status"] == "unknown"
    )  # 색을 다시 고르면 미리보기도 다시
    assert [q["item_id"] for q in result.update["pending_bundle"]["questions"]] == [
        "color-tone"
    ]
    prompt = llm.calls_for("interview_design")[0]
    assert "## 사용자가 고치기로 고른 디자인 항목\ncolor-tone" in prompt
    assert (
        "preview-check" not in prompt.split("## 사용자가 고치기로 고른 디자인 항목")[1]
    )


def test_change_color_from_preview_is_not_refilled_from_old_answer():
    """미리보기에서 "색을 바꿀래요" 로 되돌린 항목도 같은 판정으로 다시 묻는다."""
    items = [
        design("color-tone"),
        design("layout", "confirmed", "탭 [mobile-tabs]"),
        design("preview-check"),
    ]
    qa = [
        {
            "node": "interview_design",
            "round": 1,
            "item_id": "color-tone",
            "question": "색은요?",
            "answer": "차분한 남색",
        }
    ]
    reply = design_reply([design("color-tone", "confirmed", "차분한 남색")], [])
    with pytest.raises(LLMCallError, match="질문이 없음"):
        run([reply], state_with(items, qa=qa, question_round=2))


def test_revise_design_item_on_confirm_screen_asks_it_again():
    """그래프 전체로: 확인 화면에서 색 톤을 고치기로 고르면 interview_user 는 지나가고 interview_design 이 색만 다시 묻는다."""
    llm = FakeLLM(
        {
            "interview_design": [
                design_reply(
                    [design("color-tone"), design("layout")],
                    [color_question(), layout_question()],
                ),
                design_reply([], [], draft_preview()),
                design_reply(),
                # 돌아온 뒤: LLM 이 지난 답으로 다시 확정하려 해도 버려지고 색을 다시 묻는다
                design_reply(
                    [design("color-tone", "confirmed", "차분한 남색")],
                    [color_question()],
                ),
                design_reply([], [], draft_preview()),
                design_reply(),
            ]
        }
    )
    graph = build_graph(llm, InMemorySaver())
    config = {"configurable": {"thread_id": "d2"}}

    def pick(*pairs):
        answers = [
            {"question_id": q, "kind": "option", "option_ids": [o]} for q, o in pairs
        ]
        value = graph.invoke(
            Command(resume={"action": "submit", "answers": answers}), config
        )
        return value["__interrupt__"][0].value

    graph.invoke(initial_state("동아리 휴대폰 앱"), config)
    pick(("q1", "o1"), ("q2", "o1"))  # 남색 · mobile-tabs → 미리보기
    screen = pick(("q1", "o1"))  # 맞아요 → 확인 화면
    assert "items" in screen

    again = graph.invoke(
        Command(resume={"action": "revise", "item_ids": ["color-tone"]}), config
    )["__interrupt__"][0].value
    assert [q["item_id"] for q in again["questions"]] == ["color-tone"]
    assert again["preview"] is None

    preview = pick(("q1", "o2"))  # 베이지 → 미리보기 다시
    assert preview["preview"]["colors"] == BEIGE
    screen = pick(("q1", "o1"))  # 맞아요 → 확인 화면
    by_id = {i["id"]: i for i in screen["items"]}
    assert by_id["color-tone"]["content"] == f"따뜻한 베이지 ({', '.join(BEIGE)})"
    assert by_id["preview-check"]["status"] == "confirmed"


# --- 공통 항목 (design.md "공통 항목")

COMMON = load_common_items("design")
TEXT_SIZE = COMMON["text-size"]
ACCESSIBILITY = COMMON["basic-accessibility"]


def design_reply_with(common_items, items=None, questions=None, preview=None):
    data = json.loads(design_reply(items, questions, preview))
    return json.dumps({**data, "common_items": common_items}, ensure_ascii=False)


def test_selected_design_common_items_are_added_after_llm_questions():
    reply = design_reply_with(
        ["text-size", "basic-accessibility"],
        [design("color-tone"), design("layout")],
        [color_question(), layout_question()],
    )
    result, llm = run([reply], state_with([]))

    by_id = {i["id"]: i for i in result.update["spec_items"]}
    assert (by_id["text-size"]["status"], by_id["text-size"]["content"]) == (
        "unknown",
        "",
    )
    # 작업자 항목은 묻지 않고 기본 방향으로 바로 맡긴다.
    assert by_id["basic-accessibility"] == {
        "id": "basic-accessibility",
        "name": ACCESSIBILITY["name"],
        "area": "design",
        "decided_by": "worker",
        "status": "delegated",
        "content": ACCESSIBILITY["default"],
    }
    asked = result.update["pending_bundle"]["questions"]
    assert [q["item_id"] for q in asked] == ["color-tone", "layout", "text-size"]
    assert asked[2]["text"] == TEXT_SIZE["question"]["text"]
    assert all(o["visual"] is None for o in asked[2]["options"])
    assert len(llm.calls) == 1


def test_design_context_lists_design_common_items_only():
    _, llm = run([design_reply()], state_with([]))
    context = llm.calls_for("interview_design")[0]
    assert "`text-size`" in context and "`basic-accessibility`" in context
    assert "input-validation" not in context


def test_preview_bundle_keeps_preview_first_then_fixed_question():
    items = [
        design("color-tone", "confirmed", f"차분한 남색 ({', '.join(NAVY)})"),
        design("layout", "confirmed", "아래 탭 [mobile-tabs]"),
        design("text-size"),
    ]
    result, _ = run(
        [design_reply([], [], draft_preview())], state_with(items, question_round=1)
    )

    asked = [q["item_id"] for q in result.update["pending_bundle"]["questions"]]
    assert asked == ["preview-check", "text-size"]


def test_llm_cannot_write_design_common_items():
    items = [
        design("text-size", "confirmed", "버튼 넣기"),
        design("layout", "confirmed", "[top-nav]"),
        design("color-tone", "confirmed", "남색"),
    ]
    reply = design_reply_with(
        [], [design("text-size", "confirmed", "LLM 이 바꾼 내용")], [], draft_preview()
    )
    result, _ = run([reply], state_with(items, question_round=1))

    by_id = {i["id"]: i for i in result.update["spec_items"]}
    assert by_id["text-size"]["content"] == "버튼 넣기"


def test_text_size_answer_sets_worker_content(monkeypatch):
    items = [design("text-size")]
    bundle = assign_ids(fixed_questions(items, COMMON), 1, True)
    answer(
        monkeypatch,
        {
            "action": "submit",
            "answers": [{"question_id": "q1", "kind": "option", "option_ids": ["o3"]}],
        },
    )
    result, _ = run([], state_with(items, pending_bundle=bundle))

    by_id = {i["id"]: i for i in result.update["spec_items"]}
    assert by_id["text-size"]["status"] == "confirmed"
    assert (
        by_id["text-size"]["content"] == TEXT_SIZE["question"]["options"][2]["content"]
    )
