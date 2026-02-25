import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  root: 'src',
  build: {
    outDir: '../dist',
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      '/api/live/stream': {
        target: 'http://localhost:3001',
        timeout: 0, // no timeout for MJPEG stream
      },
      '/api': 'http://localhost:3001',
      '/media': 'http://localhost:3001',
    },
  },
});
