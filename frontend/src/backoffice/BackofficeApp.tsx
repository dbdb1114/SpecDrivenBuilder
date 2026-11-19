import { useTheme } from "../hooks/useTheme";
import type { ApiError } from "../api/client";
import { NodesPage } from "./NodesPage";
import { TracesPage } from "./TracesPage";
import { routeHref } from "./route";
import styles from "./backoffice.module.css";
import { useRoute } from "./useRoute";

const TABS = [
  { tab: "traces", label: "호출 기록" },
  { tab: "nodes", label: "노드 설정" },
] as const;

export function BackofficeApp() {
  const route = useRoute();
  const { theme, toggle } = useTheme();
  const next = theme === "dark" ? "밝은 화면" : "어두운 화면";

  return (
    <div className={styles.shell}>
      <header className={styles.header}>
        <p className={styles.title}>
          <span className={styles.badge}>로컬 전용</span>
          백오피스
        </p>
        <nav className={styles.nav} aria-label="백오피스 화면">
          <ul className={styles.tabs}>
            {TABS.map(({ tab, label }) => (
              <li key={tab}>
                <a
                  href={routeHref({ tab })}
                  className={route.tab === tab ? styles.tabOn : styles.tab}
                  aria-current={route.tab === tab ? "page" : undefined}
                >
                  {label}
                </a>
              </li>
            ))}
          </ul>
        </nav>
        <button type="button" className={`${styles.theme} btn`} onClick={toggle} aria-label={`${next}으로 바꾸기`} title={`${next}으로 바꾸기`}>
          {theme === "dark" ? "☀" : "☾"}
        </button>
      </header>
      <main className={styles.main}>
        {route.tab === "nodes" ? <NodesPage /> : <TracesPage runId={route.runId} n={route.n} />}
      </main>
    </div>
  );
}

/** 읽기 실패. 404 는 대개 서버가 백오피스를 켜지 않고 떴다는 뜻이라 켜는 법을 같이 보여 준다. */
export function Problem({ error, notFound }: { error: ApiError; notFound?: string }) {
  if (error.status === 404 && !notFound) {
    return (
      <div className={styles.problem} role="alert">
        <p>백오피스가 꺼져 있어요.</p>
        <p className={styles.muted}>
          builder 서버를 <code>SPECBUILDER_BACKOFFICE=1</code> 로 띄우세요 —{" "}
          <code>SPECBUILDER_BACKOFFICE=1 uv run uvicorn specbuilder.api.main:app --reload</code>
        </p>
      </div>
    );
  }
  return (
    <div className={styles.problem} role="alert">
      <p>{error.status === 404 && notFound ? notFound : error.message}</p>
    </div>
  );
}
