import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";

const root = document.getElementById("root");

// 这个函数挂载 React 应用。
function mount() {
  if (!root) {
    return;
  }
  createRoot(root).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  );
}

mount();
