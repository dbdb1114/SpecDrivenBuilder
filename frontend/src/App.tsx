import styles from "./App.module.css";
import { Header } from "./components/Header";
import { useRun } from "./hooks/useRun";
import { DonePage } from "./pages/DonePage";
import { HomePage } from "./pages/HomePage";
import { StudioPage } from "./pages/StudioPage";

export function App() {
  const { view, pending, error, screen, draftRequest, start, submit, confirm, retry, restart } = useRun();

  // 단계 표시는 서버 상태와 기다리는 요청에서 계산한다 — 따로 상태로 두지 않는다.
  let stage = 0;
  let page;
  if (view?.status === "done") {
    stage = 3;
    page = <DonePage runId={view.run_id} artifacts={view.artifacts} onRestart={restart} />;
  } else if (view || pending === "start" || pending === "load") {
    stage = view?.status === "confirm" || pending === "confirm" ? 2 : 1;
    page = (
      <StudioPage
        view={view}
        screen={screen}
        pending={pending}
        error={error}
        request={view?.request ?? draftRequest}
        onSubmit={submit}
        onConfirm={confirm}
        onRetry={retry}
      />
    );
  } else {
    page = <HomePage initialText={draftRequest} error={error} onStart={start} />;
  }

  return (
    <div className={styles.shell}>
      <Header stage={stage} onHome={restart} />
      {page}
    </div>
  );
}
