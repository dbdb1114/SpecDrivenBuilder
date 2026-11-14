import type { AnswerSubmission, ConfirmReply, RunView } from "./types";

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function detailMessage(body: unknown, status: number): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((d: { msg?: string }) => d.msg ?? JSON.stringify(d)).join("\n");
  }
  return `요청이 실패했어요 (HTTP ${status})`;
}

async function request(path: string, init?: { method: "POST"; body?: unknown }): Promise<RunView> {
  const response = await fetch(path, {
    method: init?.method ?? "GET",
    headers: init?.body === undefined ? undefined : { "Content-Type": "application/json" },
    body: init?.body === undefined ? undefined : JSON.stringify(init.body),
  });
  const body = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(response.status, detailMessage(body, response.status));
  return body as RunView;
}

const runPath = (runId: string) => `/api/runs/${encodeURIComponent(runId)}`;

export const startRun = (text: string) => request("/api/runs", { method: "POST", body: { request: text } });

export const getRun = (runId: string) => request(runPath(runId));

export const submitAnswers = (runId: string, submission: AnswerSubmission) =>
  request(`${runPath(runId)}/answers`, { method: "POST", body: submission });

export const replyConfirm = (runId: string, reply: ConfirmReply) =>
  request(`${runPath(runId)}/confirm`, { method: "POST", body: reply });

export const retryRun = (runId: string) => request(`${runPath(runId)}/retry`, { method: "POST" });

export const artifactsZipUrl = (runId: string) => `${runPath(runId)}/artifacts.zip`;
