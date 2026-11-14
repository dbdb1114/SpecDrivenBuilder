import styles from "./App.module.css";
import { Button, ButtonRow } from "./components/Button";
import { Notice } from "./components/Notice";
import { useRun } from "./hooks/useRun";
import { ConfirmPage } from "./pages/ConfirmPage";
import { DonePage } from "./pages/DonePage";
import { QuestionPage } from "./pages/QuestionPage";
import { StartPage } from "./pages/StartPage";

export function App() {
  const { view, busy, error, screen, start, submit, confirm, retry, restart } = useRun();

  let page;
  if (!view) {
    page = <StartPage busy={busy} onStart={start} />;
  } else if (view.status === "question" && view.bundle) {
    page = <QuestionPage key={screen} bundle={view.bundle} busy={busy} onSubmit={submit} />;
  } else if (view.status === "confirm" && view.confirm) {
    page = <ConfirmPage key={screen} screen={view.confirm} busy={busy} onReply={confirm} />;
  } else if (view.status === "done") {
    page = <DonePage runId={view.run_id} artifacts={view.artifacts} onRestart={restart} />;
  } else {
    page = (
      <section>
        <p>중간에 멈췄어요. 지금까지 답한 내용은 그대로 있어요.</p>
        <ButtonRow>
          <Button primary disabled={busy} onClick={retry}>
            다시 시도
          </Button>
        </ButtonRow>
      </section>
    );
  }

  return (
    <main className={styles.main}>
      {busy && <Notice>정리하고 있어요. 1~2분 걸릴 수 있어요.</Notice>}
      {error && <Notice error>{error}</Notice>}
      {page}
    </main>
  );
}
