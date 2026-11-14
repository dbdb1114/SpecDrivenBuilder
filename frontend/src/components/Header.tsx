import { useTheme } from "../hooks/useTheme";
import styles from "./Header.module.css";

const STAGES = ["01 아이디어", "02 인터뷰", "03 확인·생성", "04 다운로드"];

type Props = { stage: number; onHome: () => void };

export function Header({ stage, onHome }: Props) {
  const { theme, toggle } = useTheme();
  const next = theme === "dark" ? "밝은 화면" : "어두운 화면";

  return (
    <header className={styles.header}>
      <button type="button" className={styles.brand} onClick={onHome} aria-label="SpecDrivenBuilder 처음으로">
        <span className={styles.logo}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M4 7h10M4 12h16M4 17h7" />
          </svg>
        </span>
        <span className={styles.name}>SpecDrivenBuilder</span>
      </button>
      <nav className={styles.nav} aria-label="진행 단계">
        <ol className={styles.stages}>
          {STAGES.map((label, i) => (
            <li
              key={label}
              className={i === stage ? styles.current : i < stage ? styles.past : styles.future}
              aria-current={i === stage ? "step" : undefined}
            >
              {label}
            </li>
          ))}
        </ol>
      </nav>
      <button type="button" className={`${styles.theme} btn`} onClick={toggle} aria-label={`${next}으로 바꾸기`} title={`${next}으로 바꾸기`}>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          {theme === "dark" ? (
            <>
              <circle cx="12" cy="12" r="4" />
              <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
            </>
          ) : (
            <path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5Z" />
          )}
        </svg>
      </button>
    </header>
  );
}
