import styles from "./Header.module.css";

const STAGES = ["01 아이디어", "02 인터뷰", "03 확인·생성", "04 다운로드"];

type Props = { stage: number; onHome: () => void };

export function Header({ stage, onHome }: Props) {
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
      <nav aria-label="진행 단계">
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
    </header>
  );
}
