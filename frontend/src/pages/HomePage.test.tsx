import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { HomePage } from "./HomePage";

function setup(props: { initialText?: string; error?: string } = {}) {
  const onStart = vi.fn();
  render(<HomePage initialText={props.initialText ?? ""} error={props.error ?? null} onStart={onStart} />);
  return { user: userEvent.setup(), onStart, input: screen.getByLabelText("만들고 싶은 프로그램") };
}

describe("HomePage", () => {
  it("입력이 비어 있으면 시작할 수 없다", () => {
    setup();

    expect(screen.getByRole("button", { name: "설계 시작" })).toBeDisabled();
  });

  it("Enter 로 앞뒤 공백을 뺀 요청을 보낸다", async () => {
    const { user, onStart, input } = setup();

    await user.type(input, "  가계부 만들어 주세요  {Enter}");

    expect(onStart).toHaveBeenCalledExactlyOnceWith("가계부 만들어 주세요");
  });

  it("한글 조합 중의 Enter 는 제출로 받지 않는다", () => {
    const { onStart, input } = setup({ initialText: "가계" });

    const allowed = fireEvent.keyDown(input, { key: "Enter", isComposing: true });

    expect(allowed).toBe(false);
    expect(onStart).not.toHaveBeenCalled();
  });

  it("예시 칩은 입력창을 채우기만 하고 바로 보내지 않는다", async () => {
    const { user, onStart, input } = setup();

    await user.click(screen.getByRole("button", { name: "팀 점심 투표 봇" }));

    expect(input).toHaveValue("팀 점심 투표 봇");
    expect(onStart).not.toHaveBeenCalled();
  });

  it("시작이 실패하면 입력을 남긴 채 오류를 보여 준다", () => {
    const { input } = setup({ initialText: "가계부", error: "서버에 연결하지 못했어요." });

    expect(input).toHaveValue("가계부");
    expect(screen.getByRole("alert")).toHaveTextContent("서버에 연결하지 못했어요.");
  });
});
