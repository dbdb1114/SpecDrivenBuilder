"""질문 묶음 · 답 제출 · 확인 화면 규격 원본 (docs/design/question-format.md).

TypedDict + pydantic TypeAdapter 로 정의한다 — 값이 plain dict 라 State·checkpoint 에 그대로 넣을 수 있고
(BaseModel 은 checkpoint 복원 때 LangGraph 가 "unregistered type" 경고를 내고 향후 막는다),
같은 정의로 pydantic 이 검증하고 FastAPI 가 OpenAPI 스키마를 만든다.
"""

from typing import Annotated, Literal, NotRequired, TypedDict

from pydantic import AfterValidator, Field, StringConstraints, TypeAdapter

from specbuilder.state.spec_items import (
    Area,
    ItemId,
    NonEmpty,
    SpecItem,
    delegate_open,
)

MAX_QUESTIONS = 10
MIN_OPTIONS, MAX_OPTIONS = 2, 4
# 레이아웃 종류 목록은 interview_design(F) 이 정한다. 그때 이 상수만 바꾼다.
LAYOUT_KEYS = ("sidebar-left",)
# CLI·프론트엔드가 항상 같은 문구로 붙이는 고정 선택지. options 에는 넣지 않는다.
DELEGATE_LABEL = "알아서 정해 주세요"

HexColor = Annotated[str, StringConstraints(pattern=r"^#[0-9A-Fa-f]{6}$")]


def _known_layout(key: str) -> str:
    if key not in LAYOUT_KEYS:
        raise ValueError(f"목록에 없는 layout key: {key!r} (허용: {LAYOUT_KEYS})")
    return key


LayoutKey = Annotated[str, AfterValidator(_known_layout)]


class PaletteVisual(TypedDict):
    type: Literal["palette"]
    colors: Annotated[list[HexColor], Field(min_length=1)]


class LayoutVisual(TypedDict):
    type: Literal["layout"]
    key: LayoutKey


Visual = Annotated[PaletteVisual | LayoutVisual, Field(discriminator="type")]


class PreviewTexts(TypedDict):
    title: NonEmpty
    menu: list[NonEmpty]


class Preview(TypedDict):
    layout: LayoutKey
    colors: Annotated[list[HexColor], Field(min_length=1)]
    texts: PreviewTexts


class Option(TypedDict):
    id: str
    label: NonEmpty
    recommended: bool
    visual: Visual | None


def _at_most_one_recommended(options: list) -> list:
    # 초안(DraftOption)은 recommended 를 생략할 수 있어 .get 으로 읽는다.
    if sum(1 for o in options if o.get("recommended", False)) > 1:
        raise ValueError("recommended 선택지는 질문당 최대 1개")
    return options


Options = Annotated[
    list[Option],
    Field(min_length=MIN_OPTIONS, max_length=MAX_OPTIONS),
    AfterValidator(_at_most_one_recommended),
]


class Question(TypedDict):
    id: str
    item_id: ItemId
    text: NonEmpty
    multiple: bool
    options: Options


class QuestionBundle(TypedDict):
    round: Annotated[int, Field(ge=1)]
    can_finish: bool
    preview: Preview | None
    questions: Annotated[list[Question], Field(min_length=1, max_length=MAX_QUESTIONS)]


# --- LLM 이 내는 초안. id 가 없다 — id 는 assign_ids 가 붙인다 (LLM 이 만든 id 는 중복·형식 흔들림).


class DraftOption(TypedDict):
    label: NonEmpty
    recommended: NotRequired[bool]
    visual: NotRequired[Visual | None]


DraftOptions = Annotated[
    list[DraftOption],
    Field(min_length=MIN_OPTIONS, max_length=MAX_OPTIONS),
    AfterValidator(_at_most_one_recommended),
]


class DraftQuestion(TypedDict):
    item_id: ItemId
    text: NonEmpty
    multiple: NotRequired[bool]
    options: DraftOptions


def assign_ids(
    drafts: list[DraftQuestion],
    round: int,
    can_finish: bool,
    preview: Preview | None = None,
) -> QuestionBundle:
    """LLM 초안에 질문 id(`q1`…)와 선택지 id(`o1`…)를 붙여 규격대로 검증된 질문 묶음을 만든다."""
    bundle = {
        "round": round,
        "can_finish": can_finish,
        "preview": preview,
        "questions": [
            {
                "id": f"q{qi}",
                "item_id": draft["item_id"],
                "text": draft["text"],
                "multiple": draft.get("multiple", False),
                "options": [
                    {
                        "id": f"o{oi}",
                        "label": option["label"],
                        "recommended": option.get("recommended", False),
                        "visual": option.get("visual"),
                    }
                    for oi, option in enumerate(draft["options"], 1)
                ],
            }
            for qi, draft in enumerate(drafts, 1)
        ],
    }
    return bundle_adapter.validate_python(bundle)


# --- 답 제출 (프론트엔드 → 빌더)


class OptionAnswer(TypedDict):
    question_id: str
    kind: Literal["option"]
    option_ids: Annotated[list[str], Field(min_length=1)]


class CustomAnswer(TypedDict):
    question_id: str
    kind: Literal["custom"]
    text: NonEmpty


class DelegateAnswer(TypedDict):
    question_id: str
    kind: Literal["delegate"]


Answer = Annotated[
    OptionAnswer | CustomAnswer | DelegateAnswer, Field(discriminator="kind")
]


class AnswerSubmission(TypedDict):
    action: Literal["submit", "finish"]
    answers: list[Answer]


class QA(TypedDict):
    """실행 기록용 문답 한 줄. LLM 입력과 run.json 에 쓴다."""

    node: str
    round: int
    item_id: str
    question: str
    answer: str


def validate_submission(bundle: QuestionBundle, raw: object) -> AnswerSubmission:
    """답 제출을 규격과 이 질문 묶음에 맞는지 검증한다. 맞지 않으면 ValueError."""
    submission = submission_adapter.validate_python(raw)
    questions = {q["id"]: q for q in bundle["questions"]}
    seen = set()
    for answer in submission["answers"]:
        question = questions.get(answer["question_id"])
        if question is None:
            raise ValueError(f"이 묶음에 없는 질문: {answer['question_id']}")
        if answer["question_id"] in seen:
            raise ValueError(f"같은 질문에 답이 둘: {answer['question_id']}")
        seen.add(answer["question_id"])
        if answer["kind"] != "option":
            continue
        option_ids = {o["id"] for o in question["options"]}
        unknown = [oid for oid in answer["option_ids"] if oid not in option_ids]
        if unknown:
            raise ValueError(f"{question['id']} 에 없는 선택지: {unknown}")
        if not question["multiple"] and len(answer["option_ids"]) > 1:
            raise ValueError(f"{question['id']} 는 하나만 고를 수 있음")
    return submission


def apply_submission(
    items: list[SpecItem],
    bundle: QuestionBundle,
    submission: AnswerSubmission,
    node: str,
    area: Area,
) -> tuple[list[SpecItem], list[QA]]:
    """검증된 답을 스펙 항목에 반영한다 (question-format.md "답이 스펙 항목을 바꾸는 방식").

    option·custom → 확정, delegate·답이 없는 질문 → 작업자에게 맡김,
    finish → 위를 반영한 뒤 그 영역의 남은 아직 모름도 전부 맡김.
    """
    answers = {a["question_id"]: a for a in submission["answers"]}
    by_id = {item["id"]: item for item in items}
    qa = []
    for question in bundle["questions"]:
        answer = answers.get(question["id"], {"kind": "delegate"})
        if answer["kind"] == "option":
            labels = {o["id"]: o["label"] for o in question["options"]}
            content = ", ".join(labels[oid] for oid in answer["option_ids"])
            change = {"status": "confirmed", "content": content}
            shown = content
        elif answer["kind"] == "custom":
            change = {"status": "confirmed", "content": answer["text"]}
            shown = answer["text"]
        else:
            # 기본 방향은 다음 LLM 호출(또는 generate_artifacts)이 채운다.
            change = {"status": "delegated", "content": ""}
            shown = DELEGATE_LABEL
        if question["item_id"] in by_id:
            by_id[question["item_id"]] = {**by_id[question["item_id"]], **change}
        qa.append(
            {
                "node": node,
                "round": bundle["round"],
                "item_id": question["item_id"],
                "question": question["text"],
                "answer": shown,
            }
        )
    updated = list(by_id.values())
    if submission["action"] == "finish":
        updated = delegate_open(updated, area)
    return updated, qa


# --- 확인 화면 (confirm_spec)


class ConfirmItem(TypedDict):
    id: ItemId
    area: Area
    name: NonEmpty
    status: Literal["confirmed", "delegated"]
    content: str
    editable: bool


class ConfirmScreen(TypedDict):
    items: list[ConfirmItem]


class ConfirmAction(TypedDict):
    action: Literal["confirm"]


class ReviseAction(TypedDict):
    action: Literal["revise"]
    item_ids: Annotated[list[ItemId], Field(min_length=1)]


ConfirmReply = Annotated[ConfirmAction | ReviseAction, Field(discriminator="action")]


bundle_adapter = TypeAdapter(QuestionBundle)
submission_adapter = TypeAdapter(AnswerSubmission)
confirm_screen_adapter = TypeAdapter(ConfirmScreen)
confirm_reply_adapter = TypeAdapter(ConfirmReply)


class InterviewReply(TypedDict):
    """묻는 노드(interview_*)의 LLM 응답: 스펙 항목 갱신 + 다음 질문 묶음 초안."""

    items: list[SpecItem]
    questions: Annotated[list[DraftQuestion], Field(max_length=MAX_QUESTIONS)]


interview_reply_adapter = TypeAdapter(InterviewReply)
