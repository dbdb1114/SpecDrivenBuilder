import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { ConfirmScreen } from "../api/types";
import { ConfirmPage } from "./ConfirmPage";

// question-format.md "확인 화면" 예시 그대로 — confirm_spec(D) 이 아직 빈 노드라 고정 데이터로 개발한다.
const SCREEN: ConfirmScreen = {
  items: [
    { id: "who-uses", area: "function", name: "누가 쓰는가", status: "confirmed", content: "저 혼자 써요", editable: true },
    {
      id: "share",
      area: "function",
      name: "다른 사람과 나누는 방법",
      status: "delegated",
      content: "나누는 기능은 넣지 않는다",
      editable: true,
    },
    {
      id: "framework",
      area: "tech",
      name: "만드는 방식",
      status: "confirmed",
      content: "내 컴퓨터에서만 도는 프로그램 — 혼자 쓰고 인터넷이 필요 없어서",
      editable: false,
    },
  ],
};

function setup() {
  const onReply = vi.fn();
  render(<ConfirmPage screen={SCREEN} busy={false} onReply={onReply} />);
  return { onReply, user: userEvent.setup() };
}

describe("ConfirmPage", () => {
  it("영역별로 요약하고, 고칠 수 있는 항목에만 체크를 붙인다", () => {
    setup();
    expect(screen.getByRole("heading", { name: "용도 · 기능" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /기술/ })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "디자인" })).not.toBeInTheDocument();
    expect(screen.getByText(/인터넷이 필요 없어서/)).toBeInTheDocument();
    expect(screen.getByText("맡긴 것")).toBeInTheDocument();
    expect(screen.getAllByRole("checkbox")).toHaveLength(2);
  });

  it("고른 항목만 revise 로 보낸다", async () => {
    const { onReply, user } = setup();
    const revise = screen.getByRole("button", { name: "고른 항목 다시 답할게요" });
    expect(revise).toBeDisabled();

    const [whoUses, share] = screen.getAllByRole("checkbox");
    await user.click(whoUses);
    await user.click(share);
    await user.click(share);
    await user.click(revise);

    expect(onReply).toHaveBeenCalledWith({ action: "revise", item_ids: ["who-uses"] });
  });

  it("이대로 만들기는 confirm 을 보낸다", async () => {
    const { onReply, user } = setup();
    await user.click(screen.getByRole("button", { name: "이대로 만들어 주세요" }));
    expect(onReply).toHaveBeenCalledWith({ action: "confirm" });
  });
});
