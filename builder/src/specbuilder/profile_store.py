"""사용자 프로필의 저장과 재사용 (docs/design/interview-profile.md "저장").

프로필은 사용자에 대한 정보라 프로젝트를 넘어 재사용한다 — 레포 밖(사용자 홈)에 둔다. 레포에 커밋될 일도 없다.
"""

import json
import os
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from specbuilder.state import Profile

PROFILE_PATH_ENV = "SPECBUILDER_PROFILE_PATH"
DEFAULT_PROFILE_PATH = Path.home() / ".specbuilder" / "profile.json"

profile_adapter = TypeAdapter(Profile)


def profile_path() -> Path:
    """저장 경로. 환경 변수가 있으면 그것 — 호출할 때마다 읽어 테스트가 경로를 바꿀 수 있다."""
    return Path(os.environ.get(PROFILE_PATH_ENV) or DEFAULT_PROFILE_PATH)


def load_profile() -> Profile | None:
    """저장된 프로필을 읽는다. 없거나 깨졌으면 None — 다시 물어 덮어쓰면 되므로 실패로 다루지 않는다."""
    try:
        raw = json.loads(profile_path().read_text(encoding="utf-8"))
        # TypedDict 검증은 모르는 키를 버린다 — 사용자가 파일에 이름 등을 적어 넣어도 프로필에 실리지 않는다.
        return profile_adapter.validate_python(raw)
    except OSError, json.JSONDecodeError, ValidationError:
        return None


def save_profile(profile: Profile) -> None:
    """프로필을 저장한다. 폴더가 없으면 만든다."""
    path = profile_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
