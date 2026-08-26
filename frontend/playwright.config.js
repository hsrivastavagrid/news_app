import { defineConfig, devices } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const frontendDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(frontendDir, "..");
const apiPort = 8010;
const origin = `http://127.0.0.1:${apiPort}`;

export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: origin,
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    command: `npm --prefix frontend run build && FETCH_ON_START=false SCHEDULER_ENABLED=false python3 -m uvicorn app.main:app --host 127.0.0.1 --port ${apiPort}`,
    url: `${origin}/api/tags`,
    reuseExistingServer: false,
    timeout: 120_000,
    cwd: repoRoot,
  },
});
