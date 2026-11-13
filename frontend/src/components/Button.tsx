import type { ButtonHTMLAttributes, ReactNode } from "react";
import styles from "./Button.module.css";

type Props = ButtonHTMLAttributes<HTMLButtonElement> & { primary?: boolean };

export function Button({ primary = false, className, type = "button", ...rest }: Props) {
  const classes = [styles.button, primary ? styles.primary : "", className ?? ""].join(" ").trim();
  return <button type={type} className={classes} {...rest} />;
}

export function ButtonRow({ children }: { children: ReactNode }) {
  return <div className={styles.row}>{children}</div>;
}
