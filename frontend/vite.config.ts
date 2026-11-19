import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  // 백오피스(/backoffice/)는 진입점을 따로 둔다 — 사용자 화면 번들에 백오피스 코드가 섞이지 않는다.
  build: {
    rollupOptions: {
      input: {
        main: "index.html",
        backoffice: "backoffice/index.html",
      },
    },
  },
  server: {
    proxy: { "/api": "http://localhost:8000" },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test-setup.ts"],
    css: { modules: { classNameStrategy: "non-scoped" } },
  },
});
