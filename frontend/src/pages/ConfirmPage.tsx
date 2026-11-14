import { useState } from "react";
import type { ConfirmItem, ConfirmReply, ConfirmScreen } from "../api/types";
import { Button, ButtonRow } from "../components/Button";
import styles from "./pages.module.css";

const AREAS: { area: ConfirmItem["area"]; title: string }[] = [
  { area: "function", title: "용도 · 기능" },
  { area: "design", title: "디자인" },
  { area: "tech", title: "기술 (빌더가 정한 것)" },
];

const STATUS_LABEL: Record<ConfirmItem["status"], string> = {
  confirmed: "정한 것",
  delegated: "맡긴 것",
};

type Props = {
  screen: ConfirmScreen;
  busy: boolean;
  onReply: (reply: ConfirmReply) => void;
};

export function ConfirmPage({ screen, busy, onReply }: Props) {
  const [picked, setPicked] = useState<string[]>([]);

  const toggle = (id: string) =>
    setPicked((prev) => (prev.includes(id) ? prev.filter((p) => p !== id) : [...prev, id]));

  return (
    <section>
      <h1 className={styles.title}>이렇게 만들까요?</h1>
      <p className={styles.lead}>잘못 이해한 게 있으면 &ldquo;고칠래요&rdquo;를 고르세요. 그 항목만 다시 여쭤볼게요.</p>
      {AREAS.map(({ area, title }) => {
        const items = screen.items.filter((item) => item.area === area);
        if (!items.length) return null;
        return (
          <div key={area} className={styles.group}>
            <h2 className={styles.groupTitle}>{title}</h2>
            {items.map((item) => (
              <div key={item.id} className={`${styles.card} ${styles.item}`}>
                <div className={styles.itemBody}>
                  <div className={styles.itemName}>
                    {item.name}
                    {item.editable && <span className={styles.status}>{STATUS_LABEL[item.status]}</span>}
                  </div>
                  <p className={styles.content}>{item.content || "만드는 쪽에서 알아서 정해요"}</p>
                </div>
                {item.editable && (
                  <label className={styles.revise}>
                    <input type="checkbox" checked={picked.includes(item.id)} onChange={() => toggle(item.id)} />
                    고칠래요
                  </label>
                )}
              </div>
            ))}
          </div>
        );
      })}
      <ButtonRow>
        <Button
          disabled={busy || picked.length === 0}
          onClick={() => onReply({ action: "revise", item_ids: picked })}
        >
          고른 항목 다시 답할게요
        </Button>
        <Button primary disabled={busy} onClick={() => onReply({ action: "confirm" })}>
          이대로 만들어 주세요
        </Button>
      </ButtonRow>
    </section>
  );
}
