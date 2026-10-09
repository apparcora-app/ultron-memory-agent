import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

const backendTarget = process.env.VITE_BACKEND_URL || 'http://127.0.0.1:8000';
const wsTarget = process.env.VITE_WS_URL || 'ws://127.0.0.1:8000';

export default defineConfig({
  plugins: [react()],
  base: process.env.VITE_BASE || '/static/',
  build: {
    outDir: '../static',
    emptyOutDir: false,
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: backendTarget,
        changeOrigin: true,
        ws: true,
      },
      '/ws': {
        target: wsTarget,
        ws: true,
      },
    },
  },
  preview: {
    port: 5173,
    proxy: {
      '/api': {
        target: backendTarget,
        changeOrigin: true,
        ws: true,
      },
      '/ws': {
        target: wsTarget,
        ws: true,
      },
    },
  },
});
