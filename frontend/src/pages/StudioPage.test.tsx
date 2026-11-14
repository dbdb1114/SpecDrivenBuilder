import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { ConfirmScreen, QuestionBundle, RunView } from "../api/types";
import type { Pending } from "../hooks/useRun";
import { DELEGATE_LABEL, StudioPage } from "./StudioPage";

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

const CONFIRM: ConfirmScreen = {
  items: [
    { id: "who-uses", area: "function", name: "누가 쓰는가", status: "confirmed", content: "저 혼자 써요", editable: true },
    { id: "share", area: "function", name: "나누는 방법", status: "delegated", content: "", editable: true },
    { id: "framework", area: "tech", name: "만드는 방식", status: "confirmed", content: "내 컴퓨터에서만 돈다", editable: false },
  ],
};

function view(patch: Partial<RunView>): RunView {
  return {
    run_id: "r1",
    status: "question",
    request: "가계부 만들어 주세요",
    qa: [],
    bundle: null,
    confirm: null,
    artifacts: {},
    error: null,
    ...patch,
  };
}

function setup(current: RunView | null, extra: { pending?: Pending; error?: string } = {}) {
  const handlers = { onSubmit: vi.fn(), onConfirm: vi.fn(), onRetry: vi.fn() };
  render(
    <StudioPage
      view={current}
      screen={1}
      pending={extra.pending ?? null}
      error={extra.error ?? null}
      request={current?.request ?? "가계부 만들어 주세요"}
      {...handlers}
    />,
  );
  return { user: userEvent.setup(), ...handlers };
}

const log = () => screen.getByRole("log");

describe("StudioPage — 질문 묶음", () => {
  it("요청 원문과 지난 문답을 대화로 보여 주고 묶음의 첫 질문만 묻는다", () => {
    setup(
      view({
        bundle: BUNDLE,
        qa: [{ node: "interview_profile", round: 1, item_id: "profile-domain", question: "무슨 일을 하세요?", answer: "회계" }],
      }),
    );

    expect(within(log()).getByText("가계부 만들어 주세요")).toBeInTheDocument();
    expect(within(log()).getByText("무슨 일을 하세요?")).toBeInTheDocument();
    expect(within(log()).getByText("회계")).toBeInTheDocument();
    expect(within(log()).getByText("이 프로그램은 누가 쓰나요?")).toBeInTheDocument();
    expect(screen.queryByText("무엇을 적나요?")).not.toBeInTheDocument();
  });

  it("번호 버튼 · 추천 표시 · 고정 선택지 · 직접 입력을 함께 보여 준다", () => {
    setup(view({ bundle: BUNDLE }));

    const first = screen.getByRole("button", { name: /저 혼자 써요/ });
    expect(first).toHaveTextContent("1");
    expect(first).toHaveTextContent("추천");
    expect(screen.getByRole("button", { name: new RegExp(DELEGATE_LABEL) })).toHaveTextContent("3");
    expect(screen.getByLabelText("직접 입력")).toBeInTheDocument();
  });

  it("답하면 같은 묶음의 다음 질문으로 넘어가고, 마지막 답에서 한 번에 보낸다", async () => {
    const { user, onSubmit } = setup(view({ bundle: BUNDLE }));

    await user.click(screen.getByRole("button", { name: /저 혼자 써요/ }));
    expect(onSubmit).not.toHaveBeenCalled();
    expect(within(log()).getByText("저 혼자 써요")).toBeInTheDocument();

    // 여러 개 고르는 질문은 고른 뒤 "다음"으로 넘긴다.
    await user.click(screen.getByRole("button", { name: /카드/ }));
    await user.click(screen.getByRole("button", { name: /계좌/ }));
    expect(screen.getByRole("button", { name: /카드/ })).toHaveAttribute("aria-pressed", "true");
    await user.click(screen.getByRole("button", { name: "다음" }));
    expect(onSubmit).not.toHaveBeenCalled();

    await user.type(screen.getByLabelText("직접 입력"), "월말에만 써요{Enter}");

    expect(onSubmit).toHaveBeenCalledExactlyOnceWith({
      action: "submit",
      answers: [
        { question_id: "q1", kind: "option", option_ids: ["o1"] },
        { question_id: "q2", kind: "option", option_ids: ["o1", "o3"] },
        { question_id: "q3", kind: "custom", text: "월말에만 써요" },
      ],
    });
  });

  it("고정 선택지를 누르면 맡김으로 답한다", async () => {
    const { user, onSubmit } = setup(view({ bundle: { ...BUNDLE, questions: [BUNDLE.questions[0]] } }));

    await user.click(screen.getByRole("button", { name: new RegExp(DELEGATE_LABEL) }));

    expect(onSubmit).toHaveBeenCalledWith({ action: "submit", answers: [{ question_id: "q1", kind: "delegate" }] });
  });

  it("선택지 없는 질문은 입력 칸과 고정 선택지만 보여 주고 적은 답을 보낸다", async () => {
    const open = { id: "q1", item_id: "location", text: "어느 동네인가요?", multiple: false, options: [] };
    const { user, onSubmit } = setup(view({ bundle: { ...BUNDLE, questions: [open] } }));

    const delegate = screen.getByRole("button", { name: new RegExp(DELEGATE_LABEL) });
    expect(within(delegate.closest("ol")!).getAllByRole("button")).toHaveLength(1);

    await user.type(screen.getByPlaceholderText("답을 적어 주세요"), "서울 마포구");
    await user.click(screen.getByRole("button", { name: "보내기" }));

    expect(onSubmit).toHaveBeenCalledWith({
      action: "submit",
      answers: [{ question_id: "q1", kind: "custom", text: "서울 마포구" }],
    });
  });

  it("그만 묻기는 지금까지 답한 것만 담아 finish 로 보낸다", async () => {
    const { user, onSubmit } = setup(view({ bundle: BUNDLE }));

    await user.click(screen.getByRole("button", { name: /저 혼자 써요/ }));
    await user.click(screen.getByRole("button", { name: "그만 묻고 만들어 주세요" }));

    expect(onSubmit).toHaveBeenCalledWith({
      action: "finish",
      answers: [{ question_id: "q1", kind: "option", option_ids: ["o1"] }],
    });
  });

  it("can_finish 가 false 면 그만 묻기 버튼이 없다", () => {
    setup(view({ bundle: { ...BUNDLE, can_finish: false } }));

    expect(screen.queryByRole("button", { name: "그만 묻고 만들어 주세요" })).not.toBeInTheDocument();
  });

  it("선택지의 그림과 묶음의 미리보기를 그린다", () => {
    setup(
      view({
        bundle: {
          round: 2,
          can_finish: true,
          preview: {
            layout: "sidebar-left",
            colors: { background: "#F5F7FA", surface: "#FBFCFD", primary: "#1E3A5F", accent: "#4A90D9", text: "#122339" },
            texts: {
              title: "가계부",
              menu: ["이번 달"],
              heading: "이번 달 지출",
              action: "내역 추가",
              items: [
                { title: "점심", detail: "9,000원" },
                { title: "교통비", detail: "1,450원" },
              ],
            },
          },
          questions: [
            {
              id: "q1",
              item_id: "color-tone",
              text: "이 느낌이 맞나요?",
              multiple: false,
              options: [
                { id: "o1", label: "차분한 남색", recommended: true, visual: { type: "palette", colors: ["#1E3A5F", "#F5F7FA"] } },
                { id: "o2", label: "왼쪽 메뉴", recommended: false, visual: { type: "layout", key: "sidebar-left" } },
              ],
            },
          ],
        },
      }),
    );

    expect(screen.getByTestId("palette")).toBeInTheDocument();
    expect(screen.getByTestId("layout-sidebar-left")).toBeInTheDocument();
    expect(within(log()).getByText("이번 달")).toBeInTheDocument();
  });

  it("기다리는 동안에는 답할 곳을 숨겨 두 번 보내지 못하게 한다", () => {
    setup(view({ bundle: BUNDLE }), { pending: "answers" });

    expect(screen.queryByRole("button", { name: /저 혼자 써요/ })).not.toBeInTheDocument();
    expect(screen.getByRole("status", { name: "답을 기다리는 중" })).toBeInTheDocument();
  });

  it("시작 요청을 기다리는 동안 요청 원문을 먼저 보여 준다", () => {
    setup(null, { pending: "start" });

    expect(within(log()).getByText("가계부 만들어 주세요")).toBeInTheDocument();
    expect(screen.getByRole("status", { name: "답을 기다리는 중" })).toBeInTheDocument();
  });
});

describe("StudioPage — 확인 화면", () => {
  it("영역별로 항목을 보여 주고 고칠 수 있는 항목에만 고치기를 둔다", () => {
    setup(view({ status: "confirm", confirm: CONFIRM }));

    expect(screen.getByRole("region", { name: "용도 · 기능" })).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "기술 (빌더가 정한 것)" })).queryByRole("checkbox")).toBeNull();
    expect(screen.getAllByRole("checkbox")).toHaveLength(2);
    expect(screen.getByText("만드는 쪽에서 알아서 정해요")).toBeInTheDocument();
  });

  it("확인하면 confirm 을 보낸다", async () => {
    const { user, onConfirm } = setup(view({ status: "confirm", confirm: CONFIRM }));

    await user.click(screen.getByRole("button", { name: "이대로 만들어 주세요" }));

    expect(onConfirm).toHaveBeenCalledWith({ action: "confirm" });
  });

  it("고칠 항목을 골라야 다시 답하기를 보낼 수 있다", async () => {
    const { user, onConfirm } = setup(view({ status: "confirm", confirm: CONFIRM }));

    const revise = screen.getByRole("button", { name: /고른 항목 다시 답할게요/ });
    expect(revise).toBeDisabled();
    await user.click(screen.getAllByRole("checkbox")[1]);
    await user.click(revise);

    expect(onConfirm).toHaveBeenCalledWith({ action: "revise", item_ids: ["share"] });
  });

  it("확인을 보낸 뒤에는 만드는 중으로 바뀐다", () => {
    setup(view({ status: "confirm", confirm: CONFIRM }), { pending: "confirm" });

    expect(screen.getByText(/산출물을 만드는 중/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "이대로 만들어 주세요" })).not.toBeInTheDocument();
    expect(screen.getAllByText("작성 중").length).toBeGreaterThan(0);
  });
});

describe("StudioPage — 멈춤 · 오류", () => {
  it("멈춘 실행은 화면을 바꾸지 않고 다시 시도를 둔다", async () => {
    const { user, onRetry } = setup(view({ status: "stalled" }), { error: "LLM 호출 실패" });

    expect(screen.getByRole("alert")).toHaveTextContent("LLM 호출 실패");
    await user.click(screen.getByRole("button", { name: "다시 시도" }));

    expect(onRetry).toHaveBeenCalled();
  });
});
