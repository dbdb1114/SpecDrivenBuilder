import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { LayoutKey, Preview as PreviewData } from "../api/types";
import { Preview } from "./Preview";

const KEYS: LayoutKey[] = ["single-column", "top-nav", "sidebar-left", "list-detail", "dashboard", "mobile-tabs"];

const COLORS = { background: "#F5F7FA", surface: "#FBFCFD", primary: "#1E3A5F", accent: "#4A90D9", text: "#122339" };
const TEXTS = {
  title: "동아리",
  menu: ["모임", "회비"],
  heading: "다가오는 모임",
  action: "모임 만들기",
  items: [
    { title: "정기 모임", detail: "11월 20일 · 7명" },
    { title: "송년회", detail: "12월 18일 · 12명" },
  ],
};

function preview(layout: LayoutKey, texts: Partial<PreviewData["texts"]> = {}): PreviewData {
  return { layout, colors: COLORS, texts: { ...TEXTS, ...texts } };
}

describe("Preview", () => {
  it.each(KEYS)("%s 틀에 문구 다섯 종류와 역할별 색을 입힌다", (layout) => {
    render(<Preview preview={preview(layout)} />);
    const figure = screen.getByRole("figure", { name: "미리보기" });
    for (const text of ["동아리", "모임", "회비", "다가오는 모임", "모임 만들기", "송년회", "12월 18일 · 12명"]) {
      expect(within(figure).getAllByText(text).length).toBeGreaterThan(0);
    }
    const box = figure.querySelector(`[data-layout="${layout}"]`) as HTMLElement;
    expect(box.style.getPropertyValue("--p-bg")).toBe(COLORS.background);
    expect(box.style.getPropertyValue("--p-surface")).toBe(COLORS.surface);
    expect(box.style.getPropertyValue("--p-primary")).toBe(COLORS.primary);
    expect(box.style.getPropertyValue("--p-accent")).toBe(COLORS.accent);
    expect(box.style.getPropertyValue("--p-text")).toBe(COLORS.text);
  });

  it("문구를 마크업으로 해석하지 않는다", () => {
    render(<Preview preview={preview("top-nav", { title: "<b>x</b>", heading: "<i>y</i>" })} />);
    expect(screen.getByText("<b>x</b>")).toBeInTheDocument();
    expect(screen.getByText("<i>y</i>")).toBeInTheDocument();
    expect(document.querySelector("b, i")).toBeNull();
  });

  it("대시보드 숫자 카드는 목록 앞 세 개만 쓴다", () => {
    const items = ["가", "나", "다", "라"].map((title, i) => ({ title, detail: `${i + 1}건` }));
    render(<Preview preview={preview("dashboard", { items })} />);
    expect(screen.getByText("3건")).toBeInTheDocument();
    expect(screen.queryByText("4건")).toBeNull();
  });
});
