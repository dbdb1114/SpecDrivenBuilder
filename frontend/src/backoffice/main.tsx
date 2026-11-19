import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BackofficeApp } from "./BackofficeApp";
import "../index.css";
import "../motion.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BackofficeApp />
  </StrictMode>,
);
