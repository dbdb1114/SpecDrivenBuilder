import { useState } from "react";
import { ApiError } from "../api/client";
import { getNodes, saveNodes } from "../api/backoffice";
import type { NodeSetting, NodeSettingsView } from "../api/types";
import { Problem } from "./BackofficeApp";
import styles from "./backoffice.module.css";
import { useLoad } from "./useLoad";

type Draft = Record<string, NodeSetting>;
type Message = { ok: boolean; text: string } | null;

const toDraft = (view: NodeSettingsView): Draft =>
  Object.fromEntries(view.nodes.map(({ node, model, effort }) => [node, { model, effort }]));

export function NodesPage() {
  const loaded = useLoad("nodes", getNodes);
  // 저장하면 폼을 새로 그리므로 결과 문구는 폼 바깥에 둔다.
  const [message, setMessage] = useState<Message>(null);
  if (loaded.error) {
    return (
      <section className={`${styles.panel} rise`}>
        <h1 className={styles.h1}>노드 설정</h1>
        <Problem error={loaded.error} />
      </section>
    );
  }
  if (!loaded.data) {
    return (
      <section className={`${styles.panel} rise`}>
        <h1 className={styles.h1}>노드 설정</h1>
        <p className={styles.muted}>읽는 중…</p>
      </section>
    );
  }
  // 저장한 뒤 서버가 돌려준 값으로 폼을 처음부터 다시 그린다 — key 가 바뀌면 입력 상태도 그 값에서 다시 시작한다.
  return (
    <NodesForm
      key={JSON.stringify(loaded.data.nodes)}
      view={loaded.data}
      onSaved={loaded.set}
      message={message}
      setMessage={setMessage}
    />
  );
}

type FormProps = {
  view: NodeSettingsView;
  onSaved: (view: NodeSettingsView) => void;
  message: Message;
  setMessage: (message: Message) => void;
};

function NodesForm({ view, onSaved, message, setMessage }: FormProps) {
  const [draft, setDraft] = useState(() => toDraft(view));
  const [saving, setSaving] = useState(false);
  const changed = JSON.stringify(draft) !== JSON.stringify(toDraft(view));

  const edit = (node: string, patch: Partial<NodeSetting>) => {
    setMessage(null);
    setDraft((d) => ({ ...d, [node]: { ...d[node], ...patch } }));
  };

  const save = async () => {
    setSaving(true);
    try {
      const saved = await saveNodes(draft);
      onSaved(saved);
      setMessage({ ok: true, text: "저장했어요. 다음 호출부터 반영돼요 — git diff builder/config/nodes.json 으로 확인하세요." });
    } catch (e) {
      setMessage({ ok: false, text: e instanceof ApiError ? e.message : String(e) });
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className={`${styles.panel} rise`} aria-labelledby="nodes-title">
      <h1 id="nodes-title" className={styles.h1}>
        노드 설정
      </h1>
      <p className={styles.muted}>
        <code>builder/config/nodes.json</code> · 비우면 기본값 (모델 <code>{view.default_model}</code>). effort 는 Claude API 로 돌 때만 적용돼요.
      </p>
      {view.error && (
        <div className={styles.problem} role="alert">
          <p>지금 파일이 틀려서 LLM 호출이 실패해요. 고쳐 저장하면 풀려요.</p>
          <p className={styles.muted}>{view.error}</p>
        </div>
      )}
      <datalist id="known-models">
        {view.known_models.map((m) => (
          <option key={m} value={m} />
        ))}
      </datalist>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void save();
        }}
      >
        <div className={styles.scroll}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th scope="col">노드</th>
                <th scope="col">모델</th>
                <th scope="col">effort</th>
              </tr>
            </thead>
            <tbody>
              {view.nodes.map(({ node }) => (
                <tr key={node}>
                  <th scope="row" className={styles.mono}>
                    {node}
                  </th>
                  <td>
                    <input
                      className={styles.input}
                      list="known-models"
                      aria-label={`${node} 모델`}
                      placeholder={`기본값 (${view.default_model})`}
                      value={draft[node].model ?? ""}
                      onChange={(e) => edit(node, { model: e.target.value.trim() || null })}
                    />
                  </td>
                  <td>
                    <select
                      className={styles.input}
                      aria-label={`${node} effort`}
                      value={draft[node].effort ?? ""}
                      onChange={(e) => edit(node, { effort: (e.target.value || null) as NodeSetting["effort"] })}
                    >
                      <option value="">기본값</option>
                      {view.efforts.map((effort) => (
                        <option key={effort} value={effort}>
                          {effort}
                        </option>
                      ))}
                    </select>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className={styles.actions}>
          <button type="submit" className={`${styles.primary} btn`} disabled={!changed || saving}>
            {saving ? "저장 중…" : "저장"}
          </button>
          <button type="button" className={`${styles.secondary} btn`} disabled={!changed || saving} onClick={() => setDraft(toDraft(view))}>
            되돌리기
          </button>
          {message && (
            <p role="status" className={message.ok ? styles.ok : styles.warn}>
              {message.text}
            </p>
          )}
        </div>
      </form>
    </section>
  );
}
