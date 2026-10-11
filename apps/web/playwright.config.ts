import { defineConfig, devices } from "@playwright/test";
import path from "node:path";

const root = path.resolve(__dirname, "../..");
const python =
  process.env.REFLOW_PYTHON ??
  path.join(
    root,
    process.platform === "win32"
      ? ".venv/Scripts/python.exe"
      : ".venv/bin/python",
  );

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 60_000,
  expect: { timeout: 15_000 },
  use: {
    baseURL: "http://127.0.0.1:3100",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: `"${python}" -m uvicorn apps.api.main:app --host 127.0.0.1 --port 8100`,
      cwd: root,
      url: "http://127.0.0.1:8100/api/v1/health",
      env: {
        REFLOW_STORAGE_DIR: path.resolve(__dirname, ".e2e-storage"),
        REFLOW_CORS_ORIGINS: "http://127.0.0.1:3100",
      },
      reuseExistingServer: false,
    },
    {
      command:
        process.env.REFLOW_E2E_PRODUCTION === "1"
          ? "npm run start -- --hostname 127.0.0.1 --port 3100"
          : "npm run dev -- --hostname 127.0.0.1 --port 3100",
      url: "http://127.0.0.1:3100",
      env: { NEXT_PUBLIC_API_URL: "http://127.0.0.1:8100" },
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
