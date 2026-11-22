import { useEffect, useState } from "react";

import { applyTheme, readSavedTheme, saveTheme, systemPrefersDark } from "./theme.js";
import "./css/ThemeToggle.css";

// Switch between light and dark. Starts from the saved choice, or from the
// operating system setting when nothing has been saved yet.
export default function ThemeToggle({ className = "" }) {
  const [theme, setTheme] = useState(
    () => readSavedTheme() ?? (systemPrefersDark() ? "dark" : "light")
  );

  // Keep following the operating system until the user picks a theme.
  useEffect(() => {
    if (readSavedTheme() || !window.matchMedia) return undefined;

    const query = window.matchMedia("(prefers-color-scheme: dark)");
    const follow = (event) => setTheme(event.matches ? "dark" : "light");
    query.addEventListener("change", follow);
    return () => query.removeEventListener("change", follow);
  }, []);

  const isDark = theme === "dark";

  function toggle() {
    const next = isDark ? "light" : "dark";
    setTheme(next);
    applyTheme(next);
    saveTheme(next);
  }

  return (
    <button
      type="button"
      className={`theme-toggle ${className}`.trim()}
      aria-label="Dark mode"
      aria-pressed={isDark}
      title={isDark ? "Switch to light mode" : "Switch to dark mode"}
      onClick={toggle}
    >
      {/* Shows the mode you would switch to: a moon in light mode, a sun in dark mode */}
      <svg aria-hidden="true" viewBox="0 0 24 24" width="18" height="18">
        {isDark ? (
          <g fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <circle cx="12" cy="12" r="4" />
            <path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M5.3 18.7l1.4-1.4M17.3 6.7l1.4-1.4" />
          </g>
        ) : (
          <path
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinejoin="round"
            d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5Z"
          />
        )}
      </svg>
    </button>
  );
}
