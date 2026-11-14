import json
from typing import Annotated, Literal, TypedDict

from langgraph.types import Command
from pydantic import Field, TypeAdapter, ValidationError

from specbuilder.llm import LLMCallError, LLMClient, parse_json_reply
from specbuilder.paths import load_prompt
from specbuilder.registry.client import NAME_PATTERNS, VERSION_PATTERN
from specbuilder.registry.refs import PackageRef, render_content
from specbuilder.state import State
from specbuilder.state.spec_items import (
    ItemId,
    NonEmpty,
    SpecItem,
    merge_updates,
    spec_items_adapter,
)

NODE = "select_stack"
NEXT = "verify_stack"
BACK = "interview_user"
TECH_PREFIX = "tech-"
# 실행 전체에서 interview_user 로 돌아가는 횟수. interview_user 는 한 번 들어가면 묶음 5개까지 물을 수 있어 1회면 충분하다.
MAX_STACK_RETURNS = 1
# 주요 도구만 버전을 정한다 — 세부 라이브러리는 작업자가 lock 파일로 정한다.
MAX_PACKAGES = 10


class DraftPackage(TypedDict):
    registry: Literal["npm", "pypi", "maven", "eol"]
    name: NonEmpty
    version: NonEmpty


class DraftTechItem(TypedDict):
    id: ItemId
    name: NonEmpty
    choice: NonEmpty
    reason: NonEmpty
    packages: Annotated[list[DraftPackage], Field(max_length=4)]
    # 이 기술이 쓰이는 프로그램의 부분. 런타임처럼 여러 부분이 같이 쓰면 비운다.
    parts: list[Literal["frontend", "backend", "database"]]


class MissingInfo(TypedDict):
    id: ItemId
    name: NonEmpty


class StackReply(TypedDict):
    items: list[DraftTechItem]
    missing: list[MissingInfo]


stack_reply_adapter = TypeAdapter(StackReply)


def render_context(state: State, can_ask: bool) -> str:
    """요청 원문·프로필의 환경·스펙 항목·검증에서 돌아온 불일치를 LLM 입력용 데이터 블록으로 만든다 (지시는 prompts/ 에)."""
    profile = state["profile"]
    lines = [
        "## 요청 원문",
        state["request"].strip(),
        "",
        "## 사용자의 환경",
        (profile["environment"] or "(모름)") if profile else "(모름)",
        "",
        "## 현재 스펙 항목",
        json.dumps(state["spec_items"], ensure_ascii=False, indent=2),
        "",
        "## 저장소 검증에서 맞지 않은 항목",
    ]
    mismatches = state["stack_mismatches"]
    if not mismatches:
        lines.append("(없음)")
    lines += [f"- [{m['item_id']}] {m['reason']}" for m in mismatches]
    lines += [
        "",
        "## 부족한 정보를 사용자에게 다시 물을 수 있는가",
        "예" if can_ask else "아니오",
    ]
    return "\n".join(lines)


def _parse_reply(text: str) -> StackReply:
    try:
        reply = stack_reply_adapter.validate_python(parse_json_reply(text))
    except ValidationError as e:
        raise LLMCallError(f"{NODE} 응답이 규격에 맞지 않음: {e}") from e
    count = 0
    for draft in reply["items"]:
        for package in draft["packages"]:
            count += 1
            if not NAME_PATTERNS[package["registry"]].match(package["name"]):
                raise LLMCallError(
                    f"{NODE}: {package['registry']} 패키지 이름 형식이 아님: {package['name']!r}"
                )
            if not VERSION_PATTERN.match(package["version"]):
                raise LLMCallError(
                    f"{NODE}: 버전 형식이 아님: {package['name']}@{package['version']!r}"
                )
    if count > MAX_PACKAGES:
        raise LLMCallError(
            f"{NODE}: 버전을 정한 패키지가 {count}개 (상한 {MAX_PACKAGES})"
        )
    return reply


def _tech_items(drafts: list[DraftTechItem]) -> list[SpecItem]:
    items = []
    for draft in drafts:
        item_id = (
            draft["id"]
            if draft["id"].startswith(TECH_PREFIX)
            else TECH_PREFIX + draft["id"]
        )
        refs = [
            PackageRef(p["registry"], p["name"], p["version"])
            for p in draft["packages"]
        ]
        items.append(
            {
                "id": item_id,
                "name": draft["name"],
                "area": "tech",
                "decided_by": "worker",
                # 빌더가 골랐지만 작업자가 따를 기본 방향이다 — 사용자가 확정한 것과 섞이지 않게 맡김으로 둔다.
                "status": "delegated",
                "content": render_content(
                    draft["choice"],
                    refs,
                    draft["reason"],
                    # 같은 부분을 두 번 적어도 한 번만 — 순서는 LLM 이 쓴 대로.
                    list(dict.fromkeys(draft["parts"])),
                ),
            }
        )
    return items


def _missing_items(missing: list[MissingInfo], items: list[SpecItem]) -> list[SpecItem]:
    existing = {item["id"]: item for item in items}
    added = []
    for info in missing:
        current = existing.get(info["id"])
        # 이미 답이 있거나 다른 영역의 항목이면 다시 묻지 않는다 — 실행 규칙상 "아직 모름" 만 묻게 된다.
        if current is not None and not (
            current["area"] == "function"
            and current["decided_by"] == "user"
            and current["status"] == "unknown"
        ):
            continue
        added.append(
            {
                "id": info["id"],
                "name": info["name"],
                "area": "function",
                "decided_by": "user",
                "status": "unknown",
                "content": "",
            }
        )
    return added


def _validated(items: list[SpecItem]) -> list[SpecItem]:
    try:
        return spec_items_adapter.validate_python(items)
    except ValidationError as e:
        raise LLMCallError(f"{NODE} 항목이 규격에 맞지 않음: {e}") from e


def make_select_stack(llm: LLMClient):
    """LLM 클라이언트를 주입한 select_stack 노드를 만든다."""
    system = load_prompt(NODE)
    schema = stack_reply_adapter.json_schema()

    def select_stack(state: State) -> Command:
        items = state["spec_items"]
        returns = state["stack_returns"]
        can_ask = returns < MAX_STACK_RETURNS
        reply = _parse_reply(
            llm.complete(system, render_context(state, can_ask), schema)
        )

        missing = _missing_items(reply["missing"], items) if can_ask else []
        if missing:
            return Command(
                update={
                    "spec_items": _validated(merge_updates(items, missing)),
                    "stack_returns": returns + 1,
                    "stack_mismatches": [],
                },
                goto=BACK,
            )

        if not reply["items"]:
            raise LLMCallError(f"{NODE}: 기술 스펙 항목도 부족한 정보도 없음")
        # 기술 항목은 통째로 다시 정한다 — merge_updates 는 기존 항목을 덮지 않아 버전을 고칠 수 없다.
        kept = [item for item in items if item["area"] != "tech"]
        update = {
            "spec_items": _validated(kept + _tech_items(reply["items"])),
            "stack_mismatches": [],
        }
        # 검증에서 돌아온 게 아니면 새 진입이다 — verify_stack 의 왕복 횟수를 새로 센다 (confirm_spec 에서 고쳐 돌아온 경우 등).
        if not state["stack_mismatches"]:
            update["verify_returns"] = 0
        return Command(update=update, goto=NEXT)

    return select_stack
