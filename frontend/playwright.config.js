import { defineConfig } from '@playwright/test'
import path from 'node:path'

const projectRoot = path.resolve(process.cwd(), '..')
const python = path.join(projectRoot, 'runtime', 'python', 'python.exe')

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 180_000,
  fullyParallel: false,
  workers: 1,
  reporter: [['list'], ['html', { outputFolder: '../work/playwright-report', open: 'never' }]],
  outputDir: '../work/playwright-results',
  use: {
    baseURL: 'http://127.0.0.1:8765',
    browserName: 'chromium',
    channel: 'msedge',
    headless: true,
    viewport: { width: 1440, height: 900 },
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
  webServer: {
    command: `"${python}" -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8765 --log-level warning`,
    cwd: projectRoot,
    url: 'http://127.0.0.1:8765/api/health',
    timeout: 60_000,
    reuseExistingServer: false,
    env: {
      ...process.env,
      URBAN_FLOW_HOME: projectRoot,
      JAVA_HOME: path.join(projectRoot, 'runtime', 'java'),
      PYTHONIOENCODING: 'utf-8',
    },
  },
})
