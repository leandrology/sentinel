import { defineConfig, devices } from "@playwright/test";
import { resolve } from "node:path";

const E2E_DIR = resolve(__dirname, "..", ".e2e");
const DB_URL = `sqlite:///${E2E_DIR}/e2e.db`.replace(/\\/g, "/");
const VIDEO_SRC = `${E2E_DIR}/motion.mp4`.replace(/\\/g, "/");

/**
 * Full chain: simulator (WS) -> backend (ingest/triage/persist/SSE) -> dashboard.
 * The simulator is spawned by globalSetup (no HTTP probe available for it).
 * Backend runs with a scratch SQLite DB and the synthetic motion video so both
 * sensor and camera events flow in one run.
 */
export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 150000,
  retries: 0,
  use: {
    baseURL: "http://localhost:3100",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  globalSetup: "./tests/e2e/globalSetup.ts",
  globalTeardown: "./tests/e2e/globalTeardown.ts",
  webServer: [
    {
      command: ".venv\\Scripts\\python.exe -m uvicorn app.main:app --port 8100",
      cwd: "../backend",
      url: "http://localhost:8100/api/health",
      timeout: 90000,
      reuseExistingServer: false,
      env: {
        DATABASE_URL: DB_URL,
        INGEST_ENABLED: "true",
        SIMULATOR_URL: "ws://localhost:8765",
        AI_PROVIDER: "mock",
        VIDEO_ENABLED: "true",
        VIDEO_SOURCE: VIDEO_SRC,
        VIDEO_SAMPLE_FPS: "10",
        VIDEO_COOLDOWN_S: "2",
        VIDEO_SITE_ID: "site-100",
        VIDEO_ZONE: "roof",
        CORS_ORIGINS: "http://localhost:3100",
        LOG_LEVEL: "WARNING",
      },
    },
    {
      command: "npm run dev -- --port 3100",
      url: "http://localhost:3100",
      timeout: 120000,
      reuseExistingServer: false,
      env: { NEXT_PUBLIC_API_URL: "http://localhost:8100" },
    },
  ],
});
