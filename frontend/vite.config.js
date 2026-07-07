import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  base: '/ps3/',
  server: {
    port: 5174,
    strictPort: true,
  },
})


