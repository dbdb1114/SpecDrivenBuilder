from langgraph.types import Command, interrupt

from specbuilder.llm import LLMCallError, LLMClient, parse_json_reply
from specbuilder.paths import load_prompt
from specbuilder.state import State

MAX_QUESTIONS = 3


def render_context(state: State) -> str:
    """요청 원문과 지금까지의 문답을 LLM 입력용 데이터 블록으로 만든다 (지시문 없음 — 지시는 prompts/ 에)."""
    lines = ["## 요청 원문", state["request"].strip(), "", "## 지금까지의 질문과 답"]
    if not state["qa"]:
        lines.append("(없음)")
    for i, qa in enumerate(state["qa"], 1):
        lines += [f"Q{i}. {qa['question']}", f"A{i}. {qa['answer']}"]
    return "\n".join(lines)


def make_interview_user(llm: LLMClient):
    """LLM 클라이언트를 주입한 interview_user 노드를 만든다."""
    system = load_prompt("interview_user")

    def interview_user(state: State) -> Command:
        if state["pending_question"] is None:
            if len(state["qa"]) >= MAX_QUESTIONS:
                return Command(goto="generate_artifacts")
            reply = parse_json_reply(llm.complete(system, render_context(state)))
            question = reply.get("question")
            if question is not None and not isinstance(question, str):
                raise LLMCallError(f"question 필드가 문자열이 아님: {reply!r}")
            if not question or not question.strip():
                return Command(goto="generate_artifacts")
            # 질문을 먼저 체크포인트에 남기고 자기 자신으로 돌아온다 — 그래야 resume 시 LLM 재호출 없이 interrupt 로 바로 들어간다.
            return Command(
                update={"pending_question": question.strip()}, goto="interview_user"
            )

        answer = interrupt(state["pending_question"])
        return Command(
            update={
                "qa": [{"question": state["pending_question"], "answer": str(answer)}],
                "pending_question": None,
            },
            goto="interview_user",
        )

    return interview_user
