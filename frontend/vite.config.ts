import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  base: '/dev-ui/',
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/health': 'http://127.0.0.1:2026',
      '/version': 'http://127.0.0.1:2026',
      '/list-apps': 'http://127.0.0.1:2026',
      '/cli-info': 'http://127.0.0.1:2026',
      '/apps': 'http://127.0.0.1:2026',
      '/run_sse': 'http://127.0.0.1:2026',
      '/run': 'http://127.0.0.1:2026',
      '/schedule': 'http://127.0.0.1:2026',
      '/aiap-store': 'http://127.0.0.1:2026',
      '/observability': 'http://127.0.0.1:2026',
    },
  },
  build: {
    outDir: resolve(__dirname, '../src/soulbot/server/static'),
    emptyOutDir: true,
  },
})
