"""공통 항목 목록 — 빌더가 미리 써 둔 스펙 항목 (docs/design/design.md "공통 항목").

넣을지는 묻는 노드의 LLM 이 id 로 고르고, 질문 문구·선택지·기본 방향은 여기서 붙인다.
LLM 이 매번 쓰면 프로그램마다 묻기도 하고 빠뜨리기도 하고 문구가 흔들리기 때문이다.
원본은 `prompts/common_items.json` — 사용자에게 보이는 고정 문구라 코드 밖에 둔다 (`interview_profile.json` 과 같은 자리).
"""

import json
from typing import Annotated, Literal, NotRequired, TypedDict

from pydantic import AfterValidator, Field, TypeAdapter

from specbuilder.paths import PROMPTS_DIR
from specbuilder.state.question_format import (
    MAX_OPTIONS,
    MAX_QUESTIONS,
    MIN_OPTIONS,
    AnswerSubmission,
    DraftQuestion,
    QuestionBundle,
)
from specbuilder.state.spec_items import (
    DecidedBy,
    ItemId,
    NonEmpty,
    SpecItem,
    is_open,
)

COMMON_ITEMS_FILE = PROMPTS_DIR / "common_items.json"


class CommonOption(TypedDict):
    label: NonEmpty
    # 라벨("네, 넣어 주세요")만으로는 질문을 모르는 작업자가 뜻을 알 수 없어서, 고르면 항목 내용이 될 문장을 따로 둔다.
    content: NonEmpty
    recommended: NotRequired[bool]


class CommonQuestion(TypedDict):
    text: NonEmpty
    multiple: NotRequired[bool]
    options: Annotated[
        list[CommonOption], Field(min_length=MIN_OPTIONS, max_length=MAX_OPTIONS)
    ]


class CommonItem(TypedDict):
    id: ItemId
    name: NonEmpty
    # 기술 영역은 묻는 노드가 없어 공통 항목을 둘 수 없다.
    area: Literal["function", "design"]
    when: NonEmpty
    decided_by: DecidedBy
    question: NotRequired[CommonQuestion]
    # 결정 주체가 작업자이거나 사용자가 맡겼을 때(알아서·답 없음·그만 묻기·상한)의 항목 내용
    default: NonEmpty


def _check(items: list[CommonItem]) -> list[CommonItem]:
    ids = [item["id"] for item in items]
    duplicated = sorted({i for i in ids if ids.count(i) > 1})
    if duplicated:
        raise ValueError(f"공통 항목 id 중복: {duplicated}")
    for item in items:
        question = item.get("question")
        if (item["decided_by"] == "user") != (question is not None):
            raise ValueError(f"{item['id']}: 결정 주체가 사용자인 항목만 질문을 가진다")
        if (
            question
            and sum(o.get("recommended", False) for o in question["options"]) > 1
        ):
            raise ValueError(f"{item['id']}: recommended 선택지는 최대 1개")
    return items


common_items_adapter = TypeAdapter(Annotated[list[CommonItem], AfterValidator(_check)])


def load_common_items(area: str | None = None) -> dict[str, CommonItem]:
    """공통 항목을 id → 항목으로 읽는다. area 를 주면 그 영역 것만. 파일 순서를 지켜 질문 순서가 실행마다 같다."""
    raw = json.loads(COMMON_ITEMS_FILE.read_text(encoding="utf-8"))
    items = common_items_adapter.validate_python(raw["items"])
    return {item["id"]: item for item in items if area in (None, item["area"])}


def render_catalog(catalog: dict[str, CommonItem], items: list[SpecItem]) -> str:
    """LLM 입력용 공통 항목 목록 블록 (지시문 없음 — 지시는 prompts/ 에). 고를 것이 없으면 빈 문자열."""
    if not catalog:
        return ""
    present = {item["id"] for item in items}
    lines = ["## 공통 항목 목록"]
    for common in catalog.values():
        mark = " (이미 넣음)" if common["id"] in present else ""
        lines.append(
            f"- `{common['id']}` {common['name']} — 언제 넣는가: {common['when']}{mark}"
        )
    return "\n".join(lines)


def add_selected(
    items: list[SpecItem], ids: list[str], catalog: dict[str, CommonItem]
) -> list[SpecItem]:
    """LLM 이 고른 id 를 스펙 항목으로 넣는다. 목록에 없는 id 는 버린다 — 잘못 고른 id 하나로 실행 전체를 멈추지 않는다."""
    present = {item["id"] for item in items}
    added = []
    for common_id in dict.fromkeys(ids):
        common = catalog.get(common_id)
        if common is None or common_id in present:
            continue
        asks = common["decided_by"] == "user"
        added.append(
            {
                "id": common_id,
                "name": common["name"],
                "area": common["area"],
                "decided_by": common["decided_by"],
                "status": "unknown" if asks else "delegated",
                "content": "" if asks else common["default"],
            }
        )
    return [*items, *added]


def fixed_questions(
    items: list[SpecItem], catalog: dict[str, CommonItem]
) -> list[DraftQuestion]:
    """아직 모름인 공통 항목의 고정 질문 초안. 확인 화면에서 고치기로 고른 공통 항목도 여기서 다시 묻는다."""
    open_ids = {item["id"] for item in items if is_open(item, item["area"])}
    return [
        {
            "item_id": common["id"],
            "text": common["question"]["text"],
            "multiple": common["question"].get("multiple", False),
            "options": [
                {"label": o["label"], "recommended": o.get("recommended", False)}
                for o in common["question"]["options"]
            ],
        }
        for common in catalog.values()
        if common["id"] in open_ids and "question" in common
    ]


def append_fixed(
    drafts: list[DraftQuestion], fixed: list[DraftQuestion]
) -> list[DraftQuestion]:
    """고정 질문을 묶음 뒤에 붙인다. 묶음 상한을 넘는 것은 아직 모름으로 남아 다음 묶음에서 묻는다."""
    return [*drafts, *fixed[: max(0, MAX_QUESTIONS - len(drafts))]]


def fill_defaults(
    items: list[SpecItem], catalog: dict[str, CommonItem]
) -> list[SpecItem]:
    """맡김인데 내용이 빈 공통 항목에 기본 방향을 넣는다. LLM 을 기다리지 않는다 — 기본 방향이 고정이다."""
    return [
        {**item, "content": catalog[item["id"]]["default"]}
        if item["id"] in catalog
        and item["status"] == "delegated"
        and not item["content"]
        else item
        for item in items
    ]


def record_answers(
    items: list[SpecItem],
    bundle: QuestionBundle,
    submission: AnswerSubmission,
    catalog: dict[str, CommonItem],
) -> list[SpecItem]:
    """apply_submission 뒤에 공통 항목의 내용을 고친다 — 고른 선택지는 작업자용 문장으로, 맡긴 것은 기본 방향으로."""
    answers = {a["question_id"]: a for a in submission["answers"]}
    by_id = {item["id"]: item for item in items}
    for question in bundle["questions"]:
        common = catalog.get(question["item_id"])
        answer = answers.get(question["id"])
        if (
            common is None
            or "question" not in common
            or question["item_id"] not in by_id
        ):
            continue
        if answer is None or answer["kind"] != "option":
            continue
        labels = {o["id"]: o["label"] for o in question["options"]}
        contents = {o["label"]: o["content"] for o in common["question"]["options"]}
        chosen = [labels[oid] for oid in answer["option_ids"]]
        by_id[question["item_id"]] = {
            **by_id[question["item_id"]],
            "content": " ".join(contents.get(label, label) for label in chosen),
        }
    return fill_defaults(list(by_id.values()), catalog)
