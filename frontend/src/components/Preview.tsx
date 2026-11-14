import type { CSSProperties, ReactNode } from "react";
import type { LayoutKey, Preview as PreviewData } from "../api/types";
import styles from "./Preview.module.css";

// 미리 만들어 둔 틀에 색과 문구만 입힌다 (design.md "interview_design"). 문구는 글자로만 넣는다 —
// LLM 이 쓴 문구를 마크업으로 해석하지 않는다. 색은 역할 이름 그대로 CSS 변수가 된다.

type Texts = PreviewData["texts"];
type Item = Texts["items"][number];

function Nav({ items, className }: { items: string[]; className: string }) {
  return (
    <ul className={className}>
      {items.map((label, i) => (
        <li key={i} className={i === 0 ? styles.current : undefined}>
          <span className={styles.icon} aria-hidden="true" />
          {label}
        </li>
      ))}
    </ul>
  );
}

function Brand({ title }: { title: string }) {
  return (
    <strong className={styles.brand}>
      <span className={styles.logo} aria-hidden="true" />
      {title}
    </strong>
  );
}

function TitleRow({ heading, action }: { heading: string; action: string }) {
  return (
    <div className={styles.titleRow}>
      <h3 className={styles.heading}>{heading}</h3>
      <span className={styles.button}>{action}</span>
    </div>
  );
}

function Cards({ items }: { items: Item[] }) {
  return (
    <ul className={styles.cards}>
      {items.map((item, i) => (
        <li key={i} className={styles.card}>
          <span className={styles.itemTitle}>{item.title}</span>
          <span className={styles.itemDetail}>{item.detail}</span>
        </li>
      ))}
    </ul>
  );
}

function Rows({ items }: { items: Item[] }) {
  return (
    <ul className={styles.rows}>
      {items.map((item, i) => (
        <li key={i} className={styles.row}>
          <span className={styles.itemTitle}>{item.title}</span>
          <span className={styles.itemDetail}>{item.detail}</span>
        </li>
      ))}
    </ul>
  );
}

// 막대 길이는 장식이다 — 값을 읽어 그리지 않는다 (문구는 숫자가 아닐 수도 있다).
const BAR_WIDTHS = ["92%", "68%", "54%", "38%", "26%"];

// Record 라서 빌더가 key 를 늘리면 틀이 없을 때 타입 검사가 실패한다.
const FRAMES: Record<LayoutKey, (texts: Texts) => ReactNode> = {
  "single-column": ({ title, menu, heading, action, items }) => (
    <div className={styles.singleColumn}>
      <header className={styles.bar}>
        <Brand title={title} />
      </header>
      <main className={styles.column}>
        <Nav items={menu} className={styles.segments} />
        <TitleRow heading={heading} action={action} />
        <Rows items={items} />
      </main>
    </div>
  ),
  "top-nav": ({ title, menu, heading, action, items }) => (
    <div className={styles.topNav}>
      <header className={styles.primaryBar}>
        <Brand title={title} />
        <Nav items={menu} className={styles.navRow} />
      </header>
      <main className={styles.main}>
        <TitleRow heading={heading} action={action} />
        <Cards items={items} />
      </main>
    </div>
  ),
  "sidebar-left": ({ title, menu, heading, action, items }) => (
    <div className={styles.sidebarLeft}>
      <aside className={styles.sidebar}>
        <Brand title={title} />
        <Nav items={menu} className={styles.navColumn} />
      </aside>
      <main className={styles.main}>
        <TitleRow heading={heading} action={action} />
        <div className={styles.panel}>
          <Rows items={items} />
        </div>
      </main>
    </div>
  ),
  "list-detail": ({ title, menu, heading, action, items }) => (
    <div className={styles.listDetail}>
      <header className={styles.bar}>
        <Brand title={title} />
        <Nav items={menu} className={styles.navRow} />
      </header>
      <div className={styles.split}>
        <section className={styles.listPane}>
          <h3 className={styles.paneLabel}>{heading}</h3>
          <ul className={styles.picks}>
            {items.map((item, i) => (
              <li key={i} className={i === 0 ? styles.current : undefined}>
                <span className={styles.itemTitle}>{item.title}</span>
                <span className={styles.itemDetail}>{item.detail}</span>
              </li>
            ))}
          </ul>
        </section>
        <section className={styles.detailPane}>
          <span className={styles.detailTitle}>{items[0].title}</span>
          <span className={styles.detailValue}>{items[0].detail}</span>
          <span className={styles.button}>{action}</span>
        </section>
      </div>
    </div>
  ),
  dashboard: ({ title, menu, heading, action, items }) => (
    <div className={styles.dashboard}>
      <header className={styles.bar}>
        <Brand title={title} />
        <Nav items={menu} className={styles.navRow} />
      </header>
      <main className={styles.main}>
        <TitleRow heading={heading} action={action} />
        <ul className={styles.stats}>
          {items.slice(0, 3).map((item, i) => (
            <li key={i} className={styles.stat}>
              <span className={styles.statLabel}>{item.title}</span>
              <span className={styles.statValue}>{item.detail}</span>
            </li>
          ))}
        </ul>
        <div className={styles.panel}>
          <ul className={styles.bars} aria-hidden="true">
            {items.map((item, i) => (
              <li key={i}>
                <span className={styles.barLabel}>{item.title}</span>
                <span className={styles.barTrack}>
                  <span className={styles.barFill} style={{ width: BAR_WIDTHS[i] }} />
                </span>
              </li>
            ))}
          </ul>
        </div>
      </main>
    </div>
  ),
  "mobile-tabs": ({ title, menu, heading, action, items }) => (
    <div className={styles.phone}>
      <div className={styles.statusBar} aria-hidden="true">
        <span>9:41</span>
        <span className={styles.signal} />
      </div>
      <header className={styles.phoneHead}>
        <Brand title={title} />
      </header>
      <main className={styles.phoneMain}>
        <h3 className={styles.heading}>{heading}</h3>
        <Rows items={items} />
      </main>
      <span className={`${styles.button} ${styles.fab}`}>{action}</span>
      <Nav items={menu} className={styles.tabs} />
    </div>
  ),
};

export function Preview({ preview }: { preview: PreviewData }) {
  const { background, surface, primary, accent, text } = preview.colors;
  const theme = {
    "--p-bg": background,
    "--p-surface": surface,
    "--p-primary": primary,
    "--p-accent": accent,
    "--p-text": text,
  } as CSSProperties;
  return (
    <figure className={styles.figureBox} aria-label="미리보기">
      <div className={styles.screen} style={theme} data-layout={preview.layout}>
        {preview.layout !== "mobile-tabs" && (
          <div className={styles.chrome} aria-hidden="true">
            <span />
            <span />
            <span />
          </div>
        )}
        {FRAMES[preview.layout](preview.texts)}
      </div>
      <figcaption className={styles.caption}>이런 느낌으로 만들어져요. 실제 화면의 내용은 달라질 수 있어요.</figcaption>
    </figure>
  );
}
