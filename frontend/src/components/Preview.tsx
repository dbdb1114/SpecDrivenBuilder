import type { CSSProperties, ReactNode } from "react";
import type { LayoutKey, Preview as PreviewData } from "../api/types";
import styles from "./Preview.module.css";

// 미리 만들어 둔 틀에 색과 문구만 입힌다 (design.md "interview_design"). 문구는 글자로만 넣는다 —
// LLM 이 쓴 문구를 마크업으로 해석하지 않는다.

type FrameProps = { title: string; menu: string[] };

function Menu({ items, className }: { items: string[]; className: string }) {
  return (
    <ul className={className}>
      {items.map((label, i) => (
        <li key={i} className={i === 0 ? styles.current : undefined}>
          {label}
        </li>
      ))}
    </ul>
  );
}

function Lines({ count }: { count: number }) {
  return (
    <div className={styles.lines}>
      {Array.from({ length: count }, (_, i) => (
        <span key={i} className={styles.line} />
      ))}
    </div>
  );
}

function Header({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <header className={styles.header}>
      <strong className={styles.brand}>{title}</strong>
      {children}
    </header>
  );
}

// Record 라서 빌더가 key 를 늘리면 틀이 없을 때 타입 검사가 실패한다.
const FRAMES: Record<LayoutKey, (props: FrameProps) => ReactNode> = {
  "single-column": ({ title, menu }) => (
    <div className={styles.singleColumn}>
      <Header title={title} />
      <main className={styles.column}>
        <Menu items={menu} className={styles.chips} />
        <div className={styles.panel}>
          <Lines count={3} />
        </div>
        {menu.length > 0 && <span className={styles.button}>{menu[0]}</span>}
      </main>
    </div>
  ),
  "top-nav": ({ title, menu }) => (
    <div className={styles.topNav}>
      <Header title={title}>
        <Menu items={menu} className={styles.navRow} />
      </Header>
      <main className={styles.main}>
        <div className={styles.panel}>
          <Lines count={4} />
        </div>
      </main>
    </div>
  ),
  "sidebar-left": ({ title, menu }) => (
    <div className={styles.sidebarLeft}>
      <aside className={styles.sidebar}>
        <strong className={styles.brand}>{title}</strong>
        <Menu items={menu} className={styles.navColumn} />
      </aside>
      <main className={styles.main}>
        <div className={styles.panel}>
          <Lines count={4} />
        </div>
      </main>
    </div>
  ),
  "list-detail": ({ title, menu }) => (
    <div className={styles.listDetail}>
      <Header title={title}>
        <Menu items={menu} className={styles.navRow} />
      </Header>
      <div className={styles.split}>
        <ul className={styles.list}>
          {[0, 1, 2, 3].map((i) => (
            <li key={i} className={i === 0 ? styles.current : undefined}>
              <span className={styles.line} />
            </li>
          ))}
        </ul>
        <div className={styles.panel}>
          <Lines count={4} />
        </div>
      </div>
    </div>
  ),
  dashboard: ({ title, menu }) => (
    <div className={styles.dashboard}>
      <Header title={title}>
        <Menu items={menu} className={styles.navRow} />
      </Header>
      <main className={styles.main}>
        <div className={styles.cards}>
          {[0, 1, 2].map((i) => (
            <div key={i} className={styles.stat}>
              <span className={styles.line} />
              <span className={styles.figure} />
            </div>
          ))}
        </div>
        <div className={styles.panel}>
          <Lines count={3} />
        </div>
      </main>
    </div>
  ),
  "mobile-tabs": ({ title, menu }) => (
    <div className={styles.phone}>
      <Header title={title} />
      <main className={styles.main}>
        <div className={styles.panel}>
          <Lines count={2} />
        </div>
        <div className={styles.panel}>
          <Lines count={2} />
        </div>
      </main>
      <Menu items={menu} className={styles.tabs} />
    </div>
  ),
};

export function Preview({ preview }: { preview: PreviewData }) {
  const [primary, background = "#ffffff", accent = primary] = preview.colors;
  const theme = { "--p-primary": primary, "--p-bg": background, "--p-accent": accent } as CSSProperties;
  const Frame = FRAMES[preview.layout];
  return (
    <figure className={styles.figureBox} aria-label="미리보기">
      <div className={styles.screen} style={theme} data-layout={preview.layout}>
        <Frame title={preview.texts.title} menu={preview.texts.menu} />
      </div>
      <figcaption className={styles.caption}>이런 느낌으로 만들어져요. 실제 화면의 내용은 달라질 수 있어요.</figcaption>
    </figure>
  );
}
