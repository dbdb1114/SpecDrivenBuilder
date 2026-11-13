import { useState } from "react";
import { Button, ButtonRow } from "../components/Button";
import styles from "./pages.module.css";

type Props = { busy: boolean; onStart: (request: string) => void };

export function StartPage({ busy, onStart }: Props) {
  const [text, setText] = useState("");

  return (
    <section>
      <h1 className={styles.title}>어떤 프로그램을 만들고 싶으세요?</h1>
      <p className={styles.lead}>평소 말하듯 적어 주세요. 필요한 건 차례로 여쭤볼게요.</p>
      <textarea
        className={styles.textarea}
        aria-label="만들고 싶은 프로그램"
        rows={6}
        value={text}
        placeholder="예) 우리 가게 예약을 받는 프로그램이 필요해요. 손님이 날짜랑 시간을 고르면…"
        onChange={(e) => setText(e.target.value)}
      />
      <ButtonRow>
        <Button primary disabled={busy || !text.trim()} onClick={() => onStart(text.trim())}>
          시작하기
        </Button>
      </ButtonRow>
    </section>
  );
}
