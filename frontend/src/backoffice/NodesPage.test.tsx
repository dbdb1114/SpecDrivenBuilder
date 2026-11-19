import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as api from "../api/backoffice";
import { ApiError } from "../api/client";
import type { NodeSettingsView } from "../api/types";
import { NodesPage } from "./NodesPage";

vi.mock("../api/backoffice");

const NODES = ["interview_user", "interview_design", "select_stack", "select_skills", "generate_artifacts"];

function view(overrides: Partial<NodeSettingsView> = {}): NodeSettingsView {
  return {
    nodes: NODES.map((node) => ({ node, model: null, effort: null })),
    efforts: ["low", "medium", "high", "xhigh", "max"],
    default_model: "claude-sonnet-5-5",
    known_models: ["claude-sonnet-5-5", "claude-opus-5-5"],
    error: null,
    ...overrides,
  };
}

afterEach(() => vi.resetAllMocks());

describe("NodesPage", () => {
  it("노드마다 모델과 effort 를 고쳐 저장한다 — 비운 칸은 null(기본값)로 보낸다", async () => {
    vi.mocked(api.getNodes).mockResolvedValue(view());
    const saved = view({
      nodes: NODES.map((node) => ({ node, model: node === "select_stack" ? "claude-haiku-5-5" : null, effort: node === "select_stack" ? "low" : null })),
    });
    vi.mocked(api.saveNodes).mockResolvedValue(saved);
    const user = userEvent.setup();
    render(<NodesPage />);

    const save = await screen.findByRole("button", { name: "저장" });
    expect(save).toBeDisabled();
    await user.type(screen.getByLabelText("select_stack 모델"), "claude-haiku-5-5");
    await user.selectOptions(screen.getByLabelText("select_stack effort"), "low");
    await user.click(save);

    const sent = vi.mocked(api.saveNodes).mock.calls[0][0];
    expect(sent.select_stack).toEqual({ model: "claude-haiku-5-5", effort: "low" });
    expect(sent.interview_user).toEqual({ model: null, effort: null });
    expect(Object.keys(sent)).toEqual(NODES);
    expect(await screen.findByRole("status")).toHaveTextContent("저장했어요");
    expect(screen.getByLabelText("select_stack 모델")).toHaveValue("claude-haiku-5-5");
    expect(screen.getByRole("button", { name: "저장" })).toBeDisabled();
  });

  it("서버가 거부하면 그 문구를 보여 주고 입력은 그대로 둔다", async () => {
    vi.mocked(api.getNodes).mockResolvedValue(view());
    vi.mocked(api.saveNodes).mockRejectedValue(new ApiError(422, "nodes.json 형식이 맞지 않음: effort"));
    const user = userEvent.setup();
    render(<NodesPage />);

    await user.type(await screen.findByLabelText("select_skills 모델"), "x");
    await user.click(screen.getByRole("button", { name: "저장" }));

    expect(await screen.findByRole("status")).toHaveTextContent("형식이 맞지 않음");
    expect(screen.getByLabelText("select_skills 모델")).toHaveValue("x");
  });

  it("파일이 틀려 있으면 경고를 보여 준다", async () => {
    vi.mocked(api.getNodes).mockResolvedValue(view({ error: "nodes.json 에 모르는 노드: ['x']" }));
    render(<NodesPage />);

    expect(await screen.findByRole("alert")).toHaveTextContent("모르는 노드");
  });

  it("되돌리기는 저장된 값으로 돌아간다", async () => {
    vi.mocked(api.getNodes).mockResolvedValue(view());
    const user = userEvent.setup();
    render(<NodesPage />);

    const input = await screen.findByLabelText("interview_user 모델");
    await user.type(input, "claude-opus-5-5");
    await user.click(screen.getByRole("button", { name: "되돌리기" }));

    expect(input).toHaveValue("");
    expect(api.saveNodes).not.toHaveBeenCalled();
  });
});
