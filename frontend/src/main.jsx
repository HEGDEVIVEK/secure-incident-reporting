import { createRoot } from 'react-dom/client'
import { BrowserRouter } from "react-router";

// Self-hosted font (no requests to outside font servers).
import "@fontsource-variable/atkinson-hyperlegible-next";
import "./theme.css";

import App from './App.jsx'
import { applyTheme, readSavedTheme } from "./shared/theme.js";

// Apply a saved light/dark choice before the first render.
applyTheme(readSavedTheme());

createRoot(document.getElementById('root')).render(
  <BrowserRouter>
    <App />
  </BrowserRouter>
)
