import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { LayoutKey } from "../api/types";
import { Preview } from "./Preview";

const KEYS: LayoutKey[] = ["single-column", "top-nav", "sidebar-left", "list-detail", "dashboard", "mobile-tabs"];

describe("Preview", () => {
  it.each(KEYS)("%s 틀에 제목과 메뉴 문구, 색을 입힌다", (layout) => {
    render(
      <Preview preview={{ layout, colors: ["#1E3A5F", "#F5F7FA", "#4A90D9"], texts: { title: "동아리", menu: ["모임", "회비"] } }} />,
    );
    const figure = screen.getByRole("figure", { name: "미리보기" });
    expect(within(figure).getByText("동아리")).toBeInTheDocument();
    expect(within(figure).getAllByText("모임").length).toBeGreaterThan(0);
    expect(within(figure).getByText("회비")).toBeInTheDocument();
    const box = figure.querySelector(`[data-layout="${layout}"]`) as HTMLElement;
    expect(box.style.getPropertyValue("--p-primary")).toBe("#1E3A5F");
    expect(box.style.getPropertyValue("--p-accent")).toBe("#4A90D9");
  });

  it("문구를 마크업으로 해석하지 않는다", () => {
    render(<Preview preview={{ layout: "top-nav", colors: ["#000000"], texts: { title: "<b>x</b>", menu: [] } }} />);
    expect(screen.getByText("<b>x</b>")).toBeInTheDocument();
    expect(document.querySelector("b")).toBeNull();
  });

  it("색이 하나뿐이면 바탕은 흰색, 강조는 주색으로 채운다", () => {
    render(<Preview preview={{ layout: "dashboard", colors: ["#123456"], texts: { title: "집계", menu: ["현황"] } }} />);
    const box = document.querySelector('[data-layout="dashboard"]') as HTMLElement;
    expect(box.style.getPropertyValue("--p-bg")).toBe("#ffffff");
    expect(box.style.getPropertyValue("--p-accent")).toBe("#123456");
  });
});
