import { render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as api from "../api/backoffice";
import { ApiError } from "../api/client";
import type { CallDetail, RunTrace } from "../api/types";
import { TracesPage } from "./TracesPage";

vi.mock("../api/backoffice");

const usage = { input: 1000, output: 200, cache_write: 4988, cache_read: 0 };
const TRACE: RunTrace = {
  run_id: "run-1",
  rows: [
    { n: 1, at: "2026-11-17T19:13:24", node: "interview_user", model: "claude-sonnet-5-5", effort: null, usage, seconds: 6.1, dollars: 0.0168, error: null },
    { n: 2, at: "2026-11-17T19:13:30", node: "select_stack", model: "claude-haiku-5-5", effort: "low", usage: { input: 0, output: 0, cache_write: 0, cache_read: 0 }, seconds: 2, dollars: null, error: "시간 초과" },
  ],
  totals: { usage, seconds: 8.1, dollars: null },
};

afterEach(() => vi.resetAllMocks());

describe("TracesPage", () => {
  it("실행 목록은 실행마다 호출 수 · 토큰 합 · 비용을 보여 주고 그 실행으로 이어진다", async () => {
    vi.mocked(api.listTraces).mockResolvedValue([
      { run_id: "run-1", started_at: "2026-11-17T19:13:24", calls: 11, usage, seconds: 116.6, dollars: 0.2597431 },
    ]);
    render(<TracesPage />);

    const link = await screen.findByRole("link", { name: "run-1" });
    expect(link).toHaveAttribute("href", "#traces/run-1");
    const row = link.closest("tr")!;
    expect(within(row).getByText("11")).toBeInTheDocument();
    expect(within(row).getByText("6,188")).toBeInTheDocument();
    expect(within(row).getByText("$0.2597")).toBeInTheDocument();
  });

  it("서버가 404 면 백오피스를 켜는 법을 보여 준다", async () => {
    vi.mocked(api.listTraces).mockRejectedValue(new ApiError(404, "Not Found"));
    render(<TracesPage />);

    expect(await screen.findByRole("alert")).toHaveTextContent("SPECBUILDER_BACKOFFICE=1");
  });

  it("호출 표는 서버가 계산한 달러를 쓰고, 모르면 — 로 둔다", async () => {
    vi.mocked(api.getTrace).mockResolvedValue(TRACE);
    render(<TracesPage runId="run-1" />);

    const node = await screen.findByRole("link", { name: "select_stack" });
    expect(node).toHaveAttribute("href", "#traces/run-1/2");
    const row = node.closest("tr")!;
    expect(within(row).getByText("실패", { exact: false })).toBeInTheDocument();
    expect(within(row).getByText("claude-haiku-5-5 · low")).toBeInTheDocument();
    expect(within(row).getByText("—")).toBeInTheDocument();
    expect(screen.getByText("$0.0168")).toBeInTheDocument();
    expect(api.getTrace).toHaveBeenCalledWith("run-1");
  });

  it("없는 실행은 그 이름으로 알린다", async () => {
    vi.mocked(api.getTrace).mockRejectedValue(new ApiError(404, "없는 기록: nope"));
    render(<TracesPage runId="nope" />);

    expect(await screen.findByRole("alert")).toHaveTextContent("없는 기록: nope");
  });

  it("호출 하나는 프롬프트와 응답 전문을 보여 준다", async () => {
    const detail: CallDetail = { ...TRACE.rows[0], system: "시스템 프롬프트", prompt: "운동 기록 앱", response: '{"items":[]}' };
    vi.mocked(api.getCall).mockResolvedValue(detail);
    render(<TracesPage runId="run-1" n={1} />);

    expect(await screen.findByText("운동 기록 앱")).toBeInTheDocument();
    expect(screen.getByText('{"items":[]}')).toBeInTheDocument();
    expect(screen.getByText("시스템 프롬프트")).toBeInTheDocument();
    expect(api.getCall).toHaveBeenCalledWith("run-1", 1);
  });
});
