import io
import json

import pytest

from specbuilder.graph import main as cli
from specbuilder.nodes.confirm_spec import build_screen
from tests.fakes.fake_llm import FakeLLM, interview_reply, item, question


@pytest.mark.parametrize(
    "line, expected",
    [
        ("2", ["b"]),
        ("1, 3", ["a", "c"]),
        ("3,1,3", ["c", "a"]),
        ("4", None),
        ("0", None),
        ("고쳐줘", None),
        (",", None),
    ],
)
def test_parse_revise(line, expected):
    assert cli.parse_revise(line, ["a", "b", "c"]) == expected


def test_ask_confirm_numbers_only_editable_items(monkeypatch, capsys):
    screen = build_screen(
        [
            item("framework", content="웹 페이지", decided_by="worker", area="tech"),
            item("purpose", content="혼자 쓰는 가계부"),
            item("color", "delegated", "", area="design"),
        ]
    )
    monkeypatch.setattr("sys.stdin", io.StringIO("3\n2\n"))

    reply = cli.ask_confirm(screen)

    out = capsys.readouterr().out
    assert reply == {"action": "revise", "item_ids": ["color"]}
    assert "1. purpose 항목: 혼자 쓰는 가계부" in out
    assert "2. color 항목: (알아서 정함)" in out
    assert "- framework 항목: 웹 페이지" in out
    assert "번호를 다시 확인해 주세요." in out


def test_ask_confirm_empty_line_confirms(monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("\n"))
    assert cli.ask_confirm(build_screen([item("purpose")])) == {"action": "confirm"}


def test_cli_revise_then_confirm_writes_artifacts(monkeypatch, tmp_path):
    llm = FakeLLM(
        {
            "interview_user": [
                interview_reply([], [question("purpose")]),
                interview_reply([], []),
                interview_reply([], [question("purpose")]),
                interview_reply([], []),
            ]
        }
    )
    monkeypatch.setattr(cli, "ClaudeCLIClient", lambda: llm)
    # 묶음 답 → 확인 화면에서 1번 고치기 → 다시 묻는 묶음 답 → 확인
    monkeypatch.setattr("sys.stdin", io.StringIO("저 혼자요\n1\n가족이 같이 써요\n\n"))
    request = tmp_path / "case.md"
    request.write_text("가계부 만들어줘", encoding="utf-8")

    cli.main(
        [str(request), "--out", str(tmp_path / "out"), "--db", str(tmp_path / "db")]
    )

    (run_dir,) = (tmp_path / "out").iterdir()
    assert (run_dir / "spec.md").exists()
    meta = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    assert [qa["answer"] for qa in meta["qa"]] == ["저 혼자요", "가족이 같이 써요"]
    assert meta["spec_items"][0]["content"] == "가족이 같이 써요"
    # interview_user 2 + select_stack + select_skills, 고친 뒤 한 번 더, 그리고 generate_artifacts
    assert meta["llm_calls"] == 10
