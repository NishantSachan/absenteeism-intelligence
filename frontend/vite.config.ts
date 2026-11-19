/// <reference types="vitest" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In development the Vite server proxies /api to the local FastAPI server, so the browser sees one origin.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true } } },
  build: { sourcemap: false, chunkSizeWarningLimit: 900 },
  test: { environment: 'jsdom', globals: true, setupFiles: ['./src/test/setup.ts'], css: false },
})
