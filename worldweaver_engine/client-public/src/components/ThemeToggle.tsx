// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Levi Banks

import { useTheme } from "../theme/ThemeProvider";

export function ThemeToggle({ inline = false }: { inline?: boolean }) {
  const { theme, toggleTheme } = useTheme();
  return (
    <button
      className={`theme-toggle${inline ? " theme-toggle--inline" : ""}`}
      onClick={toggleTheme}
      title={theme === "light" ? "Switch to night" : "Switch to day"}
      aria-label={theme === "light" ? "Switch to dark theme" : "Switch to light theme"}
    >
      {theme === "light" ? "☾" : "☀"}
    </button>
  );
}
