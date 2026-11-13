"""스펙 항목 — 노드 사이를 오가는 데이터. 규격 원본 (docs/design/design.md "스펙 항목")."""

from typing import Annotated, Literal, TypedDict

from pydantic import AfterValidator, StringConstraints, TypeAdapter

Area = Literal["function", "design", "tech"]
DecidedBy = Literal["user", "worker"]
Status = Literal["confirmed", "delegated", "unknown"]

# 항목 id 는 LLM 이 제안한다 — 여러 호출에 걸쳐 같은 항목을 가리켜야 해서 의미 있는 slug 가 필요하다. 형식은 코드가 검증.
ItemId = Annotated[str, StringConstraints(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")]
NonEmpty = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

PURPOSE_ITEM_ID = "purpose"


class SpecItem(TypedDict):
    id: ItemId
    name: NonEmpty
    area: Area
    decided_by: DecidedBy
    status: Status
    # 확정된 답, 또는 작업자가 따를 기본 방향. 아직 모름이거나 기본 방향을 아직 못 정한 맡김 항목은 빈 문자열.
    content: str


def _unique_ids(items: list[SpecItem]) -> list[SpecItem]:
    ids = [item["id"] for item in items]
    duplicated = sorted({i for i in ids if ids.count(i) > 1})
    if duplicated:
        raise ValueError(f"스펙 항목 id 중복: {duplicated}")
    return items


SpecItems = Annotated[list[SpecItem], AfterValidator(_unique_ids)]
spec_items_adapter = TypeAdapter(SpecItems)


def purpose_item() -> SpecItem:
    """모든 실행이 처음부터 갖는 "용도" 항목. 묻는 노드의 실행 규칙상 첫 진입에 반드시 묻게 된다."""
    return {
        "id": PURPOSE_ITEM_ID,
        "name": "용도 (누가, 어디서, 무엇을 위해 쓰는가)",
        "area": "function",
        "decided_by": "user",
        "status": "unknown",
        "content": "",
    }


def is_open(item: SpecItem, area: Area) -> bool:
    """묻는 노드가 물어야 하는 항목인가 — 자기 영역, 결정 주체 사용자, 아직 모름."""
    return (
        item["area"] == area
        and item["decided_by"] == "user"
        and item["status"] == "unknown"
    )


def needs_asking(items: list[SpecItem], area: Area) -> bool:
    """묻는 노드의 실행 규칙: 자기 영역에 물어야 하는 항목이 하나라도 있는가."""
    return any(is_open(item, area) for item in items)


def delegate_open(items: list[SpecItem], area: Area) -> list[SpecItem]:
    """물어야 하는 항목을 전부 "작업자에게 맡김"으로 바꾼다 (사용자가 그만 묻기를 골랐거나 상한에 닿았을 때)."""
    return [
        {**item, "status": "delegated"} if is_open(item, area) else item
        for item in items
    ]


def merge_updates(items: list[SpecItem], updates: list[SpecItem]) -> list[SpecItem]:
    """LLM 이 낸 항목 갱신을 반영한다 (upsert, 삭제 없음).

    확정 항목은 바꾸지 않는다 — 사용자의 답을 LLM 이 덮어쓰면 안 된다.
    맡김 항목은 내용(기본 방향)만 바꾼다. 아직 모름 항목과 새 항목은 그대로 반영한다.
    """
    merged = {item["id"]: item for item in items}
    for update in updates:
        current = merged.get(update["id"])
        if current is None or current["status"] == "unknown":
            merged[update["id"]] = update
        elif current["status"] == "delegated":
            merged[update["id"]] = {**current, "content": update["content"]}
    return list(merged.values())
