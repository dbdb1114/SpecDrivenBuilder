import { getCall, getTrace, listTraces } from "../api/backoffice";
import type { CallRow, Usage } from "../api/types";
import { Problem } from "./BackofficeApp";
import { dollars, seconds, tokens, usageTotal, when } from "./format";
import { routeHref } from "./route";
import styles from "./backoffice.module.css";
import { useLoad } from "./useLoad";

type Props = { runId?: string; n?: number };

export function TracesPage({ runId, n }: Props) {
  if (runId && n) return <CallView runId={runId} n={n} />;
  if (runId) return <RunView runId={runId} />;
  return <RunList />;
}

function RunList() {
  const { data, error, loading } = useLoad("runs", listTraces);

  return (
    <section className={`${styles.panel} rise`} aria-labelledby="runs-title">
      <h1 id="runs-title" className={styles.h1}>
        실행 목록
      </h1>
      {error && <Problem error={error} />}
      {loading && <p className={styles.muted}>읽는 중…</p>}
      {data && data.length === 0 && (
        <p className={styles.muted}>
          기록이 없어요. builder 를 <code>SPECBUILDER_TRACE=1</code> 로 실행하면 <code>output/_traces/</code> 에 남아요.
        </p>
      )}
      {data && data.length > 0 && (
        <div className={styles.scroll}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th scope="col">실행</th>
                <th scope="col">시작</th>
                <th scope="col" className={styles.num}>호출</th>
                <th scope="col" className={styles.num}>토큰</th>
                <th scope="col" className={styles.num}>초</th>
                <th scope="col" className={styles.num}>달러</th>
              </tr>
            </thead>
            <tbody>
              {data.map((run) => (
                <tr key={run.run_id}>
                  <th scope="row">
                    <a className={styles.link} href={routeHref({ tab: "traces", runId: run.run_id })}>
                      {run.run_id}
                    </a>
                  </th>
                  <td className={styles.mono}>{when(run.started_at)}</td>
                  <td className={styles.num}>{run.calls}</td>
                  <td className={styles.num}>{tokens(usageTotal(run.usage))}</td>
                  <td className={styles.num}>{seconds(run.seconds)}</td>
                  <td className={styles.num}>{dollars(run.dollars)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function UsageCells({ usage }: { usage: Usage }) {
  return (
    <>
      <td className={styles.num}>{tokens(usage.input)}</td>
      <td className={styles.num}>{tokens(usage.cache_write)}</td>
      <td className={styles.num}>{tokens(usage.cache_read)}</td>
      <td className={styles.num}>{tokens(usage.output)}</td>
    </>
  );
}

const model = (row: Pick<CallRow, "model" | "effort">) => (row.effort ? `${row.model} · ${row.effort}` : row.model);

function RunView({ runId }: { runId: string }) {
  const { data, error, loading } = useLoad(`run:${runId}`, () => getTrace(runId));

  return (
    <section className={`${styles.panel} rise`} aria-labelledby="run-title">
      <a className={styles.back} href={routeHref({ tab: "traces" })}>
        ← 실행 목록
      </a>
      <h1 id="run-title" className={`${styles.h1} ${styles.mono}`}>
        {runId}
      </h1>
      {error && <Problem error={error} notFound={`없는 기록: ${runId}`} />}
      {loading && <p className={styles.muted}>읽는 중…</p>}
      {data && (
        <div className={styles.scroll}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th scope="col" className={styles.num}>#</th>
                <th scope="col">노드</th>
                <th scope="col">모델</th>
                <th scope="col" className={styles.num}>입력</th>
                <th scope="col" className={styles.num}>캐시 쓰기</th>
                <th scope="col" className={styles.num}>캐시 읽기</th>
                <th scope="col" className={styles.num}>출력</th>
                <th scope="col" className={styles.num}>초</th>
                <th scope="col" className={styles.num}>달러</th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map((row) => (
                <tr key={row.n}>
                  <td className={styles.num}>{row.n}</td>
                  <th scope="row">
                    <a className={styles.link} href={routeHref({ tab: "traces", runId, n: row.n })}>
                      {row.node}
                    </a>
                    {row.error && <span className={styles.warn}> 실패</span>}
                  </th>
                  <td className={styles.mono}>{model(row)}</td>
                  <UsageCells usage={row.usage} />
                  <td className={styles.num}>{seconds(row.seconds)}</td>
                  <td className={styles.num}>{dollars(row.dollars)}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <td />
                <th scope="row">합계</th>
                <td />
                <UsageCells usage={data.totals.usage} />
                <td className={styles.num}>{seconds(data.totals.seconds)}</td>
                <td className={styles.num}>{dollars(data.totals.dollars)}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      )}
    </section>
  );
}

function CallView({ runId, n }: { runId: string; n: number }) {
  const { data, error, loading } = useLoad(`call:${runId}:${n}`, () => getCall(runId, n));

  return (
    <section className={`${styles.panel} rise`} aria-labelledby="call-title">
      <a className={styles.back} href={routeHref({ tab: "traces", runId })}>
        ← {runId}
      </a>
      <h1 id="call-title" className={styles.h1}>
        {n}번째 호출{data && ` · ${data.node}`}
      </h1>
      {error && <Problem error={error} notFound={`없는 호출: ${runId} #${n}`} />}
      {loading && <p className={styles.muted}>읽는 중…</p>}
      {data && (
        <>
          <dl className={styles.meta}>
            <div>
              <dt>모델</dt>
              <dd>{model(data)}</dd>
            </div>
            <div>
              <dt>시각</dt>
              <dd>{when(data.at)}</dd>
            </div>
            <div>
              <dt>입력 · 캐시 쓰기 · 캐시 읽기 · 출력</dt>
              <dd>
                {[data.usage.input, data.usage.cache_write, data.usage.cache_read, data.usage.output].map(tokens).join(" · ")}
              </dd>
            </div>
            <div>
              <dt>초 · 달러</dt>
              <dd>
                {seconds(data.seconds)} · {dollars(data.dollars)}
              </dd>
            </div>
          </dl>
          <FullText title="system" text={data.system} />
          <FullText title="prompt" text={data.prompt} open />
          {data.error ? (
            <FullText title="실패" text={data.error} open warn />
          ) : (
            <FullText title="response" text={data.response ?? ""} open />
          )}
        </>
      )}
    </section>
  );
}

function FullText({ title, text, open, warn }: { title: string; text: string; open?: boolean; warn?: boolean }) {
  return (
    <details className={styles.full} open={open}>
      <summary className={warn ? styles.warn : undefined}>
        {title} <span className={styles.muted}>{tokens(text.length)}자</span>
      </summary>
      <pre className={styles.pre}>{text}</pre>
    </details>
  );
}
