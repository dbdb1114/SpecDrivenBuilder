import json

from langgraph.types import Command, interrupt
from pydantic import ValidationError

from specbuilder.llm import LLMCallError, LLMClient, parse_json_reply
from specbuilder.paths import load_prompt
from specbuilder.state import State
from specbuilder.state.question_format import (
    apply_submission,
    assign_ids,
    interview_reply_adapter,
    validate_submission,
)
from specbuilder.state.spec_items import (
    PURPOSE_ITEM_ID,
    delegate_open,
    is_open,
    merge_updates,
    needs_asking,
    spec_items_adapter,
)

NODE = "interview_user"
AREA = "function"
NEXT = "interview_design"
# 진입 1회당 질문 묶음 상한. 보통 2~3묶음이면 끝난다 — 끝없이 묻는 것만 막는다.
MAX_ROUNDS = 5


def reopened_ids(items: list, qa: list) -> set[str]:
    """확인 화면에서 사용자가 고치기로 고른 항목 — 아직 모름인데 지난 답이 있다.

    답을 받은 항목은 확정·맡김이 되고 LLM 은 그 상태를 아직 모름으로 되돌릴 수 없으므로(merge_updates), 이 조합은 confirm_spec 만 만든다.
    """
    answered = {line["item_id"] for line in qa}
    return {
        item["id"] for item in items if is_open(item, AREA) and item["id"] in answered
    }


def render_context(state: State) -> str:
    """요청 원문·결정 위임 범위·현재 스펙 항목·지난 문답을 LLM 입력용 데이터 블록으로 만든다 (지시문 없음 — 지시는 prompts/ 에)."""
    profile = state["profile"]
    lines = [
        "## 요청 원문",
        state["request"].strip(),
        "",
        # 위임 범위가 "누가 정하는가"(decided_by)의 경계를 옮긴다 (docs/design/design.md "interview_user").
        "## 결정 위임 범위",
        (profile["delegation"] or "(모름)") if profile else "(모름)",
        "",
        "## 현재 스펙 항목",
        json.dumps(state["spec_items"], ensure_ascii=False, indent=2),
        "",
    ]
    reopened = reopened_ids(state["spec_items"], state["qa"])
    if reopened:
        lines += ["## 사용자가 고치기로 고른 항목", ", ".join(sorted(reopened)), ""]
    lines += ["## 지금까지의 질문과 답"]
    if not state["qa"]:
        lines.append("(없음)")
    for i, qa in enumerate(state["qa"], 1):
        lines += [f"Q{i}. [{qa['item_id']}] {qa['question']}", f"A{i}. {qa['answer']}"]
    return "\n".join(lines)


def _parse_reply(text: str, items: list, reopened: set[str]) -> tuple[list, list]:
    try:
        reply = interview_reply_adapter.validate_python(parse_json_reply(text))
    except ValidationError as e:
        raise LLMCallError(f"{NODE} 응답이 규격에 맞지 않음: {e}") from e
    # 사용자가 고치겠다고 고른 항목을 LLM 이 지난 답으로 다시 채우면 고치기가 조용히 무시된다 — 다시 묻게 아직 모름으로 둔다.
    reply["items"] = [i for i in reply["items"] if i["id"] not in reopened]
    for item in reply["items"]:
        if item["area"] != AREA:
            raise LLMCallError(f"{NODE} 는 {AREA} 항목만 다룬다: {item['id']}")
        if item["decided_by"] == "worker" and item["status"] == "unknown":
            raise LLMCallError(f"작업자가 정할 항목이 아직 모름: {item['id']}")
    try:
        merged = spec_items_adapter.validate_python(
            merge_updates(items, reply["items"])
        )
    except ValidationError as e:
        raise LLMCallError(f"{NODE} 항목 갱신이 규격에 맞지 않음: {e}") from e
    return merged, reply["questions"]


def _check_questions(questions: list, items: list) -> list:
    open_ids = {item["id"] for item in items if is_open(item, AREA)}
    asked = [q["item_id"] for q in questions]
    if not questions:
        raise LLMCallError(f"아직 모름인 항목이 있는데 질문이 없음: {sorted(open_ids)}")
    if len(asked) != len(set(asked)):
        raise LLMCallError(f"한 묶음에 같은 항목을 두 번 물음: {asked}")
    stray = [i for i in asked if i not in open_ids]
    if stray:
        raise LLMCallError(f"물을 필요가 없는 항목을 물음: {stray}")
    # 뒤의 모든 결정이 용도에 달려 있으므로 용도 질문은 항상 맨 앞 (안정 정렬이라 나머지 순서는 LLM 의 중요도 순 유지).
    return sorted(questions, key=lambda q: q["item_id"] != PURPOSE_ITEM_ID)


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


def make_interview_user(llm: LLMClient):
    """LLM 클라이언트를 주입한 interview_user 노드를 만든다."""
    system = load_prompt(NODE)
    schema = interview_reply_adapter.json_schema()

    def interview_user(state: State) -> Command:
        items = state["spec_items"]
        rounds = state["question_round"]
        bundle = state["pending_bundle"]

        if bundle is not None:
            try:
                submission = validate_submission(bundle, interrupt(bundle))
            except (ValidationError, ValueError) as e:
                raise ValueError(f"답 제출이 규격에 맞지 않음: {e}") from e
            items, qa = apply_submission(items, bundle, submission, NODE, AREA)
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
            return _stop(delegate_open(items, AREA), "round_limit", rounds)
        # 돌아오는 경로의 실행 규칙: 물을 항목이 없으면 기록 없이 지나간다.
        # 이번 진입에서 이미 물었다면(rounds > 0) 마지막 답을 반영하는 호출이 필요하므로 지나가지 않는다.
        if rounds == 0 and not needs_asking(items, AREA):
            return Command(goto=NEXT)

        items, questions = _parse_reply(
            llm.complete(system, render_context(state), schema),
            items,
            reopened_ids(items, state["qa"]),
        )
        if not needs_asking(items, AREA):
            return _stop(items, "resolved", rounds)
        bundle = assign_ids(_check_questions(questions, items), rounds + 1, True)
        # 묶음을 먼저 체크포인트에 남기고 자기 자신으로 돌아온다 — 그래야 resume 시 LLM 재호출 없이 interrupt 로 바로 들어간다.
        return Command(
            update={"spec_items": items, "pending_bundle": bundle}, goto=NODE
        )

    return interview_user
