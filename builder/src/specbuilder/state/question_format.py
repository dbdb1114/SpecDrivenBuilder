"""질문 묶음 · 답 제출 · 확인 화면 규격 원본 (docs/design/question-format.md).

TypedDict + pydantic TypeAdapter 로 정의한다 — 값이 plain dict 라 State·checkpoint 에 그대로 넣을 수 있고
(BaseModel 은 checkpoint 복원 때 LangGraph 가 "unregistered type" 경고를 내고 향후 막는다),
같은 정의로 pydantic 이 검증하고 FastAPI 가 OpenAPI 스키마를 만든다.
"""

from typing import Annotated, Literal, NotRequired, TypedDict, get_args

from pydantic import (
    AfterValidator,
    BeforeValidator,
    Field,
    StringConstraints,
    TypeAdapter,
)

from specbuilder.state.spec_items import (
    Area,
    ItemId,
    NonEmpty,
    SpecItem,
    delegate_open,
)

MAX_QUESTIONS = 10
# 선택지는 0개(직접 입력만 받는 질문) 또는 2~4개. 1개는 고를 것이 없으므로 받지 않는다.
MIN_OPTIONS, MAX_OPTIONS = 2, 4
# 레이아웃 종류 목록 (2026-11-14 결정, 작업 단위 F). 원본은 여기 하나 — Literal 이라 OpenAPI enum 으로 나가고
# 프론트엔드는 생성 타입으로 받는다. key 를 추가하면 프론트엔드 틀이 없을 때 타입 검사가 실패한다.
LayoutKey = Literal[
    "single-column",
    "top-nav",
    "sidebar-left",
    "list-detail",
    "dashboard",
    "mobile-tabs",
]
LAYOUT_KEYS = get_args(LayoutKey)
# CLI·프론트엔드가 항상 같은 문구로 붙이는 고정 선택지. options 에는 넣지 않는다.
DELEGATE_LABEL = "알아서 정해 주세요"

HexColor = Annotated[str, StringConstraints(pattern=r"^#[0-9A-Fa-f]{6}$")]


class PaletteVisual(TypedDict):
    type: Literal["palette"]
    colors: Annotated[list[HexColor], Field(min_length=1)]


class LayoutVisual(TypedDict):
    type: Literal["layout"]
    key: LayoutKey


Visual = Annotated[PaletteVisual | LayoutVisual, Field(discriminator="type")]


class PreviewColors(TypedDict):
    """역할 이름이 붙은 색 — 프론트엔드가 "몇 번째 색이 무엇인지" 추측하지 않는다.

    surface·text 는 LLM 이 아니라 빌더 코드가 다른 색에서 계산한다 (바탕 위 글자 대비를 코드가 보장).
    """

    background: HexColor
    surface: HexColor
    primary: HexColor
    accent: HexColor
    text: HexColor


class PreviewItem(TypedDict):
    title: NonEmpty
    detail: NonEmpty


class PreviewTexts(TypedDict):
    title: NonEmpty
    menu: list[NonEmpty]
    heading: NonEmpty
    action: NonEmpty
    items: Annotated[list[PreviewItem], Field(min_length=2, max_length=5)]


class Preview(TypedDict):
    layout: LayoutKey
    colors: PreviewColors
    texts: PreviewTexts


def _drop_old_preview(value: object) -> object:
    # 작업 단위 I 이전 checkpoint 의 미리보기(colors 가 목록)는 새 틀에 입힐 문구가 없다 — 지어내지 않고 그림만 뺀다.
    # 같은 묶음의 "이 느낌이 맞나요? (배치: … / 색: …)" 질문은 문장만으로 뜻이 통한다.
    if isinstance(value, dict) and isinstance(value.get("colors"), list):
        return None
    return value


class Option(TypedDict):
    id: str
    label: NonEmpty
    recommended: bool
    visual: Visual | None


def _check_options(options: list) -> list:
    # 답이 이름·장소·숫자인 질문에 선택지를 강제하면 LLM 이 "직접 적어 주세요" 같은 답이 아닌 선택지를 지어낸다 — 빈 목록을 허용한다.
    if options and len(options) < MIN_OPTIONS:
        raise ValueError(f"선택지는 0개 또는 {MIN_OPTIONS}~{MAX_OPTIONS}개")
    # 초안(DraftOption)은 recommended 를 생략할 수 있어 .get 으로 읽는다.
    if sum(1 for o in options if o.get("recommended", False)) > 1:
        raise ValueError("recommended 선택지는 질문당 최대 1개")
    return options


Options = Annotated[
    list[Option],
    Field(max_length=MAX_OPTIONS),
    AfterValidator(_check_options),
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
    preview: Annotated[Preview | None, BeforeValidator(_drop_old_preview)]
    questions: Annotated[list[Question], Field(min_length=1, max_length=MAX_QUESTIONS)]


# --- LLM 이 내는 초안. id 가 없다 — id 는 assign_ids 가 붙인다 (LLM 이 만든 id 는 중복·형식 흔들림).


class DraftOption(TypedDict):
    label: NonEmpty
    recommended: NotRequired[bool]
    visual: NotRequired[Visual | None]


DraftOptions = Annotated[
    list[DraftOption],
    Field(max_length=MAX_OPTIONS),
    AfterValidator(_check_options),
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
                # 고를 것이 없는 질문에 "여러 개 고르기"는 뜻이 없다.
                "multiple": bool(draft["options"]) and draft.get("multiple", False),
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
