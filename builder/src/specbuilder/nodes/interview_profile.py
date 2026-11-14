import json
from typing import Annotated, Literal, NotRequired, TypedDict

from langgraph.types import Command, interrupt
from pydantic import Field, TypeAdapter, ValidationError

from specbuilder.llm import LLMClient
from specbuilder.paths import PROMPTS_DIR
from specbuilder.profile_store import load_profile, save_profile
from specbuilder.state import AnswerSubmission, Profile, QuestionBundle, State
from specbuilder.state.question_format import (
    DraftOption,
    assign_ids,
    validate_submission,
)
from specbuilder.state.spec_items import NonEmpty

NODE = "interview_profile"
NEXT = "interview_user"
QUESTIONS_FILE = PROMPTS_DIR / f"{NODE}.json"
FIELDS = tuple(Profile.__annotations__)


class ProfileQuestion(TypedDict):
    """`prompts/interview_profile.json` 의 질문 한 개. 질문 묶음 초안 + 답이 들어갈 프로필 필드와 기본값."""

    field: Literal[
        "domain", "tech_exposure", "explanation", "environment", "delegation"
    ]
    # 한 필드를 여러 질문이 채울 때(환경 = 운영체제 + AI 도구·요금제) 답 앞에 붙는 이름
    label: NonEmpty
    text: NonEmpty
    multiple: NotRequired[bool]
    options: list[DraftOption]
    # "알아서 정해 주세요" · 답 없음 · "그만" 일 때 프로필에 들어가는 문장
    default: NonEmpty


questions_adapter = TypeAdapter(Annotated[list[ProfileQuestion], Field(min_length=1)])


def load_questions() -> list[ProfileQuestion]:
    """고정 질문 목록을 읽고 프로필의 모든 필드를 채우는지 확인한다."""
    raw = json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))
    questions = questions_adapter.validate_python(raw["questions"])
    missing = set(FIELDS) - {q["field"] for q in questions}
    if missing:
        raise ValueError(
            f"{QUESTIONS_FILE.name}: 채우지 않는 프로필 필드 {sorted(missing)}"
        )
    return questions


def build_bundle(questions: list[ProfileQuestion]) -> QuestionBundle:
    """고정 질문으로 질문 묶음을 만든다. 축이 고정이라 요청마다 질문이 달라질 이유가 없다 — LLM 을 부르지 않는다."""
    drafts = [
        {
            # item_id 는 스펙 항목이 아니라 프로필 필드를 가리킨다 — 실행 기록에서 어느 축의 질문인지 보이게.
            "item_id": f"profile-{i}-{q['field'].replace('_', '-')}",
            "text": q["text"],
            "multiple": q.get("multiple", False),
            "options": q["options"],
        }
        for i, q in enumerate(questions, 1)
    ]
    return assign_ids(drafts, 1, True)


def profile_from(
    bundle: QuestionBundle,
    submission: AnswerSubmission,
    questions: list[ProfileQuestion],
) -> Profile:
    """답을 프로필로 바꾼다. 선택지 문구·직접 입력은 그대로, 맡김·답 없음은 그 질문의 기본값 문장으로."""
    answers = {a["question_id"]: a for a in submission["answers"]}
    parts = {field: [] for field in FIELDS}
    for asked, spec in zip(bundle["questions"], questions):
        answer = answers.get(asked["id"], {"kind": "delegate"})
        if answer["kind"] == "option":
            labels = {o["id"]: o["label"] for o in asked["options"]}
            value = ", ".join(labels[oid] for oid in answer["option_ids"])
        elif answer["kind"] == "custom":
            value = answer["text"]
        else:
            value = spec["default"]
        parts[spec["field"]].append((spec["label"], value))
    return {
        field: (
            values[0][1]
            if len(values) == 1
            else " / ".join(f"{label}: {value}" for label, value in values)
        )
        for field, values in parts.items()
    }


def make_interview_profile(llm: LLMClient):
    """interview_profile 노드를 만든다. 질문이 고정이라 LLM 을 쓰지 않는다 — 인자는 그래프 조립의 팩토리 규약 때문에만 받는다."""
    questions = load_questions()
    fresh_bundle = build_bundle(questions)

    def interview_profile(state: State) -> Command:
        bundle = state["pending_bundle"]
        if bundle is not None:
            try:
                submission = validate_submission(bundle, interrupt(bundle))
            except (ValidationError, ValueError) as e:
                raise ValueError(f"답 제출이 규격에 맞지 않음: {e}") from e
            profile = profile_from(bundle, submission, questions)
            save_profile(profile)
            reason = "user_finished" if submission["action"] == "finish" else "resolved"
            # 프로필 문답은 qa 에 남기지 않는다 — qa 는 interview_user 의 문답 컨텍스트라 스펙 문답에 섞인다.
            return Command(
                update={
                    "profile": profile,
                    "pending_bundle": None,
                    "question_round": 0,
                    "interview_stops": [{"node": NODE, "reason": reason, "rounds": 1}],
                },
                goto=NEXT,
            )

        profile = state["profile"] or load_profile()
        if profile is not None:
            return Command(update={"profile": profile}, goto=NEXT)
        # 묶음을 먼저 체크포인트에 남기고 자기 자신으로 돌아온다 — interview_user 와 같은 실행 규칙.
        return Command(update={"pending_bundle": fresh_bundle}, goto=NODE)

    return interview_profile
