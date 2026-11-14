import { artifactsZipUrl } from "../api/client";
import { Button, ButtonRow } from "../components/Button";
import styles from "./pages.module.css";

type Props = { runId: string; artifacts: Record<string, string>; onRestart: () => void };

export function DonePage({ runId, artifacts, onRestart }: Props) {
  return (
    <section>
      <h1 className={styles.title}>다 만들었어요</h1>
      <p className={styles.lead}>
        아래 파일을 받아 한 폴더에 풀고, 그 폴더에서 Claude Code 나 Codex 를 열어 &ldquo;만들어 줘&rdquo;라고 하면 돼요.
      </p>
      <p>
        <a className={styles.link} href={artifactsZipUrl(runId)} download>
          파일 모두 받기 (zip)
        </a>
      </p>
      <ul className={styles.files}>
        {Object.entries(artifacts).map(([name, content]) => (
          <li key={name} className={styles.card}>
            <details>
              <summary>{name}</summary>
              <pre>{content}</pre>
            </details>
          </li>
        ))}
      </ul>
      <ButtonRow>
        <Button onClick={onRestart}>새로 만들기</Button>
      </ButtonRow>
    </section>
  );
}
