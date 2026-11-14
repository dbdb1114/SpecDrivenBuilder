import { useCallback, useEffect, useState } from "react";
import { ApiError, getRun, replyConfirm, retryRun, startRun, submitAnswers } from "../api/client";
import type { AnswerSubmission, ConfirmReply, RunView } from "../api/types";

const RUN_PARAM = "run";

// 지금 기다리는 요청의 종류. 화면이 "다음 질문을 준비하는 중"과 "산출물을 만드는 중"을 구분하는 데 쓴다.
export type Pending = "load" | "start" | "answers" | "confirm" | "revise" | "retry";

function readRunId(): string | null {
  return new URLSearchParams(window.location.search).get(RUN_PARAM);
}

// 새로고침해도 같은 실행으로 돌아오도록 run_id 를 URL 에 둔다 (체크포인트는 서버에 있다).
function writeRunId(runId: string | null) {
  const url = new URL(window.location.href);
  if (runId) url.searchParams.set(RUN_PARAM, runId);
  else url.searchParams.delete(RUN_PARAM);
  window.history.replaceState(null, "", url);
}

export function useRun() {
  const [view, setView] = useState<RunView | null>(null);
  // URL 에 run_id 가 있으면 첫 화면부터 불러오는 중이다 — effect 안에서 켜지 않으려고 초기값으로 둔다.
  const [pending, setPending] = useState<Pending | null>(() => (readRunId() !== null ? "load" : null));
  const [error, setError] = useState<string | null>(null);
  // 시작 요청을 기다리는 동안 화면에 보여 줄 요청 원문. 응답이 오면 view.request 가 대신한다.
  const [draftRequest, setDraftRequest] = useState("");
  // 같은 실행에서 round 번호가 다시 1부터 시작할 수 있어(돌아오는 경로) 화면을 새로 그리는 기준을 따로 센다.
  const [screen, setScreen] = useState(0);

  // setState 는 then 콜백 안에서만 부른다 — 첫 화면을 불러오는 effect 에서도 같은 함수를 쓰기 때문.
  const settle = useCallback((call: Promise<RunView>) => {
    return call
      .then(
        (next) => {
          setView(next);
          setScreen((n) => n + 1);
          writeRunId(next.run_id);
        },
        (e: unknown) => {
          if (e instanceof ApiError && e.status === 404) {
            setView(null);
            writeRunId(null);
          }
          setError(e instanceof Error ? e.message : String(e));
        },
      )
      .finally(() => setPending(null));
  }, []);

  const run = (kind: Pending, call: () => Promise<RunView>) => {
    setPending(kind);
    setError(null);
    return settle(call());
  };

  useEffect(() => {
    const runId = readRunId();
    if (runId) void settle(getRun(runId));
  }, [settle]);

  const runId = view?.run_id ?? "";

  return {
    view,
    pending,
    error: error ?? view?.error ?? null,
    screen,
    draftRequest,
    start: (request: string) => {
      setDraftRequest(request);
      return run("start", () => startRun(request));
    },
    submit: (submission: AnswerSubmission) => run("answers", () => submitAnswers(runId, submission)),
    confirm: (reply: ConfirmReply) =>
      run(reply.action === "confirm" ? "confirm" : "revise", () => replyConfirm(runId, reply)),
    retry: () => run("retry", () => retryRun(runId)),
    restart: () => {
      setView(null);
      setError(null);
      setDraftRequest("");
      writeRunId(null);
    },
  };
}
