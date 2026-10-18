import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// dev: фронт на :5173, запросы /api проксируются на бэкенд :8000
export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/api': 'http://localhost:8000' } },
  build: { outDir: '../backend/static', emptyOutDir: true, chunkSizeWarningLimit: 2000 },
})
