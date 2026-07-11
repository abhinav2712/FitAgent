import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev: `npm run dev` serves the app on :5173 and proxies API calls to FastAPI on :8000.
// Prod: `npm run build` → dist/ is served by FastAPI itself (same origin, zero CORS).
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: Object.fromEntries(
      ["/plan", "/log", "/healthz", "/webhook"].map((p) => [p, "http://localhost:8000"])
    ),
  },
});
