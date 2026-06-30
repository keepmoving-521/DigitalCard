import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [vue()],
  server: {
    host: '0.0.0.0',
  },
  test: {
    environment: 'jsdom',
    globals: true,
  },
})
