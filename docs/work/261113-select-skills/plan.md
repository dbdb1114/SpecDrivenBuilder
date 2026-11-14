# 작업 단위 C — select_skills · 공통 스킬 (브랜치 `feat/select-skills`)

승인 (2026-11-13): 계획 전체 — `graph/main.py` 2줄 수정 포함. Codex 는 사용자가 설치한 뒤 실행 검증한다.
변경 (2026-11-14): Codex 실행 검증은 미루고 미검증 사실을 기록한 채 커밋한다 (전체 진행을 맡은 develop-2 세션의 요청).

## 1. 분석 (현재 상태)

- [확정] A 가 `develop` 에 머지됨 (`2b13db7`). 선행 조건 3개 충족: 스펙 항목·JSON 규격 모델(`state/spec_items.py`, `state/question_format.py`),
  노드 8개 등록 + `nodes/select_skills.py` 빈 노드, 노드별 fake LLM(`tests/fakes/fake_llm.py`). `uv run pytest -q` → 44 passed.
- [확정] `State.skills: list[SkillEntry]` (`name`·`when`·`source: "common"|"new"`·`basis: list[str]`) 가 이미 선언돼 있다. State 스키마를 고칠 필요 없음.
- [확정] `graph/build.py` 는 `make_select_skills(llm)` 을 `destinations=("confirm_spec",)` 로 이미 등록했다. 고칠 필요 없음.
- [확정] `generate_artifacts` 는 LLM 에게 `spec.md`·`SKILL.md`·`AGENTS.md` 세 파일을 구분선 형식으로 받고, `SKILL.md` 를 **폴더 루트**에 둔다.
  `state["skills"]` 를 읽지 않는다.
- [확정] A 의 실행 검증에서 "스킬이 발견·로드되는가" 가 3건 모두 실패 — 루트의 `SKILL.md` 는 작업자의 스킬 목록에 안 잡힌다.
- [확정] Claude Code 2.1.323 은 `.claude/skills/<이름>/SKILL.md` 만 발견한다. 빈 폴더에 `.claude/skills/probe-claude`,
  `.agents/skills/probe-agents` 를 두고 `claude -p --setting-sources project` 의 init 을 보니 `probe-claude` 만 skills 목록에 있었다 (2026-11-13).
- [확정] Codex 는 현재 폴더부터 저장소 루트까지의 `.agents/skills/<이름>/SKILL.md` 를 읽는다 (공식 문서 developers.openai.com/codex/skills, 2026-11-13 확인).
  → 두 작업자가 같이 읽는 경로는 없다.
- [확정] CLI(`graph/main.py`) 는 `(run_dir / name).write_text(...)` 로 쓴다 — 파일명에 하위 폴더가 있으면 상위 폴더가 없어 실패한다.
  `run.json` 에 `skills` 를 남기지 않는다.
- [확정] `builder/templates/`, `builder/tests/templates/` 는 비어 있다 (`.gitkeep` 만).
- [확정] 이 PC 에 `codex` 가 설치돼 있지 않다 (`which codex` → not found).

## 2. 계획 단계에서 정할 것 — 결정

| 항목 | 결정 | 이유 |
|---|---|---|
| 공통 스킬 목록의 저장 형식 | `builder/templates/skills/<이름>/SKILL.md` 폴더가 곧 목록. 별도 목록 파일 없음 — 이름과 "언제 쓰는지"는 각 SKILL.md 의 frontmatter 에서 읽는다 | 원본이 한 곳이라 목록과 본문이 어긋날 수 없다. 산출물에 그대로 복사되는 파일이므로 `templates/` 가 맞는 자리 |
| 첫 공통 스킬 | `verify-before-report` — "다 됐다"고 말하기 전에 프로그램을 실제로 실행해 스펙의 완료 기준을 확인하고, 사용자의 말로 보고한다 | 어느 프로그램에나 쓰인다. 비개발자는 코드를 검토할 수 없어 "됐다"는 말을 그대로 믿는다 — 인수 조건과 직결 |
| 산출물에서 스킬을 두는 경로 | 스킬마다 **두 곳에 같은 내용**: `.claude/skills/<이름>/SKILL.md`, `.agents/skills/<이름>/SKILL.md`. 루트 `SKILL.md` 는 없앤다 | 위 분석 — 공통 경로가 없다. 산출물은 Claude 전용이면 안 된다 |
| 발견 실패 대비 | 산출물 AGENTS.md "작업 절차" 에 스킬 이름과 경로(`.agents/skills/...`)를 적게 한다 | 스킬 목록에 안 잡히는 작업자도 파일을 직접 읽고 시작한다 |
| 새로 쓰는 스킬의 frontmatter | LLM 은 **본문만** 쓰고, `name`·`description` 은 코드가 스킬 목록 값으로 템플릿(`templates/SKILL.md`)에 채운다 | 필수 필드 누락·select_skills 와의 불일치가 구조적으로 불가능. `description` 은 JSON 따옴표 문자열로 넣어 YAML 이 깨지지 않게 한다 |
| 스킬 수 | 1~6개. 새로 쓰는 스킬 최소 1개(그 프로그램을 만드는 스킬) | 스킬이 0개면 작업 순서가 사라진다. 상한은 생성 1회 호출의 출력 길이를 막는 용도 |
| 미결정 전제 | 공통(템플릿 방식 쪽)과 새로 씀(프로세스 가이드 방식 쪽)을 둘 다 지원. 비중을 코드로 고정하지 않는다 | `design.md` "select_skills" 그대로 |

LLM 호출: `select_skills` 1회 추가 — `design.md` "LLM 호출 수" 에 이미 정해진 호출이다. `generate_artifacts` 는 1회 그대로.

## 3. 변경 요지

**select_skills** (`nodes/select_skills.py`, `prompts/select_skills.md`)
- 입력: 스펙 항목 전체(JSON) + 공통 스킬 목록(이름·언제 쓰는지). 출력: `{"skills": [{name, when, source, basis}]}` — `--json-schema` 로 형식 강제.
- `basis` 는 스펙 항목 id 의 enum, 호출마다 스키마를 만든다 — 없는 항목을 근거로 대는 것을 형식 단계에서 막는다.
- 코드 검증: `common` 은 목록에 있는 이름만(그리고 "언제 쓰는지"는 목록의 것으로 덮어쓴다), `new` 는 목록 이름과 겹치지 않는 slug,
  이름 중복 없음, `new` 최소 1개. 어기면 `LLMCallError`.
- 반환: `Command(update={"skills": ...}, goto="confirm_spec")`.

**공통 스킬 목록** (`src/specbuilder/common_skills.py` 새 모듈, `paths.py` 에 `TEMPLATES_DIR` 한 줄)
- `load_common_skills()` → `{이름: {description, content}}`. select_skills 와 generate_artifacts 가 같이 쓴다 — 노드끼리 import 하지 않게 별도 모듈.

**generate_artifacts** (`nodes/generate_artifacts.py`, `prompts/generate_artifacts.md`)
- LLM 입력에 "## 스킬 목록" 블록 추가 (이름·언제 쓰는지·출처·경로).
- LLM 출력: `spec.md`, `AGENTS.md`, 새로 쓰는 스킬마다 `skills/<이름>.md`(본문만). 공통 스킬은 LLM 이 쓰지 않는다.
- 코드가 조립: 공통 스킬은 템플릿 원문 그대로, 새 스킬은 `templates/SKILL.md` 에 frontmatter + 본문. 각각 두 경로에 넣는다.
- 프로필을 다루는 부분은 건드리지 않는다 (G).

## 4. 건드릴 파일

| 파일 | 변경 |
|---|---|
| `builder/src/specbuilder/nodes/select_skills.py` | 빈 노드 → 구현 |
| `builder/prompts/select_skills.md` | 새 프롬프트 |
| `builder/src/specbuilder/common_skills.py` | 새 모듈 — 공통 스킬 목록 읽기 |
| `builder/src/specbuilder/paths.py` | `TEMPLATES_DIR` 한 줄 추가 |
| `builder/templates/skills/verify-before-report/SKILL.md` | 첫 공통 스킬 |
| `builder/templates/SKILL.md` | 새로 쓰는 스킬의 서식 (frontmatter + 본문 자리) |
| `builder/src/specbuilder/nodes/generate_artifacts.py` | 스킬 목록을 받아 스킬 여러 개 조립 |
| `builder/prompts/generate_artifacts.md` | 써야 할 파일·출력 형식 변경 |
| `builder/tests/nodes/test_select_skills.py` | 다시 씀 |
| `builder/tests/nodes/test_generate_artifacts.py` | 새 형식에 맞춤 + 스킬 조립 테스트 |
| `builder/tests/templates/test_templates.py`, `builder/tests/templates/snapshots/` | 스냅샷 테스트 (공통 스킬 원문, 새 스킬 서식) + 플레이스홀더·위험 명령 검사. 새 의존성 없이 파일 비교 |
| `builder/tests/fakes/fake_llm.py` | `DEFAULT_REPLIES` 에 `select_skills` 한 줄, `files_reply` 를 새 출력 형식으로 |
| `builder/tests/test_graph.py` | 산출물 파일 집합·LLM 호출 순서 단언을 새 구조로 |
| `builder/src/specbuilder/graph/main.py` | **범위 밖 — 승인 필요.** 2줄: 쓰기 전에 상위 폴더 생성, `run.json` 에 `skills` 기록 |
| `docs/design/design.md` | "select_skills" 절에 결정(첫 공통 스킬·저장 형식·경로) 추가, "미결정" 에서 자기 줄 하나 삭제 |
| `builder/AGENTS.md` | 구조의 `templates/` 설명 한 줄을 실제 구성으로 |

건드리지 않음: `graph/build.py`, `state/`, 다른 노드 파일, `api/`, `frontend/`.

## 5. 검증

1. `cd builder && uv run pytest -q`, `uv run ruff check . && uv run ruff format --check .`
2. 품질 회귀: 3 케이스를 같은 모델(`claude-sonnet-5-5`)로 바꾸기 전(계획 작성 중 실행) / 후. 스킬 수·출처·LLM 호출 수·줄 수·플레이스홀더 grep 을 나란히.
3. 실행 검증 (`claude -p`, 빈 임시 폴더): init 의 skills 목록에 산출물 스킬이 전부 있는가, AGENTS.md 가 읽히는가, 첫 작업이 되묻지 않고 시작되는가.
4. 공통 스킬 실행 검증: `verify-before-report` 만 든 임시 폴더에서 작은 작업을 시키고 스킬이 로드되는지 본다 — Claude Code, 그리고 Codex(아래 열린 질문).

## 6. 열린 질문 (승인 때 답 필요)

- `graph/main.py` 2줄 수정 — 하위 폴더 경로 없이는 스킬을 발견시킬 방법이 없다.
- Codex 가 설치돼 있지 않아 "양쪽에서 실행 검증" 의 Codex 쪽을 지금은 돌릴 수 없다.

## 남는 것 (이번에 안 함)

- `.claude`·`.agents` 는 점으로 시작하는 폴더라 Finder 에서 안 보인다. 사용자가 산출물을 손으로 옮기면 빠뜨릴 수 있다 — 전달 방식(압축 등)은 E 의 몫.

## 7. 계획과 달라진 점

- 없음 (건드린 파일은 "4. 건드릴 파일" 그대로). `builder/templates/.gitkeep`, `builder/tests/templates/.gitkeep` 는 폴더에 실제 파일이 생겨 지웠다.
- 기준선 eval 을 작업 폴더에서 돌리다가 코드 수정과 겹쳤다 — 01 만 쓰고, 02·03 은 `origin/develop`(`2b13db7`)을 따로 체크아웃한 폴더에서 다시 돌렸다.

## 8. 검증 결과

```
$ cd builder && uv run pytest -q
64 passed, 13 warnings in 0.25s      # 경고는 기존과 같은 langsmith DeprecationWarning (Python 3.14)
$ uv run ruff check . && uv run ruff format --check .
All checks passed!
53 files already formatted
```

### 품질 회귀 — 같은 모델 `claude-sonnet-5-5`, `claude -p` 헤드리스, 2026-11-13

전 = `develop` `2b13db7`, 후 = 이 브랜치. 답은 모든 질문에 빈 줄(= 추천 선택지). 줄 수는 spec + AGENTS + 스킬 (두 경로 중복은 한 번만 셈).

| 케이스 | | 질문 수 | 묶음 수 | LLM 호출 | 스킬 | 작업자가 발견하는 스킬 | spec.md 두 절 | 줄 수 | 플레이스홀더·위험 명령 grep |
|---|---|---|---|---|---|---|---|---|---|
| 01-short | 전 | 8 | 2 | 4 | 루트 `SKILL.md` 1 | 0 | 있음 | 199 | 없음 |
| | 후 | 4 | 1 | 4 | 새 1 (`build-expense-tracker`) + 공통 1 | 2 | 있음 | 231 | AGENTS.md 예시 문장에 `...` 1곳 |
| 02-domain | 전 | 11 | 3 | 5 | 루트 `SKILL.md` 1 | 0 | 있음 | 265 | 없음 |
| | 후 | 12 | 3 | 6 | 새 2 (`build-vat-summary`, `adapt-excel-input`) + 공통 1 | 3 | 있음 | 328 | 없음 |
| 03-vague | 전 | 9 | 2 | 4 | 루트 `SKILL.md` 1 | 0 | 있음 | 179 | 없음 |
| | 후 | 8 | 2 | 5 | 새 1 (`build-club-app`) + 공통 1 | 2 | 있음 | 238 | 없음 |

- LLM 호출은 `select_skills` 의 1회만 늘었다 (02·03). 01 은 질문 묶음이 1개로 끝나 총 호출 수가 같다 — 질문 수·묶음 수의 차이는 `interview_user` 의 실행마다의 변동이고 이번 변경과 무관하다 (`interview_user` 는 고치지 않았다).
- 세 건 모두 공통 스킬을 골랐고, 산출물의 `verify-before-report/SKILL.md` 는 템플릿 원문과 바이트 단위로 같다 (`cmp`).
- 새로 쓰는 스킬의 frontmatter 는 세 건 모두 `name` + 큰따옴표 `description` 으로 들어갔다. 02 의 두 번째 새 스킬은 "거래처 엑셀 양식이 달라졌을 때" 라는 되풀이되는 작업이다.
- 새 스킬 본문은 마지막 단계에서 `verify-before-report` 를 이름으로 가리킨다. AGENTS.md "작업 절차" 에 스킬 목록(이름·언제·`.agents/skills/...` 경로)이 들어갔다.
- 01 후의 `...` 는 AGENTS.md 질문 규칙의 예시 문장(`예: "1. (추천) ... 2. ..."`)이다. 프롬프트가 금지한 표기인데 모델이 예시에 썼다 — 채워야 할 빈칸은 아니다. AGENTS.md 본문은 이번 범위가 아니라 고치지 않았다.
- `basis` 를 스펙 항목 id enum 으로 묶은 스키마는 `claude -p --json-schema` 에서 3/3 통과했다.

### 실행 검증 (인수 조건) — 2026-11-13, `claude-sonnet-5-5`, Claude Code 2.1.323

후 산출물 3건을 각각 빈 임시 폴더(git init)에 풀고 `echo 시작해 | claude -p --setting-sources project --tools Read,Glob,Grep,Skill --max-turns 8`.
A 와 같은 방법 — 도구를 읽기 전용으로 제한해 첫 행동만 본다.

| 확인할 것 | 01 | 02 | 03 |
|---|---|---|---|
| 스킬이 발견되는가 (init 의 skills 목록에 산출물 스킬 전부) | 통과 (2/2) | 통과 (3/3) | 통과 (2/2) |
| 스킬이 로드되는가 | 통과 (Skill 도구로 `build-expense-tracker`) | 통과 (`.agents/skills/build-vat-summary/SKILL.md` 를 직접 읽음) | 통과 (Skill 도구로 `build-club-app`) |
| AGENTS.md 가 읽히는가 | 통과 | 통과 | 통과 |
| 첫 작업이 되묻지 않고 시작되는가 | 통과 | 통과 | 통과 |

- A 에서 3건 모두 실패했던 "스킬이 발견·로드되는가" 가 통과로 바뀌었다.
- 02 는 AGENTS.md 에 적힌 경로로 스킬을 직접 읽었다 — "발견 실패 대비" 로 넣은 경로 안내가 실제로 쓰였다.
- 세 건 모두 테스트가 막은 쓰기·실행 권한에서 멈췄고, "기술 선택은 spec.md 에 정해져 있어 물을 것이 없다" 고 보고했다.
- [미확인] 쓰기·실행 권한을 준 끝까지의 실행 (프로그램 완성 여부) — 비용·시간이 커서 돌리지 않았다.

### 공통 스킬 실행 검증 — `verify-before-report`

| 작업자 | 결과 |
|---|---|
| Claude Code 2.1.323, `claude-sonnet-5-5`, 2026-11-13 | **통과** |
| Codex | **[미확인]** — 이 PC 에 `codex` 가 없다 (`which codex` → not found). 사용자가 설치하면 돌린다 |

- 방법: 임시 폴더에 이 스킬(두 경로), 완료 기준 3개짜리 `spec.md`("글자 수 세기"), 짧은 AGENTS.md 를 두고 "spec.md 대로 만들어 주세요".
  도구는 Read·Write·Edit·Glob·Grep·Skill·`python3` 실행만 허용.
- Claude Code: init 의 skills 목록에 있음 → `count.py` 를 쓴 뒤 보고 전에 Skill 도구로 `verify-before-report` 를 스스로 불렀다 →
  완료 기준 3개를 `python3 count.py ...` 로 하나씩 실행 → 보고가 스킬의 형식(된 것 / 직접 확인하지 못한 것 / 써 보는 방법)을 따랐다.

## 9. 안 한 것 / 남은 것

- **Codex 실행 검증 — 미룸 (2026-11-14 결정).** `verify-before-report` 는 **Claude Code 에서 검증됨, Codex 미검증** 상태로 공통 스킬 목록에 올라 있다.
  "양쪽에서 검증한 것만 올린다" 규칙의 예외이고 `design.md` "select_skills" 에 적었다. Codex 가 설치되면 "공통 스킬 실행 검증" 과 같은 방법으로 돌리고,
  실패하면 목록에서 내린다. 산출물의 `.agents/skills/` 경로를 Codex 가 발견하는지도 공식 문서로만 확인했고 실행으로는 [미확인] 이다.
- `.claude`·`.agents` 는 점으로 시작하는 폴더라 Finder 에서 안 보인다. 사용자가 산출물을 손으로 옮기면 빠뜨릴 수 있다 — 전달 방식은 E 의 몫.
- `run.json` 의 `skills` 는 CLI 에만 있다. FastAPI(E) 가 스킬 목록을 내보낼지는 E 의 몫.
- 공통 스킬과 새로 쓰는 스킬의 비중은 고정하지 않았다 (미결정 전제). 공통 스킬이 1개뿐이라 지금은 비교할 것이 없다.

토큰 소모 [추정]: 세션 약 25만 토큰 + 실제 `claude -p` 약 38회 (eval 전 3건 + 중단된 1건, 후 3건, 경로 확인 1, 공통 스킬 검증 1, 실행 검증 3).
