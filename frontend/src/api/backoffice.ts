// 백오피스 API (/api/backoffice/**). 서버가 SPECBUILDER_BACKOFFICE 로 켜졌을 때만 있고, 꺼져 있으면 모든 주소가 404 다.
import { ApiError } from "./client";
import type { CallDetail, NodeSetting, NodeSettingsView, RunSummary, RunTrace } from "./types";

const BASE = "/api/backoffice";

async function call<T>(path: string, init?: { method: "PUT"; body: unknown }): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    method: init?.method ?? "GET",
    headers: init ? { "Content-Type": "application/json" } : undefined,
    body: init ? JSON.stringify(init.body) : undefined,
  });
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = (body as { detail?: unknown } | null)?.detail;
    const message = typeof detail === "string" ? detail : detail ? JSON.stringify(detail) : `HTTP ${response.status}`;
    throw new ApiError(response.status, message);
  }
  return body as T;
}

const runPath = (runId: string) => `/traces/${encodeURIComponent(runId)}`;

export const listTraces = () => call<RunSummary[]>("/traces");

export const getTrace = (runId: string) => call<RunTrace>(runPath(runId));

export const getCall = (runId: string, n: number) => call<CallDetail>(`${runPath(runId)}/calls/${n}`);

export const getNodes = () => call<NodeSettingsView>("/nodes");

export const saveNodes = (settings: Record<string, NodeSetting>) =>
  call<NodeSettingsView>("/nodes", { method: "PUT", body: settings });
