import { describe, expect, it } from "vitest";
import { parseRoute, routeHref } from "./route";

describe("route", () => {
  it.each([
    ["", { tab: "traces", runId: undefined, n: undefined }],
    ["#traces", { tab: "traces", runId: undefined, n: undefined }],
    ["#traces/261117-web-a", { tab: "traces", runId: "261117-web-a", n: undefined }],
    ["#traces/261117-web-a/3", { tab: "traces", runId: "261117-web-a", n: 3 }],
    ["#traces/r/0", { tab: "traces", runId: "r", n: undefined }],
    ["#nodes", { tab: "nodes" }],
  ])("%s", (hash, route) => {
    expect(parseRoute(hash)).toEqual(route);
  });

  it("주소를 만들고 다시 읽으면 같은 화면이다", () => {
    const route = { tab: "traces", runId: "a b", n: 2 } as const;
    expect(parseRoute(routeHref(route))).toEqual(route);
  });
});
