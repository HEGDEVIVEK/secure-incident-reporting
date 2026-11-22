// Light and dark theme handling.
//
// With no saved choice, the app follows the operating system setting
// (CSS handles that through color-scheme). Choosing a theme with the toggle
// sets data-theme on <html> and remembers the choice in localStorage.
// Only the words "light" or "dark" are stored, nothing about the user.
// If storage is blocked, the toggle still works for the current visit.

const STORAGE_KEY = "incident-reporting-theme";

export function readSavedTheme() {
  try {
    const value = window.localStorage.getItem(STORAGE_KEY);
    return value === "light" || value === "dark" ? value : null;
  } catch {
    return null;
  }
}

export function saveTheme(theme) {
  try {
    window.localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    // Storage unavailable (private mode or blocked): keep it for this visit only.
  }
}

export function applyTheme(theme) {
  const root = document.documentElement;
  if (theme === "light" || theme === "dark") {
    root.dataset.theme = theme;
  } else {
    delete root.dataset.theme;
  }
}

export function systemPrefersDark() {
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false;
}
