import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

const apiTarget = process.env.ORBIT_API_PROXY_TARGET ?? 'http://localhost:8000'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': path.resolve(import.meta.dirname, 'src') },
  },
  server: {
    port: 5173,
    strictPort: true,
    // Same-origin proxy in development so the session cookie stays first-party.
    proxy: {
      '/api': apiTarget,
      '/health': apiTarget,
      '/ready': apiTarget,
    },
  },
  build: {
    sourcemap: true,
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./tests/setup.js'],
    include: ['src/**/*.test.{js,jsx}'],
    css: false,
    // First render of a lazy route compiles its module, which is slow on cold caches.
    testTimeout: 20_000,
  },
})
