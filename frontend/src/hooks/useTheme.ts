import { useEffect, useState } from "react";

export type Theme = "dark" | "light";

const KEY = "theme";

function current(): Theme {
  return document.documentElement.dataset.theme === "light" ? "light" : "dark";
}

/** 테마는 <html data-theme> 하나가 원본이다 (index.html 의 스크립트가 처음 값을 붙인다). 고르면 저장하고, 고른 적이 없으면 시스템 설정을 따라간다. */
export function useTheme() {
  const [theme, setTheme] = useState<Theme>(current);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  useEffect(() => {
    const media = window.matchMedia?.("(prefers-color-scheme: light)");
    if (!media) return;
    const follow = (e: MediaQueryListEvent) => {
      let saved: string | null = null;
      try {
        saved = localStorage.getItem(KEY);
      } catch {
        // 저장소를 못 쓰면 고른 값이 없는 것으로 본다.
      }
      if (!saved) setTheme(e.matches ? "light" : "dark");
    };
    media.addEventListener("change", follow);
    return () => media.removeEventListener("change", follow);
  }, []);

  const toggle = () => {
    const next: Theme = theme === "dark" ? "light" : "dark";
    try {
      localStorage.setItem(KEY, next);
    } catch {
      // 저장하지 못해도 이번 화면에서는 바뀐다.
    }
    setTheme(next);
  };

  return { theme, toggle };
}
