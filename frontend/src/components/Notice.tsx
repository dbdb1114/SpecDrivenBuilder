import type { ReactNode } from "react";
import styles from "./Notice.module.css";

export function Notice({ error = false, children }: { error?: boolean; children: ReactNode }) {
  return (
    <div role={error ? "alert" : "status"} className={`${styles.notice} ${error ? styles.error : ""}`}>
      {children}
    </div>
  );
}
