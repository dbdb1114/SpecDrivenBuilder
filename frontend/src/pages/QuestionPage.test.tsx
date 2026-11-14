import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { QuestionBundle } from "../api/types";
import { DELEGATE_LABEL, QuestionPage } from "./QuestionPage";

const BUNDLE: QuestionBundle = {
  round: 1,
  can_finish: true,
  preview: null,
  questions: [
    {
      id: "q1",
      item_id: "who-uses",
      text: "이 프로그램은 누가 쓰나요?",
      multiple: false,
      options: [
        { id: "o1", label: "저 혼자 써요", recommended: true, visual: null },
        { id: "o2", label: "우리 팀 여러 명이 써요", recommended: false, visual: null },
      ],
    },
    {
      id: "q2",
      item_id: "input-data",
      text: "무엇을 적나요?",
      multiple: true,
      options: [
        { id: "o1", label: "카드", recommended: false, visual: null },
        { id: "o2", label: "현금", recommended: false, visual: null },
        { id: "o3", label: "계좌", recommended: false, visual: null },
      ],
    },
    {
      id: "q3",
      item_id: "when",
      text: "언제 쓰나요?",
      multiple: false,
      options: [
        { id: "o1", label: "매일", recommended: false, visual: null },
        { id: "o2", label: "가끔", recommended: false, visual: null },
      ],
    },
  ],
};

function setup(bundle: QuestionBundle = BUNDLE) {
  const onSubmit = vi.fn();
  render(<QuestionPage bundle={bundle} busy={false} onSubmit={onSubmit} />);
  const card = (name: RegExp) => within(screen.getByRole("group", { name }));
  return { onSubmit, card, user: userEvent.setup() };
}

describe("QuestionPage", () => {
  it("선택지를 번호 버튼으로 그리고, 추천과 고정 선택지를 붙인다", () => {
    const { card } = setup();
    const first = card(/누가 쓰나요/);
    const buttons = first.getAllByRole("button");
    expect(buttons.map((b) => b.textContent)).toEqual(["1저 혼자 써요추천", "2우리 팀 여러 명이 써요", `3${DELEGATE_LABEL}`]);
    expect(first.getByRole("textbox", { name: "1번 직접 입력" })).toBeInTheDocument();
  });

  it("선택 · 여러 개 · 직접 입력 · 맡김을 답 제출 규격으로 보낸다", async () => {
    const { onSubmit, card, user } = setup();
    await user.click(card(/누가 쓰나요/).getByRole("button", { name: /우리 팀/ }));
    await user.click(card(/무엇을 적나요/).getByRole("button", { name: /카드/ }));
    await user.click(card(/무엇을 적나요/).getByRole("button", { name: /계좌/ }));
    await user.click(card(/무엇을 적나요/).getByRole("button", { name: /카드/ }));
    await user.click(card(/무엇을 적나요/).getByRole("button", { name: /현금/ }));
    await user.type(card(/언제 쓰나요/).getByRole("textbox"), " 월요일마다 ");
    await user.click(screen.getByRole("button", { name: "다음" }));

    expect(onSubmit).toHaveBeenCalledWith({
      action: "submit",
      answers: [
        { question_id: "q1", kind: "option", option_ids: ["o2"] },
        { question_id: "q2", kind: "option", option_ids: ["o3", "o2"] },
        { question_id: "q3", kind: "custom", text: "월요일마다" },
      ],
    });
  });

  it("하나만 고르는 질문은 새로 고르면 바뀌고, 맡김을 누르면 맡김이 된다", async () => {
    const { onSubmit, card, user } = setup();
    const first = card(/누가 쓰나요/);
    await user.click(first.getByRole("button", { name: /저 혼자/ }));
    await user.click(first.getByRole("button", { name: /우리 팀/ }));
    expect(first.getByRole("button", { name: /저 혼자/ })).toHaveAttribute("aria-pressed", "false");
    await user.click(card(/언제 쓰나요/).getByRole("button", { name: new RegExp(DELEGATE_LABEL) }));
    await user.click(screen.getByRole("button", { name: "다음" }));

    expect(onSubmit).toHaveBeenCalledWith({
      action: "submit",
      answers: [
        { question_id: "q1", kind: "option", option_ids: ["o2"] },
        { question_id: "q3", kind: "delegate" },
      ],
    });
  });

  it("'그만 묻고 만들어 주세요'는 고른 답과 함께 finish 를 보낸다", async () => {
    const { onSubmit, card, user } = setup();
    await user.click(card(/누가 쓰나요/).getByRole("button", { name: /저 혼자/ }));
    await user.click(screen.getByRole("button", { name: "그만 묻고 만들어 주세요" }));

    expect(onSubmit).toHaveBeenCalledWith({
      action: "finish",
      answers: [{ question_id: "q1", kind: "option", option_ids: ["o1"] }],
    });
  });

  it("can_finish 가 false 면 그만 묻기 버튼이 없다", () => {
    setup({ ...BUNDLE, can_finish: false });
    expect(screen.queryByRole("button", { name: "그만 묻고 만들어 주세요" })).not.toBeInTheDocument();
  });

  it("visual · preview 가 와도 글자 선택지로 그린다", () => {
    const bundle: QuestionBundle = {
      ...BUNDLE,
      preview: {
        layout: "sidebar-left",
        colors: ["#1E3A5F"],
        texts: { title: "가계부", menu: ["이번 달"] },
      },
      questions: [
        {
          ...BUNDLE.questions[0],
          options: [
            { id: "o1", label: "차분한 남색", recommended: true, visual: { type: "palette", colors: ["#1E3A5F", "#F5F7FA"] } },
            { id: "o2", label: "왼쪽 메뉴", recommended: false, visual: { type: "layout", key: "sidebar-left" } },
          ],
        },
      ],
    };
    setup(bundle);
    expect(screen.getByRole("button", { name: /차분한 남색/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /왼쪽 메뉴/ })).toBeInTheDocument();
  });
});
