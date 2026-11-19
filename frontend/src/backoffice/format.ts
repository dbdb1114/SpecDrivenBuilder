import type { Usage } from "../api/types";

export const tokens = (n: number) => n.toLocaleString("ko-KR");

export const usageTotal = (u: Usage) => u.input + u.output + u.cache_write + u.cache_read;

// 가격표(builder llm/trace.py)에 없는 모델이면 서버가 null 을 준다 — 화면에서 다시 계산하지 않는다.
export const dollars = (d: number | null | undefined) => (d === null || d === undefined ? "—" : `$${d.toFixed(4)}`);

export const seconds = (s: number) => `${s.toFixed(1)}s`;

export const when = (at: string) => at.replace("T", " ");
