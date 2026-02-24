/// <reference types="vitest/config" />
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { storybookTest } from '@storybook/addon-vitest/vitest-plugin';
import { playwright } from '@vitest/browser-playwright';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Backend for dev proxy (telemetry /data, /api/*, WebSocket /ws/signaling)
const BACKEND_URL = process.env.VITE_BACKEND_URL ?? "http://localhost:8000";

// https://vite.dev/config/
// React app entry is index.react.html so Vite dev/build don't process the large static index.html (telemetry UI).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      "/data": { target: BACKEND_URL, changeOrigin: true },
      "/api": { target: BACKEND_URL, changeOrigin: true },
      "/ws": { target: BACKEND_URL.replace(/^http/, "ws"), ws: true },
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src')
    }
  },
  build: {
    rollupOptions: {
      input: path.resolve(__dirname, 'index.html')
    }
  },
  test: {
    projects: [{
      extends: true,
      plugins: [
      // The plugin will run tests for the stories defined in your Storybook config
      // See options at: https://storybook.js.org/docs/next/writing-tests/integrations/vitest-addon#storybooktest
      storybookTest({
        configDir: path.join(__dirname, '.storybook')
      })],
      test: {
        name: 'storybook',
        browser: {
          enabled: true,
          headless: true,
          provider: playwright({}),
          instances: [{
            browser: 'chromium'
          }]
        },
        setupFiles: ['.storybook/vitest.setup.ts']
      }
    }]
  }
});