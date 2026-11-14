import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { DonePage } from "./DonePage";

const ARTIFACTS = {
  "spec.md": "# 가계부\n\n## 사용자가 정한 것\n- 혼자 쓴다",
  "AGENTS.md": "# 규칙",
  ".claude/skills/build-ledger/SKILL.md": "---\nname: build-ledger\n---",
};

function setup() {
  const onRestart = vi.fn();
  const user = userEvent.setup();
  render(<DonePage runId="run 1" artifacts={ARTIFACTS} onRestart={onRestart} />);
  return { user, onRestart };
}

describe("DonePage", () => {
  it("zip 링크는 그 실행의 다운로드 주소를 가리킨다", () => {
    setup();

    const link = screen.getByRole("link", { name: "zip 다운로드" });
    expect(link).toHaveAttribute("href", "/api/runs/run%201/artifacts.zip");
    expect(link).toHaveAttribute("download");
  });

  it("받은 파일 수와 이름을 실제 산출물대로 보여 준다", () => {
    setup();

    expect(screen.getByText(/3 FILES/)).toBeInTheDocument();
    expect(screen.getByText(".claude/skills/build-ledger/SKILL.md")).toBeInTheDocument();
  });

  it("실행 안내의 명령을 복사한다", async () => {
    const { user } = setup();
    const writeText = vi.spyOn(navigator.clipboard, "writeText").mockResolvedValue();

    await user.click(screen.getByRole("button", { name: "2단계 명령 복사" }));

    expect(writeText).toHaveBeenCalledWith("claude");
    expect(await screen.findByRole("button", { name: "2단계 명령 복사" })).toHaveTextContent("복사됨");
  });

  it("파일 내용 보기를 열어 탭으로 파일을 바꾼다", async () => {
    const { user } = setup();

    await user.click(screen.getByRole("button", { name: "파일 내용 보기" }));
    expect(screen.getByRole("tabpanel")).toHaveTextContent("사용자가 정한 것");
    await user.click(screen.getByRole("tab", { name: "AGENTS.md" }));

    expect(screen.getByRole("tabpanel")).toHaveTextContent("# 규칙");
  });

  it("새 프로젝트를 누르면 처음으로 돌아간다", async () => {
    const { user, onRestart } = setup();

    await user.click(screen.getByRole("button", { name: "새 프로젝트" }));

    expect(onRestart).toHaveBeenCalled();
  });
});
