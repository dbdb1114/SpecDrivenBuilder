// 백오피스 안의 화면은 주소의 해시 하나로 정한다 — 새로고침해도 같은 화면이고, 라우터 라이브러리는 두지 않는다.
//   #traces            실행 목록
//   #traces/<run>      실행 하나의 호출 표
//   #traces/<run>/<n>  호출 하나의 전문
//   #nodes             노드 설정
export type Route =
  | { tab: "traces"; runId?: string; n?: number }
  | { tab: "nodes" };

export function parseRoute(hash: string): Route {
  const [tab, runId, n] = hash.replace(/^#\/?/, "").split("/").map(decodeURIComponent);
  if (tab === "nodes") return { tab: "nodes" };
  const num = Number(n);
  return { tab: "traces", runId: runId || undefined, n: Number.isInteger(num) && num > 0 ? num : undefined };
}

export function routeHref(route: Route): string {
  if (route.tab === "nodes") return "#nodes";
  const parts = ["traces", route.runId, route.n].filter((p) => p !== undefined).map((p) => encodeURIComponent(String(p)));
  return `#${parts.join("/")}`;
}
