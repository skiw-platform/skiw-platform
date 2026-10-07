import { StrictMode } from "react";
import { hydrateRoot } from "react-dom/client";

import { App } from "./App";
import "./styles.css";

const root = document.getElementById("root");
if (!root) {
  throw new Error("Missing #root element");
}

// Hydrate the server-rendered shell (app/shell/templates/shell/shell.html) so the focused
// node survives startup. The two must stay equal.
hydrateRoot(
  root,
  <StrictMode>
    <App />
  </StrictMode>,
);
