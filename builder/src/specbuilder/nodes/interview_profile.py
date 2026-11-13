from langgraph.types import Command

from specbuilder.llm import LLMClient
from specbuilder.state import State

NEXT = "interview_user"


def make_interview_profile(llm: LLMClient):
    """[빈 노드 — G 가 구현] 읽음: `profile`. 채움: `profile`(저장된 프로필이 있으면 그것, 없으면 질문 묶음으로 수집).
    묻는 노드 규칙(`pending_bundle`·`question_round`·`qa`·`interview_stops`)은 interview_user 와 같다. 갈 곳: 자기 자신 | interview_user.
    """

    def interview_profile(state: State) -> Command:
        return Command(goto=NEXT)

    return interview_profile
