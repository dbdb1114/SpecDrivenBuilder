import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, submitAnswers } from "./client";

function mockFetch(status: number, body: unknown) {
  const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status }));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => vi.unstubAllGlobals());

describe("api client", () => {
  it("답 제출을 JSON 으로 보낸다", async () => {
    const fetchMock = mockFetch(200, { run_id: "r1", status: "done" });
    await submitAnswers("r 1", { action: "finish", answers: [] });

    const [path, init] = fetchMock.mock.calls[0];
    expect(path).toBe("/api/runs/r%201/answers");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({ action: "finish", answers: [] });
  });

  it("서버의 detail 을 메시지로 올린다", async () => {
    mockFetch(422, { detail: "q1 는 하나만 고를 수 있음" });
    await expect(submitAnswers("r1", { action: "submit", answers: [] })).rejects.toEqual(
      new ApiError(422, "q1 는 하나만 고를 수 있음"),
    );
  });

  it("검증 오류 목록은 msg 를 줄로 잇는다", async () => {
    mockFetch(422, { detail: [{ msg: "가" }, { msg: "나" }] });
    await expect(submitAnswers("r1", { action: "submit", answers: [] })).rejects.toThrow("가\n나");
  });
});
