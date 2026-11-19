"""노드별 설정 — 어느 노드를 어느 모델·effort 로 돌릴지 (`config/nodes.json`).

값이 null 이면 기본값을 쓴다 (모델은 `SPECBUILDER_MODEL`, effort 는 클라이언트의 기본). 파일은 호출할 때마다 다시 읽는다 —
고치면 서버를 다시 띄우지 않아도 그 뒤의 호출부터 반영된다 (docs/design/backoffice.md).
"""

import json
from typing import Literal, TypedDict

from pydantic import TypeAdapter, ValidationError

from specbuilder.paths import BUILDER_ROOT
from specbuilder.state.spec_items import NonEmpty

CONFIG_FILE = BUILDER_ROOT / "config" / "nodes.json"
# LLM 을 호출하는 노드. 여기 없는 이름이 파일에 있으면 오타로 보고 거부한다 — 조용히 무시하면 설정이 안 먹는 이유를 찾기 어렵다.
LLM_NODES = (
    "interview_user",
    "interview_design",
    "select_stack",
    "select_skills",
    "generate_artifacts",
)
Effort = Literal["low", "medium", "high", "xhigh", "max"]


class NodeSetting(TypedDict):
    model: NonEmpty | None
    effort: Effort | None


DEFAULT = {"model": None, "effort": None}
_adapter = TypeAdapter(dict[str, NodeSetting])


def validate(data: object) -> dict[str, NodeSetting]:
    """설정 값을 검증한다. 형식이 틀리거나 모르는 노드가 있으면 ValueError."""
    try:
        settings = _adapter.validate_python(data)
    except ValidationError as e:
        raise ValueError(f"{CONFIG_FILE.name} 형식이 맞지 않음: {e}") from e
    unknown = sorted(set(settings) - set(LLM_NODES))
    if unknown:
        raise ValueError(f"{CONFIG_FILE.name} 에 모르는 노드: {unknown}")
    return settings


def load() -> dict[str, NodeSetting]:
    """설정 파일을 읽어 검증한다. 파일이 없으면 모든 노드가 기본값이다. 형식이 틀리면 ValueError."""
    if not CONFIG_FILE.is_file():
        return {}
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"{CONFIG_FILE.name} 형식이 맞지 않음: {e}") from e
    return validate(data)


def save(data: object) -> dict[str, NodeSetting]:
    """검증을 통과한 설정만 파일에 쓴다 (백오피스). 틀리면 ValueError 이고 파일은 그대로다."""
    settings = validate(data)
    # 사람이 git diff 로 보고 커밋하는 파일이라 레포의 모양(노드 한 줄씩, 정해진 순서)으로 쓴다.
    lines = [
        f'  "{node}": {{ "model": {json.dumps(settings[node]["model"], ensure_ascii=False)},'
        f' "effort": {json.dumps(settings[node]["effort"])} }}'
        for node in LLM_NODES
        if node in settings
    ]
    CONFIG_FILE.write_text("{\n" + ",\n".join(lines) + "\n}\n", encoding="utf-8")
    return settings


def setting(node: str) -> NodeSetting:
    """노드 하나의 설정. 파일에 없는 노드는 기본값."""
    return load().get(node, DEFAULT)
