import { useEffect, useRef, useState } from "react";
import { artifactsZipUrl } from "../api/client";
import styles from "./DonePage.module.css";

// 압축을 풀 폴더 이름. 백엔드가 프로젝트 이름을 주지 않으므로 안내 문구에서만 쓰는 고정 이름이다.
const FOLDER = "my-project";

function describe(name: string): string {
  if (name === "spec.md") return "기획 스펙";
  if (name === "AGENTS.md") return "작업자 규칙";
  if (name === "CLAUDE.md") return "Claude Code 연결";
  if (name.endsWith("SKILL.md")) return "스킬";
  return "";
}

type Props = { runId: string; artifacts: Record<string, string>; onRestart: () => void };

export function DonePage({ runId, artifacts, onRestart }: Props) {
  const names = Object.keys(artifacts);
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState(names[0] ?? "");
  const [copied, setCopied] = useState<number | null>(null);
  const timer = useRef<number | undefined>(undefined);
  useEffect(() => () => window.clearTimeout(timer.current), []);

  const zipName = `${runId}.zip`;
  const steps = [
    { title: "압축을 풀고 폴더로 이동", code: `unzip ${zipName} -d ${FOLDER} && cd ${FOLDER}` },
    { title: "Claude Code 실행 (Codex 를 쓰면 codex)", code: "claude" },
    { title: "이렇게 한 마디만", code: '"spec.md 대로 만들어줘"' },
  ];

  const copy = async (index: number, text: string) => {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      return; // 복사 권한이 없으면 아무 표시도 하지 않는다 — 코드는 화면에 그대로 보인다.
    }
    setCopied(index);
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setCopied(null), 1500);
  };

  const specLines = (artifacts["spec.md"] ?? "").split("\n").slice(0, 40);

  return (
    <main className={styles.main}>
      <div className={styles.lead}>
        <p className={`${styles.kicker} rise`}>● BUILD COMPLETE · {names.length} FILES</p>
        <h1 className={styles.hero}>
          <span className="rise d1">설계도 완성.</span>
          <span className={`${styles.dim} rise d2`}>이제 넘기기만</span>
          <span className={`${styles.dim} rise d3`}>하면 돼요.</span>
        </h1>

        <div className={`${styles.buttons} rise d4`}>
          <a className={`${styles.go} btn`} href={artifactsZipUrl(runId)} download>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M12 4v11M7 10l5 5 5-5M5 20h14" />
            </svg>
            zip 다운로드
          </a>
          <button
            type="button"
            className={`${styles.ghost} btn`}
            aria-expanded={open}
            aria-controls="file-viewer"
            onClick={() => setOpen((value) => !value)}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z" />
              <circle cx="12" cy="12" r="3" />
            </svg>
            {open ? "파일 내용 닫기" : "파일 내용 보기"}
          </button>
          <button type="button" className={`${styles.ghost} btn`} onClick={onRestart}>
            새 프로젝트
          </button>
        </div>

        <ol className={`${styles.steps} rise d5`}>
          {steps.map((step, i) => (
            <li key={step.title} className={styles.step}>
              <span className={styles.stepNo}>{i + 1}</span>
              <div className={styles.stepBody}>
                <span className={styles.stepTitle}>{step.title}</span>
                <code className={styles.code}>{step.code}</code>
              </div>
              <button
                type="button"
                className={`${styles.copy} btn`}
                aria-label={`${i + 1}단계 명령 복사`}
                onClick={() => void copy(i, step.code)}
              >
                {copied === i ? "복사됨" : "복사"}
              </button>
            </li>
          ))}
        </ol>
      </div>

      <div className={`${styles.card} rise d3`}>
        <div className={styles.cardHead}>
          <span className={styles.zip}>{zipName}</span>
          <span className={styles.note}>산출물</span>
        </div>
        <ul className={styles.files}>
          {names.map((name, i) => (
            <li key={name} className="flash" style={{ animationDelay: `${0.3 + i * 0.12}s` }}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--ac)" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
                <path d="M14 3v5h5" />
              </svg>
              <span className={styles.fileName}>{name}</span>
              <span className={styles.note}>{describe(name)}</span>
            </li>
          ))}
        </ul>
        {specLines.length > 1 && (
          <div className={styles.preview} aria-label="spec.md 앞부분">
            {specLines.map((line, i) => (
              <div key={i} className={line.startsWith("#") ? styles.heading : undefined}>
                {line || "\u00a0"}
              </div>
            ))}
          </div>
        )}
      </div>

      {open && (
        <section id="file-viewer" className={`${styles.viewer} rise`} aria-label="파일 내용">
          <div className={styles.tabs} role="tablist" aria-label="산출물 파일">
            {names.map((name) => (
              <button
                key={name}
                type="button"
                role="tab"
                aria-selected={name === tab}
                className={`${styles.tab} btn`}
                onClick={() => setTab(name)}
              >
                {name}
              </button>
            ))}
          </div>
          <pre className={styles.content} role="tabpanel" aria-label={tab} tabIndex={0}>
            {artifacts[tab]}
          </pre>
        </section>
      )}
    </main>
  );
}
