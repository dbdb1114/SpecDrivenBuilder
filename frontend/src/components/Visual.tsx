import type { LayoutKey, Visual as VisualData } from "../api/types";
import styles from "./Visual.module.css";

// 그림은 선택지 라벨을 보조할 뿐이라 읽기 도구에는 숨긴다 — 라벨이 이미 뜻을 말한다.
export function Visual({ visual }: { visual: VisualData }) {
  if (visual.type === "palette") return <PaletteSwatch colors={visual.colors} />;
  return <LayoutThumb layout={visual.key} />;
}

export function PaletteSwatch({ colors }: { colors: string[] }) {
  return (
    <span className={styles.swatch} aria-hidden="true" data-testid="palette">
      {colors.map((color, i) => (
        <span key={i} className={styles.chip} style={{ background: color }} />
      ))}
    </span>
  );
}

// key 별 작은 배치 그림. 칸 이름은 Visual.module.css 의 grid-template-areas 와 짝이다.
// Record 라서 빌더가 key 를 늘리면 여기서 타입 검사가 실패한다.
const THUMBS: Record<LayoutKey, string[]> = {
  "single-column": ["head", "body"],
  "top-nav": ["head", "nav", "body"],
  "sidebar-left": ["side", "body"],
  "list-detail": ["head", "list", "body"],
  dashboard: ["head", "card1", "card2", "card3", "body"],
  "mobile-tabs": ["head", "body", "tabs"],
};

export function LayoutThumb({ layout }: { layout: LayoutKey }) {
  return (
    <span className={`${styles.thumb} ${styles[layout]}`} aria-hidden="true" data-testid={`layout-${layout}`}>
      {THUMBS[layout].map((area) => (
        <span key={area} className={styles.block} style={{ gridArea: area }} data-area={area} />
      ))}
    </span>
  );
}
