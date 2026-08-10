import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";

/**
 * Tighten the CSP meta tag for production builds only.
 *
 * The checked-in CSP keeps `'unsafe-inline' 'unsafe-eval'` in script-src so
 * Vite's dev-mode HMR preamble (an inline script) works. Production output
 * contains no inline scripts and the app never calls eval, so we strip those
 * directives at build time — the single most effective XSS control. `apply:
 * "build"` guarantees dev is untouched.
 */
function strictCsp(): Plugin {
  return {
    name: "strict-csp",
    apply: "build",
    transformIndexHtml(html) {
      return html
        .replace(/script-src 'self' 'unsafe-inline' 'unsafe-eval'/, "script-src 'self'")
        .replace(/style-src 'self' 'unsafe-inline'/, "style-src 'self'");
    },
  };
}

export default defineConfig({
  plugins: [react(), strictCsp()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/ws": {
        target: "ws://localhost:8000",
        ws: true,
      },
      "/sse": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
