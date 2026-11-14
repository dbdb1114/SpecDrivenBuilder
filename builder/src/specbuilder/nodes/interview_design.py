import re
from typing import Annotated, NotRequired, TypedDict

from langgraph.types import Command, interrupt
from pydantic import Field, TypeAdapter, ValidationError

from specbuilder.common_items import (
    CommonItem,
    add_selected,
    append_fixed,
    fill_defaults,
    fixed_questions,
    load_common_items,
    record_answers,
    render_catalog,
)
from specbuilder.llm import LLMCallError, LLMClient, parse_json_reply
from specbuilder.nodes.interview_user import render_context
from specbuilder.paths import load_prompt
from specbuilder.state import State
from specbuilder.state.question_format import (
    LAYOUT_KEYS,
    MAX_QUESTIONS,
    DraftQuestion,
    Preview,
    apply_submission,
    assign_ids,
    validate_submission,
)
from specbuilder.state.spec_items import (
    ItemId,
    SpecItem,
    delegate_open,
    is_open,
    merge_updates,
    needs_asking,
    spec_items_adapter,
)

NODE = "interview_design"
AREA = "design"
NEXT = "select_stack"
# interview_user 와 같은 이유의 진입 1회당 상한.
MAX_ROUNDS = 5

# 미리보기는 색 톤과 배치를 코드가 찾아 읽어야 하므로 이 두 항목의 id 를 고정한다 (프롬프트와 같은 값).
COLOR_ITEM_ID = "color-tone"
LAYOUT_ITEM_ID = "layout"
# 아래 둘은 코드가 만들고 관리한다. LLM 이 고치면 버린다.
SCREEN_ITEM_ID = "screen"
PREVIEW_ITEM_ID = "preview-check"
CODE_OWNED = {SCREEN_ITEM_ID, PREVIEW_ITEM_ID}

PREVIEW_OK, PREVIEW_COLOR, PREVIEW_LAYOUT = "맞아요", "색을 바꿀래요", "배치를 바꿀래요"

HEX = re.compile(r"#[0-9A-Fa-f]{6}")
LAYOUT_TAG = re.compile(r"\[([a-z-]+)\]")


class DesignReply(TypedDict):
    """이 노드의 LLM 응답. 질문 묶음 규격이 아니라 LLM 과 주고받는 형식이라 규격 모듈이 아니라 여기에 둔다.

    InterviewReply 에 미리보기 초안이 더해진다 — 제목·메뉴 문구는 스펙 항목을 읽어야 나오므로 LLM 이 쓴다.
    이 프로그램에 해당하는 공통 항목 id 도 고른다 (interview_user.UserReply 와 같다).
    """

    items: list[SpecItem]
    questions: Annotated[list[DraftQuestion], Field(max_length=MAX_QUESTIONS)]
    preview: NotRequired[Preview | None]
    common_items: NotRequired[list[ItemId]]


design_reply_adapter = TypeAdapter(DesignReply)
preview_adapter = TypeAdapter(Preview)


def _screen_item() -> SpecItem:
    # 화면이 없다는 판정도 스펙 항목으로 남긴다 — 돌아오는 경로에서 다시 판정(LLM 호출)하지 않고, 작업자도 이유를 본다.
    return {
        "id": SCREEN_ITEM_ID,
        "name": "화면",
        "area": AREA,
        "decided_by": "worker",
        "status": "delegated",
        "content": "화면이 없는 프로그램이라 디자인 결정이 없다",
    }


def _preview_item() -> SpecItem:
    return {
        "id": PREVIEW_ITEM_ID,
        "name": "미리보기 확인",
        "area": AREA,
        "decided_by": "user",
        "status": "unknown",
        "content": "",
    }


def reopened_ids(items: list, qa: list) -> set[str]:
    """다시 물어야 하는 디자인 항목 — 아직 모름인데 지난 답이 있다 (interview_user.reopened_ids 와 같은 판정, 영역만 다름).

    확인 화면에서 고치기로 고른 항목과, 미리보기에서 "색을/배치를 바꿀래요"로 되돌린 항목이 여기에 든다.
    """
    answered = {line["item_id"] for line in qa}
    return {
        item["id"] for item in items if is_open(item, AREA) and item["id"] in answered
    }


def _render_context(state: State, catalog: dict[str, CommonItem]) -> str:
    lines = [render_context(state)]
    # preview-check 와 공통 항목은 코드가 묻는 항목이라 LLM 에게 알릴 필요가 없다.
    reopened = sorted(
        reopened_ids(state["spec_items"], state["qa"]) - CODE_OWNED - set(catalog)
    )
    if reopened:
        lines += ["", "## 사용자가 고치기로 고른 디자인 항목", ", ".join(reopened)]
    block = render_catalog(catalog, state["spec_items"])
    if block:
        lines += ["", block]
    return "\n".join(lines)


def _parse_reply(
    text: str, items: list, reopened: set[str], catalog: dict[str, CommonItem]
) -> tuple[list, list, Preview | None]:
    try:
        reply = design_reply_adapter.validate_python(parse_json_reply(text))
    except ValidationError as e:
        raise LLMCallError(f"{NODE} 응답이 규격에 맞지 않음: {e}") from e
    # 고치기로 고른 항목을 LLM 이 지난 답으로 다시 채우면 고치기가 조용히 무시된다 — 다시 묻게 아직 모름으로 둔다.
    # 공통 항목은 코드가 만들고 채운다. LLM 이 쓴 갱신·질문은 버린다 (design.md "공통 항목").
    updates = [
        item
        for item in reply["items"]
        if item["id"] not in CODE_OWNED
        and item["id"] not in reopened
        and item["id"] not in catalog
    ]
    for item in updates:
        if item["area"] != AREA:
            raise LLMCallError(f"{NODE} 는 {AREA} 항목만 다룬다: {item['id']}")
        if item["decided_by"] == "worker" and item["status"] == "unknown":
            raise LLMCallError(f"작업자가 정할 항목이 아직 모름: {item['id']}")
    try:
        merged = spec_items_adapter.validate_python(merge_updates(items, updates))
    except ValidationError as e:
        raise LLMCallError(f"{NODE} 항목 갱신이 규격에 맞지 않음: {e}") from e
    merged = add_selected(merged, reply.get("common_items", []), catalog)
    questions = [q for q in reply["questions"] if q["item_id"] not in catalog]
    return merged, questions, reply.get("preview")


def _check_questions(questions: list, items: list, catalog: dict) -> list:
    open_ids = {
        item["id"]
        for item in items
        if is_open(item, AREA)
        and item["id"] != PREVIEW_ITEM_ID
        and item["id"] not in catalog
    }
    asked = [q["item_id"] for q in questions]
    if open_ids and not questions:
        raise LLMCallError(f"아직 모름인 항목이 있는데 질문이 없음: {sorted(open_ids)}")
    if len(asked) != len(set(asked)):
        raise LLMCallError(f"한 묶음에 같은 항목을 두 번 물음: {asked}")
    stray = [i for i in asked if i not in open_ids]
    if stray:
        raise LLMCallError(f"물을 필요가 없는 항목을 물음: {stray}")
    # 색·배치는 그림이 있어야 고를 수 있는 질문이다. 그림이 빠지면 미리보기에 쓸 값도 없다.
    want = {COLOR_ITEM_ID: "palette", LAYOUT_ITEM_ID: "layout"}
    for q in questions:
        kind = want.get(q["item_id"])
        if kind is None:
            continue
        if q.get("multiple", False):
            raise LLMCallError(f"{q['item_id']} 는 하나만 고르는 질문이어야 함")
        if any((o.get("visual") or {}).get("type") != kind for o in q["options"]):
            raise LLMCallError(f"{q['item_id']} 의 선택지마다 {kind} 그림이 있어야 함")
    return questions


def _describe(option: dict) -> str:
    """선택지를 스펙 항목 내용으로 — 고른 색 값·배치 key 를 함께 남겨 미리보기와 작업자가 그대로 쓴다."""
    visual = option["visual"]
    if visual["type"] == "palette":
        return f"{option['label']} ({', '.join(visual['colors'])})"
    return f"{option['label']} [{visual['key']}]"


def _record_choices(items: list, bundle: dict, submission: dict) -> list:
    """apply_submission 이 라벨만 남긴 색·배치 답에 그림 값을 붙이고, 미리보기 답을 반영한다."""
    answers = {a["question_id"]: a for a in submission["answers"]}
    by_id = {item["id"]: item for item in items}
    for q in bundle["questions"]:
        item = by_id.get(q["item_id"])
        if item is None:
            continue
        answer = answers.get(q["id"], {"kind": "delegate"})
        if q["item_id"] in (COLOR_ITEM_ID, LAYOUT_ITEM_ID):
            if answer["kind"] == "option":
                option = next(
                    o for o in q["options"] if o["id"] in answer["option_ids"]
                )
            elif answer["kind"] == "delegate":
                # 맡김의 기본 방향은 추천 선택지 — LLM 을 다시 부르지 않고도 미리보기를 그릴 수 있다.
                option = next(
                    (o for o in q["options"] if o["recommended"]), q["options"][0]
                )
            else:
                continue
            by_id[q["item_id"]] = {**item, "content": _describe(option)}
        elif q["item_id"] == PREVIEW_ITEM_ID and answer["kind"] == "option":
            label = next(
                o["label"] for o in q["options"] if o["id"] in answer["option_ids"]
            )
            target = {PREVIEW_COLOR: COLOR_ITEM_ID, PREVIEW_LAYOUT: LAYOUT_ITEM_ID}.get(
                label
            )
            # 그만 묻기(finish)와 함께 오면 되돌리지 않는다 — 다시 물을 기회가 없어 내용만 지워진다.
            if target in by_id and submission["action"] == "submit":
                by_id[target] = {**by_id[target], "status": "unknown", "content": ""}
    return list(by_id.values())


def _reopen_preview(items: list) -> list:
    """색이나 배치를 다시 묻게 되면(미리보기에서 바꾸기, 확인 화면에서 고치기) 미리보기도 다시 보여 준다."""
    by_id = {item["id"]: item for item in items}
    if PREVIEW_ITEM_ID in by_id and any(
        by_id.get(i, {}).get("status") == "unknown"
        for i in (COLOR_ITEM_ID, LAYOUT_ITEM_ID)
    ):
        by_id[PREVIEW_ITEM_ID] = _preview_item()
    return list(by_id.values())


def _build_preview(items: list, draft: Preview | None) -> Preview | None:
    by_id = {item["id"]: item for item in items}
    color, layout = by_id.get(COLOR_ITEM_ID), by_id.get(LAYOUT_ITEM_ID)
    check = by_id.get(PREVIEW_ITEM_ID)
    if color is None or layout is None:
        return None
    if "unknown" in (color["status"], layout["status"]):
        return None
    if "user" not in (color["decided_by"], layout["decided_by"]):
        return None
    if check is not None and check["status"] != "unknown":
        return None
    if draft is None:
        raise LLMCallError(f"{NODE}: 색 톤과 배치가 정해졌는데 미리보기 초안이 없음")
    # 사용자가 고른 값이 LLM 의 초안보다 우선이다. 직접 입력한 답이라 값이 없을 때만 LLM 이 고른 값을 쓴다.
    colors = HEX.findall(color["content"]) or draft["colors"]
    tag = LAYOUT_TAG.search(layout["content"])
    key = tag.group(1) if tag and tag.group(1) in LAYOUT_KEYS else draft["layout"]
    try:
        return preview_adapter.validate_python(
            {**draft, "layout": key, "colors": colors}
        )
    except ValidationError as e:
        raise LLMCallError(f"{NODE} 미리보기가 규격에 맞지 않음: {e}") from e


def _plain(content: str) -> str:
    """_describe 가 붙인 "(#색, …)"·"[key]" 를 떼어 사용자에게 보일 말만 남긴다."""
    content = re.sub(r"\s*\((#[0-9A-Fa-f]{6}(,\s*)?)+\)", "", content)
    return LAYOUT_TAG.sub("", content).strip()


def _preview_question(items: list) -> DraftQuestion:
    by_id = {item["id"]: item for item in items}
    # CLI 는 미리보기 그림을 그리지 않는다 — 문장에 배치와 색을 적어 글자로도 뜻이 통하게 한다.
    # 색 값·key 는 작업자용이라 사용자에게 보이는 문장에서는 뺀다.
    layout = _plain(by_id[LAYOUT_ITEM_ID]["content"])
    color = _plain(by_id[COLOR_ITEM_ID]["content"])
    return {
        "item_id": PREVIEW_ITEM_ID,
        "text": f"이 느낌이 맞나요? (배치: {layout} / 색: {color})",
        "multiple": False,
        "options": [
            {"label": PREVIEW_OK, "recommended": True},
            {"label": PREVIEW_COLOR},
            {"label": PREVIEW_LAYOUT},
        ],
    }


def _stop(items: list, reason: str, rounds: int, qa: list | None = None) -> Command:
    return Command(
        update={
            "spec_items": items,
            "qa": qa or [],
            "pending_bundle": None,
            "question_round": 0,
            "interview_stops": [{"node": NODE, "reason": reason, "rounds": rounds}],
        },
        goto=NEXT,
    )


def make_interview_design(llm: LLMClient):
    """LLM 클라이언트를 주입한 interview_design 노드를 만든다."""
    system = load_prompt(NODE)
    schema = design_reply_adapter.json_schema()
    catalog = load_common_items(AREA)

    def interview_design(state: State) -> Command:
        items = state["spec_items"]
        rounds = state["question_round"]
        bundle = state["pending_bundle"]

        if bundle is not None:
            try:
                submission = validate_submission(bundle, interrupt(bundle))
            except (ValidationError, ValueError) as e:
                raise ValueError(f"답 제출이 규격에 맞지 않음: {e}") from e
            items, qa = apply_submission(items, bundle, submission, NODE, AREA)
            items = _record_choices(items, bundle, submission)
            items = record_answers(items, bundle, submission, catalog)
            if submission["action"] == "finish":
                return _stop(items, "user_finished", rounds + 1, qa)
            return Command(
                update={
                    "spec_items": items,
                    "qa": qa,
                    "pending_bundle": None,
                    "question_round": rounds + 1,
                },
                goto=NODE,
            )

        if rounds >= MAX_ROUNDS:
            return _stop(
                fill_defaults(delegate_open(items, AREA), catalog),
                "round_limit",
                rounds,
            )
        first_visit = not any(item["area"] == AREA for item in items)
        # 처음 오면 화면 유무부터 LLM 이 판정해야 한다. 그 뒤로는 묻는 노드의 실행 규칙을 따른다.
        if rounds == 0 and not first_visit and not needs_asking(items, AREA):
            return Command(goto=NEXT)

        items, questions, draft = _parse_reply(
            llm.complete(system, _render_context(state, catalog), schema),
            items,
            reopened_ids(items, state["qa"]),
            catalog,
        )
        if first_visit and not any(item["area"] == AREA for item in items):
            return Command(update={"spec_items": [*items, _screen_item()]}, goto=NEXT)

        items = _reopen_preview(items)
        preview = _build_preview(items, draft)
        if preview is not None and PREVIEW_ITEM_ID not in {i["id"] for i in items}:
            items = [*items, _preview_item()]
        if not needs_asking(items, AREA):
            return _stop(items, "resolved", rounds)
        drafts = _check_questions(questions, items, catalog)
        if preview is not None:
            drafts = [_preview_question(items), *drafts]
        drafts = append_fixed(drafts, fixed_questions(items, catalog))
        bundle = assign_ids(drafts, rounds + 1, True, preview)
        # interview_user 와 같은 이유로 묶음을 먼저 체크포인트에 남기고 자기 자신으로 돌아온다.
        return Command(
            update={"spec_items": items, "pending_bundle": bundle}, goto=NODE
        )

    return interview_design
