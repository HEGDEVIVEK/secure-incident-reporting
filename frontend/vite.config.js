import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
// Requests to /api/* are forwarded to the FastAPI backend, so the browser
// only ever talks to one origin and the session cookie stays first-party.
const apiProxy = {
  "/api": {
    target: "http://127.0.0.1:8000",
    changeOrigin: true,
    rewrite: (path) => path.replace(/^\/api/, ""),
  },
}

// Defensive headers for the pages Vite serves (SR-16). A strict
// Content-Security-Policy is set on the API responses instead; adding one here
// would block the inline scripts Vite's dev server injects for hot reload.
const securityHeaders = {
  "X-Content-Type-Options": "nosniff",
  "X-Frame-Options": "DENY",
  "Referrer-Policy": "no-referrer",
}

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    headers: securityHeaders,
    proxy: apiProxy,
  },
  // Same proxy for `npm run build && npm run preview`, so the built app works too.
  preview: {
    port: 4173,
    strictPort: true,
    headers: securityHeaders,
    proxy: apiProxy,
  },
})
