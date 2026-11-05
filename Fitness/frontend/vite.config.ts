import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // Local-only dev server; the backend only allows this origin via CORS.
    host: '127.0.0.1',
    port: 5173,
  },
})
