// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Levi Banks

import React from "react";
import ReactDOM from "react-dom/client";
import { Router } from "wouter";
import { App } from "./App";
import { currentShardBase } from "./api/base";
import { ThemeProvider } from "./theme/ThemeProvider";
import "./styles/app.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ThemeProvider>
      <Router base={currentShardBase()}>
        <App />
      </Router>
    </ThemeProvider>
  </React.StrictMode>,
);
